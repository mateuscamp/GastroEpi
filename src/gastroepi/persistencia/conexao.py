"""Conexão SQLCipher (ADR-0003) e transação explícita."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlcipher3


def abrir_conexao(caminho: Path, chave: bytes) -> sqlcipher3.Connection:
    conexao = sqlcipher3.connect(str(caminho), isolation_level=None)
    conexao.row_factory = sqlcipher3.Row
    conexao.execute(f"PRAGMA key = \"x'{chave.hex()}'\"")
    conexao.execute("PRAGMA foreign_keys = ON")
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
