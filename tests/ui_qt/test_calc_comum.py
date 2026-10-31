"""Peças das calculadoras: tabela de contagens e quadro de resultado."""

from pytestqt.qtbot import QtBot

from gastroepi.ui_qt.calc_comum import Resultado, TabelaDeContagens, caixa_de_contagem
from tests.ui_qt.formularios import clicar


def test_tabela_de_contagens_com_nome(qtbot: QtBot) -> None:
    tabela = TabelaDeContagens(("Nome", "Casos", "Total"), 2)
    qtbot.addWidget(tabela)

    tabela.definir([(1, 10), (3, 12), (5, 9)])
    clicar(qtbot, tabela.adicionar)
    clicar(qtbot, tabela.remover)

    assert tabela.contagens() == [(1, 10), (3, 12), (5, 9)]
    assert tabela.nomes() == ["Grupo 1", "Grupo 2", "Grupo 3"]


def test_tabela_sem_coluna_de_nome(qtbot: QtBot) -> None:
    tabela = TabelaDeContagens(("A", "B"), 1)
    qtbot.addWidget(tabela)

    assert tabela.contagens() == [(0, 0)]
    assert tabela.nomes() == [""]


def test_resultado_escapa_o_texto_e_mostra_o_erro(qtbot: QtBot) -> None:
    resultado = Resultado()
    qtbot.addWidget(resultado)

    resultado.mostrar([("a < b", "1")], "nota")
    assert "a &lt; b" in resultado.texto() and "nota" in resultado.texto()
    resultado.falhar("deu errado")
    assert resultado.texto() == "" and resultado.erro.text() == "deu errado"
    assert caixa_de_contagem(5).value() == 5
