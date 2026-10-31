"""Tamanho de amostra: percentuais digitados vão como fração ao serviço."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos import calculadoras
from gastroepi.ui_qt.calc_amostra import CalcAmostra
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar


def test_inquerito_e_comparativo(qtbot: QtBot, capturar: Capturar) -> None:
    tela = CalcAmostra()
    qtbot.addWidget(tela)
    tela.inquerito.populacao.definir(5000)

    clicar(qtbot, tela.inquerito.calcular)
    clicar(qtbot, tela.comparativo.calcular)
    capturar(tela, "43-amostra")

    n = calculadoras.calcular_amostra_inquerito(0.5, 0.05, 0.95, 5000)
    comparativa = calculadoras.calcular_amostra_comparativa(0.8, 0.95, 1.0, 0.2, 0.35)
    assert f"{n} participantes" in tela.inquerito.resultado.texto()
    assert f"<b>{comparativa.total}</b>" in tela.comparativo.resultado.texto()


def test_entradas_fora_do_intervalo_mostram_o_erro(qtbot: QtBot) -> None:
    tela = CalcAmostra()
    qtbot.addWidget(tela)
    tela.inquerito.d.setValue(0)
    tela.comparativo.p1.setValue(20.0)

    clicar(qtbot, tela.inquerito.calcular)
    clicar(qtbot, tela.comparativo.calcular)

    assert "margem de erro" in tela.inquerito.resultado.erro.text()
    assert "iguais" in tela.comparativo.resultado.erro.text()
