"""Tamanho de amostra: inquérito (uma proporção) e estudo comparativo (Fleiss).

As proporções são digitadas em %, como na v0.1.16, e vão ao serviço como fração.
"""

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QWidget

from gastroepi.servicos import calculadoras
from gastroepi.servicos.calculadoras import EntradaInvalida
from gastroepi.ui_qt.calc_comum import Resultado, botao_calcular
from gastroepi.ui_qt.campos_da_tela import InteiroOpcional


def caixa_de_percentual(valor: float, pai: QWidget) -> QDoubleSpinBox:
    caixa = QDoubleSpinBox(pai)
    caixa.setRange(0.0, 100.0)
    caixa.setDecimals(1)
    caixa.setSuffix(" %")
    caixa.setValue(valor)
    return caixa


class _Inquerito(QGroupBox):
    def __init__(self, pai: QWidget) -> None:
        super().__init__("Inquérito (estimar uma proporção)", pai)
        self.p = caixa_de_percentual(50.0, self)
        self.d = caixa_de_percentual(5.0, self)
        self.confianca = caixa_de_percentual(95.0, self)
        self.populacao = InteiroOpcional(100_000_000, "infinita", self)
        self.calcular = botao_calcular(self)
        self.resultado = Resultado(self)
        formulario = QFormLayout(self)
        formulario.addRow("Frequência esperada", self.p)
        formulario.addRow("Margem de erro", self.d)
        formulario.addRow("Confiança", self.confianca)
        formulario.addRow("População", self.populacao)
        formulario.addRow(self.calcular)
        formulario.addRow(self.resultado)
        self.calcular.clicked.connect(self._calcular)

    def _calcular(self) -> None:
        try:
            n = calculadoras.calcular_amostra_inquerito(
                self.p.value() / 100,
                self.d.value() / 100,
                self.confianca.value() / 100,
                self.populacao.valor(),
            )
        except EntradaInvalida as erro:
            self.resultado.falhar(str(erro))
            return
        self.resultado.mostrar([("Amostra necessária", f"{n} participantes")])


class _Comparativo(QGroupBox):
    def __init__(self, pai: QWidget) -> None:
        super().__init__("Estudo comparativo (duas proporções, Fleiss)", pai)
        self.poder = caixa_de_percentual(80.0, self)
        self.confianca = caixa_de_percentual(95.0, self)
        self.razao = QDoubleSpinBox(self)
        self.razao.setRange(0.0, 100.0)
        self.razao.setValue(1.0)
        self.p0 = caixa_de_percentual(20.0, self)
        self.p1 = caixa_de_percentual(35.0, self)
        self.calcular = botao_calcular(self)
        self.resultado = Resultado(self)
        formulario = QFormLayout(self)
        formulario.addRow("Poder", self.poder)
        formulario.addRow("Confiança", self.confianca)
        formulario.addRow("Não expostos por exposto", self.razao)
        formulario.addRow("Desfecho nos não expostos", self.p0)
        formulario.addRow("Desfecho nos expostos", self.p1)
        formulario.addRow(self.calcular)
        formulario.addRow(self.resultado)
        self.calcular.clicked.connect(self._calcular)

    def _calcular(self) -> None:
        try:
            n = calculadoras.calcular_amostra_comparativa(
                self.poder.value() / 100,
                self.confianca.value() / 100,
                self.razao.value(),
                self.p0.value() / 100,
                self.p1.value() / 100,
            )
        except EntradaInvalida as erro:
            self.resultado.falhar(str(erro))
            return
        self.resultado.mostrar(
            [
                ("Expostos", str(n.expostos)),
                ("Não expostos", str(n.nao_expostos)),
                ("Total", str(n.total)),
            ]
        )


class CalcAmostra(QWidget):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.inquerito = _Inquerito(self)
        self.comparativo = _Comparativo(self)
        disposicao = QHBoxLayout(self)
        disposicao.addWidget(self.inquerito)
        disposicao.addWidget(self.comparativo)
