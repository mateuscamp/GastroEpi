import pytest

from gastroepi.estatistica.contingencia import qui_quadrado_rxc
from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from tests.estatistica.referencias import Json, aprox, oraculo, referencias_r


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["qui_quadrado_rxc"], ids=str)
def test_rxc_bate_com_o_chisq_test_do_r(caso: Json) -> None:
    """R 4.5.1: chisq.test(m, correct = FALSE)."""
    resultado = qui_quadrado_rxc(caso["matriz"])
    assert resultado.qui_quadrado == aprox(caso["chi2"])
    assert resultado.graus_liberdade == caso["graus_liberdade"]
    assert resultado.p_valor == aprox(caso["p_valor"])


@pytest.mark.parametrize("caso", oraculo()["analisar_contingencia_geral"], ids=str)
def test_rxc_bate_com_o_oraculo(caso: Json) -> None:
    """Onde a v0.1.16 devolvia nada (null), aqui há erro tipado que a casca traduz."""
    matriz = caso["entrada"][0]
    if caso["saida"] is None:
        with pytest.raises(EntradaInvalida):
            qui_quadrado_rxc(matriz)
        return
    resultado = qui_quadrado_rxc(matriz)
    assert resultado.qui_quadrado == aprox(caso["saida"]["chi2"])
    assert resultado.p_valor == aprox(caso["saida"]["p_valor"])


@pytest.mark.parametrize("matriz", [[[1, 2]], [[1, 2], [3]], [[1], [2]], [[1, 0], [2, 0]]])
def test_forma_ou_margem_invalida_e_recusada(matriz: list[list[int]]) -> None:
    with pytest.raises(EntradaInvalida):
        qui_quadrado_rxc(matriz)


def test_tabela_vazia_e_sem_observacao() -> None:
    with pytest.raises(SemObservacao):
        qui_quadrado_rxc([[0, 0], [0, 0]])
