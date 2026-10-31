"""Descritivas, frequências, estratificação, tabela cruzada e prevalência de pólipo.

Unidade de análise: o exame. Quartis pelo tipo 7 do R (`quantile(type = 7)`, o padrão),
desvio padrão amostral (n - 1, `sd`). Referências no R: tests/fixtures/referencias_r.json.
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import NamedTuple

import numpy as np

from gastroepi.dominio.ficha import Ficha
from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from gastroepi.estatistica.proporcoes import Proporcao, proporcao
from gastroepi.estatistica.variaveis import (
    Variavel,
    VariavelNumerica,
    categorias,
    exames_de,
    medida,
)


class Descritivas(NamedTuple):
    n: int
    media: float
    mediana: float
    desvio_padrao: float  # 0 com um valor só (o `sd` do R dá NA)
    q1: float
    q3: float
    minimo: float
    maximo: float


class ItemFrequencia(NamedTuple):
    valor: str
    contagem: int
    percentual: float  # dos exames; em comorbidade e sintoma a soma passa de 100


def descritivas(valores: Sequence[float]) -> Descritivas:
    if not valores:
        raise SemObservacao("descritivas de uma lista vazia")
    if not all(math.isfinite(v) for v in valores):
        raise EntradaInvalida("descritivas aceitam só números finitos; recebido NaN ou infinito")
    vetor = np.asarray(valores, dtype=np.float64)
    q1, mediana, q3 = (float(q) for q in np.quantile(vetor, [0.25, 0.5, 0.75]))
    desvio = float(np.std(vetor, ddof=1)) if len(vetor) > 1 else 0.0
    return Descritivas(
        len(vetor),
        float(vetor.mean()),
        mediana,
        desvio,
        q1,
        q3,
        float(vetor.min()),
        float(vetor.max()),
    )


def frequencias(fichas: Iterable[Ficha], variavel: Variavel) -> tuple[ItemFrequencia, ...]:
    """Da maior contagem para a menor; empate em ordem alfabética.

    O percentual é sobre o nº de exames, não sobre o nº de menções (a v0.1.16 dividia
    pelas menções, e "25% têm tabagismo" virava 25% das comorbidades citadas).
    """
    registros = exames_de(fichas)
    contagem = Counter(c for r in registros for c in categorias(r, variavel))
    ordem = sorted(contagem.items(), key=lambda par: (-par[1], par[0]))
    return tuple(ItemFrequencia(v, n, 100.0 * n / len(registros)) for v, n in ordem)


def estratificar(
    fichas: Iterable[Ficha], grupo: Variavel, valor: VariavelNumerica
) -> dict[str, Descritivas]:
    """Exame sem a medida fica de fora; com vários grupos (comorbidades), entra em cada um."""
    grupos: dict[str, list[float]] = {}
    for registro in exames_de(fichas):
        numero = medida(registro, valor)
        if numero is None:
            continue
        for chave in categorias(registro, grupo):
            grupos.setdefault(chave, []).append(numero)
    return {chave: descritivas(numeros) for chave, numeros in sorted(grupos.items())}


def tabular_cruzado(
    fichas: Iterable[Ficha], linha: Variavel, coluna: Variavel
) -> dict[str, dict[str, int]]:
    tabela: dict[str, Counter[str]] = {}
    for registro in exames_de(fichas):
        for chave_linha in categorias(registro, linha):
            tabela.setdefault(chave_linha, Counter()).update(categorias(registro, coluna))
    return {chave: dict(sorted(contagem.items())) for chave, contagem in sorted(tabela.items())}


def prevalencia_polipo(fichas: Iterable[Ficha], alfa: float = 0.05) -> Proporcao:
    """Exames com ao menos uma lesão; sem exame, a estimativa é `None` e o IC é [0, 1]."""
    registros = exames_de(fichas)
    com_polipo = sum(1 for r in registros if r.exame.n_polipos > 0)
    return proporcao(com_polipo, len(registros), alfa)
