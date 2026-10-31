"""Tabela 2x2: odds ratio (IC de Woolf), risco relativo (IC log), qui-quadrado e Fisher.

Disposição: `a` expostos com o desfecho, `b` expostos sem, `c` não expostos com,
`d` não expostos sem.

Referências do R (tests/fixtures/referencias_r.json): `epitools::oddsratio.wald`,
`epitools::riskratio.wald`, `chisq.test(correct = FALSE/TRUE)` e `fisher.test`.
- Woolf B. On estimating the relation between blood group and disease. Ann Hum Genet
  1955;19:251-253.
- Katz D et al. Obtaining confidence intervals for the risk ratio in cohort studies.
  Biometrics 1978;34:469-474.
"""

import math
from typing import NamedTuple

from scipy.stats import chi2, fisher_exact

from gastroepi.estatistica.entrada import SemObservacao, conferir_contagens
from gastroepi.estatistica.proporcoes import Intervalo, quantil_normal, razao

SEM_LIMITE = Intervalo(0.0, math.inf)  # uma célula zerada: o IC não exclui nada


class ResultadoTabela2x2(NamedTuple):
    odds_ratio: float
    odds_ratio_ic: Intervalo
    risco_relativo: float
    risco_relativo_ic: Intervalo
    chi2_pearson: float
    p_valor_pearson: float
    chi2_yates: float
    p_valor_yates: float
    p_valor_fisher: float
    n_total: int


class QuiQuadrado(NamedTuple):
    estatistica: float
    p_valor: float


def fisher_exato(a: int, b: int, c: int, d: int) -> float:
    """p bicaudal do teste exato de Fisher, como o `fisher.test` do R.

    Soma as tabelas com probabilidade ≤ a observada (tolerância relativa 1e-7, a mesma do R).
    """
    conferir_contagens(a, b, c, d)
    return float(fisher_exact([[a, b], [c, d]], alternative="two-sided").pvalue)


def _ic_log(estimativa: float, erro_padrao: float, z: float) -> Intervalo:
    log = math.log(estimativa)
    return Intervalo(math.exp(log - z * erro_padrao), math.exp(log + z * erro_padrao))


def _odds_ratio_woolf(a: int, b: int, c: int, d: int, z: float) -> Intervalo:
    if 0 in (a, b, c, d):
        return SEM_LIMITE
    erro_padrao = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return _ic_log(a * d / (b * c), erro_padrao, z)


def _risco_relativo_log(a: int, b: int, c: int, d: int, z: float) -> Intervalo:
    if a == 0 or c == 0:
        return SEM_LIMITE
    erro_padrao = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    return _ic_log((a / (a + b)) / (c / (c + d)), erro_padrao, z)


def _qui_quadrados(a: int, b: int, c: int, d: int) -> tuple[QuiQuadrado, QuiQuadrado]:
    """Pearson e Yates. Com uma margem zerada não há o que testar: 0 e p = 1 (o R dá NaN).

    Yates como no R: a correção é min(0,5; |O - E|), então |ad - bc| ≤ n/2 dá 0.
    """
    n = a + b + c + d
    margens = (a + b) * (c + d) * (a + c) * (b + d)
    if margens == 0:
        return QuiQuadrado(0.0, 1.0), QuiQuadrado(0.0, 1.0)
    diferenca = abs(a * d - b * c)
    pearson = n * diferenca**2 / margens
    yates = n * max(0.0, diferenca - n / 2) ** 2 / margens
    return (
        QuiQuadrado(pearson, float(chi2.sf(pearson, 1))),
        QuiQuadrado(yates, float(chi2.sf(yates, 1))),
    )


def tabela_2x2(a: int, b: int, c: int, d: int, alfa: float = 0.05) -> ResultadoTabela2x2:
    """OR = ad/bc e RR = [a/(a+b)]/[c/(c+d)]; x/0 = ∞ e 0/0 = NaN (`razao`).

    Com uma célula zerada o IC é [0, ∞), como na v0.1.16 (o R dá NaN ou ∞).
    """
    conferir_contagens(a, b, c, d)
    if a + b + c + d == 0:
        raise SemObservacao("tabela 2x2 vazia: a + b + c + d = 0")
    z = quantil_normal(alfa)
    risco_expostos = razao(a, a + b)
    risco_nao_expostos = razao(c, c + d)
    pearson, yates = _qui_quadrados(a, b, c, d)
    return ResultadoTabela2x2(
        odds_ratio=razao(a * d, b * c),
        odds_ratio_ic=_odds_ratio_woolf(a, b, c, d, z),
        risco_relativo=razao(risco_expostos, risco_nao_expostos),
        risco_relativo_ic=_risco_relativo_log(a, b, c, d, z),
        chi2_pearson=pearson.estatistica,
        p_valor_pearson=pearson.p_valor,
        chi2_yates=yates.estatistica,
        p_valor_yates=yates.p_valor,
        p_valor_fisher=fisher_exato(a, b, c, d),
        n_total=a + b + c + d,
    )
