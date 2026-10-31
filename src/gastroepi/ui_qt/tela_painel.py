"""Painel: números da base e um gráfico por variável, lidos numa passada só do banco.

A unidade é o exame (ADR-0004): a prevalência é a proporção de exames com lesão, e os
percentuais de comorbidade e sintoma podem somar mais de 100%.
"""

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gastroepi.servicos import indicadores
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.indicadores import ItemFrequencia, Painel, Variavel
from gastroepi.ui_qt.aparencia import com_papel, rotulo
from gastroepi.ui_qt.graficos import GraficoDeBarras
from gastroepi.ui_qt.textos import numero, proporcao

TITULOS = {
    Variavel.SEXO: "Sexo",
    Variavel.FAIXA_ETARIA: "Faixa etária no exame",
    Variavel.N_POLIPOS: "Nº de lesões por exame",
    Variavel.INDICACAO: "Indicação",
    Variavel.COMORBIDADE: "Comorbidades (as mais frequentes)",
    Variavel.SINTOMA: "Sintomas (as mais frequentes)",
    Variavel.EXAMINADOR: "Examinador",
}
_EM_ORDEM_DO_VALOR = frozenset({Variavel.FAIXA_ETARIA, Variavel.N_POLIPOS})


def barras_de(
    variavel: Variavel, itens: tuple[ItemFrequencia, ...]
) -> list[tuple[str, float, str]]:
    """Faixa etária e nº de lesões em ordem do valor; o resto, do mais frequente."""
    if variavel in _EM_ORDEM_DO_VALOR:
        itens = tuple(sorted(itens, key=lambda i: int(i.valor.split("-")[0])))
    return [(i.valor, i.percentual, f"{i.contagem} ({numero(i.percentual, 1)}%)") for i in itens]


class _Numero(QFrame):
    def __init__(self, titulo: str, pai: QWidget) -> None:
        super().__init__(pai)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.valor = com_papel(QLabel("—", self), "titulo")
        self.detalhe = rotulo("", "explicacao", self)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo(titulo, "explicacao", self))
        disposicao.addWidget(self.valor)
        disposicao.addWidget(self.detalhe)


class TelaPainel(QWidget):
    def __init__(self, sessao: Sessao) -> None:
        super().__init__()
        self._sessao = sessao
        self.pacientes = _Numero("Pacientes", self)
        self.exames = _Numero("Exames", self)
        self.prevalencia = _Numero("Exames com lesão", self)
        self.pendentes = _Numero("Aguardando histologia", self)
        self.vazio = rotulo("Ainda não há exames cadastrados.", "alerta", self)
        self.graficos = {v: GraficoDeBarras() for v in indicadores.VARIAVEIS_DO_PAINEL}
        self._montar()

    def _montar(self) -> None:
        numeros = QHBoxLayout()
        for cartao in (self.pacientes, self.exames, self.prevalencia, self.pendentes):
            numeros.addWidget(cartao)
        grade = QGridLayout()
        for posicao, (variavel, grafico) in enumerate(self.graficos.items()):
            grupo = QGroupBox(TITULOS[variavel])
            QVBoxLayout(grupo).addWidget(grafico)
            grade.addWidget(grupo, posicao // 2, posicao % 2)
        conteudo = QWidget()
        disposicao = QVBoxLayout(conteudo)
        # Sem isto a rolagem espreme o conteúdo na altura da janela e corta os gráficos.
        disposicao.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        disposicao.addWidget(rotulo("Painel", "titulo"))
        disposicao.addLayout(numeros)
        disposicao.addWidget(self.vazio)
        disposicao.addLayout(grade)
        disposicao.addStretch()
        rolagem = QScrollArea(self)
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(conteudo)
        QVBoxLayout(self).addWidget(rolagem)

    def atualizar(self) -> None:
        self.mostrar(indicadores.painel(self._sessao))

    def mostrar(self, painel: Painel) -> None:
        self.pacientes.valor.setText(str(painel.n_pacientes))
        self.exames.valor.setText(str(painel.n_exames))
        self.prevalencia.valor.setText(
            numero(100 * (painel.prevalencia_polipo.estimativa or 0), 1) + "%"
        )
        self.prevalencia.detalhe.setText(proporcao(painel.prevalencia_polipo))
        self.pendentes.valor.setText(str(painel.aguardando_histologia))
        self.pendentes.detalhe.setText("exames fora dos indicadores até o laudo")
        self.vazio.setVisible(painel.n_exames == 0)
        for variavel, grafico in self.graficos.items():
            grafico.definir(barras_de(variavel, painel.frequencias.get(variavel, ())))
