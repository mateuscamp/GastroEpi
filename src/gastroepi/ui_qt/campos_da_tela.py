"""Campos de formulário reaproveitados: lista fechada, número opcional e lista de marcar.

Nenhum deles valida: o valor vai como está para o domínio, que recusa e explica.
Lista fechada começa sem escolha ("Escolha…") para nenhum valor entrar sem querer.
"""

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.listas import ListaFechada


def rotulo_do_item(item: Enum) -> str:
    return item.rotulo if isinstance(item, ListaFechada) else str(item.value)


class ComboDeLista[E: Enum](QComboBox):
    """Combo de uma lista fechada do domínio: mostra o rótulo e guarda o item."""

    def __init__(self, lista: type[E], pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self._itens: list[E] = list(lista)
        for item in self._itens:
            self.addItem(rotulo_do_item(item))
        self.setPlaceholderText("Escolha…")
        self.setCurrentIndex(-1)

    def valor(self) -> E | None:
        indice = self.currentIndex()
        return None if indice < 0 else self._itens[indice]

    def definir(self, valor: E | None) -> None:
        self.setCurrentIndex(-1 if valor is None else self._itens.index(valor))


class SimOuNao(QComboBox):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.addItems(["Sim", "Não"])
        self.setPlaceholderText("Escolha…")
        self.setCurrentIndex(-1)

    def valor(self) -> bool | None:
        indice = self.currentIndex()
        return None if indice < 0 else indice == 0

    def definir(self, valor: bool | None) -> None:
        self.setCurrentIndex(-1 if valor is None else (0 if valor else 1))


class InteiroOpcional(QSpinBox):
    """O mínimo da caixa mostra "não sei" e vale `None`."""

    def __init__(self, maximo: int, texto_vazio: str = "não sei", pai: QWidget | None = None):
        super().__init__(pai)
        self.setRange(-1, maximo)
        self.setSpecialValueText(texto_vazio)
        self.setValue(-1)

    def valor(self) -> int | None:
        return None if self.value() < 0 else self.value()

    def definir(self, valor: int | None) -> None:
        self.setValue(-1 if valor is None else valor)


class DecimalOpcional(QDoubleSpinBox):
    """Zero mostra "não registrado" e vale `None` (o tempo de retirada pode faltar)."""

    def __init__(self, maximo: float, sufixo: str, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.setRange(0.0, maximo)
        self.setDecimals(1)
        self.setSingleStep(0.5)
        self.setSuffix(sufixo)
        self.setSpecialValueText("não registrado")

    def valor(self) -> float | None:
        return None if self.value() == 0 else self.value()

    def definir(self, valor: float | None) -> None:
        self.setValue(0.0 if valor is None else valor)


class ListaDeMarcar(QWidget):
    """Itens de catálogo para marcar; um item novo digitado entra marcado e vai para o
    catálogo quando a ficha for salva (o repositório o cria e audita)."""

    def __init__(self, dica_do_novo: str, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.lista = QListWidget(self)
        self.novo = QLineEdit(self)
        self.novo.setPlaceholderText(dica_do_novo)
        self.incluir = QPushButton("Incluir", self)
        linha = QHBoxLayout()
        linha.addWidget(self.novo)
        linha.addWidget(self.incluir)
        disposicao = QVBoxLayout(self)
        disposicao.setContentsMargins(0, 0, 0, 0)
        disposicao.addWidget(self.lista)
        disposicao.addLayout(linha)
        self.incluir.clicked.connect(self._incluir_novo)
        self.novo.returnPressed.connect(self._incluir_novo)

    def definir(self, catalogo: tuple[str, ...], marcados: tuple[str, ...]) -> None:
        self.lista.clear()
        dobrados = {nome.casefold() for nome in marcados}
        extras = [m for m in marcados if m.casefold() not in {c.casefold() for c in catalogo}]
        for nome in (*catalogo, *extras):
            self._acrescentar(nome, nome.casefold() in dobrados)

    def _acrescentar(self, nome: str, marcado: bool) -> None:
        item = QListWidgetItem(nome, self.lista)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked)

    def _incluir_novo(self) -> None:
        nome = self.novo.text()
        self.novo.clear()
        if nome.strip():
            self._acrescentar(nome, True)

    def marcados(self) -> tuple[str, ...]:
        itens = (self.lista.item(i) for i in range(self.lista.count()))
        return tuple(i.text() for i in itens if i.checkState() == Qt.CheckState.Checked)

    def marcar(self, nome: str) -> None:
        for item in self.lista.findItems(nome, Qt.MatchFlag.MatchExactly):
            item.setCheckState(Qt.CheckState.Checked)
