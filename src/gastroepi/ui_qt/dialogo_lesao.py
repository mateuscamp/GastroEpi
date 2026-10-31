"""Diálogo de uma lesão (pólipo): localização, tamanho, Paris, histologia e displasia.

A histologia pode chegar depois: "Aguardando histologia" deixa o exame pendente até o
laudo (ADR-0004). O domínio recusa displasia incoerente com a histologia.
"""

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.lesao import Lesao
from gastroepi.dominio.listas import Displasia, Histologia, Paris, Segmento
from gastroepi.ui_qt.aparencia import Aviso
from gastroepi.ui_qt.campos_da_tela import ComboDeLista
from gastroepi.ui_qt.textos import mensagem_de_erro


class DialogoLesao(QDialog):
    def __init__(self, lesao: Lesao | None = None, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.setWindowTitle("Lesão")
        self.lesao: Lesao | None = None
        self.segmento = ComboDeLista(Segmento, self)
        self.tamanho = QSpinBox(self)
        self.tamanho.setRange(0, 300)
        self.tamanho.setSuffix(" mm")
        self.paris = ComboDeLista(Paris, self)
        self.histologia = ComboDeLista(Histologia, self)
        self.histologia_outra = QLineEdit(self)
        self.displasia = ComboDeLista(Displasia, self)
        self.laudo = QPlainTextEdit(self)
        self.laudo.setPlaceholderText("Texto do laudo, só para consulta (não entra na estatística)")
        self.laudo.setMaximumHeight(80)
        self.erro = Aviso(self)
        self.botoes = QDialogButtonBox(self)
        self.botoes.addButton("Guardar lesão", QDialogButtonBox.ButtonRole.AcceptRole)
        self.botoes.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self._montar()
        self.histologia.currentIndexChanged.connect(self._mostrar_outra)
        self.botoes.accepted.connect(self._guardar)
        self.botoes.rejected.connect(self.reject)
        if lesao is not None:
            self._preencher(lesao)
        self._mostrar_outra()

    def _montar(self) -> None:
        formulario = QFormLayout()
        formulario.addRow("Segmento", self.segmento)
        formulario.addRow("Tamanho", self.tamanho)
        formulario.addRow("Morfologia (Paris)", self.paris)
        formulario.addRow("Histologia", self.histologia)
        formulario.addRow("Qual histologia", self.histologia_outra)
        formulario.addRow("Displasia", self.displasia)
        formulario.addRow("Laudo", self.laudo)
        disposicao = QVBoxLayout(self)
        disposicao.addLayout(formulario)
        disposicao.addWidget(self.erro)
        disposicao.addWidget(self.botoes)

    def _mostrar_outra(self) -> None:
        self.histologia_outra.setEnabled(self.histologia.valor() is Histologia.OUTRO)
        if not self.histologia_outra.isEnabled():
            self.histologia_outra.clear()

    def _preencher(self, lesao: Lesao) -> None:
        self.segmento.definir(lesao.segmento)
        self.tamanho.setValue(lesao.tamanho_mm)
        self.paris.definir(lesao.paris)
        self.histologia.definir(lesao.histologia)
        self.histologia_outra.setText(lesao.histologia_outra or "")
        self.displasia.definir(lesao.displasia)
        self.laudo.setPlainText(lesao.laudo_texto or "")

    def campos(self) -> dict[str, object]:
        return {
            "segmento": self.segmento.valor(),
            "tamanho_mm": self.tamanho.value(),
            "paris": self.paris.valor(),
            "histologia": self.histologia.valor(),
            "displasia": self.displasia.valor(),
            "histologia_outra": self.histologia_outra.text(),
            "laudo_texto": self.laudo.toPlainText(),
        }

    def _guardar(self) -> None:
        try:
            self.lesao = Lesao.model_validate(self.campos())
        except (ValidationError, ValueError) as erro:
            self.erro.erro(mensagem_de_erro(erro))
            return
        self.accept()
