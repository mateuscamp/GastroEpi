"""Indicadores de qualidade da colonoscopia por examinador, com IC de Wilson (ADR-0004).

Definições e limiares: Rex DK, Anderson JC, Butterly LF et al. Quality indicators for
colonoscopy. Am J Gastroenterol 2024;119:1754-1780 (ACG/ASGE; também em Gastrointest
Endosc 2024). Escolha do dono em 2026-10-31, que emendou o ADR-0004:
- detecção (adenoma, avançado, serrilhada, pólipo, adenomas por exame): ≥ 45 anos, com
  indicação de rastreio, vigilância ou diagnóstica; ficam de fora FIT positivo, DII e
  "outra", como na diretriz;
- exame com lesão aguardando histologia fica fora dos indicadores histológicos até o
  laudo chegar, e é contado à parte (`aguardando_histologia`).
A v0.1.16 procurava "adenoma" no texto do laudo e dividia por todos os exames; o oráculo
dela diverge daqui de propósito (tests/estatistica/test_qualidade.py).
"""

from collections.abc import Callable, Iterable, Sequence
from enum import StrEnum
from typing import NamedTuple

from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.listas import Histologia, Indicacao
from gastroepi.estatistica.proporcoes import Proporcao, proporcao
from gastroepi.estatistica.variaveis import ExameDoPaciente, exames_de

IDADE_MINIMA_DETECCAO = 45  # ACG/ASGE 2024, ADR
INDICACOES_DE_DETECCAO = frozenset(
    {
        Indicacao.RASTREIO_RISCO_MEDIO,
        Indicacao.RASTREIO_RISCO_AUMENTADO,
        Indicacao.VIGILANCIA_POS_POLIPECTOMIA,
        Indicacao.DIAGNOSTICA_POR_SINTOMAS,
    }
)


class Indicador(StrEnum):
    DETECCAO_ADENOMA = "deteccao_adenoma"
    SERRILHADA_SESSIL = "serrilhada_sessil"
    INTUBACAO_CECAL = "intubacao_cecal"
    PREPARO_ADEQUADO = "preparo_adequado"
    TEMPO_RETIRADA = "tempo_retirada"


# ACG/ASGE 2024 (Rex et al.): metas mínimas. A v0.1.16 usava 25% para a taxa de adenoma,
# a meta de 2015 (Rex DK et al., Gastrointest Endosc 2015;81:31-53).
LIMIARES: dict[Indicador, float] = {
    Indicador.DETECCAO_ADENOMA: 0.35,  # ≥ 35% (prioritário)
    Indicador.SERRILHADA_SESSIL: 0.06,  # ≥ 6% (prioritário, novo em 2024)
    Indicador.INTUBACAO_CECAL: 0.95,  # ≥ 95%
    Indicador.PREPARO_ADEQUADO: 0.90,  # ≥ 90% dos exames com preparo adequado
    Indicador.TEMPO_RETIRADA: 8.0,  # ≥ 8 min, média nos exames sem lesão
}


class Media(NamedTuple):
    n: int
    media: float | None  # None sem nenhum exame


class Alerta(NamedTuple):
    """Indicador abaixo da meta. `ic_abaixo` diz se até o limite superior do IC está
    abaixo: aí a diferença não se explica pelo acaso de poucos exames."""

    indicador: Indicador
    estimativa: float
    limiar: float
    ic_abaixo: bool


class IndicadoresDoExaminador(NamedTuple):
    examinador: Examinador
    n_exames: int
    deteccao_adenoma: Proporcao
    adenoma_avancado: Proporcao
    serrilhada_sessil: Proporcao
    adenomas_por_exame: Media
    deteccao_polipo: Proporcao
    intubacao_cecal: Proporcao
    tempo_retirada: Media
    preparo_adequado: Proporcao
    aguardando_histologia: int
    alertas: tuple[Alerta, ...]


def elegivel_para_deteccao(registro: ExameDoPaciente) -> bool:
    return (
        registro.exame.indicacao in INDICACOES_DE_DETECCAO
        and registro.idade >= IDADE_MINIMA_DETECCAO
    )


def _contar(
    registros: Sequence[ExameDoPaciente], criterio: Callable[[ExameDoPaciente], bool], alfa: float
) -> Proporcao:
    return proporcao(sum(1 for r in registros if criterio(r)), len(registros), alfa)


