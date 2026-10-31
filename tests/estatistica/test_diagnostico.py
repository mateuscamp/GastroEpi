import math

import pytest

from gastroepi.estatistica.diagnostico import desempenho_diagnostico
from gastroepi.estatistica.entrada import SemObservacao
from tests.estatistica.referencias import Json, aprox, oraculo, referencias_r


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["diagnostico"], ids=str)
def test_diagnostico_bate_com_o_r(caso: Json) -> None:
    """R 4.5.1: prop.test(correct = FALSE) para as proporções; LR pela fórmula de Simel
    (J Clin Epidemiol 1991;44:763-770) em ferramentas/referencias_r/gerar.R."""
    vp, fp, fn, vn = caso["entrada"]
    resultado = desempenho_diagnostico(vp, fp, fn, vn, caso["alfa"])
    assert resultado.sensibilidade.ic == aprox(caso["sensibilidade_ic"])
    assert resultado.especificidade.ic == aprox(caso["especificidade_ic"])
    assert resultado.vpp.ic == aprox(caso["vpp_ic"])
    assert resultado.vpn.ic == aprox(caso["vpn_ic"])
    assert resultado.lr_positivo == aprox(caso["lr_positivo"])
    assert resultado.lr_positivo_ic == aprox(caso["lr_positivo_ic"])
    assert resultado.lr_negativo == aprox(caso["lr_negativo"])
    assert resultado.lr_negativo_ic == aprox(caso["lr_negativo_ic"])


@pytest.mark.parametrize(
    "caso", [c for c in oraculo()["analise_teste_diagnostico"] if "Ok" in c["saida"]], ids=str
)
def test_diagnostico_bate_com_o_oraculo(caso: Json) -> None:
    """Divergência: 0/0 era 0 na v0.1.16 e aqui é NaN (sensibilidade 0 e especificidade 1
    não acontecem juntas nesta grade, então o teste só pula os NaN)."""
    esperado = caso["saida"]["Ok"]
    vp, fp, fn, vn, alfa = caso["entrada"]
    resultado = desempenho_diagnostico(vp, fp, fn, vn, alfa)
    for nome in ("sensibilidade", "especificidade", "vpp", "vpn"):
        medida = getattr(resultado, nome)
        assert medida.estimativa == aprox(esperado[nome])
        assert medida.ic == aprox(esperado[f"{nome}_ic"])
    for nome in ("lr_positivo", "lr_negativo"):
        if not math.isnan(getattr(resultado, nome)):
            assert getattr(resultado, nome) == aprox(esperado[nome])
        assert getattr(resultado, f"{nome}_ic") == aprox(esperado[f"{nome}_ic"])


@pytest.mark.referencia
def test_teste_perfeito_da_razao_infinita_sem_travar() -> None:
    """R: 1 / (1 - 1) = Inf e (1 - 1) / 1 = 0. Sem FP nem FN não há IC: [0, ∞)."""
    resultado = desempenho_diagnostico(10, 0, 0, 10)
    assert resultado.lr_positivo == math.inf
    assert resultado.lr_negativo == 0.0
    assert resultado.lr_positivo_ic == resultado.lr_negativo_ic == (0.0, math.inf)


@pytest.mark.referencia
def test_sem_doentes_a_sensibilidade_nao_existe() -> None:
    """Sem doentes, sens = 0/0 (R: NaN): estimativa None, IC [0, 1] e LR indefinidas."""
    resultado = desempenho_diagnostico(0, 4, 0, 6)
    assert resultado.sensibilidade.estimativa is None
    assert resultado.sensibilidade.ic == (0.0, 1.0)
    assert math.isnan(resultado.lr_positivo)


def test_tabela_vazia_e_recusada() -> None:
    with pytest.raises(SemObservacao):
        desempenho_diagnostico(0, 0, 0, 0)
