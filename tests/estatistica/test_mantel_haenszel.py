import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from gastroepi.estatistica.mantel_haenszel import Estrato, mantel_haenszel
from tests.estatistica.referencias import Json, aprox, oraculo, referencias_r


def _estratos(lista: list[list[int]]) -> list[Estrato]:
    return [(a, b, c, d) for a, b, c, d in lista]


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["mantel_haenszel"], ids=str)
def test_mh_bate_com_mantelhaen_test_e_breslow_day_do_r(caso: Json) -> None:
    """R 4.5.1: mantelhaen.test(x, correct = FALSE) e DescTools::BreslowDayTest(x)."""
    resultado = mantel_haenszel(_estratos(caso["estratos"]))
    assert resultado.odds_ratio == aprox(caso["odds_ratio"])
    assert resultado.odds_ratio_ic == aprox(caso["odds_ratio_ic"])
    assert resultado.qui_quadrado == aprox(caso["chi2"])
    assert resultado.p_valor == aprox(caso["p_valor"])
    assert resultado.chi2_homogeneidade == aprox(caso["chi2_homogeneidade"])
    assert resultado.p_valor_homogeneidade == aprox(caso["p_valor_homogeneidade"])


@pytest.mark.parametrize(
    "caso",
    [c for c in oraculo()["mantel_haenszel"] if c["entrada"] and c["entrada"] != [[0, 0, 0, 0]]],
)
def test_mh_bate_com_o_oraculo(caso: Json) -> None:
    esperado = caso["saida"]["Ok"]
    resultado = mantel_haenszel(_estratos(caso["entrada"]))
    assert resultado.odds_ratio == aprox(esperado["odds_ratio_mh"])
    assert resultado.odds_ratio_ic == aprox(esperado["odds_ratio_mh_ic"])
    assert resultado.p_valor == aprox(esperado["p_valor_mh"])
    assert resultado.chi2_homogeneidade == aprox(esperado["chi2_homogeneidade"])
    assert resultado.graus_liberdade == esperado["graus_liberdade"]


@pytest.mark.referencia
def test_estrato_sem_discordantes_da_odds_ratio_infinita() -> None:
    """R: soma(ad/n) / soma(bc/n) com bc = 0 em todos é Inf; sem homogeneidade a testar.
    Divergência: na v0.1.16, só estratos vazios davam OR 1 com IC [1, 1]; aqui, SemObservacao."""
    resultado = mantel_haenszel([(5, 0, 2, 5), (3, 0, 1, 4)])
    assert resultado.odds_ratio == math.inf
    assert resultado.odds_ratio_ic == (0.0, math.inf)
    assert (resultado.graus_liberdade, resultado.p_valor_homogeneidade) == (0, 1.0)
    with pytest.raises(SemObservacao):
        mantel_haenszel([(0, 0, 0, 0)])


@pytest.mark.referencia
def test_estrato_vazio_e_ignorado_e_margem_zero_nao_conta_na_homogeneidade() -> None:
    """Igual ao caso de 2 estratos do R depois de remover os sem informação."""
    caso = referencias_r()["mantel_haenszel"][0]
    resultado = mantel_haenszel([*_estratos(caso["estratos"]), (0, 0, 0, 0), (0, 0, 3, 4)])
    assert resultado.odds_ratio == aprox(caso["odds_ratio"])
    assert resultado.graus_liberdade == 1


def test_sem_estrato_e_recusado() -> None:
    with pytest.raises(EntradaInvalida, match="ao menos 1"):
        mantel_haenszel([])


def test_odds_ratio_um_usa_o_valor_esperado_sem_associacao() -> None:
    """Com OR = 1, o a esperado de Breslow-Day é n1·m1/n: estratos iguais são homogêneos."""
    resultado = mantel_haenszel([(5, 5, 5, 5), (2, 4, 2, 4)])
    assert resultado.odds_ratio == pytest.approx(1.0)
    assert resultado.chi2_homogeneidade == pytest.approx(0.0, abs=1e-12)


contagem = st.integers(min_value=0, max_value=30)


@settings(max_examples=300, deadline=None)
@given(st.lists(st.tuples(contagem, contagem, contagem, contagem), min_size=1, max_size=5))
def test_nenhum_conjunto_de_estratos_trava(estratos: list[Estrato]) -> None:
    """Princípio IV: bordas (zeros, n = 1, OR infinito) dão resultado ou erro tipado."""
    try:
        resultado = mantel_haenszel(estratos)
    except SemObservacao:
        assert all(sum(e) == 0 for e in estratos)
        return
    assert resultado.chi2_homogeneidade >= 0
    assert 0.0 <= resultado.p_valor <= 1.0
    assert 0.0 <= resultado.p_valor_homogeneidade <= 1.0
    assert resultado.odds_ratio_ic.inferior <= resultado.odds_ratio_ic.superior


def test_estrato_de_um_so_paciente_nao_tem_variancia() -> None:
    """mantelhaen.test do R recusa estrato com n < 2; aqui ele não soma variância nem OR."""
    resultado = mantel_haenszel([(1, 0, 0, 0)])
    assert math.isnan(resultado.odds_ratio)
    assert (resultado.qui_quadrado, resultado.p_valor) == (0.0, 1.0)
