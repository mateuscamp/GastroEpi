"""Tabela de lesões: adicionar, editar e remover pelo diálogo."""

from pytestqt.qtbot import QtBot

from gastroepi.dominio.listas import Histologia
from gastroepi.ui_qt.dialogo_lesao import DialogoLesao
from gastroepi.ui_qt.tabela_de_lesoes import TabelaDeLesoes
from tests.ui_qt.formularios import celula, clicar, preencher_lesao


def _guardar(qtbot: QtBot, tabela: TabelaDeLesoes, histologia: Histologia) -> None:
    dialogo = tabela.dialogo
    assert isinstance(dialogo, DialogoLesao)
    preencher_lesao(qtbot, dialogo, histologia)
    dialogo.botoes.accepted.emit()


def test_adicionar_editar_e_remover(qtbot: QtBot) -> None:
    tabela = TabelaDeLesoes()
    qtbot.addWidget(tabela)

    clicar(qtbot, tabela.adicionar)
    _guardar(qtbot, tabela, Histologia.TUBULAR)
    clicar(qtbot, tabela.adicionar)
    _guardar(qtbot, tabela, Histologia.VILOSO)
    assert [x.histologia for x in tabela.lesoes()] == [Histologia.TUBULAR, Histologia.VILOSO]
    assert celula(tabela.tabela, 1, 3) == "Adenoma viloso"

    tabela.tabela.selectRow(0)
    clicar(qtbot, tabela.editar)
    _guardar(qtbot, tabela, Histologia.TUBULOVILOSO)
    tabela.tabela.selectRow(1)
    clicar(qtbot, tabela.remover)

    assert [x.histologia for x in tabela.lesoes()] == [Histologia.TUBULOVILOSO]


def test_sem_selecao_editar_e_remover_nao_fazem_nada(qtbot: QtBot) -> None:
    tabela = TabelaDeLesoes()
    qtbot.addWidget(tabela)

    clicar(qtbot, tabela.editar)
    clicar(qtbot, tabela.remover)

    assert tabela.dialogo is None and tabela.lesoes() == ()


def test_cancelar_o_dialogo_nao_acrescenta(qtbot: QtBot) -> None:
    tabela = TabelaDeLesoes()
    qtbot.addWidget(tabela)

    clicar(qtbot, tabela.adicionar)
    assert tabela.dialogo is not None
    tabela.dialogo.accept()  # aceito sem lesão guardada (não acontece pela tela)

    assert tabela.lesoes() == ()
