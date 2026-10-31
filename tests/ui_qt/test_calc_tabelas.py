"""Tabela 2x2 e teste diagnóstico: os números da estatística chegam formatados."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos import calculadoras
from gastroepi.ui_qt.calc_tabelas import (
    CalcDiagnostico,
    CalcTabela2x2,
    linhas_da_tabela_2x2,
    linhas_do_diagnostico,
)
from gastroepi.ui_qt.textos import com_ic
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar


def test_tabela_2x2(qtbot: QtBot, capturar: Capturar) -> None:
    tela = CalcTabela2x2()
    qtbot.addWidget(tela)
    tela.grade.definir(10, 20, 5, 30)

    clicar(qtbot, tela.calcular)
    capturar(tela, "41-tabela-2x2")

    esperado = calculadoras.calcular_tabela_2x2(10, 20, 5, 30)
    assert com_ic(esperado.odds_ratio, esperado.odds_ratio_ic) in tela.resultado.texto()
    assert len(linhas_da_tabela_2x2(esperado)) == 6


def test_tabela_2x2_vazia_mostra_o_erro(qtbot: QtBot) -> None:
    tela = CalcTabela2x2()
    qtbot.addWidget(tela)

    clicar(qtbot, tela.calcular)

    assert "vazia" in tela.resultado.erro.text()


def test_diagnostico_le_a_grade_na_ordem_vp_fp_fn_vn(qtbot: QtBot, capturar: Capturar) -> None:
    tela = CalcDiagnostico()
    qtbot.addWidget(tela)
    tela.grade.definir(40, 10, 5, 45)

    clicar(qtbot, tela.calcular)
    capturar(tela, "42-diagnostico")

    esperado = calculadoras.calcular_teste_diagnostico(40, 10, 5, 45)
    assert tela.grade.valores() == (40, 10, 5, 45)
    assert "40 de 45 = 88,9%" in tela.resultado.texto()  # sensibilidade = VP/(VP+FN)
    assert len(linhas_do_diagnostico(esperado)) == 6
    tela.grade.definir(0, 0, 0, 0)
    clicar(qtbot, tela.calcular)
    assert tela.resultado.erro.text()
