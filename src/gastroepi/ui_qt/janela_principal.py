"""Janela principal: desbloqueio, área de trabalho, bloqueio por inatividade e timers.

- O backup automático tem o timer aqui: `tique()` a cada minuto e `ao_fechar()` ao
  bloquear ou fechar (ADR-0005, item 6).
- Bloquear (o botão ou 15 min sem uso) fecha a conexão e descarta a chave: a sessão
  fechada não guarda a chave (ADR-0003). Diálogo aberto com dado não salvo se perde.
- Banco com defeito: o assistente de restauração. Restaurar exige a sessão somente
  leitura fechada, então ela fecha antes; se a restauração falhar, a tela volta ao
  desbloqueio e o banco com defeito continua lá, intacto.
"""

from contextlib import suppress
from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from gastroepi.servicos.acesso import Backup, BancoIlegivel, Sessao
from gastroepi.servicos.durabilidade import BackupAutomatico
from gastroepi.ui_qt.area_de_trabalho import AreaDeTrabalho
from gastroepi.ui_qt.assistente_restauracao import AssistenteDeRestauracao
from gastroepi.ui_qt.perguntas import Perguntas, PerguntasNaTela
from gastroepi.ui_qt.tela_desbloqueio import TelaDesbloqueio
from gastroepi.ui_qt.textos import mensagem_de_erro
from gastroepi.ui_qt.vigia_inatividade import INATIVIDADE_PADRAO, VigiaDeInatividade

INTERVALO_DO_TIQUE = timedelta(minutes=1)


class JanelaPrincipal(QMainWindow):
    def __init__(
        self,
        pasta: Path,
        perguntas: Perguntas | None = None,
        inatividade: timedelta = INATIVIDADE_PADRAO,
        tique: timedelta = INTERVALO_DO_TIQUE,
    ) -> None:
        super().__init__()
        self.setWindowTitle("GastroEpi")
        self.resize(1200, 780)
        self.pasta = pasta
        self._perguntas = perguntas or PerguntasNaTela()
        self.sessao: Sessao | None = None
        self.area: AreaDeTrabalho | None = None
        self.automatico: BackupAutomatico | None = None
        self.assistente: AssistenteDeRestauracao | None = None
        self.desbloqueio = TelaDesbloqueio(pasta)
        self.pilha = QStackedWidget(self)
        self.pilha.setObjectName("fundo")
        self.pilha.addWidget(self.desbloqueio)
        self.setCentralWidget(self.pilha)
        self.vigia = VigiaDeInatividade(inatividade, self)
        self.vigia.inativo.connect(self.bloquear)
        _aplicacao().installEventFilter(self.vigia)
        self.relogio_do_backup = QTimer(self)
        self.relogio_do_backup.setInterval(int(tique.total_seconds() * 1000))
        self.relogio_do_backup.timeout.connect(self.tique_do_backup)
        self.desbloqueio.desbloqueado.connect(self.abrir_sessao)
        self.desbloqueio.banco_ilegivel.connect(self._banco_ilegivel)

    def abrir_sessao(self, sessao: Sessao) -> None:
        self.sessao = sessao
        self.automatico = BackupAutomatico(sessao, sessao.relogio)
        self.area = AreaDeTrabalho(sessao, self._perguntas)
        self.area.bloquear_pedido.connect(self.bloquear)
        self.area.restaurar_pedido.connect(self._restaurar_pedido)
        self.pilha.addWidget(self.area)
        self.pilha.setCurrentWidget(self.area)
        self.vigia.iniciar()
        self.relogio_do_backup.start()
        if sessao.somente_leitura:
            self.oferecer_restauracao(sessao.backup_oferecido)

    def _restaurar_pedido(self) -> None:
        if self.sessao is not None:
            self.oferecer_restauracao(self.sessao.backup_oferecido)

    def encerrar_sessao(self) -> None:
        """Backup se houve alteração, fecha a conexão e volta ao desbloqueio."""
        self.vigia.parar()
        self.relogio_do_backup.stop()
        sessao, automatico, area = self.sessao, self.automatico, self.area
        self.sessao = self.automatico = self.area = None
        if sessao is not None and automatico is not None:
            # O backup do último tique continua valendo; fechar não pode travar.
            with suppress(OSError, RuntimeError):
                automatico.ao_fechar()
            sessao.fechar()
        if area is not None:
            self.pilha.removeWidget(area)
            area.deleteLater()
        self.desbloqueio.reiniciar()
        self.pilha.setCurrentWidget(self.desbloqueio)

    def bloquear(self) -> None:
        self.encerrar_sessao()

    def tique_do_backup(self) -> None:
        if self.automatico is None or self.area is None:
            return
        try:
            self.automatico.tique()
        except (OSError, RuntimeError) as erro:
            self.area.faixa.alerta(f"O backup automático falhou: {mensagem_de_erro(erro)}")

    def oferecer_restauracao(self, backup: Backup | None, abriu: bool = True) -> None:
        self.assistente = AssistenteDeRestauracao(
            self.pasta, backup, abriu, antes_de_restaurar=self.encerrar_sessao, pai=self
        )
        self.assistente.restaurado.connect(self.abrir_sessao)
        self.assistente.open()

    def _banco_ilegivel(self, erro: BancoIlegivel) -> None:
        self.oferecer_restauracao(erro.backup_oferecido, abriu=False)

    def closeEvent(self, evento: QCloseEvent) -> None:
        self.encerrar_sessao()
        _aplicacao().removeEventFilter(self.vigia)
        super().closeEvent(evento)


def _aplicacao() -> QCoreApplication:
    aplicacao = QCoreApplication.instance()
    assert aplicacao is not None  # a janela só existe com a QApplication criada
    return aplicacao
