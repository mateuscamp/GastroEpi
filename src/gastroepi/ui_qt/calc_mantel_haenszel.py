"""Mantel-Haenszel: OR combinado de estratos 2x2 e homogeneidade de Breslow-Day."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gastroepi.servicos import calculadoras
from gastroepi.servicos.calculadoras import EntradaInvalida, Estrato
from gastroepi.ui_qt.aparencia import rotulo
from gastroepi.ui_qt.calc_comum import Resultado, TabelaDeContagens, botao_calcular
from gastroepi.ui_qt.textos import com_ic, qui_quadrado

COLUNAS = ("Nome", "Expostos com", "Expostos sem", "Não expostos com", "Não expostos sem")


class CalcMantelHaenszel(QWidget):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.estratos = TabelaDeContagens(COLUNAS, 2, self)
        self.calcular = botao_calcular(self)
        self.resultado = Resultado(self)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Mantel-Haenszel", "subtitulo", self))
        disposicao.addWidget(rotulo("Um estrato por linha (ex.: faixa etária).", "explicacao"))
        disposicao.addWidget(self.estratos)
        disposicao.addWidget(self.calcular)
        disposicao.addWidget(self.resultado)
        self.calcular.clicked.connect(self._calcular)

    def _calcular(self) -> None:
        estratos: list[Estrato] = [(a, b, c, d) for a, b, c, d in self.estratos.contagens()]
        try:
            r = calculadoras.calcular_mantel_haenszel(estratos)
        except EntradaInvalida as erro:
            self.resultado.falhar(str(erro))
            return
        homogeneo = "sim" if r.p_valor_homogeneidade >= 0.05 else "não (os estratos diferem)"
        self.resultado.mostrar(
            [
                ("OR combinado", com_ic(r.odds_ratio, r.odds_ratio_ic)),
                (
                    "Qui-quadrado de Mantel-Haenszel",
                    qui_quadrado(r.qui_quadrado, r.p_valor),
                ),
                (
                    f"Breslow-Day ({r.graus_liberdade} gl)",
                    qui_quadrado(r.chi2_homogeneidade, r.p_valor_homogeneidade),
                ),
                ("Estratos homogêneos?", homogeneo),
            ]
        )
