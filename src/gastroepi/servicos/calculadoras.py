"""Calculadoras do StatCalc sobre números digitados: a porta da casca para `estatistica`.

Os sete comandos `calcular_*` da v0.1.16. Os erros de entrada chegam como
`EntradaInvalida`, com a mensagem do que se esperava.
"""

from collections.abc import Sequence

from gastroepi.estatistica import amostra, contingencia, diagnostico, tabela_2x2, tendencia
from gastroepi.estatistica.amostra import AmostraComparativa
from gastroepi.estatistica.contingencia import ResultadoQuiQuadrado
from gastroepi.estatistica.diagnostico import ResultadoDiagnostico
from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from gastroepi.estatistica.mantel_haenszel import Estrato, ResultadoMantelHaenszel, mantel_haenszel
from gastroepi.estatistica.proporcoes import Intervalo, Proporcao
from gastroepi.estatistica.tabela_2x2 import ResultadoTabela2x2
from gastroepi.estatistica.tendencia import Direcao, ResultadoTendencia

__all__ = [
    "AmostraComparativa",
    "Direcao",
    "EntradaInvalida",
    "Estrato",
    "Intervalo",
    "Proporcao",
    "ResultadoDiagnostico",
    "ResultadoMantelHaenszel",
    "ResultadoQuiQuadrado",
    "ResultadoTabela2x2",
    "ResultadoTendencia",
    "SemObservacao",
]


def calcular_tabela_2x2(a: int, b: int, c: int, d: int) -> ResultadoTabela2x2:
    return tabela_2x2.tabela_2x2(a, b, c, d)


def calcular_teste_diagnostico(vp: int, fp: int, fn: int, vn: int) -> ResultadoDiagnostico:
    return diagnostico.desempenho_diagnostico(vp, fp, fn, vn)


def calcular_amostra_inquerito(
    p: float, d: float, confianca: float, populacao: int | None = None
) -> int:
    return amostra.amostra_inquerito(p, d, confianca, populacao)


def calcular_amostra_comparativa(
    poder: float, confianca: float, razao: float, p0: float, p1: float
) -> AmostraComparativa:
    return amostra.amostra_comparativa(poder, confianca, razao, p0, p1)


def calcular_tendencia(
    casos: Sequence[int], totais: Sequence[int], escores: Sequence[float] | None = None
) -> ResultadoTendencia:
    return tendencia.cochran_armitage(casos, totais, escores)


def calcular_mantel_haenszel(estratos: Sequence[Estrato]) -> ResultadoMantelHaenszel:
    return mantel_haenszel(estratos)


def calcular_qui_quadrado_geral(matriz: Sequence[Sequence[int]]) -> ResultadoQuiQuadrado:
    return contingencia.qui_quadrado_rxc(matriz)
