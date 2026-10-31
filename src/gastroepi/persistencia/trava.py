"""Instância única por trava de arquivo, sem socket (ADR-0005, item 7; Princípio I).

Trava exclusiva e não bloqueante no 1º byte de `gastroepi.trava`: `flock` no Linux,
`msvcrt.locking` no Windows. O sistema solta a trava quando o processo morre, então uma
queda não deixa o cofre preso. O arquivo fica vazio e nunca é apagado: apagá-lo enquanto
outro processo o trava abriria espaço para uma segunda trava num arquivo novo.
"""

import os
import sys
from pathlib import Path
from types import TracebackType
from typing import Self

NOME_DA_TRAVA = "gastroepi.trava"

if sys.platform == "win32":
    import msvcrt

    def _travar(descritor: int) -> None:
        os.lseek(descritor, 0, os.SEEK_SET)
        msvcrt.locking(descritor, msvcrt.LK_NBLCK, 1)

    def _destravar(descritor: int) -> None:
        os.lseek(descritor, 0, os.SEEK_SET)
        msvcrt.locking(descritor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _travar(descritor: int) -> None:
        fcntl.flock(descritor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _destravar(descritor: int) -> None:
        fcntl.flock(descritor, fcntl.LOCK_UN)


class OutraInstanciaAberta(RuntimeError):
    def __init__(self) -> None:
        super().__init__("O GastroEpi já está aberto com este cofre")


class Trava:
    def __init__(self, arquivo: Path) -> None:
        self._descritor: int | None = os.open(arquivo, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _travar(self._descritor)
        except OSError:
            os.close(self._descritor)
            raise OutraInstanciaAberta from None

    def soltar(self) -> None:
        if self._descritor is None:
            return
        _destravar(self._descritor)
        os.close(self._descritor)
        self._descritor = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.soltar()
