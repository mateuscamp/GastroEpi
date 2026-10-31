import math

import pytest

from gastroepi.estatistica.entrada import EntradaInvalida
from gastroepi.estatistica.proporcoes import (
    Intervalo,
    intervalo_wilson,
    proporcao,
    quantil_normal,
    razao,
)
from tests.estatistica.referencias import aprox, oraculo, referencias_r


@pytest.mark.referencia
def test_wilson_de_zero_em_dez_e_o_do_r() -> None:
    """R 4.x: prop.test(0, 10, correct = FALSE)$conf.int → 0.0000000 0.2775328."""
    assert intervalo_wilson(0, 10) == pytest.approx((0.0, 0.2775328), abs=1e-7)


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["wilson"], ids=str)
def test_wilson_bate_com_o_prop_test_do_r(caso: dict[str, float]) -> None:
    """R 4.5.1: prop.test(x, n, conf.level = 1 - alfa, correct = FALSE)$conf.int."""
    ic = intervalo_wilson(int(caso["casos"]), int(caso["total"]), caso["alfa"])
    assert ic == aprox(caso["ic"])


@pytest.mark.parametrize("caso", oraculo()["wilson_ci"], ids=str)
def test_wilson_bate_com_o_oraculo_salvo_sem_observacao(caso: dict[str, list[float]]) -> None:
    casos, total, alfa = caso["entrada"]
    esperado = caso["saida"] if total else [0.0, 1.0]  # divergência: ver o teste abaixo
    assert intervalo_wilson(int(casos), int(total), alfa) == aprox(esperado)


@pytest.mark.referencia
def test_wilson_sem_observacao_e_o_limite_zero_um() -> None:
    """Wilson (1927): com n → 0 o centro tende a 1/2 e a margem a 1/2, então o IC tende a
    [0, 1]. Divergência intencional: a v0.1.16 devolvia [0, 0], um IC que parece certeza."""
    assert intervalo_wilson(0, 0) == Intervalo(0.0, 1.0)
    assert intervalo_wilson(0, 1, 0.05) == aprox(referencias_r()["wilson"][7]["ic"])


@pytest.mark.parametrize(
    ("casos", "total", "alfa"), [(-1, 10, 0.05), (11, 10, 0.05), (1, 10, 0.0), (1, 10, 1.0)]
)
def test_wilson_recusa_entrada_fora_do_dominio(casos: int, total: int, alfa: float) -> None:
    with pytest.raises(EntradaInvalida):
        intervalo_wilson(casos, total, alfa)


@pytest.mark.referencia
def test_proporcao_leva_a_estimativa_e_o_ic_de_wilson_do_r() -> None:
    """R: prop.test(37, 120, correct = FALSE); sem total, a estimativa não existe."""
    caso = referencias_r()["wilson"][4]
    resultado = proporcao(37, 120)
    assert resultado.estimativa == pytest.approx(37 / 120)
    assert resultado.ic == aprox(caso["ic"])
    assert proporcao(0, 0).estimativa is None


@pytest.mark.referencia
def test_quantil_normal_e_o_qnorm_do_r() -> None:
    """R: qnorm(0.975) = 1.959963984540054; qnorm(0.995) = 2.575829303548901."""
    assert quantil_normal(0.05) == pytest.approx(1.959963984540054, rel=1e-12)
    assert quantil_normal(0.01) == pytest.approx(2.575829303548901, rel=1e-12)


@pytest.mark.referencia
def test_razao_segue_a_aritmetica_do_r_nas_bordas() -> None:
    """R (IEEE 754): 1/0 = Inf; 0/0 = NaN; NaN/1 = NaN."""
    assert razao(3, 4) == 0.75
    assert razao(1, 0) == math.inf
    assert math.isnan(razao(0, 0))
    assert math.isnan(razao(math.nan, 1))
