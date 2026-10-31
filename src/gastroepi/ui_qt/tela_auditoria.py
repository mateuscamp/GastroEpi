"""Auditoria: quem opera o app, a verificação de integridade e a lista de eventos.

A verificação roda as três camadas de uma vez (páginas do arquivo, cadeia de auditoria
e dados) e diz, em frase, o que achou. Os três botões da v0.1.16 viraram um só: quem
usa não precisa saber qual camada escolher.
"""

from collections.abc import Callable
from datetime import datetime

from pydantic import ValidationError
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gastroepi.servicos import acesso, integridade, pacientes
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.integridade import Divergencia, Motivo, Verificacao
from gastroepi.ui_qt.aparencia import Aviso, com_papel, rotulo
from gastroepi.ui_qt.textos import mensagem_de_erro, momento_local

ENTRADAS_MOSTRADAS = 200
COLUNAS = ("Nº", "Quando", "Usuário", "Ação", "Registro", "Elo (início)")
MOTIVOS = {
    Motivo.ALTERADO: "foi alterado por fora do app",
    Motivo.SEM_EVENTO: "existe sem nenhum registro na auditoria",
    Motivo.AUSENTE: "sumiu sem registro de exclusão",
    Motivo.EXCLUIDO_PRESENTE: "foi excluído, mas continua no banco",
    Motivo.HISTORICO_INTERROMPIDO: "foi alterado por fora entre duas edições",
}


def frase_da_divergencia(divergencia: Divergencia) -> str:
    entrada = "" if divergencia.entrada_id is None else f" (auditoria nº {divergencia.entrada_id})"
    registro = f"{divergencia.entidade} nº {divergencia.entidade_id}"
    return f"O registro {registro} {MOTIVOS[divergencia.motivo]}{entrada}."


def frases_da_verificacao(verificacao: Verificacao) -> list[str]:
    if verificacao.ok:
        return ["Tudo certo: o arquivo, a cadeia de auditoria e os dados conferem."]
    if verificacao.auditoria is None:
        n = len(verificacao.paginas_corrompidas)
        return [f"O arquivo do banco tem {n} página(s) com defeito. Restaure um backup."]
    frases = []
    quebra = verificacao.auditoria.cadeia
    if quebra is not None:
        quando = momento_local(datetime.fromisoformat(quebra.momento))
        frases.append(f"A cadeia de auditoria quebra na entrada nº {quebra.entrada_id} ({quando}).")
    frases += [frase_da_divergencia(d) for d in verificacao.auditoria.dados]
    return frases


class TelaAuditoria(QWidget):
    usuario_mudou = Signal(str)

    def __init__(self, sessao: Sessao, usuario: Callable[[], str]) -> None:
        super().__init__()
        self._sessao = sessao
        self.nome = QLineEdit(usuario(), self)
        self.salvar_nome = QPushButton("Salvar nome", self)
        self.verificar = com_papel(QPushButton("Verificar integridade", self), "principal")
        self.aviso = Aviso(self)
        self.tabela = QTableWidget(0, len(COLUNAS), self)
        self.tabela.setHorizontalHeaderLabels(list(COLUNAS))
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.verticalHeader().hide()
        self._montar()
        self.salvar_nome.clicked.connect(self._salvar_nome)
        self.verificar.clicked.connect(self._verificar)
        self.salvar_nome.setEnabled(not sessao.somente_leitura)

    def _montar(self) -> None:
        quem = QGroupBox("Quem está usando", self)
        linha = QHBoxLayout(quem)
        linha.addWidget(self.nome, stretch=1)
        linha.addWidget(self.salvar_nome)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Auditoria", "titulo", self))
        disposicao.addWidget(
            rotulo(
                "Cada cadastro, edição e exclusão fica registrado com o nome abaixo, numa"
                " cadeia que acusa qualquer alteração feita por fora do app.",
                "explicacao",
            )
        )
        disposicao.addWidget(quem)
        disposicao.addWidget(self.verificar)
        disposicao.addWidget(self.aviso)
        disposicao.addWidget(rotulo(f"Últimos {ENTRADAS_MOSTRADAS} registros", "subtitulo"))
        disposicao.addWidget(self.tabela)

    def atualizar(self) -> None:
        entradas = pacientes.listar_auditoria(self._sessao)[-ENTRADAS_MOSTRADAS:][::-1]
        self.tabela.setRowCount(len(entradas))
        for linha, entrada in enumerate(entradas):
            evento = entrada.evento
            celulas = (
                str(entrada.id),
                momento_local(datetime.fromisoformat(evento.momento)),
                evento.usuario,
                evento.acao,
                f"{evento.entidade} nº {evento.entidade_id}",
                entrada.elo.removeprefix("v2:")[:16],
            )
            for coluna, texto in enumerate(celulas):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(texto))
        self.tabela.resizeColumnsToContents()

    def _salvar_nome(self) -> None:
        try:
            nome = acesso.definir_nome_do_usuario(self._sessao, self.nome.text())
        except (ValidationError, PermissionError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        self.nome.setText(nome)
        self.aviso.sucesso(f"Daqui em diante, a auditoria registra: {nome}.")
        self.usuario_mudou.emit(nome)

    def _verificar(self) -> None:
        verificacao = integridade.verificar(self._sessao)
        texto = "\n".join(frases_da_verificacao(verificacao))
        if verificacao.ok:
            self.aviso.sucesso(texto)
        else:
            self.aviso.erro(texto)
