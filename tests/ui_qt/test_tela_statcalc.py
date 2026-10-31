"""StatCalc: uma aba por calculadora; atualizar relê o que vem do banco."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.tela_statcalc import TelaStatCalc
from tests.ui_qt.conftest import Capturar


def test_abas_e_atualizar(qtbot: QtBot, sessao: Sessao, capturar: Capturar) -> None:
    tela = TelaStatCalc(sessao)
    qtbot.addWidget(tela)
    tela.atualizar()
    capturar(tela, "39-statcalc")

    nomes = [tela.abas.tabText(i) for i in range(tela.abas.count())]
    assert nomes == [
        "Qualidade", "Tabela 2x2", "Teste diagnóstico", "Tamanho de amostra",
        "Tendência", "Mantel-Haenszel", "Estratificação",
    ]  # fmt: skip
    assert tela.qualidade.tabela.rowCount() > 0
    assert tela.estratificacao.tabela.rowCount() > 0
