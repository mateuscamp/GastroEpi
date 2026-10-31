"""Tela de desbloqueio: criar a senha, mostrar a recovery key, entrar e recuperar.

- Cenário 1: a senha nova é digitada duas vezes; a recovery key aparece uma única vez,
  em 8 blocos, e o botão Entrar só libera depois de "Anotei a chave no papel". Não há
  botão copiar: a área de transferência pode ir para a nuvem (escolha do dono, 2026-10-31).
- Esqueceu a senha: a recovery key abre o cofre e define uma senha nova.
- Banco com a página 1 estragada: a tela avisa a janela (`banco_ilegivel`), que oferece
  restaurar o backup (ADR-0005, item 2).
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gastroepi.servicos import acesso
from gastroepi.servicos.acesso import (
    ArquivoDeChaveAusente,
    BancoIlegivel,
    Sessao,
)
from gastroepi.ui_qt.aparencia import Aviso, com_papel, rotulo
from gastroepi.ui_qt.textos import mensagem_de_erro

_LARGURA = 520
_LARGURA_DA_CHAVE = 680  # 4 blocos de 8 caracteres em letra grande, sem cortar


def _campo_de_senha(pai: QWidget, dica: str) -> QLineEdit:
    campo = QLineEdit(pai)
    campo.setEchoMode(QLineEdit.EchoMode.Password)
    campo.setPlaceholderText(dica)
    return campo


def _botao(texto: str, pai: QWidget, papel: str = "") -> QPushButton:
    botao = QPushButton(texto, pai)
    return com_papel(botao, papel) if papel else botao


class _Pagina(QWidget):
    def __init__(self, titulo: str, explicacao: str) -> None:
        super().__init__()
        self.setMaximumWidth(_LARGURA)
        self.disposicao = QVBoxLayout(self)
        self.disposicao.addWidget(rotulo(titulo, "titulo", self))
        self.disposicao.addWidget(rotulo(explicacao, "explicacao", self))
        self.erro = Aviso(self)

    def fechar_disposicao(self) -> None:
        self.disposicao.addWidget(self.erro)
        self.disposicao.addStretch()


class PaginaCriar(_Pagina):
    def __init__(self) -> None:
        super().__init__(
            "Criar a senha do GastroEpi",
            "Os dados ficam cifrados neste computador. Escolha uma senha de pelo menos 8"
            " caracteres; uma frase de 4 palavras é mais fácil de lembrar e mais segura.",
        )
        self.senha = _campo_de_senha(self, "Senha")
        self.confirmacao = _campo_de_senha(self, "A mesma senha de novo")
        self.botao = _botao("Criar senha", self, "principal")
        for widget in (self.senha, self.confirmacao, self.botao):
            self.disposicao.addWidget(widget)
        self.confirmacao.returnPressed.connect(self.botao.click)
        self.fechar_disposicao()


class PaginaChave(_Pagina):
    def __init__(self) -> None:
        super().__init__(
            "Anote a sua recovery key",
            "Se você esquecer a senha, só esta chave abre os dados. Ela aparece só agora:"
            " escreva os 8 blocos num papel e guarde longe do computador. Não fotografe e"
            " não salve na nuvem.",
        )
        self.setMaximumWidth(_LARGURA_DA_CHAVE)
        grade = QGridLayout()
        self.blocos = [com_papel(QLabel(self), "bloco") for _ in range(8)]
        for indice, bloco in enumerate(self.blocos):
            bloco.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bloco.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            grade.addWidget(bloco, indice // 4, indice % 4)
        self.disposicao.addLayout(grade)
        self.anotei = QCheckBox("Anotei a chave no papel", self)
        self.botao_entrar = _botao("Entrar", self, "principal")
        self.botao_entrar.setEnabled(False)
        self.anotei.toggled.connect(self.botao_entrar.setEnabled)
        self.disposicao.addWidget(self.anotei)
        self.disposicao.addWidget(self.botao_entrar)
        self.fechar_disposicao()

    def mostrar(self, recovery_key: str) -> None:
        for bloco, texto in zip(self.blocos, recovery_key.split(), strict=True):
            bloco.setText(texto)
            bloco.setMinimumWidth(bloco.sizeHint().width())  # o bloco nunca sai cortado
        self.anotei.setChecked(False)

    def blocos_mostrados(self) -> list[str]:
        return [bloco.text() for bloco in self.blocos]

    def esquecer(self) -> None:
        for bloco in self.blocos:
            bloco.clear()


class PaginaEntrar(_Pagina):
    def __init__(self) -> None:
        super().__init__("GastroEpi bloqueado", "Digite a senha para abrir os dados.")
        self.senha = _campo_de_senha(self, "Senha")
        self.botao = _botao("Entrar", self, "principal")
        self.esqueci = _botao("Esqueci a senha (usar a recovery key)", self)
        for widget in (self.senha, self.botao, self.esqueci):
            self.disposicao.addWidget(widget)
        self.senha.returnPressed.connect(self.botao.click)
        self.fechar_disposicao()


class PaginaRecuperar(_Pagina):
    def __init__(self) -> None:
        super().__init__(
            "Entrar com a recovery key",
            "Digite os 8 blocos anotados no papel (com ou sem espaços) e escolha uma senha"
            " nova. A senha antiga deixa de valer.",
        )
        self.recovery_key = QLineEdit(self)
        self.recovery_key.setPlaceholderText("XXXXXXXX XXXXXXXX …")
        self.senha = _campo_de_senha(self, "Senha nova")
        self.confirmacao = _campo_de_senha(self, "A mesma senha nova de novo")
        self.botao = _botao("Entrar e trocar a senha", self, "principal")
        self.voltar = _botao("Voltar", self)
        for widget in (self.recovery_key, self.senha, self.confirmacao, self.botao, self.voltar):
            self.disposicao.addWidget(widget)
        self.fechar_disposicao()


class TelaDesbloqueio(QWidget):
    desbloqueado = Signal(object)  # Sessao
    banco_ilegivel = Signal(object)  # BancoIlegivel

    def __init__(self, pasta: Path) -> None:
        super().__init__()
        self.pasta = pasta
        self._criada: Sessao | None = None
        self.criar, self.chave = PaginaCriar(), PaginaChave()
        self.entrar, self.recuperar = PaginaEntrar(), PaginaRecuperar()
        self.paginas = QStackedWidget(self)
        for pagina in (self.criar, self.chave, self.entrar, self.recuperar):
            self.paginas.addWidget(pagina)
        disposicao = QVBoxLayout(self)
        disposicao.addStretch(1)
        disposicao.addWidget(self.paginas, alignment=Qt.AlignmentFlag.AlignHCenter)
        disposicao.addStretch(2)
        self._ligar()
        self.reiniciar()

    def _ligar(self) -> None:
        self.criar.botao.clicked.connect(self._criar)
        self.chave.botao_entrar.clicked.connect(self._entrar_depois_de_criar)
        self.entrar.botao.clicked.connect(self._entrar)
        self.entrar.esqueci.clicked.connect(self._ir_para_recuperar)
        self.recuperar.botao.clicked.connect(self._recuperar)
        self.recuperar.voltar.clicked.connect(self._ir_para_entrar)

    def _ir_para_recuperar(self) -> None:
        self._ir_para(self.recuperar)

    def _ir_para_entrar(self) -> None:
        self._ir_para(self.entrar)

    def reiniciar(self) -> None:
        """Volta ao começo: criar a senha se não há cofre, senão pedir a senha."""
        for campo in self.findChildren(QLineEdit):
            campo.clear()
        self.chave.esquecer()
        self._ir_para(self.entrar if acesso.cofre_existe(self.pasta) else self.criar)

    def _ir_para(self, pagina: _Pagina) -> None:
        pagina.erro.limpar()
        self.paginas.setCurrentWidget(pagina)
        campos = pagina.findChildren(QLineEdit)
        if campos:
            campos[0].setFocus()

    def _criar(self) -> None:
        try:
            sessao, recovery_key = acesso.criar_cofre(
                self.pasta, self.criar.senha.text(), self.criar.confirmacao.text()
            )
        except (ValueError, OSError) as erro:
            self.criar.erro.erro(mensagem_de_erro(erro))
            return
        self._criada = sessao
        self.criar.senha.clear()
        self.criar.confirmacao.clear()
        self.chave.mostrar(recovery_key)
        self._ir_para(self.chave)

    def _entrar_depois_de_criar(self) -> None:
        sessao, self._criada = self._criada, None
        self.chave.esquecer()
        if sessao is not None:
            self.desbloqueado.emit(sessao)

    def _entrar(self) -> None:
        senha = self.entrar.senha.text()
        self.entrar.senha.clear()
        try:
            sessao = acesso.desbloquear(self.pasta, senha)
        except BancoIlegivel as erro:
            self.banco_ilegivel.emit(erro)
            return
        except ArquivoDeChaveAusente as erro:
            self._ir_para(self.recuperar)
            self.recuperar.erro.alerta(f"{erro}. Entre com a recovery key e crie uma senha nova.")
            return
        except (ValueError, OSError, RuntimeError) as erro:
            self.entrar.erro.erro(mensagem_de_erro(erro))
            return
        self.desbloqueado.emit(sessao)

    def _recuperar(self) -> None:
        pagina = self.recuperar
        try:
            sessao = acesso.recuperar_acesso(
                self.pasta,
                pagina.recovery_key.text(),
                pagina.senha.text(),
                pagina.confirmacao.text(),
            )
        except (ValueError, OSError, RuntimeError) as erro:
            pagina.erro.erro(mensagem_de_erro(erro))
            return
        for campo in (pagina.recovery_key, pagina.senha, pagina.confirmacao):
            campo.clear()
        self.desbloqueado.emit(sessao)
