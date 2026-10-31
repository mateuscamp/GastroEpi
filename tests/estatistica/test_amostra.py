import math

import pytest

from gastroepi.estatistica.amostra import AmostraComparativa, amostra_comparativa, amostra_inquerito
from gastroepi.estatistica.entrada import EntradaInvalida
from tests.estatistica.referencias import Json, oraculo, referencias_r


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["amostra_survey"], ids=str)
def test_inquerito_bate_com_a_formula_do_epi_info_no_r(caso: Json) -> None:
    """Epi Info StatCalc/OpenEpi SSPropor, recalculada no R 4.5.1 com qnorm; arredonda para cima."""
    n = amostra_inquerito(caso["p"], caso["d"], caso["confianca"], caso["populacao"])
    assert n == math.ceil(caso["n"])


@pytest.mark.referencia
def test_inquerito_classico_de_385() -> None:
    """Epi Info StatCalc, população infinita, p = 50%, d = 5%, 95%: 384,15 → 385."""
    assert amostra_inquerito(0.5, 0.05, 0.95) == 385


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["amostra_comparativa"], ids=str)
def test_comparativa_bate_com_fleiss_no_r(caso: Json) -> None:
    """Fleiss, Levin e Paik 2003, eq. 4.14, sem correção, recalculada no R 4.5.1."""
    resultado = amostra_comparativa(
        caso["poder"], caso["confianca"], caso["razao"], caso["p0"], caso["p1"]
    )
    assert resultado == AmostraComparativa(math.ceil(caso["n1"]), math.ceil(caso["n0"]))


@pytest.mark.parametrize("caso", oraculo()["amostra_survey"], ids=str)
def test_inquerito_bate_com_o_oraculo(caso: Json) -> None:
    populacao, p, d, confianca = caso["entrada"]
    if "Err" in caso["saida"]:
        with pytest.raises(EntradaInvalida):
            amostra_inquerito(p, d, confianca, populacao)
    else:
        assert (
            amostra_inquerito(p, d, confianca, populacao) == caso["saida"]["Ok"]["tamanho_amostra"]
        )


@pytest.mark.parametrize("caso", oraculo()["amostra_comparativa"], ids=str)
def test_comparativa_bate_com_o_oraculo(caso: Json) -> None:
    if "Err" in caso["saida"]:
        with pytest.raises(EntradaInvalida):
            amostra_comparativa(*caso["entrada"])
        return
    esperado, resultado = caso["saida"]["Ok"], amostra_comparativa(*caso["entrada"])
    assert (resultado.expostos, resultado.nao_expostos, resultado.total) == (
        esperado["amostra_grupo1"],
        esperado["amostra_grupo2"],
        esperado["amostra_total"],
    )


@pytest.mark.parametrize(
    ("p", "d", "confianca", "populacao"),
    [(0.0, 0.05, 0.95, None), (0.5, 1.0, 0.95, None), (0.5, 0.05, 1.0, None), (0.5, 0.05, 0.95, 0)],
)
def test_inquerito_recusa_parametro_fora_do_dominio(
    p: float, d: float, confianca: float, populacao: int | None
) -> None:
    with pytest.raises(EntradaInvalida):
        amostra_inquerito(p, d, confianca, populacao)


def test_comparativa_recusa_razao_nao_positiva() -> None:
    with pytest.raises(EntradaInvalida, match="razão"):
        amostra_comparativa(0.8, 0.95, 0.0, 0.2, 0.3)


def test_inquerito_nunca_passa_da_populacao() -> None:
    assert amostra_inquerito(0.5, 0.01, 0.99, 50) == 50
