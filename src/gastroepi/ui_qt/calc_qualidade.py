"""Indicadores de qualidade por examinador (ACG/ASGE 2024), lidos do banco.

Cada célula mostra a estimativa e o IC de Wilson; o alerta diz a meta e se o IC inteiro
está abaixo dela (aí a diferença não se explica por poucos exames). Exame com lesão
aguardando histologia fica fora dos indicadores histológicos e é contado à parte.
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gastroepi.servicos import indicadores
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.indicadores import (
    Alerta,
    Indicador,
    IndicadoresDoExaminador,
    Media,
    Proporcao,
)
from gastroepi.ui_qt.aparencia import rotulo
from gastroepi.ui_qt.dialogo_exame import rotulo_do_examinador
from gastroepi.ui_qt.textos import numero, percentual, proporcao

COLUNAS = (
    "Examinador", "Exames", "Detecção de adenoma", "Adenoma avançado",
    "Lesão serrilhada séssil", "Intubação cecal", "Preparo adequado",
    "Retirada (min, sem lesão)", "Aguardando histologia", "Alertas",
)  # fmt: skip
NOMES = {
    Indicador.DETECCAO_ADENOMA: "adenoma",
    Indicador.SERRILHADA_SESSIL: "serrilhada séssil",
    Indicador.INTUBACAO_CECAL: "intubação cecal",
    Indicador.PREPARO_ADEQUADO: "preparo adequado",
    Indicador.TEMPO_RETIRADA: "retirada",
}


def _proporcao_curta(valor: Proporcao) -> str:
    return proporcao(valor).replace(" (IC 95%:", "\n(IC 95%:")


def _media(valor: Media) -> str:
    return "—" if valor.media is None else f"{numero(valor.media, 1)} (n = {valor.n})"


def texto_do_alerta(alerta: Alerta) -> str:
    if alerta.indicador is Indicador.TEMPO_RETIRADA:
        return f"retirada abaixo de {numero(alerta.limiar, 0)} min"
    meta = percentual(alerta.limiar, 0)
    certeza = "" if alerta.ic_abaixo else " (pode ser acaso: IC inclui a meta)"
    return f"{NOMES[alerta.indicador]} abaixo de {meta}{certeza}"


def celulas_do_examinador(linha: IndicadoresDoExaminador) -> tuple[str, ...]:
    return (
        rotulo_do_examinador(linha.examinador),
        str(linha.n_exames),
        _proporcao_curta(linha.deteccao_adenoma),
        _proporcao_curta(linha.adenoma_avancado),
        _proporcao_curta(linha.serrilhada_sessil),
        _proporcao_curta(linha.intubacao_cecal),
        _proporcao_curta(linha.preparo_adequado),
        _media(linha.tempo_retirada),
        str(linha.aguardando_histologia),
        "\n".join(texto_do_alerta(a) for a in linha.alertas) or "nenhum",
    )


class CalcQualidade(QWidget):
    def __init__(self, sessao: Sessao, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self._sessao = sessao
        self.prevalencia = rotulo("", "", self)
        self.tabela = QTableWidget(0, len(COLUNAS), self)
        self.tabela.setHorizontalHeaderLabels(list(COLUNAS))
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setWordWrap(True)
        self.tabela.verticalHeader().hide()
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Indicadores de qualidade por examinador", "subtitulo"))
        disposicao.addWidget(
            rotulo(
                "Metas da ACG/ASGE 2024: adenoma ≥ 35%, serrilhada séssil ≥ 6%, intubação cecal"
                " ≥ 95%, preparo adequado ≥ 90% e retirada ≥ 8 min. A detecção conta exames a"
                " partir de 45 anos, de rastreio, vigilância ou por sintomas.",
                "explicacao",
            )
        )
        disposicao.addWidget(self.prevalencia)
        disposicao.addWidget(self.tabela)

    def atualizar(self) -> None:
        prevalencia = indicadores.prevalencia_polipo(self._sessao)
        self.prevalencia.setText(f"Exames com ao menos uma lesão: {proporcao(prevalencia)}")
        linhas = indicadores.indicadores_de_qualidade(self._sessao)
        self.tabela.setRowCount(len(linhas))
        for indice, linha in enumerate(linhas):
            for coluna, texto in enumerate(celulas_do_examinador(linha)):
                self.tabela.setItem(indice, coluna, QTableWidgetItem(texto))
        self.tabela.resizeColumnsToContents()
        self.tabela.resizeRowsToContents()
