"""Área de trabalho do cofre aberto: menu à esquerda, como na v0.1.16, e uma tela por módulo.

A faixa do topo avisa o que pede atenção: banco em somente leitura (com o botão de
restaurar) e cópia externa atrasada há mais de 7 dias (ADR-0005, item 10).
"""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.usuario import USUARIO_PADRAO
from gastroepi.servicos import acesso, destino_externo
from gastroepi.servicos.acesso import BancoCorrompido, Sessao
from gastroepi.ui_qt.aparencia import Aviso, com_papel
from gastroepi.ui_qt.perguntas import Perguntas
from gastroepi.ui_qt.tela_auditoria import TelaAuditoria
from gastroepi.ui_qt.tela_backup import TelaBackup
from gastroepi.ui_qt.tela_catalogos import TelaCatalogos
from gastroepi.ui_qt.tela_exportar import TelaExportar
from gastroepi.ui_qt.tela_pacientes import TelaPacientes
from gastroepi.ui_qt.tela_painel import TelaPainel
from gastroepi.ui_qt.tela_statcalc import TelaStatCalc
from gastroepi.ui_qt.textos import PARTE_ILEGIVEL

SOMENTE_LEITURA = (
    "O banco tem um defeito e foi aberto só para leitura: dá para consultar, mas não para"
    " cadastrar, editar, fazer backup ou exportar."
)
COPIA_ATRASADA = (
    "A cópia fora do computador está atrasada (mais de 7 dias). Conecte o pendrive ou"
    " abra Backup e clique em Copiar agora."
)


class AreaDeTrabalho(QWidget):
    bloquear_pedido = Signal()
    restaurar_pedido = Signal()

    def __init__(self, sessao: Sessao, perguntas: Perguntas) -> None:
        super().__init__()
        self.sessao = sessao
        self.usuario = QLabel(self)
        self.pacientes = TelaPacientes(sessao, self.nome_do_usuario, perguntas)
        self.painel = TelaPainel(sessao)
        self.statcalc = TelaStatCalc(sessao)
        self.catalogos = TelaCatalogos(sessao, self.nome_do_usuario)
        self.auditoria = TelaAuditoria(sessao, self.nome_do_usuario)
        self.backup = TelaBackup(sessao, perguntas)
        self.exportar = TelaExportar(sessao, perguntas)
        telas: list[tuple[str, QWidget, Callable[[], None]]] = [
            ("Pacientes", self.pacientes, self.pacientes.atualizar),
            ("Painel", self.painel, self.painel.atualizar),
            ("StatCalc", self.statcalc, self.statcalc.atualizar),
            ("Catálogos", self.catalogos, self.catalogos.atualizar),
            ("Auditoria", self.auditoria, self.auditoria.atualizar),
            ("Backup", self.backup, self.backup.atualizar),
            ("Exportar", self.exportar, self.exportar.atualizar),
        ]
        self.nomes = [nome for nome, _, _ in telas]
        self._atualizacoes = [atualizar for _, _, atualizar in telas]
        self.navegacao = QListWidget(self)
        self.navegacao.setObjectName("navegacao")
        self.navegacao.setFixedWidth(180)
        self.pilha = QStackedWidget(self)
        for nome, tela, _ in telas:
            self.navegacao.addItem(nome)
            self.pilha.addWidget(tela)
        self.faixa = Aviso(self)
        self.restaurar = com_papel(QPushButton("Restaurar backup…", self), "principal")
        self.bloquear = QPushButton("Bloquear", self)
        self._montar()
        self.navegacao.currentRowChanged.connect(self.ir_para)
        self.bloquear.clicked.connect(self.bloquear_pedido.emit)
        self.restaurar.clicked.connect(self.restaurar_pedido.emit)
        self.auditoria.usuario_mudou.connect(self._mostrar_usuario)
        self._mostrar_usuario(self.nome_do_usuario())
        self.mostrar_avisos()
        self.navegacao.setCurrentRow(0)

    def _montar(self) -> None:
        topo = QHBoxLayout()
        topo.addWidget(self.faixa, stretch=1)
        topo.addWidget(self.restaurar)
        topo.addStretch()
        topo.addWidget(self.usuario)
        topo.addWidget(self.bloquear)
        direita = QVBoxLayout()
        direita.addLayout(topo)
        direita.addWidget(self.pilha)
        disposicao = QHBoxLayout(self)
        disposicao.setContentsMargins(0, 0, 0, 0)
        disposicao.addWidget(self.navegacao)
        disposicao.addLayout(direita)

    def nome_do_usuario(self) -> str:
        """Em somente leitura nada é gravado, então o nome padrão basta se o defeito
        cair justo nas preferências."""
        try:
            return acesso.nome_do_usuario(self.sessao)
        except BancoCorrompido:
            return USUARIO_PADRAO

    def _mostrar_usuario(self, nome: str) -> None:
        self.usuario.setText(f"Usuário: {nome}")

    def ir_para(self, indice: int) -> None:
        self.pilha.setCurrentIndex(indice)
        self.mostrar_avisos()
        try:
            self._atualizacoes[indice]()
        except BancoCorrompido:
            self.faixa.erro(PARTE_ILEGIVEL)

    def ir_para_tela(self, nome: str) -> None:
        self.navegacao.setCurrentRow(self.nomes.index(nome))

    def mostrar_avisos(self) -> None:
        self.restaurar.setVisible(self.sessao.somente_leitura)
        if self.sessao.somente_leitura:
            self.faixa.erro(SOMENTE_LEITURA)
            return
        situacao = destino_externo.situacao(self.sessao)
        if situacao is not None and situacao.atrasada(self.sessao.relogio.agora()):
            self.faixa.alerta(COPIA_ATRASADA)
        else:
            self.faixa.limpar()
