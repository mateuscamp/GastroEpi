"""Modelo da tabela de pacientes, com ordenação e filtro para 10 mil linhas.

As células são montadas uma vez em `carregar`; a ordenação usa a chave guardada no
`UserRole` (data em ISO, número como número), não o texto mostrado. O filtro pergunta a
`servicos.pacientes.corresponde_ao_termo`: a regra de busca mora no serviço.
"""

from datetime import date

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)

from gastroepi.dominio.datas import formatar_data_br
from gastroepi.dominio.ficha import Ficha
from gastroepi.servicos import pacientes

COLUNAS = ("Prontuário", "Nome", "Sexo", "Nascimento", "Exames", "Último exame", "Pendente")
type Indice = QModelIndex | QPersistentModelIndex
type Celula = tuple[str, str | int]  # (texto mostrado, chave de ordenação)


def _data(valor: date | None) -> Celula:
    return (formatar_data_br(valor), "" if valor is None else valor.isoformat())


def celulas_da_ficha(ficha: Ficha) -> tuple[Celula, ...]:
    paciente = ficha.paciente
    ultimo = max((e.data_exame for e in ficha.exames), default=None)
    pendente = "histologia" if any(e.aguardando_histologia for e in ficha.exames) else ""
    return (
        (paciente.prontuario, paciente.prontuario.casefold()),
        (paciente.nome, paciente.nome.casefold()),
        (paciente.sexo.rotulo, paciente.sexo.rotulo),
        _data(paciente.data_nascimento),
        (str(len(ficha.exames)), len(ficha.exames)),
        _data(ultimo),
        (pendente, pendente),
    )


class ModeloDePacientes(QAbstractTableModel):
    """Passe o `pai`: sem ele, o Python pode recolher o modelo antes da tabela que o usa."""

    def __init__(self, pai: QObject | None = None) -> None:
        super().__init__(pai)
        self._ids: list[int] = []
        self._fichas: list[Ficha] = []
        self._celulas: list[tuple[Celula, ...]] = []

    def carregar(self, fichas: dict[int, Ficha]) -> None:
        self.beginResetModel()
        self._ids = list(fichas)
        self._fichas = list(fichas.values())
        self._celulas = [celulas_da_ficha(f) for f in self._fichas]
        self.endResetModel()

    def rowCount(self, pai: Indice = QModelIndex()) -> int:  # noqa: B008 (assinatura do Qt)
        return 0 if pai.isValid() else len(self._ids)

    def columnCount(self, pai: Indice = QModelIndex()) -> int:  # noqa: B008 (assinatura do Qt)
        return 0 if pai.isValid() else len(COLUNAS)

    def data(self, indice: Indice, papel: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not indice.isValid():
            return None
        texto, chave = self._celulas[indice.row()][indice.column()]
        if papel == Qt.ItemDataRole.DisplayRole:
            return texto
        return chave if papel == Qt.ItemDataRole.UserRole else None

    def headerData(
        self, secao: int, orientacao: Qt.Orientation, papel: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientacao == Qt.Orientation.Horizontal and papel == Qt.ItemDataRole.DisplayRole:
            return COLUNAS[secao]
        return None

    def paciente_id(self, linha: int) -> int:
        return self._ids[linha]

    def ficha(self, linha: int) -> Ficha:
        return self._fichas[linha]


class FiltroDePacientes(QSortFilterProxyModel):
    def __init__(self, modelo: ModeloDePacientes, pai: QObject | None = None) -> None:
        super().__init__(pai)
        self._modelo = modelo
        self._termo = ""
        self.setSourceModel(modelo)
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def definir_termo(self, termo: str) -> None:
        self.beginFilterChange()
        self._termo = termo
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, linha: int, pai: Indice) -> bool:
        return pacientes.corresponde_ao_termo(self._modelo.ficha(linha), self._termo)

    def paciente_id(self, linha_visivel: int) -> int:
        return self._modelo.paciente_id(self.mapToSource(self.index(linha_visivel, 0)).row())

    def ficha(self, linha_visivel: int) -> Ficha:
        return self._modelo.ficha(self.mapToSource(self.index(linha_visivel, 0)).row())
