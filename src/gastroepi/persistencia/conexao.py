"""Conexão SQLCipher (ADR-0003) e transação explícita.

Ordem fixa em toda conexão:
1. `PRAGMA key` com a chave bruta (`x'…'`), antes de qualquer outro comando. A chave
   bruta dispensa o PBKDF2 do SQLCipher: a derivação da senha é nossa (`cofre`).
2. `cipher_log_level = NONE`. Com chave errada, o SQLCipher 4.19 escreve
   "ERROR CORE … hmac check failed" no stderr do processo. O app já traduz isso em
   `ChaveIncorreta`, e no executável sem console o stderr não vai a lugar nenhum.
3. `temp_store = MEMORY`: nenhuma tabela temporária vai para o disco em claro.
4. Uma leitura do `sqlite_master`: é aí que a chave errada aparece.
5. `foreign_keys = ON` (o cascade de paciente → exames → lesões depende dele) e WAL.

A transação é explícita (`isolation_level=None` + `BEGIN IMMEDIATE`): a escrita trava o
banco já no início, e a mutação e o evento de auditoria entram juntos ou não entram.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlcipher3

TAMANHO_DA_CHAVE = 32  # 256 bits
ESPERA_POR_TRAVA_MS = 5000


class ChaveIncorreta(ValueError):
    """A chave não abre o banco. O SQLCipher não distingue chave errada de página 1
    corrompida: as duas falham no HMAC da primeira página."""

    def __init__(self) -> None:
        super().__init__("A chave não abre este banco")


class BancoCorrompido(RuntimeError):
    """Uma página não passou no HMAC do SQLCipher (ou o SQLite a achou malformada).
    A casca não importa sqlcipher3, então o erro do binding vira este."""

    def __init__(self) -> None:
        super().__init__("O arquivo do banco está corrompido")


def _conferir_tamanho(chave: bytes) -> None:
    if len(chave) != TAMANHO_DA_CHAVE:
        raise ValueError(f"Chave de {len(chave)} bytes; esperado {TAMANHO_DA_CHAVE}")


def _pragma_de_chave(nome: str, chave: bytes) -> str:
    # PRAGMA não aceita parâmetro; o hex vem de bytes, nunca de texto digitado.
    return f"PRAGMA {nome} = \"x'{chave.hex()}'\""


def abrir_conexao(caminho: Path, chave: bytes) -> sqlcipher3.Connection:
    _conferir_tamanho(chave)
    conexao = sqlcipher3.connect(str(caminho), isolation_level=None)
    conexao.execute(_pragma_de_chave("key", chave))
    conexao.execute("PRAGMA cipher_log_level = NONE")
    conexao.execute("PRAGMA temp_store = MEMORY")
    try:
        conexao.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlcipher3.DatabaseError:
        conexao.close()
        raise ChaveIncorreta from None
    conexao.row_factory = sqlcipher3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA journal_mode = WAL")
    conexao.execute(f"PRAGMA busy_timeout = {ESPERA_POR_TRAVA_MS}")
    return conexao


@contextmanager
def traduzir_corrupcao() -> Iterator[None]:
    try:
        yield
    except sqlcipher3.DatabaseError as erro:
        if type(erro) is not sqlcipher3.DatabaseError:  # IntegrityError etc. passam como são
            raise
        raise BancoCorrompido from erro


@contextmanager
def transacao(conexao: sqlcipher3.Connection, modo: str = "IMMEDIATE") -> Iterator[None]:
    """`IMMEDIATE` para escrever; `DEFERRED` para ler um retrato coerente sem travar."""
    with traduzir_corrupcao():
        conexao.execute(f"BEGIN {modo}")
        try:
            yield
        except BaseException:
            if conexao.in_transaction:
                conexao.execute("ROLLBACK")
            raise
        conexao.execute("COMMIT")


def trocar_chave(conexao: sqlcipher3.Connection, nova: bytes) -> None:
    """`PRAGMA rekey`: recifra todas as páginas com a chave nova; a antiga deixa de abrir.

    Em WAL, as páginas recifradas vão para o -wal, e o .db segue com as da chave antiga
    até um checkpoint: o `cipher_integrity_check` acusaria todas. O checkpoint TRUNCATE
    leva tudo para o .db na hora e esvazia o -wal (achado da Fase 2, 2026-10-31).
    """
    _conferir_tamanho(nova)
    conexao.execute(_pragma_de_chave("rekey", nova))
    conexao.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def paginas_corrompidas(conexao: sqlcipher3.Connection) -> tuple[str, ...]:
    """`PRAGMA cipher_integrity_check`: confere o HMAC de cada página sem decifrar o conteúdo
    para o SQLite. Vazio quando o arquivo está íntegro."""
    return tuple(linha[0] for linha in conexao.execute("PRAGMA cipher_integrity_check"))


def copiar_banco(conexao: sqlcipher3.Connection, destino: Path, chave: bytes) -> None:
    """API de backup entre duas conexões SQLCipher com a mesma chave (ADR-0003, item 7):
    a cópia sai cifrada, página a página, sem passar por um arquivo em claro."""
    copia = abrir_conexao(destino, chave)
    try:
        conexao.backup(copia)
    finally:
        copia.close()
