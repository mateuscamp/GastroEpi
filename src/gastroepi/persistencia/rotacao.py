"""Rotação por data dos backups (ADR-0005, item 5): 7 diários, 4 semanais e 12 mensais.

Para cada período, fica a cópia mais recente dos N períodos mais recentes que TÊM cópia,
como o `--keep-daily` do restic. Um mês sem abrir o app não apaga nada, e vinte cópias
num dia só ocupam a vaga daquele dia. A cópia mais nova sempre fica. Puro: sem disco.
"""

from collections.abc import Callable, Hashable, Iterable
from datetime import datetime

DIARIOS = 7
SEMANAIS = 4
MENSAIS = 12


def _dia(momento: datetime) -> Hashable:
    return momento.date()


def _semana(momento: datetime) -> Hashable:
    ano, semana, _ = momento.isocalendar()
    return (ano, semana)


def _mes(momento: datetime) -> Hashable:
    return (momento.year, momento.month)


_PERIODOS: tuple[tuple[Callable[[datetime], Hashable], int], ...] = (
    (_dia, DIARIOS),
    (_semana, SEMANAIS),
    (_mes, MENSAIS),
)


def a_manter[T](itens: Iterable[T], momento: Callable[[T], datetime]) -> list[T]:
    """Os itens que a rotação guarda, do mais novo para o mais antigo."""
    ordenados = sorted(itens, key=momento, reverse=True)
    manter = {id(item) for item in ordenados[:1]}
    for periodo, quantos in _PERIODOS:
        vistos: set[Hashable] = set()
        for item in ordenados:
            chave = periodo(momento(item))
            if chave not in vistos and len(vistos) < quantos:
                vistos.add(chave)
                manter.add(id(item))
    return [item for item in ordenados if id(item) in manter]
