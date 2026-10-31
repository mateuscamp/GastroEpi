"""Teste de tendência de Cochran-Armitage para proporções ordenadas.

Armitage P. Tests for linear trends in proportions and frequencies. Biometrics
1955;11:375-386. Mesma estatística do `prop.trend.test` do R: a variância usa N, não
N - 1. O plano esperava diferir da v0.1.16 por N/(N - 1); não difere: a v0.1.16 também
usa N.
"""

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import NamedTuple

from scipy.stats import chi2

from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao, conferir_contagens
from gastroepi.estatistica.proporcoes import razao


class Direcao(StrEnum):
    CRESCENTE = "crescente"
    DECRESCENTE = "decrescente"
    NEUTRA = "neutra"


class ResultadoTendencia(NamedTuple):
    qui_quadrado: float
    p_valor: float
    escores: tuple[float, ...]
    proporcoes: tuple[float, ...]  # NaN no grupo sem nenhuma observação
    direcao: Direcao


def _conferir(casos: Sequence[int], totais: Sequence[int], escores: Sequence[float]) -> None:
    if not len(casos) == len(totais) == len(escores):
        raise EntradaInvalida(
            f"casos, totais e escores com tamanhos diferentes: "
            f"{len(casos)}, {len(totais)}, {len(escores)}"
        )
    if len(casos) < 2:
        raise EntradaInvalida(f"são precisos ao menos 2 grupos; recebido {len(casos)}")
    conferir_contagens(*casos, *totais)
    excedentes = [i for i, (r, n) in enumerate(zip(casos, totais, strict=True)) if r > n]
    if excedentes:
        raise EntradaInvalida(f"casos maiores que o total nos grupos {excedentes}")


def cochran_armitage(
    casos: Sequence[int], totais: Sequence[int], escores: Sequence[float] | None = None
) -> ResultadoTendencia:
    """Escores padrão 0, 1, 2…; sem variação (p̄ = 0, p̄ = 1 ou escores iguais), χ² = 0 e p = 1."""
    pesos = tuple(float(e) for e in (range(len(casos)) if escores is None else escores))
    _conferir(casos, totais, pesos)
    n_total = sum(totais)
    if n_total == 0:
        raise SemObservacao("teste de tendência sem observações: soma dos totais = 0")
    proporcoes = tuple(razao(r, n) for r, n in zip(casos, totais, strict=True))
    p_barra = sum(casos) / n_total
    u = sum(t * (r - n * p_barra) for t, r, n in zip(pesos, casos, totais, strict=True))
    soma_nt = sum(n * t for n, t in zip(totais, pesos, strict=True))
    soma_nt2 = sum(n * t * t for n, t in zip(totais, pesos, strict=True))
    variancia = p_barra * (1 - p_barra) * (soma_nt2 - soma_nt**2 / n_total)
    if variancia <= 0 or math.isclose(u, 0.0, abs_tol=1e-12):
        return ResultadoTendencia(0.0, 1.0, pesos, proporcoes, Direcao.NEUTRA)
    estatistica = u * u / variancia
    direcao = Direcao.CRESCENTE if u > 0 else Direcao.DECRESCENTE
    return ResultadoTendencia(
        estatistica, float(chi2.sf(estatistica, 1)), pesos, proporcoes, direcao
    )
