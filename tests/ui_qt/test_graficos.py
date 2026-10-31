"""Gráfico de barras: altura pelo nº de barras e no máximo 12."""

from pytestqt.qtbot import QtBot

from gastroepi.ui_qt.graficos import GraficoDeBarras
from tests.ui_qt.conftest import Capturar


def test_altura_acompanha_as_barras_e_corta_no_maximo(qtbot: QtBot, capturar: Capturar) -> None:
    grafico = GraficoDeBarras(maximo_de_barras=3)
    qtbot.addWidget(grafico)
    vazio = grafico.sizeHint().height()

    grafico.definir([(f"Item {n}", float(n), str(n)) for n in range(5)])
    capturar(grafico, "grafico-de-barras")

    assert len(grafico.barras()) == 3
    assert grafico.height() == grafico.sizeHint().height() > vazio


def test_grafico_vazio_desenha_sem_erro(qtbot: QtBot, capturar: Capturar) -> None:
    grafico = GraficoDeBarras()
    qtbot.addWidget(grafico)
    grafico.definir([("Zero", 0.0, "0")])
    capturar(grafico, "grafico-zerado")

    assert grafico.barras() == [("Zero", 0.0, "0")]
