"""Catálogos: comorbidades, sintomas e examinadores (nome + CRM + UF).

Cada inclusão é auditada pelo serviço. Comorbidade ou sintoma digitado na ficha também
entra no catálogo quando a ficha é salva; aqui é para preparar as listas antes.
"""

from collections.abc import Callable

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.listas import UF
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.aparencia import Aviso, rotulo
from gastroepi.ui_qt.dialogo_exame import rotulo_do_examinador
from gastroepi.ui_qt.textos import mensagem_de_erro

type Inclusao = Callable[[Sessao, ItemDeCatalogo, str], str]


class _Catalogo(QGroupBox):
    def __init__(self, titulo: str, dica: str, inclusao: Inclusao, pai: QWidget) -> None:
        super().__init__(titulo, pai)
        self.inclusao = inclusao
        self.lista = QListWidget(self)
        self.novo = QLineEdit(self)
        self.novo.setPlaceholderText(dica)
        self.incluir = QPushButton("Incluir", self)
        linha = QHBoxLayout()
        linha.addWidget(self.novo)
        linha.addWidget(self.incluir)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(self.lista)
        disposicao.addLayout(linha)


class _Examinadores(QGroupBox):
    def __init__(self, pai: QWidget) -> None:
        super().__init__("Examinadores", pai)
        self.lista = QListWidget(self)
        self.nome, self.crm = QLineEdit(self), QLineEdit(self)
        self.nome.setPlaceholderText("Nome do médico")
        self.crm.setPlaceholderText("Só os números")
        self.uf = QComboBox(self)
        self.uf.addItems([uf.value for uf in UF])
        self.uf.setPlaceholderText("UF")
        self.uf.setCurrentIndex(-1)
        self.incluir = QPushButton("Incluir examinador", self)
        formulario = QFormLayout()
        formulario.addRow("Nome", self.nome)
        formulario.addRow("CRM", self.crm)
        formulario.addRow("UF do CRM", self.uf)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(self.lista)
        disposicao.addLayout(formulario)
        disposicao.addWidget(self.incluir)

    def campos(self) -> dict[str, object]:
        indice = self.uf.currentIndex()
        uf = None if indice < 0 else list(UF)[indice]
        return {"nome": self.nome.text(), "crm": self.crm.text(), "uf": uf}


class TelaCatalogos(QWidget):
    def __init__(self, sessao: Sessao, usuario: Callable[[], str]) -> None:
        super().__init__()
        self._sessao, self._usuario = sessao, usuario
        self.comorbidades = _Catalogo(
            "Comorbidades", "Nova comorbidade", pacientes.adicionar_comorbidade, self
        )
        self.sintomas = _Catalogo("Sintomas", "Novo sintoma", pacientes.adicionar_sintoma, self)
        self.examinadores = _Examinadores(self)
        self.aviso = Aviso(self)
        colunas = QHBoxLayout()
        for grupo in (self.comorbidades, self.sintomas, self.examinadores):
            colunas.addWidget(grupo)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Catálogos", "titulo", self))
        disposicao.addWidget(
            rotulo(
                "As listas que a ficha oferece. Toda inclusão vai para a auditoria.", "explicacao"
            )
        )
        disposicao.addWidget(self.aviso)
        disposicao.addLayout(colunas)
        self.comorbidades.incluir.clicked.connect(self._incluir_comorbidade)
        self.comorbidades.novo.returnPressed.connect(self._incluir_comorbidade)
        self.sintomas.incluir.clicked.connect(self._incluir_sintoma)
        self.sintomas.novo.returnPressed.connect(self._incluir_sintoma)
        self.examinadores.incluir.clicked.connect(self._incluir_examinador)
        for grupo in (self.comorbidades, self.sintomas, self.examinadores):
            grupo.setEnabled(not sessao.somente_leitura)

    # Métodos e não closures no connect: closure com `self` derruba o PySide ao recolher.
    def _incluir_comorbidade(self) -> None:
        self._incluir(self.comorbidades)

    def _incluir_sintoma(self) -> None:
        self._incluir(self.sintomas)

    def atualizar(self) -> None:
        self.comorbidades.lista.clear()
        self.comorbidades.lista.addItems(list(pacientes.listar_comorbidades(self._sessao)))
        self.sintomas.lista.clear()
        self.sintomas.lista.addItems(list(pacientes.listar_sintomas(self._sessao)))
        self.examinadores.lista.clear()
        examinadores = pacientes.listar_examinadores(self._sessao)
        self.examinadores.lista.addItems([rotulo_do_examinador(e) for e in examinadores])

    def _incluir(self, grupo: _Catalogo) -> None:
        try:
            item = ItemDeCatalogo(nome=grupo.novo.text())
            nome = grupo.inclusao(self._sessao, item, self._usuario())
        except (ValidationError, ValueError, PermissionError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        grupo.novo.clear()
        self.aviso.sucesso(f"Incluído: {nome}.")
        self.atualizar()

    def _incluir_examinador(self) -> None:
        try:
            examinador = Examinador.model_validate(self.examinadores.campos())
            pacientes.adicionar_examinador(self._sessao, examinador, self._usuario())
        except (ValidationError, ValueError, PermissionError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        self.examinadores.nome.clear()
        self.examinadores.crm.clear()
        self.aviso.sucesso(f"Incluído: {rotulo_do_examinador(examinador)}.")
        self.atualizar()
