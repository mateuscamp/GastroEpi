"""Gráfico de barras horizontais desenhado com QPainter.

O PySide6-Essentials não traz o QtCharts (está no Addons, que pesa no instalador,
ADR-0002). Barra horizontal lê bem com rótulo comprido (indicação, comorbidade) e
mostra o número escrito ao lado: a cor não é o único sinal.
"""

from collections.abc import Sequence

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

_ALTURA_DA_BARRA = 22
_ESPACO = 6
_COR_DA_BARRA = QColor("#2563eb")
_COR_DO_TEXTO = QColor("#1f2937")


class GraficoDeBarras(QWidget):
    def __init__(self, pai: QWidget | None = None, maximo_de_barras: int = 12) -> None:
        super().__init__(pai)
        self._barras: list[tuple[str, float, str]] = []
        self._maximo_de_barras = maximo_de_barras
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def definir(self, barras: Sequence[tuple[str, float, str]]) -> None:
        """(rótulo, valor, texto do valor). Passando do máximo, ficam as primeiras."""
        self._barras = list(barras)[: self._maximo_de_barras]
        self.setFixedHeight(self.sizeHint().height())
        self.update()

    def barras(self) -> list[tuple[str, float, str]]:
        return list(self._barras)

    def sizeHint(self) -> QSize:
        return QSize(420, max(1, len(self._barras)) * (_ALTURA_DA_BARRA + _ESPACO) + _ESPACO)

    def paintEvent(self, evento: QPaintEvent) -> None:
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        largura_do_rotulo = self.width() * 0.38
        largura_util = self.width() - largura_do_rotulo - 90
        maior = max((valor for _, valor, _ in self._barras), default=0) or 1
        for posicao, (texto, valor, texto_do_valor) in enumerate(self._barras):
            topo = _ESPACO + posicao * (_ALTURA_DA_BARRA + _ESPACO)
            caixa = QRectF(0, topo, largura_do_rotulo - 8, _ALTURA_DA_BARRA)
            pintor.setPen(_COR_DO_TEXTO)
            alinhamento = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            elidido = pintor.fontMetrics().elidedText(
                texto, Qt.TextElideMode.ElideRight, int(caixa.width())
            )
            pintor.drawText(caixa, alinhamento, elidido)
            comprimento = max(2.0, largura_util * valor / maior)
            pintor.fillRect(
                QRectF(largura_do_rotulo, topo, comprimento, _ALTURA_DA_BARRA), _COR_DA_BARRA
            )
            fim = QRectF(largura_do_rotulo + comprimento + 6, topo, 84, _ALTURA_DA_BARRA)
            pintor.drawText(
                fim, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, texto_do_valor
            )
        pintor.end()
