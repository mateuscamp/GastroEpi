"""Qui-quadrado de Pearson para tabelas RxC, sem correção de continuidade.

Pearson K. On the criterion that a given system of deviations… Philos Mag 1900;50:157-175.
Referência no R: `chisq.test(m, correct = FALSE)`.
"""

from collections.abc import Sequence
from typing import NamedTuple

from scipy.stats import chi2

from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao, conferir_contagens


class ResultadoQuiQuadrado(NamedTuple):
    qui_quadrado: float
    graus_liberdade: int
    p_valor: float


def _conferir_forma(matriz: Sequence[Sequence[int]]) -> None:
    colunas = {len(linha) for linha in matriz}
    if len(matriz) < 2 or len(colunas) != 1 or min(colunas) < 2:
        formas = [len(linha) for linha in matriz]
        raise EntradaInvalida(f"tabela deve ter ≥ 2 linhas e ≥ 2 colunas iguais; recebido {formas}")


def qui_quadrado_rxc(matriz: Sequence[Sequence[int]]) -> ResultadoQuiQuadrado:
    """Linha ou coluna toda zerada não tem frequência esperada: é recusada (o R dá NaN)."""
    _conferir_forma(matriz)
    conferir_contagens(*(c for linha in matriz for c in linha))
    somas_linhas = [sum(linha) for linha in matriz]
    somas_colunas = [sum(coluna) for coluna in zip(*matriz, strict=True)]
    n = sum(somas_linhas)
    if n == 0:
        raise SemObservacao("tabela RxC vazia")
    if 0 in somas_linhas or 0 in somas_colunas:
        raise EntradaInvalida(
            f"linha ou coluna sem observação: linhas {somas_linhas}, colunas {somas_colunas}"
        )
    estatistica = 0.0
    for linha, soma_linha in zip(matriz, somas_linhas, strict=True):
        for observado, soma_coluna in zip(linha, somas_colunas, strict=True):
            esperado = soma_linha * soma_coluna / n
            estatistica += (observado - esperado) ** 2 / esperado
    graus = (len(matriz) - 1) * (len(somas_colunas) - 1)
    return ResultadoQuiQuadrado(estatistica, graus, float(chi2.sf(estatistica, graus)))
