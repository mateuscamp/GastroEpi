"""Tamanho de amostra: inquérito (proporção) e estudo comparativo (Fleiss, sem correção).

- Inquérito: n = N z² p q / (d² (N - 1) + z² p q); sem N, n = z² p q / d² (Epi Info
  StatCalc; Dean AG, Sullivan KM, Soe MM, OpenEpi, SSPropor).
- Comparativo: Fleiss JL, Levin B, Paik MC. Statistical Methods for Rates and
  Proportions, 3ª ed., Wiley 2003, eq. 4.14 (OpenEpi SSCohort, "Fleiss").
A referência numérica é a mesma fórmula recalculada no R (ferramentas/referencias_r/gerar.R).
"""

import math
from typing import NamedTuple

from scipy.stats import norm

from gastroepi.estatistica.entrada import EntradaInvalida
from gastroepi.estatistica.proporcoes import quantil_normal


class AmostraComparativa(NamedTuple):
    expostos: int  # grupo com a proporção p1
    nao_expostos: int  # grupo com a proporção p0, razao vezes o primeiro

    @property
    def total(self) -> int:
        return self.expostos + self.nao_expostos


def _conferir_aberto(nome: str, valor: float) -> None:
    if not 0.0 < valor < 1.0:
        raise EntradaInvalida(f"{nome} deve estar em (0, 1); recebido {valor}")


def amostra_inquerito(p: float, d: float, confianca: float, populacao: int | None = None) -> int:
    """Arredonda para cima e nunca passa da população."""
    _conferir_aberto("frequência esperada p", p)
    _conferir_aberto("margem de erro d", d)
    _conferir_aberto("confiança", confianca)
    if populacao is not None and populacao <= 0:
        raise EntradaInvalida(f"população deve ser > 0; recebido {populacao}")
    z = quantil_normal(1.0 - confianca)
    n0 = z * z * p * (1.0 - p) / (d * d)
    if populacao is None:
        return math.ceil(n0)
    return min(math.ceil(populacao * n0 / (n0 + populacao - 1)), populacao)


def amostra_comparativa(
    poder: float, confianca: float, razao: float, p0: float, p1: float
) -> AmostraComparativa:
    """`razao` = não expostos por exposto; poder unicaudal, confiança bicaudal."""
    for nome, valor in (("poder", poder), ("confiança", confianca), ("p0", p0), ("p1", p1)):
        _conferir_aberto(nome, valor)
    if razao <= 0:
        raise EntradaInvalida(f"razão deve ser > 0; recebido {razao}")
    if math.isclose(p0, p1, abs_tol=1e-9):
        raise EntradaInvalida(f"p0 e p1 iguais ({p0}): não há diferença a detectar")
    z_alfa, z_beta = quantil_normal(1.0 - confianca), float(norm.ppf(poder))
    p_barra = (p1 + razao * p0) / (1.0 + razao)
    raiz_nula = math.sqrt((razao + 1.0) * p_barra * (1.0 - p_barra))
    raiz_alternativa = math.sqrt(razao * p1 * (1.0 - p1) + p0 * (1.0 - p0))
    n1 = (z_alfa * raiz_nula + z_beta * raiz_alternativa) ** 2 / (razao * (p1 - p0) ** 2)
    return AmostraComparativa(math.ceil(n1), math.ceil(razao * n1))
