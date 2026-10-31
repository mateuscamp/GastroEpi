"""Mantel-Haenszel: estratos digitados, OR combinado e homogeneidade."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos import calculadoras
from gastroepi.ui_qt.calc_mantel_haenszel import CalcMantelHaenszel
from gastroepi.ui_qt.textos import com_ic
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar


def test_or_combinado(qtbot: QtBot, capturar: Capturar) -> None:
    tela = CalcMantelHaenszel()
    qtbot.addWidget(tela)
    tela.estratos.definir([(10, 20, 5, 30), (8, 12, 6, 25)])

    clicar(qtbot, tela.calcular)
    capturar(tela, "45-mantel-haenszel")

    r = calculadoras.calcular_mantel_haenszel([(10, 20, 5, 30), (8, 12, 6, 25)])
    assert com_ic(r.odds_ratio, r.odds_ratio_ic) in tela.resultado.texto()
    assert "Estratos homogêneos?" in tela.resultado.texto()


def test_estratos_vazios_mostram_o_erro(qtbot: QtBot) -> None:
    tela = CalcMantelHaenszel()
    qtbot.addWidget(tela)

    clicar(qtbot, tela.calcular)

    assert "vazios" in tela.resultado.erro.text()
