"""Calculadoras do StatCalc: a casca chega à estatística por aqui. Os valores de
referência estão nos testes de `estatistica`; aqui se confere que o caminho chega lá."""

import pytest

from gastroepi.estatistica import amostra, contingencia, diagnostico, tabela_2x2, tendencia
from gastroepi.estatistica.mantel_haenszel import mantel_haenszel
from gastroepi.servicos import calculadoras
from gastroepi.servicos.calculadoras import EntradaInvalida, SemObservacao


def test_cada_calculadora_devolve_o_mesmo_que_a_estatistica() -> None:
    estratos = [(10, 20, 5, 30), (8, 12, 6, 25)]

    assert calculadoras.calcular_tabela_2x2(10, 20, 5, 30) == tabela_2x2.tabela_2x2(10, 20, 5, 30)
    assert calculadoras.calcular_teste_diagnostico(
        40, 10, 5, 45
    ) == diagnostico.desempenho_diagnostico(40, 10, 5, 45)
    assert calculadoras.calcular_amostra_inquerito(0.3, 0.05, 0.95) == amostra.amostra_inquerito(
        0.3, 0.05, 0.95
    )
    assert calculadoras.calcular_amostra_comparativa(
        0.8, 0.95, 1.0, 0.2, 0.35
    ) == amostra.amostra_comparativa(0.8, 0.95, 1.0, 0.2, 0.35)
    assert calculadoras.calcular_tendencia([2, 5, 9], [20, 20, 20]) == tendencia.cochran_armitage(
        [2, 5, 9], [20, 20, 20]
    )
    assert calculadoras.calcular_mantel_haenszel(estratos) == mantel_haenszel(estratos)
    assert calculadoras.calcular_qui_quadrado_geral(
        [[10, 20], [30, 5]]
    ) == contingencia.qui_quadrado_rxc([[10, 20], [30, 5]])


def test_entrada_ruim_chega_tipada() -> None:
    with pytest.raises(SemObservacao):
        calculadoras.calcular_tabela_2x2(0, 0, 0, 0)
    with pytest.raises(EntradaInvalida):
        calculadoras.calcular_amostra_inquerito(1.5, 0.05, 0.95)
