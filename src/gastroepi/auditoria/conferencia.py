"""Verificação dos dados: o estado atual de cada registro contra o seu último snapshot."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from gastroepi.auditoria.cadeia import Acao, EntradaDeAuditoria, QuebraDaCadeia


class Motivo(StrEnum):
    ALTERADO = "alterado"  # o estado atual difere do último snapshot (ou é ilegível)
    SEM_EVENTO = "sem_evento"  # o registro existe e nenhuma entrada o cita
    AUSENTE = "ausente"  # a última entrada não é exclusão, mas o registro sumiu
    EXCLUIDO_PRESENTE = "excluido_presente"  # a última entrada é exclusão, mas ele existe
    # o 'antes' da entrada difere do 'depois' da anterior: alterado por fora entre as duas
    HISTORICO_INTERROMPIDO = "historico_interrompido"


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
    cadeia: QuebraDaCadeia | None
    dados: tuple[Divergencia, ...]

    @property
    def ok(self) -> bool:
        return self.cadeia is None and not self.dados


def conferir_dados(
    entradas: Iterable[EntradaDeAuditoria], atuais: Mapping[tuple[str, int], str | None]
) -> tuple[Divergencia, ...]:
    """`atuais` leva (entidade, id) ao retrato JSON do registro, ou a `None` se ele existe
    mas não pôde ser lido (um valor alterado por fora que o domínio recusa).

    Por registro, aponta a primeira entrada cujo 'antes' não é o 'depois' da anterior
    (histórico interrompido) ou, se o histórico é contínuo, confere o estado atual com
    a última entrada.
    """
    historicos: dict[tuple[str, int], list[EntradaDeAuditoria]] = defaultdict(list)
    for entrada in entradas:
        historicos[(entrada.evento.entidade, entrada.evento.entidade_id)].append(entrada)
    chaves = sorted(historicos.keys() | atuais.keys())
    divergencias = (_conferir(chave, historicos.get(chave, []), atuais) for chave in chaves)
    return tuple(d for d in divergencias if d is not None)


def _interrupcao(historico: list[EntradaDeAuditoria]) -> EntradaDeAuditoria | None:
    pares = pairwise(historico)
    return next((seguinte for anterior, seguinte in pares
                 if seguinte.evento.antes != anterior.evento.depois), None)  # fmt: skip


def _motivo_do_estado(
    chave: tuple[str, int], ultima: EntradaDeAuditoria, atuais: Mapping[tuple[str, int], str | None]
) -> Motivo | None:
    excluido, presente = ultima.evento.acao == Acao.EXCLUIR, chave in atuais
    if excluido:
        return Motivo.EXCLUIDO_PRESENTE if presente else None
    if not presente:
        return Motivo.AUSENTE
    return Motivo.ALTERADO if atuais[chave] != ultima.evento.depois else None


def _conferir(
    chave: tuple[str, int],
    historico: list[EntradaDeAuditoria],
    atuais: Mapping[tuple[str, int], str | None],
) -> Divergencia | None:
    entidade, entidade_id = chave
    if not historico:
        return Divergencia(entidade, entidade_id, Motivo.SEM_EVENTO, None, None)
    interrompida = _interrupcao(historico)
    if interrompida is not None:
        motivo: Motivo | None = Motivo.HISTORICO_INTERROMPIDO
        alvo = interrompida
    else:
        alvo = historico[-1]
        motivo = _motivo_do_estado(chave, alvo, atuais)
    if motivo is None:
        return None
    return Divergencia(entidade, entidade_id, motivo, alvo.id, alvo.evento.momento)
