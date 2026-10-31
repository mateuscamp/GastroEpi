import math

import pytest

from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from gastroepi.estatistica.tendencia import Direcao, cochran_armitage
from tests.estatistica.referencias import Json, aprox, oraculo, referencias_r


@pytest.mark.referencia
def test_fumantes_da_documentacao_do_r() -> None:
    """R, ?prop.trend.test: smokers <- c(83, 90, 129, 70); patients <- c(86, 93, 136, 82)
    → X-squared = 8.2249, df = 1, p-value = 0.004132."""
    resultado = cochran_armitage([83, 90, 129, 70], [86, 93, 136, 82], [1, 2, 3, 4])
    assert resultado.qui_quadrado == pytest.approx(8.2249, abs=1e-4)
    assert resultado.p_valor == pytest.approx(0.004132, abs=1e-6)
    assert resultado.direcao is Direcao.DECRESCENTE


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["tendencia"], ids=str)
def test_tendencia_bate_com_o_prop_trend_test_do_r(caso: Json) -> None:
    """R 4.5.1: prop.trend.test(casos, totais, score = escores)."""
    resultado = cochran_armitage(caso["casos"], caso["totais"], caso["escores"])
    assert resultado.qui_quadrado == aprox(caso["qui_quadrado"])
    assert resultado.p_valor == aprox(caso["p_valor"])


@pytest.mark.parametrize("caso", oraculo()["tendencia_cochran_armitage"], ids=str)
def test_tendencia_bate_com_o_oraculo(caso: Json) -> None:
    """Sem divergência N/(N - 1): a v0.1.16 já usava a variância do prop.trend.test."""
    if "Err" in caso["saida"]:
        with pytest.raises(EntradaInvalida):
            cochran_armitage(*caso["entrada"])
        return
    esperado, resultado = caso["saida"]["Ok"], cochran_armitage(*caso["entrada"])
    assert resultado.qui_quadrado == aprox(esperado["qui_quadrado"])
    assert resultado.p_valor == aprox(esperado["p_valor"])
    assert list(resultado.escores) == esperado["escores"]
    assert list(resultado.proporcoes) == aprox(esperado["proporcoes"])
    assert resultado.direcao == esperado["direcao"]


@pytest.mark.referencia
def test_sem_variacao_nao_ha_tendencia() -> None:
    """R: prop.trend.test(c(0, 0, 0), c(10, 10, 10)) dá NaN; aqui χ² = 0, p = 1, neutra,
    como na v0.1.16. Grupo vazio tem proporção NaN (0/0), e não 0 como na v0.1.16."""
    nula = cochran_armitage([0, 0, 0], [10, 10, 10])
    assert (nula.qui_quadrado, nula.p_valor, nula.direcao) == (0.0, 1.0, Direcao.NEUTRA)
    com_vazio = cochran_armitage([1, 0, 4], [10, 0, 10])
    assert math.isnan(com_vazio.proporcoes[1])
    assert com_vazio.direcao is Direcao.CRESCENTE


@pytest.mark.parametrize(
    ("casos", "totais", "escores"),
    [([1], [2], None), ([3, 1], [2, 2], None), ([1, 1], [2, 2], [1.0])],
)
def test_entrada_incoerente_e_recusada(
    casos: list[int], totais: list[int], escores: list[float] | None
) -> None:
    with pytest.raises(EntradaInvalida):
        cochran_armitage(casos, totais, escores)


def test_sem_observacao_e_recusada() -> None:
    with pytest.raises(SemObservacao):
        cochran_armitage([0, 0], [0, 0])
