"""Mantel-Haenszel para estratos 2x2: OR combinado, IC, teste de associação e
homogeneidade de Breslow-Day.

- Mantel N, Haenszel W. J Natl Cancer Inst 1959;22:719-748 (OR e χ² sem correção).
- Robins J, Breslow N, Greenland S. Biometrics 1986;42:311-323 (variância do log OR).
- Breslow NE, Day NE. Statistical Methods in Cancer Research I, IARC 1980 (homogeneidade,
  sem a correção de Tarone).
Referências no R: `mantelhaen.test(x, correct = FALSE)` e
`DescTools::BreslowDayTest(x, correct = FALSE)`.

Cada estrato é (a, b, c, d) na disposição de `tabela_2x2`.
"""

import math
from collections.abc import Sequence
from typing import NamedTuple

from scipy.stats import chi2

from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao, conferir_contagens
from gastroepi.estatistica.proporcoes import Intervalo, quantil_normal, razao

type Estrato = tuple[int, int, int, int]


class ResultadoMantelHaenszel(NamedTuple):
    odds_ratio: float
    odds_ratio_ic: Intervalo
    qui_quadrado: float
    p_valor: float
    chi2_homogeneidade: float
    p_valor_homogeneidade: float
    graus_liberdade: int  # da homogeneidade: estratos usados - 1


def _ic_robins_breslow_greenland(estratos: Sequence[Estrato], z: float) -> Intervalo:
    soma_r = soma_s = soma_pr = soma_ps_qr = soma_qs = 0.0
    for a, b, c, d in estratos:
        n = a + b + c + d
        p, q, r, s = (a + d) / n, (b + c) / n, a * d / n, b * c / n
        soma_r, soma_s = soma_r + r, soma_s + s
        soma_pr, soma_ps_qr, soma_qs = soma_pr + p * r, soma_ps_qr + p * s + q * r, soma_qs + q * s
    if soma_r == 0 or soma_s == 0:
        return Intervalo(0.0, math.inf)
    variancia = (
        soma_pr / (2 * soma_r**2) + soma_ps_qr / (2 * soma_r * soma_s) + soma_qs / (2 * soma_s**2)
    )
    log_or, margem = math.log(soma_r / soma_s), z * math.sqrt(variancia)
    return Intervalo(math.exp(log_or - margem), math.exp(log_or + margem))


def _qui_quadrado_mh(estratos: Sequence[Estrato]) -> tuple[float, float]:
    observado = esperado = variancia = 0.0
    for a, b, c, d in estratos:
        n = a + b + c + d
        observado += a
        esperado += (a + b) * (a + c) / n
        if n > 1:
            variancia += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
    if variancia == 0:
        return 0.0, 1.0
    estatistica = (observado - esperado) ** 2 / variancia
    return estatistica, float(chi2.sf(estatistica, 1))


def _a_esperado(estrato: Estrato, odds_ratio: float) -> float:
    """Raiz de a(n0 - m1 + a) = OR (n1 - a)(m1 - a) dentro dos limites da tabela.

    É sempre a raiz (-B + raiz(delta)) / 2A: para OR em (0, 1) e (1, ∞) ela fica em
    [max(0, m1 - n0), min(n1, m1)] (conferido por busca exaustiva em contagens até 5).
    """
    a, b, c, d = estrato
    n1, n0, m1 = a + b, c + d, a + c
    if math.isclose(odds_ratio, 1.0):
        return n1 * m1 / (n1 + n0)
    qa, qb, qc = 1 - odds_ratio, (n0 - m1) + odds_ratio * (n1 + m1), -odds_ratio * n1 * m1
    raiz = (-qb + math.sqrt(max(0.0, qb * qb - 4 * qa * qc))) / (2 * qa)
    return min(max(raiz, max(0, m1 - n0)), min(n1, m1))


def _breslow_day(estratos: Sequence[Estrato], odds_ratio: float) -> tuple[float, int]:
    """Estrato com margem zerada não informa sobre a homogeneidade e fica de fora. Nos
    outros, com OR finito e positivo, as quatro células esperadas são > 0."""
    estatistica, usados = 0.0, 0
    for estrato in estratos:
        a, b, c, d = estrato
        if 0 in (a + b, c + d, a + c, b + d):
            continue
        usados += 1
        esperado = _a_esperado(estrato, odds_ratio)
        celulas = (esperado, a + b - esperado, a + c - esperado, d - a + esperado)
        estatistica += (a - esperado) ** 2 * sum(1 / x for x in celulas)
    return estatistica, max(usados - 1, 0)


def mantel_haenszel(estratos: Sequence[Estrato], alfa: float = 0.05) -> ResultadoMantelHaenszel:
    """Estratos vazios são ignorados. OR ∞ ou 0/0 (NaN) não têm homogeneidade a testar."""
    if not estratos:
        raise EntradaInvalida("Mantel-Haenszel precisa de ao menos 1 estrato; recebido 0")
    conferir_contagens(*(x for estrato in estratos for x in estrato))
    usados = [e for e in estratos if sum(e) > 0]
    if not usados:
        raise SemObservacao("todos os estratos estão vazios")
    soma_r = sum(a * d / (a + b + c + d) for a, b, c, d in usados)
    soma_s = sum(b * c / (a + b + c + d) for a, b, c, d in usados)
    odds_ratio = razao(soma_r, soma_s)
    estatistica, p_valor = _qui_quadrado_mh(usados)
    homogeneidade, graus = 0.0, 0
    if math.isfinite(odds_ratio) and odds_ratio > 0:
        homogeneidade, graus = _breslow_day(usados, odds_ratio)
    p_homogeneidade = float(chi2.sf(homogeneidade, graus)) if graus else 1.0
    return ResultadoMantelHaenszel(
        odds_ratio,
        _ic_robins_breslow_greenland(usados, quantil_normal(alfa)),
        estatistica,
        p_valor,
        homogeneidade,
        p_homogeneidade,
        graus,
    )
