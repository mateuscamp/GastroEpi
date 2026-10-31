"""Tabela de itens de uma ficha com Adicionar, Editar e Remover: as lesões do exame e os
exames do paciente usam a mesma mecânica (`TabelaDeItens`)."""

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.lesao import Lesao
from gastroepi.ui_qt.dialogo_lesao import DialogoLesao


class TabelaDeItens[T](QWidget):
    """`abrir(item | None)` cria o diálogo; `extrair(diálogo)` lê o item guardado nele."""

    def __init__(
        self,
        colunas: Sequence[str],
        celulas: Callable[[T], Sequence[str]],
        abrir: Callable[[T | None], QDialog],
        extrair: Callable[[QDialog], T | None],
        pai: QWidget | None = None,
    ) -> None:
        super().__init__(pai)
        self._itens: list[T] = []
        self._celulas, self._abrir, self._extrair = celulas, abrir, extrair
        self.dialogo: QDialog | None = None
        self._linha_do_dialogo: int | None = None
        self.tabela = QTableWidget(0, len(colunas), self)
        self.tabela.setHorizontalHeaderLabels(list(colunas))
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.adicionar = QPushButton("Adicionar", self)
        self.editar = QPushButton("Editar", self)
        self.remover = QPushButton("Remover", self)
        self._montar()

    def _montar(self) -> None:
        botoes = QHBoxLayout()
        for botao in (self.adicionar, self.editar, self.remover):
            botoes.addWidget(botao)
        botoes.addStretch()
        disposicao = QVBoxLayout(self)
        disposicao.addLayout(botoes)
        disposicao.addWidget(self.tabela)
        self.adicionar.clicked.connect(self._adicionar)
        self.editar.clicked.connect(self._editar_selecionado)
        self.tabela.doubleClicked.connect(self._editar_selecionado)
        self.remover.clicked.connect(self._remover_selecionado)

    def itens(self) -> tuple[T, ...]:
        return tuple(self._itens)

    def definir(self, itens: Sequence[T]) -> None:
        self._itens = list(itens)
        self._redesenhar()

    def selecionado(self) -> int | None:
        linhas = self.tabela.selectionModel().selectedRows()
        return linhas[0].row() if linhas else None

    def _redesenhar(self) -> None:
        self.tabela.setRowCount(len(self._itens))
        for linha, item in enumerate(self._itens):
            for coluna, texto in enumerate(self._celulas(item)):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(texto))
        self.tabela.resizeColumnsToContents()

    def _editar_selecionado(self) -> None:
        linha = self.selecionado()
        if linha is not None:
            self._abrir_dialogo(linha)

    def _remover_selecionado(self) -> None:
        linha = self.selecionado()
        if linha is not None:
            del self._itens[linha]
            self._redesenhar()

    def _adicionar(self) -> None:
        self._abrir_dialogo(None)

    def _abrir_dialogo(self, linha: int | None) -> None:
        # Método e não lambda no connect: lambda com `self` derruba o PySide ao recolher.
        self._linha_do_dialogo = linha
        self.dialogo = self._abrir(None if linha is None else self._itens[linha])
        self.dialogo.accepted.connect(self._guardar)
        self.dialogo.open()

    def _guardar(self) -> None:
        assert self.dialogo is not None
        item, linha = self._extrair(self.dialogo), self._linha_do_dialogo
        if item is None:
            return
        if linha is None:
            self._itens.append(item)
        else:
            self._itens[linha] = item
        self._redesenhar()


def celulas_da_lesao(lesao: Lesao) -> tuple[str, ...]:
    return (
        lesao.segmento.rotulo,
        f"{lesao.tamanho_mm} mm",
        lesao.paris.rotulo,
        lesao.histologia.rotulo,
        lesao.displasia.rotulo,
    )


def _lesao_do(dialogo: QDialog) -> Lesao | None:
    return dialogo.lesao if isinstance(dialogo, DialogoLesao) else None


class TabelaDeLesoes(TabelaDeItens[Lesao]):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(
            ("Segmento", "Tamanho", "Paris", "Histologia", "Displasia"),
            celulas_da_lesao,
            lambda lesao: DialogoLesao(lesao, self),
            _lesao_do,
            pai,
        )

    def lesoes(self) -> tuple[Lesao, ...]:
        return self.itens()
