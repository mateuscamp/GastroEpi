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
def transacao(conexao: sqlcipher3.Connection) -> Iterator[None]:
    conexao.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conexao.execute("ROLLBACK")
        raise
    conexao.execute("COMMIT")


def trocar_chave(conexao: sqlcipher3.Connection, nova: bytes) -> None:
    """`PRAGMA rekey`: recifra todas as páginas com a chave nova; a antiga deixa de abrir."""
    _conferir_tamanho(nova)
    conexao.execute(_pragma_de_chave("rekey", nova))


def copiar_banco(conexao: sqlcipher3.Connection, destino: Path, chave: bytes) -> None:
    """API de backup entre duas conexões SQLCipher com a mesma chave (ADR-0003, item 7):
    a cópia sai cifrada, página a página, sem passar por um arquivo em claro."""
    copia = abrir_conexao(destino, chave)
    try:
        conexao.backup(copia)
    finally:
        copia.close()
