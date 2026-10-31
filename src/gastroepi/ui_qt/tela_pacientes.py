"""Tela de pacientes: busca, tabela ordenável e os botões Novo, Editar e Excluir.

Toda gravação passa por `servicos.pacientes` com o nome do usuário, que vai para a
auditoria. Em somente leitura, os botões que gravam ficam desligados.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.ficha import Ficha
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import BancoCorrompido, Sessao
from gastroepi.ui_qt.aparencia import Aviso, com_papel, rotulo
from gastroepi.ui_qt.dialogo_exame import Catalogos
from gastroepi.ui_qt.dialogo_ficha import DialogoFicha
from gastroepi.ui_qt.modelo_pacientes import FiltroDePacientes, ModeloDePacientes
from gastroepi.ui_qt.perguntas import Perguntas
from gastroepi.ui_qt.textos import PARTE_ILEGIVEL, mensagem_de_erro


def catalogos_de(sessao: Sessao) -> Catalogos:
    return Catalogos(
        pacientes.listar_comorbidades(sessao),
        pacientes.listar_sintomas(sessao),
        pacientes.listar_examinadores(sessao),
    )


class TelaPacientes(QWidget):
    def __init__(self, sessao: Sessao, usuario: Callable[[], str], perguntas: Perguntas) -> None:
        super().__init__()
        self._sessao, self._usuario, self._perguntas = sessao, usuario, perguntas
        self.dialogo: DialogoFicha | None = None
        self.modelo = ModeloDePacientes(self)
        self.filtro = FiltroDePacientes(self.modelo, self)
        self.busca = QLineEdit(self)
        self.busca.setPlaceholderText(
            "Buscar por nome, prontuário ou CPF (Enter abre o prontuário)"
        )
        self.busca.setClearButtonEnabled(True)
        self.novo = com_papel(QPushButton("Novo paciente", self), "principal")
        self.editar = QPushButton("Abrir / editar", self)
        self.excluir = com_papel(QPushButton("Excluir", self), "perigo")
        self.contagem = rotulo("", "explicacao", self)
        self.aviso = Aviso(self)
        self.tabela = QTableView(self)
        self._configurar_tabela()
        self._montar()
        self.busca.textChanged.connect(self._filtrar)
        self.busca.returnPressed.connect(self._abrir_prontuario)
        self.novo.clicked.connect(self._novo)
        self.editar.clicked.connect(self._abrir_selecionado)
        self.tabela.doubleClicked.connect(self._abrir_selecionado)
        self.excluir.clicked.connect(self._excluir_selecionado)
        somente_leitura = sessao.somente_leitura
        for botao in (self.novo, self.excluir):
            botao.setEnabled(not somente_leitura)

    def _configurar_tabela(self) -> None:
        self.tabela.setModel(self.filtro)
        self.tabela.setSortingEnabled(True)
        self.tabela.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.verticalHeader().hide()
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setStretchLastSection(True)
        cabecalho.setMinimumSectionSize(90)
        cabecalho.resizeSection(1, 300)
        cabecalho.resizeSection(5, 120)

    def _montar(self) -> None:
        botoes = QHBoxLayout()
        botoes.addWidget(self.busca, stretch=1)
        for botao in (self.novo, self.editar, self.excluir):
            botoes.addWidget(botao)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Pacientes", "titulo", self))
        disposicao.addLayout(botoes)
        disposicao.addWidget(self.aviso)
        disposicao.addWidget(self.tabela)
        disposicao.addWidget(self.contagem)

    def atualizar(self) -> None:
        self.modelo.carregar(pacientes.listar(self._sessao))
        self._contar()

    def _filtrar(self, termo: str) -> None:
        self.filtro.definir_termo(termo)
        self._contar()

    def _contar(self) -> None:
        total, visiveis = self.modelo.rowCount(), self.filtro.rowCount()
        filtrado = f" ({visiveis} na busca)" if visiveis != total else ""
        self.contagem.setText(f"{total} pacientes{filtrado}")

    def _linha_selecionada(self) -> int | None:
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            self.aviso.alerta("Selecione um paciente na tabela.")
            return None
        return linhas[0].row()

    def _novo(self) -> None:
        self._abrir(None)

    def _abrir_selecionado(self) -> None:
        """A ficha é relida do banco: a da tabela pode ter ficado para trás."""
        linha = self._linha_selecionada()
        if linha is None:
            return
        paciente_id = self.filtro.paciente_id(linha)
        ficha = pacientes.buscar(self._sessao, paciente_id)
        if ficha is None:
            self.aviso.alerta("Este paciente não existe mais.")
            self.atualizar()
            return
        self._abrir(paciente_id, ficha)

    def _abrir_prontuario(self) -> None:
        """Enter na busca: o prontuário digitado inteiro abre direto a ficha."""
        achado = pacientes.buscar_por_prontuario(self._sessao, self.busca.text())
        if achado is not None:
            self._abrir(*achado)

    def _abrir(self, paciente_id: int | None, ficha: Ficha | None = None) -> None:
        self.aviso.limpar()
        try:
            catalogos = catalogos_de(self._sessao)
        except BancoCorrompido:
            self.aviso.erro(PARTE_ILEGIVEL)
            return
        self.dialogo = DialogoFicha(
            catalogos, ficha, lambda nova: self._gravar(paciente_id, nova), self
        )
        self.dialogo.botao_salvar.setEnabled(not self._sessao.somente_leitura)
        self.dialogo.open()

    def _gravar(self, paciente_id: int | None, ficha: Ficha) -> None:
        if paciente_id is None:
            pacientes.cadastrar(self._sessao, ficha, self._usuario())
            self.aviso.sucesso("Paciente cadastrado.")
        else:
            pacientes.editar(self._sessao, paciente_id, ficha, self._usuario())
            self.aviso.sucesso("Ficha salva.")
        self.atualizar()

    def _excluir_selecionado(self) -> None:
        linha = self._linha_selecionada()
        if linha is None:
            return
        ficha = self.filtro.ficha(linha)
        texto = (
            f"Excluir {ficha.paciente.nome} (prontuário {ficha.paciente.prontuario}) e os"
            f" {len(ficha.exames)} exames? A exclusão fica registrada na auditoria."
        )
        if not self._perguntas.confirmar(self, "Excluir paciente", texto):
            return
        try:
            pacientes.excluir(self._sessao, self.filtro.paciente_id(linha), self._usuario())
        except (LookupError, PermissionError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        self.aviso.sucesso("Paciente excluído.")
        self.atualizar()