def _media(valores: Sequence[float]) -> Media:
    return Media(len(valores), sum(valores) / len(valores) if valores else None)


def _alertas(indicadores: IndicadoresDoExaminador) -> tuple[Alerta, ...]:
    proporcoes = {
        Indicador.DETECCAO_ADENOMA: indicadores.deteccao_adenoma,
        Indicador.SERRILHADA_SESSIL: indicadores.serrilhada_sessil,
        Indicador.INTUBACAO_CECAL: indicadores.intubacao_cecal,
        Indicador.PREPARO_ADEQUADO: indicadores.preparo_adequado,
    }
    alertas = [
        Alerta(nome, p.estimativa, LIMIARES[nome], p.ic.superior < LIMIARES[nome])
        for nome, p in proporcoes.items()
        if p.estimativa is not None and p.estimativa < LIMIARES[nome]
    ]
    retirada = indicadores.tempo_retirada.media
    limiar_retirada = LIMIARES[Indicador.TEMPO_RETIRADA]
    if retirada is not None and retirada < limiar_retirada:
        alertas.append(Alerta(Indicador.TEMPO_RETIRADA, retirada, limiar_retirada, False))
    return tuple(alertas)


def _tem_adenoma(r: ExameDoPaciente) -> bool:
    return any(lesao.adenoma_convencional for lesao in r.exame.lesoes)


def _tem_avancado(r: ExameDoPaciente) -> bool:
    return any(lesao.adenoma_avancado for lesao in r.exame.lesoes)


def _tem_serrilhada_sessil(r: ExameDoPaciente) -> bool:
    """Só a séssil: a meta de 6% é da SSL (o adenoma serrilhado tradicional fica fora)."""
    return any(lesao.histologia is Histologia.SERRILHADA_SESSIL for lesao in r.exame.lesoes)


def _do_examinador(
    examinador: Examinador, registros: Sequence[ExameDoPaciente], alfa: float
) -> IndicadoresDoExaminador:
    deteccao = [r for r in registros if elegivel_para_deteccao(r)]
    com_laudo = [r for r in deteccao if not r.exame.aguardando_histologia]
    sem_lesao = [r.exame for r in registros if not r.exame.lesoes]
    com_boston = [r for r in registros if r.exame.preparo is not None]
    adenomas = [
        float(sum(1 for lesao in r.exame.lesoes if lesao.adenoma_convencional)) for r in com_laudo
    ]
    parcial = IndicadoresDoExaminador(
        examinador=examinador,
        n_exames=len(registros),
        deteccao_adenoma=_contar(com_laudo, _tem_adenoma, alfa),
        adenoma_avancado=_contar(com_laudo, _tem_avancado, alfa),
        serrilhada_sessil=_contar(com_laudo, _tem_serrilhada_sessil, alfa),
        adenomas_por_exame=_media(adenomas),
        deteccao_polipo=_contar(deteccao, lambda r: r.exame.n_polipos > 0, alfa),
        intubacao_cecal=_contar(registros, lambda r: r.exame.intubacao_cecal, alfa),
        tempo_retirada=_media([e.tempo_retirada_min for e in sem_lesao if e.tempo_retirada_min]),
        preparo_adequado=_contar(com_boston, lambda r: bool(r.exame.preparo_adequado), alfa),
        aguardando_histologia=len(deteccao) - len(com_laudo),
        alertas=(),
    )
    return parcial._replace(alertas=_alertas(parcial))


def indicadores_por_examinador(
    fichas: Iterable[Ficha], alfa: float = 0.05
) -> tuple[IndicadoresDoExaminador, ...]:
    """Um item por examinador (CRM + UF), em ordem alfabética do nome."""
    grupos: dict[tuple[str, str], list[ExameDoPaciente]] = {}
    for registro in exames_de(fichas):
        examinador = registro.exame.examinador
        grupos.setdefault((examinador.crm, examinador.uf), []).append(registro)
    resultado = [_do_examinador(r[0].exame.examinador, r, alfa) for r in grupos.values()]
    return tuple(sorted(resultado, key=lambda i: i.examinador.nome.casefold()))
