"""Sonda do ADR-0003: o sqlcipher3 funciona dentro do executável congelado?

O CI congela este script com PyInstaller em windows-latest e roda o executável.
Sai com 0 se cria, cifra, reabre e recusa a chave errada; com 1 caso contrário.
Usa só pacientes de mentira: o texto procurado nos bytes é uma constante.
"""

import secrets
import sys
import tempfile
from pathlib import Path

import sqlcipher3  # tipos em typings/sqlcipher3 (o binding não publica os seus)

SEGREDO = "segredo-da-sonda-gastroepi"


def abrir(caminho: Path, chave_hex: str) -> sqlcipher3.Connection:
    conexao = sqlcipher3.connect(str(caminho))
    # ADR-0003: PRAGMA key com chave bruta é sempre a primeira instrução.
    conexao.execute(f"PRAGMA key = \"x'{chave_hex}'\"")
    return conexao


def falha(motivo: str) -> int:
    print(f"sonda FALHOU: {motivo}", file=sys.stderr)
    return 1


def sondar(pasta: Path) -> int:
    caminho, chave = pasta / "sonda.db", secrets.token_hex(32)
    conexao = abrir(caminho, chave)
    conexao.execute("CREATE TABLE t (v TEXT)")
    conexao.execute("INSERT INTO t VALUES (?)", (SEGREDO,))
    conexao.commit()
    versao = conexao.execute("PRAGMA cipher_version").fetchone()[0]
    conexao.close()

    bruto = caminho.read_bytes()
    if SEGREDO.encode() in bruto or bruto.startswith(b"SQLite format 3"):
        return falha("o arquivo tem texto em claro ou cabeçalho de SQLite comum")

    conexao = abrir(caminho, chave)
    lido = conexao.execute("SELECT v FROM t").fetchone()[0]
    conexao.close()
    if lido != SEGREDO:
        return falha(f"reabrir devolveu {lido!r}, esperado {SEGREDO!r}")

    errada = abrir(caminho, secrets.token_hex(32))
    try:
        errada.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return falha("a chave errada abriu o banco")
    except sqlcipher3.DatabaseError:
        pass
    finally:
        errada.close()

    print(f"sonda ok: SQLCipher {versao}, congelado={getattr(sys, 'frozen', False)}")
    return 0


def principal() -> int:
    with tempfile.TemporaryDirectory() as pasta:
        return sondar(Path(pasta))


if __name__ == "__main__":
    sys.exit(principal())
