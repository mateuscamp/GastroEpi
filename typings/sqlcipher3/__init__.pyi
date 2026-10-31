"""Tipos do sqlcipher3, que não publica os seus (ADR-0003).

O binding é um fork do módulo sqlite3 da stdlib (DB-API 2.0): as classes têm a mesma
API, então os tipos vêm do typeshed do sqlite3. Só o `connect` é declarado aqui, porque
o do sqlcipher3 não tem o parâmetro `autocommit` do Python 3.12+.
"""

from os import PathLike
from sqlite3 import Connection as Connection
from sqlite3 import Cursor as Cursor
from sqlite3 import DatabaseError as DatabaseError
from sqlite3 import Error as Error
from sqlite3 import IntegrityError as IntegrityError
from sqlite3 import OperationalError as OperationalError
from sqlite3 import Row as Row

def connect(
    database: str | PathLike[str],
    timeout: float = ...,
    detect_types: int = ...,
    isolation_level: str | None = ...,
    check_same_thread: bool = ...,
    cached_statements: int = ...,
    uri: bool = ...,
) -> Connection: ...
