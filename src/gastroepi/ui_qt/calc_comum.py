"""Peças comuns das calculadoras do StatCalc: caixas de contagem, tabela de linhas
editáveis e o quadro de resultado."""

from collections.abc import Sequence
from html import escape

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gastroepi.ui_qt.aparencia import Aviso, com_papel

CONTAGEM_MAXIMA = 10_000_000


def caixa_de_contagem(valor: int = 0, pai: QWidget | None = None) -> QSpinBox:
    caixa = QSpinBox(pai)
    caixa.setRange(0, CONTAGEM_MAXIMA)
    caixa.setValue(valor)
    return caixa


def botao_calcular(pai: QWidget) -> QPushButton:
    return com_papel(QPushButton("Calcular", pai), "principal")


class Resultado(QWidget):
    """Quadro de resultado: pares (o quê, quanto) numa tabela simples, ou o erro."""

    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.quadro = QLabel(self)
        self.quadro.setWordWrap(True)
        self.erro = Aviso(self)
        disposicao = QVBoxLayout(self)
        disposicao.setContentsMargins(0, 0, 0, 0)
        disposicao.addWidget(self.quadro)
        disposicao.addWidget(self.erro)

    def mostrar(self, linhas: Sequence[tuple[str, str]], nota: str = "") -> None:
        self.erro.limpar()
        celulas = "".join(
            f"<tr><td style='padding:3px 12px 3px 0'>{escape(o)}</td>"
            f"<td style='padding:3px 0'><b>{escape(q)}</b></td></tr>"
            for o, q in linhas
        )
        rodape = f"<p style='color:#4b5563'>{escape(nota)}</p>" if nota else ""
        self.quadro.setText(f"<table>{celulas}</table>{rodape}")

    def texto(self) -> str:
        return self.quadro.text()

    def falhar(self, mensagem: str) -> None:
        self.quadro.clear()
        self.erro.erro(mensagem)


class TabelaDeContagens(QWidget):
    """Linhas com contagens editáveis (estratos, grupos), com Adicionar e Remover linha."""

    def __init__(
        self, colunas: Sequence[str], linhas_iniciais: int, pai: QWidget | None = None
    ) -> None:
        super().__init__(pai)
        self._colunas = tuple(colunas)
        self.tabela = QTableWidget(0, len(colunas), self)
        self.tabela.setHorizontalHeaderLabels(list(colunas))
        self.adicionar = QPushButton("Adicionar linha", self)
        self.remover = QPushButton("Remover linha", self)
        botoes = QHBoxLayout()
        botoes.addWidget(self.adicionar)
        botoes.addWidget(self.remover)
        botoes.addStretch()
        disposicao = QVBoxLayout(self)
        disposicao.setContentsMargins(0, 0, 0, 0)
        disposicao.addWidget(self.tabela)
        disposicao.addLayout(botoes)
        self.adicionar.clicked.connect(self.acrescentar)
        self.remover.clicked.connect(self._remover_ultima)
        for _ in range(linhas_iniciais):
            self.acrescentar()

    def _remover_ultima(self) -> None:
        self.tabela.removeRow(self.tabela.rowCount() - 1)

    def acrescentar(self) -> None:
        linha = self.tabela.rowCount()
        self.tabela.insertRow(linha)
        for coluna, nome in enumerate(self._colunas):
            if nome == "Nome":
                self.tabela.setItem(linha, coluna, QTableWidgetItem(f"Grupo {linha + 1}"))
            else:
                self.tabela.setCellWidget(linha, coluna, caixa_de_contagem())

    def definir(self, linhas: Sequence[Sequence[int]]) -> None:
        """Preenche as colunas de contagem, na ordem, sem a coluna Nome."""
        self.tabela.setRowCount(0)
        for valores in linhas:
            self.acrescentar()
            caixas = self.caixas(self.tabela.rowCount() - 1)
            for caixa, valor in zip(caixas, valores, strict=True):
                caixa.setValue(valor)

    def caixas(self, linha: int) -> list[QSpinBox]:
        celulas = (self.tabela.cellWidget(linha, c) for c in range(self.tabela.columnCount()))
        return [c for c in celulas if isinstance(c, QSpinBox)]

    def contagens(self) -> list[tuple[int, ...]]:
        return [
            tuple(c.value() for c in self.caixas(linha)) for linha in range(self.tabela.rowCount())
        ]

    def nomes(self) -> list[str]:
        itens = (self.tabela.item(linha, 0) for linha in range(self.tabela.rowCount()))
        return [item.text() if item is not None else "" for item in itens]
