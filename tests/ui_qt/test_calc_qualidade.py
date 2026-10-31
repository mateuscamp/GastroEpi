"""Indicadores de qualidade por examinador lidos do banco, com os alertas em frase."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos import indicadores
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.indicadores import Alerta, Indicador
from gastroepi.ui_qt.calc_qualidade import CalcQualidade, celulas_do_examinador, texto_do_alerta
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import celula


def test_uma_linha_por_examinador(qtbot: QtBot, sessao: Sessao, capturar: Capturar) -> None:
    tela = CalcQualidade(sessao)
    qtbot.addWidget(tela)
    tela.atualizar()
    capturar(tela, "40-qualidade")

    linhas = indicadores.indicadores_de_qualidade(sessao)
    assert tela.tabela.rowCount() == len(linhas)
    assert celula(tela.tabela, 0, 0) == celulas_do_examinador(linhas[0])[0]
    assert tela.prevalencia.text().startswith("Exames com ao menos uma lesão:")


def test_texto_do_alerta() -> None:
    abaixo = Alerta(Indicador.DETECCAO_ADENOMA, 0.2, 0.35, True)
    talvez = Alerta(Indicador.SERRILHADA_SESSIL, 0.04, 0.06, False)
    retirada = Alerta(Indicador.TEMPO_RETIRADA, 6.5, 8.0, False)

    assert texto_do_alerta(abaixo) == "adenoma abaixo de 35%"
    assert (
        texto_do_alerta(talvez)
        == "serrilhada séssil abaixo de 6% (pode ser acaso: IC inclui a meta)"
    )
    assert texto_do_alerta(retirada) == "retirada abaixo de 8 min"
