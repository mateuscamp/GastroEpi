"""Diálogo da ficha, com as abas Paciente e Exames (escolha do dono, 2026-10-31).

Cada exame abre num diálogo próprio. "Salvar" monta a `Ficha` e entrega a `salvar`, que
grava pelo serviço; o erro de gravação (prontuário repetido, banco somente leitura)
aparece aqui mesmo, sem perder o que foi digitado.
"""

from collections.abc import Callable

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.cpf import formatar_cpf
from gastroepi.dominio.datas import formatar_data_br
from gastroepi.dominio.exame import Exame
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.listas import Parentesco, Sexo
from gastroepi.dominio.paciente import HistoricoFamiliar, Paciente
from gastroepi.ui_qt.aparencia import Aviso, rotulo
from gastroepi.ui_qt.campos_da_tela import ComboDeLista, InteiroOpcional, ListaDeMarcar
from gastroepi.ui_qt.dialogo_exame import Catalogos, DialogoExame, rotulo_do_examinador
from gastroepi.ui_qt.tabela_de_lesoes import TabelaDeItens
from gastroepi.ui_qt.textos import mensagem_de_erro


class TabelaDeParentes(QWidget):
    """Parentes com câncer colorretal: o grau sai do parentesco, nunca é digitado."""

    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.tabela = QTableWidget(0, 2, self)
        self.tabela.setHorizontalHeaderLabels(["Parentesco", "Idade no diagnóstico"])
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.horizontalHeader().resizeSection(0, 240)
        self.tabela.verticalHeader().hide()
        self.adicionar = QPushButton("Adicionar parente", self)
        self.remover = QPushButton("Remover parente", self)
        botoes = QHBoxLayout()
        botoes.addWidget(self.adicionar)
        botoes.addWidget(self.remover)
        botoes.addStretch()
        disposicao = QVBoxLayout(self)
        disposicao.setContentsMargins(0, 0, 0, 0)
        disposicao.addLayout(botoes)
        disposicao.addWidget(self.tabela)
        self.adicionar.clicked.connect(self._acrescentar_vazio)
        self.remover.clicked.connect(self._remover)

    def _acrescentar_vazio(self) -> None:
        self.acrescentar(None)

    def acrescentar(self, parente: HistoricoFamiliar | None) -> None:
        linha = self.tabela.rowCount()
        self.tabela.insertRow(linha)
        parentesco, idade = ComboDeLista(Parentesco, self.tabela), InteiroOpcional(120)
        if parente is not None:
            parentesco.definir(parente.parentesco)
            idade.definir(parente.idade_diagnostico)
        self.tabela.setCellWidget(linha, 0, parentesco)
        self.tabela.setCellWidget(linha, 1, idade)

    def _remover(self) -> None:
        linha = self.tabela.currentRow()
        self.tabela.removeRow(linha if linha >= 0 else self.tabela.rowCount() - 1)

    def campos(self) -> tuple[dict[str, object], ...]:
        linhas = []
        for linha in range(self.tabela.rowCount()):
            parentesco = self.tabela.cellWidget(linha, 0)
            idade = self.tabela.cellWidget(linha, 1)
            assert isinstance(parentesco, ComboDeLista) and isinstance(idade, InteiroOpcional)
            linhas.append({"parentesco": parentesco.valor(), "idade_diagnostico": idade.valor()})
        return tuple(linhas)


class AbaPaciente(QWidget):
    def __init__(self, comorbidades: tuple[str, ...], pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self._catalogo = comorbidades
        self.prontuario, self.cpf, self.nome = QLineEdit(self), QLineEdit(self), QLineEdit(self)
        self.cpf.setPlaceholderText("000.000.000-00 (opcional)")
        self.sexo = ComboDeLista(Sexo, self)
        self.nascimento = QLineEdit(self)
        self.nascimento.setPlaceholderText("dd/mm/aaaa")
        self.comorbidades = ListaDeMarcar("Outra comorbidade", self)
        self.comorbidades.definir(comorbidades, ())
        self.parentes = TabelaDeParentes(self)
        formulario = QFormLayout(self)
        formulario.addRow("Prontuário", self.prontuario)
        formulario.addRow("CPF", self.cpf)
        formulario.addRow("Nome", self.nome)
        formulario.addRow("Sexo", self.sexo)
        formulario.addRow("Data de nascimento", self.nascimento)
        formulario.addRow("Comorbidades", self.comorbidades)
        formulario.addRow("Parentes com câncer colorretal", self.parentes)

    def preencher(self, paciente: Paciente) -> None:
        self.prontuario.setText(paciente.prontuario)
        self.cpf.setText("" if paciente.cpf is None else formatar_cpf(paciente.cpf))
        self.nome.setText(paciente.nome)
        self.sexo.definir(paciente.sexo)
        self.nascimento.setText(formatar_data_br(paciente.data_nascimento))
        self.comorbidades.definir(self._catalogo, paciente.comorbidades)
        for parente in paciente.historico_familiar:
            self.parentes.acrescentar(parente)

    def campos(self) -> dict[str, object]:
        return {
            "prontuario": self.prontuario.text(),
            "cpf": self.cpf.text(),
            "nome": self.nome.text(),
            "sexo": self.sexo.valor(),
            "data_nascimento": self.nascimento.text(),
            "comorbidades": self.comorbidades.marcados(),
            "historico_familiar": self.parentes.campos(),
        }


def celulas_do_exame(exame: Exame) -> tuple[str, ...]:
    pendente = "aguardando histologia" if exame.aguardando_histologia else ""
    return (
        formatar_data_br(exame.data_exame),
        exame.indicacao.rotulo,
        rotulo_do_examinador(exame.examinador),
        str(exame.n_polipos),
        pendente,
    )


class DialogoFicha(QDialog):
    def __init__(
        self,
        catalogos: Catalogos,
        ficha: Ficha | None,
        salvar: Callable[[Ficha], None],
        pai: QWidget | None = None,
    ) -> None:
        super().__init__(pai)
        self.setWindowTitle("Novo paciente" if ficha is None else "Editar paciente")
        self.resize(820, 680)
        self._salvar = salvar
        self.paciente = AbaPaciente(catalogos.comorbidades, self)
        self.exames = TabelaDeItens[Exame](
            ("Data", "Indicação", "Examinador", "Lesões", "Pendente"),
            celulas_do_exame,
            lambda exame: DialogoExame(catalogos, exame, self),
            lambda dialogo: dialogo.exame if isinstance(dialogo, DialogoExame) else None,
            self,
        )
        self.abas = QTabWidget(self)
        self.abas.addTab(self.paciente, "Paciente")
        self.abas.addTab(self.exames, "Exames")
        self.erro = Aviso(self)
        botoes = QDialogButtonBox(self)
        self.botao_salvar = botoes.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        botoes.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        botoes.accepted.connect(self._guardar)
        botoes.rejected.connect(self.reject)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Os exames do paciente ficam na aba Exames.", "explicacao"))
        disposicao.addWidget(self.abas)
        disposicao.addWidget(self.erro)
        disposicao.addWidget(botoes)
        if ficha is not None:
            self.paciente.preencher(ficha.paciente)
            self.exames.definir(ficha.exames)

    def montar_ficha(self) -> Ficha:
        return Ficha.model_validate(
            {"paciente": self.paciente.campos(), "exames": self.exames.itens()}
        )

    def _guardar(self) -> None:
        try:
            self._salvar(self.montar_ficha())
        except (ValidationError, ValueError, LookupError, PermissionError) as erro:
            self.erro.erro(mensagem_de_erro(erro))
            return
        self.accept()
