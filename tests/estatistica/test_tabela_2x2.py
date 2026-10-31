import math

import pytest

from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from gastroepi.estatistica.tabela_2x2 import fisher_exato, tabela_2x2
from tests.estatistica.referencias import Json, aprox, oraculo, referencias_r


@pytest.mark.referencia
def test_fisher_do_cha_da_documentacao_do_r() -> None:
    """R, ?fisher.test, exemplo TeaTasting: matrix(c(3, 1, 1, 3), 2) → p-value = 0.4857."""
    assert fisher_exato(3, 1, 1, 3) == pytest.approx(0.4857, abs=1e-4)


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["fisher"], ids=str)
def test_fisher_bate_com_o_fisher_test_do_r(caso: Json) -> None:
    """R 4.5.1: fisher.test(matrix(c(a, c, b, d), 2))$p.value."""
    assert fisher_exato(*caso["entrada"]) == aprox(caso["p_valor"])


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["tabela_2x2"], ids=str)
def test_tabela_2x2_bate_com_epitools_e_chisq_test(caso: Json) -> None:
    """R 4.5.1: epitools::oddsratio.wald e riskratio.wald; chisq.test(correct = FALSE/TRUE)."""
    resultado = tabela_2x2(*caso["entrada"])
    assert resultado.odds_ratio == aprox(caso["odds_ratio"])
    assert resultado.odds_ratio_ic == aprox(caso["odds_ratio_ic"])
    assert resultado.risco_relativo == aprox(caso["risco_relativo"])
    assert resultado.risco_relativo_ic == aprox(caso["risco_relativo_ic"])
    assert resultado.chi2_pearson == aprox(caso["chi2_pearson"])
    assert resultado.p_valor_pearson == aprox(caso["p_valor_pearson"])
    assert resultado.chi2_yates == aprox(caso["chi2_yates"])
    assert resultado.p_valor_yates == aprox(caso["p_valor_yates"])
    assert resultado.p_valor_fisher == aprox(caso["p_valor_fisher"])


@pytest.mark.parametrize("caso", oraculo()["fisher_exact_2x2"], ids=str)
def test_fisher_bate_com_o_oraculo(caso: Json) -> None:
    assert fisher_exato(*caso["entrada"]) == pytest.approx(caso["saida"], rel=1e-9)


@pytest.mark.parametrize(
    "caso", [c for c in oraculo()["tabela_2x2"] if "Ok" in c["saida"]], ids=str
)
def test_tabela_2x2_bate_com_o_oraculo_fora_das_bordas(caso: Json) -> None:
    """Divergências documentadas: p < 1e-16 (a v0.1.16 dava 0 por 1 - cdf; vale o R, que
    dá ~1e-23) e 0/0, que agora é NaN (ver test_borda_zero_sobre_zero_e_indefinida)."""
    esperado, resultado = caso["saida"]["Ok"], tabela_2x2(*caso["entrada"])
    for campo in ("odds_ratio", "risco_relativo"):
        if not math.isnan(getattr(resultado, campo)):
            assert getattr(resultado, campo) == aprox(esperado[campo])
    for campo in ("odds_ratio_ic", "risco_relativo_ic", "chi2_pearson", "chi2_yates"):
        assert getattr(resultado, campo) == aprox(esperado[campo])
    for campo in ("p_valor_pearson", "p_valor_yates", "p_valor_fisher"):
        assert getattr(resultado, campo) == pytest.approx(esperado[campo], rel=1e-9, abs=1e-15)


@pytest.mark.referencia
def test_borda_zero_sobre_zero_e_indefinida() -> None:
    """R: (0 * 5) / (0 * 5) = NaN e chisq.test com margem zero dá NaN. Aqui o OR e o RR
    ficam NaN (a v0.1.16 dava 0, "proteção máxima"), e o teste sem informação fica χ² = 0,
    p = 1, como na v0.1.16."""
    resultado = tabela_2x2(0, 0, 5, 5)
    assert math.isnan(resultado.odds_ratio)
    assert math.isnan(resultado.risco_relativo)
    assert (resultado.chi2_pearson, resultado.p_valor_pearson) == (0.0, 1.0)
    assert resultado.odds_ratio_ic == (0.0, math.inf)


@pytest.mark.referencia
def test_celula_zero_da_odds_ratio_infinita_sem_travar() -> None:
    """R: (5 * 5) / (0 * 5) = Inf. O IC de Woolf não existe com célula zero: [0, ∞)."""
    resultado = tabela_2x2(5, 0, 5, 5)
    assert resultado.odds_ratio == math.inf
    assert resultado.odds_ratio_ic == (0.0, math.inf)
    assert resultado.risco_relativo == pytest.approx(2.0)


def test_tabela_vazia_e_recusada_com_erro_tipado() -> None:
    with pytest.raises(SemObservacao, match="vazia"):
        tabela_2x2(0, 0, 0, 0)
    with pytest.raises(EntradaInvalida, match="≥ 0"):
        tabela_2x2(-1, 2, 3, 4)
