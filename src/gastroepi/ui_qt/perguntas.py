"""O que a casca pergunta ao usuário numa janela à parte: confirmar e escolher arquivo.

Fica atrás de um protocolo para os testes injetarem respostas (`PerguntasProgramadas`,
em tests/ui_qt): a caixa modal do Qt bloquearia o `qtbot`.
"""

from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


class Perguntas(Protocol):
    def confirmar(self, pai: QWidget, titulo: str, texto: str) -> bool: ...

    def arquivo_para_salvar(self, pai: QWidget, titulo: str, sugestao: Path) -> Path | None: ...

    def pasta(self, pai: QWidget, titulo: str) -> Path | None: ...


class PerguntasNaTela:
    """As caixas do Qt, em pt-BR e com "Não" como padrão nas confirmações."""

    def confirmar(self, pai: QWidget, titulo: str, texto: str) -> bool:
        caixa = QMessageBox(QMessageBox.Icon.Question, titulo, texto, parent=pai)
        sim = caixa.addButton("Sim", QMessageBox.ButtonRole.YesRole)
        caixa.setDefaultButton(caixa.addButton("Não", QMessageBox.ButtonRole.NoRole))
        caixa.exec()
        return caixa.clickedButton() is sim

    def arquivo_para_salvar(self, pai: QWidget, titulo: str, sugestao: Path) -> Path | None:
        escolhido, _ = QFileDialog.getSaveFileName(pai, titulo, str(sugestao), "CSV (*.csv)")
        return Path(escolhido) if escolhido else None

    def pasta(self, pai: QWidget, titulo: str) -> Path | None:
        escolhida = QFileDialog.getExistingDirectory(pai, titulo)
        return Path(escolhida) if escolhida else None
