"""Estratificação: uma medida (idade, nº de lesões, retirada) descrita por grupo."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gastroepi.servicos import indicadores
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.indicadores import Descritivas, Variavel, VariavelNumerica
from gastroepi.ui_qt.aparencia import rotulo
from gastroepi.ui_qt.calc_comum import botao_calcular
from gastroepi.ui_qt.campos_da_tela import ComboDeLista
from gastroepi.ui_qt.tela_painel import TITULOS
from gastroepi.ui_qt.textos import numero

COLUNAS = (
    "Grupo",
    "n",
    "Média",
    "Desvio padrão",
    "Mediana",
    "1º quartil",
    "3º quartil",
    "Mín.",
    "Máx.",
)


def celulas_das_descritivas(grupo: str, d: Descritivas) -> tuple[str, ...]:
    medidas = (d.media, d.desvio_padrao, d.mediana, d.q1, d.q3, d.minimo, d.maximo)
    return (grupo, str(d.n), *(numero(m, 1) for m in medidas))


class CalcEstratificacao(QWidget):
    def __init__(self, sessao: Sessao, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self._sessao = sessao
        self.grupo = ComboDeLista(Variavel, self)
        for indice, variavel in enumerate(Variavel):
            self.grupo.setItemText(indice, TITULOS[variavel])
        self.grupo.definir(Variavel.SEXO)
        self.medida = ComboDeLista(VariavelNumerica, self)
        for indice, nome in enumerate(("Idade no exame", "Nº de lesões", "Tempo de retirada")):
            self.medida.setItemText(indice, nome)
        self.medida.definir(VariavelNumerica.IDADE)
        self.calcular = botao_calcular(self)
        self.tabela = QTableWidget(0, len(COLUNAS), self)
        self.tabela.setHorizontalHeaderLabels(list(COLUNAS))
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        formulario = QFormLayout()
        formulario.addRow("Agrupar por", self.grupo)
        formulario.addRow("Medida", self.medida)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Estratificação", "subtitulo", self))
        disposicao.addLayout(formulario)
        disposicao.addWidget(self.calcular)
        disposicao.addWidget(self.tabela)
        self.calcular.clicked.connect(self.atualizar)

    def atualizar(self) -> None:
        grupo, medida = self.grupo.valor(), self.medida.valor()
        assert grupo is not None and medida is not None  # começam escolhidos
        estratos = indicadores.estratificacao(self._sessao, grupo, medida)
        self.tabela.setRowCount(len(estratos))
        for linha, (nome, descritivas) in enumerate(estratos.items()):
            for coluna, texto in enumerate(celulas_das_descritivas(nome, descritivas)):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(texto))
        self.tabela.resizeColumnsToContents()
