"""Tendência de Cochran-Armitage em grupos ordenados e, na mesma tabela, o qui-quadrado
geral (casos e não casos por grupo, sem correção)."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gastroepi.servicos import calculadoras
from gastroepi.servicos.calculadoras import Direcao, EntradaInvalida
from gastroepi.ui_qt.aparencia import rotulo
from gastroepi.ui_qt.calc_comum import Resultado, TabelaDeContagens, botao_calcular
from gastroepi.ui_qt.textos import percentual, qui_quadrado

DIRECOES = {
    Direcao.CRESCENTE: "cresce ao longo dos grupos",
    Direcao.DECRESCENTE: "diminui ao longo dos grupos",
    Direcao.NEUTRA: "sem tendência",
}


class CalcTendencia(QWidget):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.grupos = TabelaDeContagens(("Nome", "Casos", "Total"), 3, self)
        self.calcular = botao_calcular(self)
        self.resultado = Resultado(self)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Tendência (Cochran-Armitage)", "subtitulo", self))
        disposicao.addWidget(
            rotulo("Os grupos vão na ordem natural (ex.: faixas de idade).", "explicacao", self)
        )
        disposicao.addWidget(self.grupos)
        disposicao.addWidget(self.calcular)
        disposicao.addWidget(self.resultado)
        self.calcular.clicked.connect(self._calcular)

    def _calcular(self) -> None:
        contagens = self.grupos.contagens()
        casos = [c for c, _ in contagens]
        totais = [t for _, t in contagens]
        try:
            tendencia = calculadoras.calcular_tendencia(casos, totais)
            geral = calculadoras.calcular_qui_quadrado_geral(
                [casos, [t - c for c, t in zip(casos, totais, strict=True)]]
            )
        except EntradaInvalida as erro:
            self.resultado.falhar(str(erro))
            return
        proporcoes = ", ".join(
            f"{nome}: {percentual(p)}"
            for nome, p in zip(self.grupos.nomes(), tendencia.proporcoes, strict=True)
        )
        self.resultado.mostrar(
            [
                ("Proporção por grupo", proporcoes),
                ("Tendência", DIRECOES[tendencia.direcao]),
                (
                    "Qui-quadrado de tendência (1 gl)",
                    qui_quadrado(tendencia.qui_quadrado, tendencia.p_valor),
                ),
                (
                    f"Qui-quadrado geral ({geral.graus_liberdade} gl)",
                    qui_quadrado(geral.qui_quadrado, geral.p_valor),
                ),
            ]
        )
