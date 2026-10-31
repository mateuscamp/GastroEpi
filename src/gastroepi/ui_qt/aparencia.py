"""Aparência da casca: tema claro, letra grande e botões que dizem o que fazem.

O usuário é leigo e não tem suporte (ADR-0002), então a tela evita ícone sem texto e
cor como único sinal: os avisos têm sempre uma frase.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QWidget

FOLHA_DE_ESTILO = """
QWidget { font-size: 11pt; color: #1f2937; }
QMainWindow, QDialog, #fundo { background: #f5f6f8; }
QLineEdit, QPlainTextEdit {
    background: white; border: 1px solid #c7ccd4; border-radius: 4px; padding: 4px 6px;
}
QLineEdit:focus, QPlainTextEdit:focus { border-color: #2563eb; }
QPushButton {
    background: white; border: 1px solid #c7ccd4; border-radius: 4px; padding: 6px 14px;
}
QPushButton:hover { background: #eef2ff; }
QPushButton:disabled { color: #9ca3af; background: #f3f4f6; }
QPushButton[papel="principal"] { background: #2563eb; color: white; border-color: #1d4ed8; }
QPushButton[papel="principal"]:disabled { background: #93c5fd; border-color: #93c5fd; }
QPushButton[papel="perigo"] { color: #b91c1c; border-color: #fca5a5; }
QPushButton[papel="perigo"]:disabled { color: #9ca3af; border-color: #e5e7eb; }
QLabel[papel="titulo"] { font-size: 17pt; font-weight: 600; }
QLabel[papel="subtitulo"] { font-size: 12pt; font-weight: 600; }
QLabel[papel="explicacao"] { color: #4b5563; }
QLabel[papel="erro"] { color: #991b1b; background: #fee2e2; border-radius: 4px; padding: 6px; }
QLabel[papel="sucesso"] { color: #065f46; background: #d1fae5; border-radius: 4px; padding: 6px; }
QLabel[papel="alerta"] { color: #92400e; background: #fef3c7; border-radius: 4px; padding: 6px; }
QLabel[papel="bloco"] {
    font-family: monospace; font-size: 15pt; font-weight: 600; letter-spacing: 2px;
    background: white; border: 1px solid #c7ccd4; border-radius: 4px; padding: 6px 10px;
}
QListWidget#navegacao { background: #1f2937; color: #f9fafb; border: none; padding-top: 8px; }
QListWidget#navegacao::item { padding: 10px 16px; color: #f9fafb; }
QListWidget#navegacao::item:selected { background: #2563eb; }
QTableView { background: white; gridline-color: #e5e7eb; selection-background-color: #bfdbfe;
             selection-color: #111827; }
QHeaderView::section { background: #eef0f3; padding: 4px; border: none;
                       border-bottom: 1px solid #c7ccd4; font-weight: 600; }
QTabWidget::pane { border: 1px solid #c7ccd4; background: white; }
QGroupBox { font-weight: 600; border: 1px solid #d1d5db; border-radius: 4px; margin-top: 12px;
            padding-top: 8px; background: white; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
"""


def aplicar_aparencia(app: QApplication) -> None:
    """Fusion igual no Windows e no Linux; caixas de número e listas ficam no desenho do
    Fusion, porque a folha de estilo neles apaga as setas."""
    app.setStyle("Fusion")
    fonte = QFont(app.font())
    fonte.setPointSize(11)
    app.setFont(fonte)
    app.setStyleSheet(FOLHA_DE_ESTILO)


def com_papel[W: QWidget](widget: W, papel: str) -> W:
    """O papel escolhe o estilo da folha (`QLabel[papel="erro"]`)."""
    widget.setProperty("papel", papel)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def rotulo(texto: str, papel: str = "", pai: QWidget | None = None) -> QLabel:
    etiqueta = QLabel(texto, pai)
    etiqueta.setWordWrap(True)
    return com_papel(etiqueta, papel) if papel else etiqueta


class Aviso(QLabel):
    """Faixa de mensagem da tela: some quando vazia, e o papel diz o tipo."""

    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.setWordWrap(True)
        self.hide()

    def mostrar(self, texto: str, papel: str) -> None:
        com_papel(self, papel)
        self.setText(texto)
        self.show()

    def erro(self, texto: str) -> None:
        self.mostrar(texto, "erro")

    def sucesso(self, texto: str) -> None:
        self.mostrar(texto, "sucesso")

    def alerta(self, texto: str) -> None:
        self.mostrar(texto, "alerta")

    def limpar(self) -> None:
        self.setText("")
        self.hide()
