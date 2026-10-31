"""Verificação dos dados: o estado atual de cada registro contra o seu último snapshot."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from gastroepi.auditoria.cadeia import EntradaDeAuditoria


class Motivo(StrEnum):
    ALTERADO = "alterado"  # o estado atual difere do último snapshot


@dataclass(frozen=True, slots=True)
class Divergencia:
    """Aponta o registro e a entrada de auditoria que ele contradiz (Cenário 3)."""

    entidade: str
    entidade_id: int
    motivo: Motivo
    entrada_id: int | None
    momento: str | None


@dataclass(frozen=True, slots=True)
class RelatorioDeIntegridade:
    dados: tuple[Divergencia, ...]


def conferir_dados(
    entradas: Iterable[EntradaDeAuditoria], atuais: Mapping[tuple[str, int], str | None]
) -> tuple[Divergencia, ...]:
    ultimas = {(e.evento.entidade, e.evento.entidade_id): e for e in entradas}
    return tuple(
        Divergencia(entidade, entidade_id, Motivo.ALTERADO, entrada.id, entrada.evento.momento)
        for (entidade, entidade_id), entrada in sorted(ultimas.items())
        if atuais.get((entidade, entidade_id)) != entrada.evento.depois
    )
