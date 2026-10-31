"""Assistente de restauração (ADR-0005, itens 1 e 2): o banco não passou na checagem.

Com a página do meio estragada, o cofre abre em somente leitura e o assistente oferece o
último backup bom; com a página 1 estragada, nada abre e restaurar é a única saída. A
restauração pede a senha de novo e guarda o banco estragado ao lado
(`gastroepi.db.corrompido-<momento>`): nenhum código apaga o banco estragado.
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout, QWidget

from gastroepi.servicos import acesso
from gastroepi.servicos.acesso import Backup, Sessao
from gastroepi.ui_qt.aparencia import Aviso, com_papel, rotulo
from gastroepi.ui_qt.textos import mensagem_de_erro, momento_local

_SEM_BACKUP = (
    "Nenhum backup deste cofre passou na conferência. Os dados continuam abertos só para"
    " leitura: exporte o que precisar e procure ajuda antes de digitar novos exames."
)


def explicacao_do_defeito(backup: Backup | None, abriu: bool) -> str:
    inicio = (
        "O arquivo do banco tem um defeito. Para não estragar mais nada, ele foi aberto só"
        " para leitura: dá para consultar, mas não para cadastrar ou editar."
        if abriu
        else "O arquivo do banco tem um defeito e não abre."
    )
    if backup is None:
        return f"{inicio}\n\n{_SEM_BACKUP}"
    return (
        f"{inicio}\n\nO último backup bom é de {momento_local(backup.momento)}. Restaurar"
        " põe esse backup no lugar; o que foi digitado depois dele se perde. O arquivo com"
        " defeito fica guardado na mesma pasta."
    )


class AssistenteDeRestauracao(QDialog):
    restaurado = Signal(object)  # Sessao

    def __init__(
        self,
        pasta: Path,
        backup: Backup | None,
        abriu: bool,
        antes_de_restaurar: Callable[[], None] = lambda: None,
        pai: QWidget | None = None,
    ) -> None:
        super().__init__(pai)
        self._antes_de_restaurar = antes_de_restaurar
        self.setWindowTitle("Restaurar backup")
        self.pasta, self.backup = pasta, backup
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("O banco precisa de atenção", "titulo", self))
        disposicao.addWidget(rotulo(explicacao_do_defeito(backup, abriu), "", self))
        self.senha = QLineEdit(self)
        self.senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.senha.setPlaceholderText("Senha do GastroEpi")
        self.restaurar = com_papel(QPushButton("Restaurar o backup", self), "principal")
        self.depois = QPushButton("Agora não" if abriu else "Fechar", self)
        self.erro = Aviso(self)
        for widget in (self.senha, self.restaurar, self.depois, self.erro):
            disposicao.addWidget(widget)
        disposicao.addStretch()
        self.setMaximumWidth(600)
        self.senha.setVisible(backup is not None)
        self.restaurar.setVisible(backup is not None)
        self.restaurar.clicked.connect(self._restaurar)
        self.depois.clicked.connect(self.reject)

    def _restaurar(self) -> None:
        assert self.backup is not None  # o botão só aparece com backup
        senha = self.senha.text()
        self.senha.clear()
        self._antes_de_restaurar()  # a sessão somente leitura fecha antes da troca
        try:
            sessao: Sessao = acesso.restaurar_backup(self.pasta, self.backup, senha)
        except (ValueError, OSError, RuntimeError) as erro:
            self.erro.erro(mensagem_de_erro(erro))
            return
        self.restaurado.emit(sessao)
        self.accept()
