"""Tendência e qui-quadrado geral na mesma tabela de grupos."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos import calculadoras
from gastroepi.ui_qt.calc_tendencia import CalcTendencia
from gastroepi.ui_qt.textos import qui_quadrado
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar


def test_tendencia_crescente_e_qui_quadrado_geral(qtbot: QtBot, capturar: Capturar) -> None:
    tela = CalcTendencia()
    qtbot.addWidget(tela)
    tela.grupos.definir([(2, 20), (5, 20), (9, 20)])

    clicar(qtbot, tela.calcular)
    capturar(tela, "44-tendencia")

    tendencia = calculadoras.calcular_tendencia([2, 5, 9], [20, 20, 20])
    geral = calculadoras.calcular_qui_quadrado_geral([[2, 5, 9], [18, 15, 11]])
    texto = tela.resultado.texto()
    assert "cresce ao longo dos grupos" in texto
    assert qui_quadrado(tendencia.qui_quadrado, tendencia.p_valor) in texto
    assert qui_quadrado(geral.qui_quadrado, geral.p_valor) in texto


def test_grupos_zerados_mostram_o_erro(qtbot: QtBot) -> None:
    tela = CalcTendencia()
    qtbot.addWidget(tela)

    clicar(qtbot, tela.calcular)

    assert tela.resultado.erro.text()
