"""Backup: o manual, a lista das cópias e o destino externo (pendrive ou Drive).

O automático roda sozinho (a cada 15 min, se houve alteração, e ao fechar). Só a cópia
pronta e conferida vai para o destino externo; o banco em uso nunca (ADR-0005).
"""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gastroepi.servicos import destino_externo, durabilidade
from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.aparencia import Aviso, com_papel, rotulo
from gastroepi.ui_qt.perguntas import Perguntas
from gastroepi.ui_qt.textos import mensagem_de_erro, momento_local

_AUTOMATICO = (
    "O GastroEpi faz backup sozinho a cada 15 minutos, se algo mudou, e ao fechar. Ficam 7"
    " diários, 4 semanais e 12 mensais, na pasta backups ao lado do banco."
)
_DESTINO = (
    "Para não perder tudo se o computador estragar, escolha uma pasta num pendrive ou no"
    " Google Drive: cada backup é copiado para lá. A recovery key nunca vai junto; ela fica"
    " no papel. Para a nuvem, a senha precisa ser uma frase de 4 palavras."
)


class TelaBackup(QWidget):
    def __init__(self, sessao: Sessao, perguntas: Perguntas) -> None:
        super().__init__()
        self._sessao, self._perguntas = sessao, perguntas
        self.fazer = com_papel(QPushButton("Fazer backup agora", self), "principal")
        self.lista = QListWidget(self)
        self.situacao = rotulo("", "", self)
        self.senha = QLineEdit(self)
        self.senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.senha.setPlaceholderText("Senha do GastroEpi (para escolher o destino)")
        self.escolher = QPushButton("Escolher pasta de destino…", self)
        self.copiar = QPushButton("Copiar agora", self)
        self.remover = QPushButton("Parar de copiar", self)
        self.aviso = Aviso(self)
        self._montar()
        self.fazer.clicked.connect(self._fazer)
        self.escolher.clicked.connect(self._escolher)
        self.copiar.clicked.connect(self._copiar)
        self.remover.clicked.connect(self._remover)
        for botao in (self.fazer, self.escolher, self.copiar, self.remover):
            botao.setEnabled(not sessao.somente_leitura)

    def _montar(self) -> None:
        locais = QGroupBox("Backups neste computador", self)
        coluna = QVBoxLayout(locais)
        coluna.addWidget(rotulo(_AUTOMATICO, "explicacao"))
        coluna.addWidget(self.fazer)
        coluna.addWidget(self.lista)
        externo = QGroupBox("Cópia fora do computador", self)
        coluna_externa = QVBoxLayout(externo)
        coluna_externa.addWidget(rotulo(_DESTINO, "explicacao"))
        coluna_externa.addWidget(self.situacao)
        coluna_externa.addWidget(self.senha)
        botoes = QHBoxLayout()
        for botao in (self.escolher, self.copiar, self.remover):
            botoes.addWidget(botao)
        coluna_externa.addLayout(botoes)
        coluna_externa.addStretch()
        lado_a_lado = QHBoxLayout()
        lado_a_lado.addWidget(locais)
        lado_a_lado.addWidget(externo)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Backup", "titulo", self))
        disposicao.addWidget(self.aviso)
        disposicao.addLayout(lado_a_lado)

    def atualizar(self) -> None:
        self.lista.clear()
        for backup in durabilidade.backups_do_cofre(self._sessao):
            self.lista.addItem(momento_local(backup.momento))
        situacao = destino_externo.situacao(self._sessao)
        if situacao is None:
            self.situacao.setText("Nenhuma pasta de destino escolhida.")
        else:
            ultima = situacao.ultima_copia
            quando = "nunca" if ultima is None else momento_local(ultima)
            self.situacao.setText(f"Destino: {situacao.destino}\nÚltima cópia: {quando}")
        self.copiar.setEnabled(situacao is not None and not self._sessao.somente_leitura)
        self.remover.setEnabled(situacao is not None and not self._sessao.somente_leitura)

    def _executar(self, acao: Callable[[Sessao], object], sucesso: str) -> None:
        try:
            acao(self._sessao)
        except (OSError, ValueError, LookupError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        self.atualizar()
        self.aviso.sucesso(sucesso)

    def _fazer(self) -> None:
        self._executar(durabilidade.fazer_backup, "Backup feito e conferido.")

    def _copiar(self) -> None:
        sucesso = "Último backup copiado para o destino e conferido lá."
        self._executar(destino_externo.copiar_agora, sucesso)

    def _remover(self) -> None:
        sucesso = "As cópias param de ir para o destino; as que estão lá ficam."
        self._executar(destino_externo.remover, sucesso)

    def _escolher(self) -> None:
        pasta = self._perguntas.pasta(self, "Pasta de destino dos backups")
        if pasta is None:
            return
        senha = self.senha.text()
        self.senha.clear()
        try:
            destino_externo.configurar(self._sessao, pasta, senha)
        except (OSError, ValueError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        self.aviso.sucesso("Destino escolhido. Os próximos backups vão para lá também.")
        self.atualizar()
