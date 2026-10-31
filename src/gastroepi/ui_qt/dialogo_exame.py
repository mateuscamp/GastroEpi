"""Diálogo de um exame: data, indicação, examinador, qualidade, sintomas e lesões.

Só a intubação cecal é obrigatória entre os campos de qualidade (escolha do dono,
ADR-0004); o Boston entra com os 3 segmentos ou fica de fora. O nº de pólipos é o nº de
lesões da tabela, nunca digitado.
"""

from dataclasses import dataclass

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gastroepi.dominio.datas import formatar_data_br
from gastroepi.dominio.exame import Exame, Examinador
from gastroepi.dominio.listas import Indicacao, MotivoNaoIntubacao
from gastroepi.ui_qt.aparencia import Aviso, rotulo
from gastroepi.ui_qt.campos_da_tela import ComboDeLista, DecimalOpcional, ListaDeMarcar, SimOuNao
from gastroepi.ui_qt.tabela_de_lesoes import TabelaDeLesoes
from gastroepi.ui_qt.textos import mensagem_de_erro


@dataclass(frozen=True, slots=True)
class Catalogos:
    """O que os formulários oferecem para escolher; item novo entra pelo formulário."""

    comorbidades: tuple[str, ...]
    sintomas: tuple[str, ...]
    examinadores: tuple[Examinador, ...]


def rotulo_do_examinador(examinador: Examinador) -> str:
    return f"{examinador.nome} (CRM-{examinador.uf} {examinador.crm})"


class _Boston(QWidget):
    def __init__(self, pai: QWidget) -> None:
        super().__init__(pai)
        self.registrado = QCheckBox("Registrado", self)
        self.notas = [QSpinBox(self) for _ in range(3)]
        linha = QHBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.addWidget(self.registrado)
        for nota, nome in zip(self.notas, ("Direito", "Transverso", "Esquerdo"), strict=True):
            nota.setRange(0, 3)
            nota.setPrefix(f"{nome}: ")
            linha.addWidget(nota)
        self.registrado.toggled.connect(self._habilitar)
        self._habilitar(False)

    def _habilitar(self, ligado: bool) -> None:
        for nota in self.notas:
            nota.setEnabled(ligado)

    def valor(self) -> dict[str, int] | None:
        if not self.registrado.isChecked():
            return None
        nomes = ("direito", "transverso", "esquerdo")
        return dict(zip(nomes, (n.value() for n in self.notas), strict=True))

    def definir(self, notas: tuple[int, int, int] | None) -> None:
        self.registrado.setChecked(notas is not None)
        for nota, valor in zip(self.notas, notas or (0, 0, 0), strict=True):
            nota.setValue(valor)


