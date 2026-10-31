"""Perguntas nas caixas do Qt: o teste responde a caixa modal como o usuário faria."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from gastroepi.ui_qt.perguntas import PerguntasNaTela


def _responder(acao: Callable[[QWidget], None]) -> None:
    def quando_abrir() -> None:
        caixa = QApplication.activeModalWidget()
        if caixa is None:
            QTimer.singleShot(10, quando_abrir)
            return
        acao(caixa)

    QTimer.singleShot(10, quando_abrir)


def _clicar_em(texto: str) -> Callable[[QWidget], None]:
    def clicar(caixa: QWidget) -> None:
        assert isinstance(caixa, QMessageBox)
        next(b for b in caixa.buttons() if b.text() == texto).click()

    return clicar


def _cancelar(caixa: QWidget) -> None:
    assert isinstance(caixa, QDialog)
    caixa.reject()


def test_confirmar_devolve_o_botao_clicado(qtbot: QtBot) -> None:
    pai = QWidget()
    qtbot.addWidget(pai)

    _responder(_clicar_em("Sim"))
    assert PerguntasNaTela().confirmar(pai, "Excluir", "Excluir mesmo?")
    _responder(_clicar_em("Não"))
    assert not PerguntasNaTela().confirmar(pai, "Excluir", "Excluir mesmo?")


def test_cancelar_a_escolha_de_arquivo_ou_pasta_devolve_none(qtbot: QtBot, tmp_path: Path) -> None:
    pai = QWidget()
    qtbot.addWidget(pai)

    _responder(_cancelar)
    assert PerguntasNaTela().arquivo_para_salvar(pai, "Salvar", tmp_path / "x.csv") is None
    _responder(_cancelar)
    assert PerguntasNaTela().pasta(pai, "Pasta") is None
