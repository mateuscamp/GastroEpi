"""Intervalo de confiança de uma proporção (Wilson) e a proporção com o seu IC.

Wilson EB. Probable inference, the law of succession, and statistical inference.
J Am Stat Assoc 1927;22:209-212. É o `prop.test(x, n, correct = FALSE)` do R.
"""

import math
from typing import NamedTuple

from scipy.stats import norm

from gastroepi.estatistica.entrada import EntradaInvalida, conferir_alfa, conferir_contagens


class Intervalo(NamedTuple):
    inferior: float
    superior: float


class Proporcao(NamedTuple):
    """`casos`/`total` com o IC de Wilson. Sem total, a estimativa é `None`, nunca 0."""

    casos: int
    total: int
    ic: Intervalo

    @property
    def estimativa(self) -> float | None:
        return self.casos / self.total if self.total else None


def quantil_normal(alfa: float) -> float:
    """z bicaudal: 1,959964 para alfa = 0,05 (R: qnorm(0.975))."""
    conferir_alfa(alfa)
    return float(norm.ppf(1.0 - alfa / 2.0))


def intervalo_wilson(casos: int, total: int, alfa: float = 0.05) -> Intervalo:
    """IC de Wilson, sem correção de continuidade.

    Sem observação (total = 0), devolve [0, 1]: é o limite do intervalo quando n → 0, e
    diz que nenhuma proporção foi excluída. A v0.1.16 devolvia [0, 0].
    """
    conferir_contagens(casos, total)
    if casos > total:
        raise EntradaInvalida(f"casos ({casos}) não pode passar do total ({total})")
    z = quantil_normal(alfa)
    if total == 0:
        return Intervalo(0.0, 1.0)
    p, n = casos / total, float(total)
    denominador = 1.0 + z * z / n
    centro = (p + z * z / (2.0 * n)) / denominador
    margem = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denominador
    inferior = 0.0 if casos == 0 else max(0.0, centro - margem)
    superior = 1.0 if casos == total else min(1.0, centro + margem)
    return Intervalo(inferior, superior)


def proporcao(casos: int, total: int, alfa: float = 0.05) -> Proporcao:
    return Proporcao(casos, total, intervalo_wilson(casos, total, alfa))


def razao(numerador: float, denominador: float) -> float:
    """Razão com as bordas explícitas: x/0 = ∞ para x > 0; 0/0 e NaN dão NaN (indefinido).

    A v0.1.16 devolvia 0 no 0/0, que se lê como "efeito protetor máximo".
    """
    if math.isnan(numerador) or math.isnan(denominador):
        return math.nan
    if denominador == 0:
        return math.inf if numerador > 0 else math.nan
    return numerador / denominador