class DialogoExame(QDialog):
    def __init__(
        self, catalogos: Catalogos, exame: Exame | None = None, pai: QWidget | None = None
    ) -> None:
        super().__init__(pai)
        self.setWindowTitle("Exame")
        self.resize(760, 640)
        self.exame: Exame | None = None
        self._examinadores = list(catalogos.examinadores)
        self._catalogo_de_sintomas = catalogos.sintomas
        self._criar_campos(catalogos)
        self._montar()
        self.indicacao.currentIndexChanged.connect(self._mostrar_condicionais)
        self.intubacao.currentIndexChanged.connect(self._mostrar_condicionais)
        self.motivo.currentIndexChanged.connect(self._mostrar_condicionais)
        if exame is not None:
            self._preencher(exame)
        self._mostrar_condicionais()

    def _criar_campos(self, catalogos: Catalogos) -> None:
        self.data = QLineEdit(self)
        self.data.setPlaceholderText("dd/mm/aaaa")
        self.indicacao = ComboDeLista(Indicacao, self)
        self.indicacao_outra = QLineEdit(self)
        self.examinador = QComboBox(self)
        self.examinador.addItems([rotulo_do_examinador(e) for e in self._examinadores])
        self.examinador.setPlaceholderText("Escolha… (cadastre em Catálogos)")
        self.examinador.setCurrentIndex(-1)
        self.boston = _Boston(self)
        self.intubacao = SimOuNao(self)
        self.motivo = ComboDeLista(MotivoNaoIntubacao, self)
        self.motivo_outro = QLineEdit(self)
        self.retirada = DecimalOpcional(120.0, " min", self)
        self.sintomas = ListaDeMarcar("Outro sintoma", self)
        self.sintomas.definir(catalogos.sintomas, ())
        self.lesoes = TabelaDeLesoes(self)
        self.observacao = QPlainTextEdit(self)
        self.observacao.setPlaceholderText("Só para consulta: não entra na estatística")
        self.erro = Aviso(self)

    def _montar(self) -> None:
        geral = QWidget(self)
        formulario = QFormLayout(geral)
        formulario.addRow("Data do exame", self.data)
        formulario.addRow("Indicação", self.indicacao)
        formulario.addRow("Qual indicação", self.indicacao_outra)
        formulario.addRow("Examinador", self.examinador)
        formulario.addRow("Preparo (Boston)", self.boston)
        formulario.addRow("Ceco alcançado?", self.intubacao)
        formulario.addRow("Por que não", self.motivo)
        formulario.addRow("Qual motivo", self.motivo_outro)
        formulario.addRow("Tempo de retirada", self.retirada)
        formulario.addRow("Observação", self.observacao)
        abas = QTabWidget(self)
        abas.addTab(geral, "Exame")
        abas.addTab(self.sintomas, "Sintomas")
        abas.addTab(self.lesoes, "Lesões")
        botoes = QDialogButtonBox(self)
        self.guardar = botoes.addButton("Guardar exame", QDialogButtonBox.ButtonRole.AcceptRole)
        botoes.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        botoes.accepted.connect(self._guardar)
        botoes.rejected.connect(self.reject)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("As lesões ficam na aba Lesões.", "explicacao", self))
        disposicao.addWidget(abas)
        disposicao.addWidget(self.erro)
        disposicao.addWidget(botoes)

    def _mostrar_condicionais(self) -> None:
        sem_ceco = self.intubacao.valor() is False
        _habilitar(self.indicacao_outra, self.indicacao.valor() is Indicacao.OUTRA)
        _habilitar(self.motivo, sem_ceco)
        _habilitar(self.motivo_outro, sem_ceco and self.motivo.valor() is MotivoNaoIntubacao.OUTRO)

    def _preencher(self, exame: Exame) -> None:
        self.data.setText(formatar_data_br(exame.data_exame))
        self.indicacao.definir(exame.indicacao)
        self.indicacao_outra.setText(exame.indicacao_outra or "")
        if exame.examinador not in self._examinadores:
            self._examinadores.append(exame.examinador)
            self.examinador.addItem(rotulo_do_examinador(exame.examinador))
        self.examinador.setCurrentIndex(self._examinadores.index(exame.examinador))
        preparo = exame.preparo
        self.boston.definir(
            None if preparo is None else (preparo.direito, preparo.transverso, preparo.esquerdo)
        )
        self.intubacao.definir(exame.intubacao_cecal)
        self.motivo.definir(exame.motivo_nao_intubacao)
        self.motivo_outro.setText(exame.motivo_outro or "")
        self.retirada.definir(exame.tempo_retirada_min)
        self.sintomas.definir(self._catalogo_de_sintomas, exame.sintomas)
        self.lesoes.definir(exame.lesoes)
        self.observacao.setPlainText(exame.observacao or "")

    def campos(self) -> dict[str, object]:
        indice = self.examinador.currentIndex()
        return {
            "data_exame": self.data.text(),
            "indicacao": self.indicacao.valor(),
            "indicacao_outra": self.indicacao_outra.text(),
            "examinador": None if indice < 0 else self._examinadores[indice],
            "preparo": self.boston.valor(),
            "intubacao_cecal": self.intubacao.valor(),
            "motivo_nao_intubacao": self.motivo.valor(),
            "motivo_outro": self.motivo_outro.text(),
            "tempo_retirada_min": self.retirada.valor(),
            "sintomas": self.sintomas.marcados(),
            "lesoes": self.lesoes.lesoes(),
            "observacao": self.observacao.toPlainText(),
        }

    def _guardar(self) -> None:
        try:
            self.exame = Exame.model_validate(self.campos())
        except (ValidationError, ValueError) as erro:
            self.erro.erro(mensagem_de_erro(erro))
            return
        self.accept()


def _habilitar(campo: QWidget, ligado: bool) -> None:
    """O campo que só vale com "outra"/"não" fica apagado e vazio quando não vale."""
    campo.setEnabled(ligado)
    if ligado:
        return
    if isinstance(campo, QLineEdit):
        campo.clear()
    elif isinstance(campo, ComboDeLista):
        campo.definir(None)
