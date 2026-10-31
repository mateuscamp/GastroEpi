"""Estratificação: uma medida descrita por grupo, lida do banco."""

from pytestqt.qtbot import QtBot

from gastroepi.servicos import indicadores
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.indicadores import Variavel, VariavelNumerica
from gastroepi.ui_qt.calc_estratificacao import CalcEstratificacao
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import celula, clicar


def test_idade_por_sexo_e_retirada_por_indicacao(
    qtbot: QtBot, sessao: Sessao, capturar: Capturar
) -> None:
    tela = CalcEstratificacao(sessao)
    qtbot.addWidget(tela)
    tela.atualizar()
    capturar(tela, "46-estratificacao")
    assert tela.tabela.rowCount() == 2
    assert tela.grupo.currentText() == "Sexo"

    tela.grupo.definir(Variavel.INDICACAO)
    tela.medida.definir(VariavelNumerica.TEMPO_RETIRADA)
    clicar(qtbot, tela.calcular)

    esperado = indicadores.estratificacao(
        sessao, Variavel.INDICACAO, VariavelNumerica.TEMPO_RETIRADA
    )
    assert tela.tabela.rowCount() == len(esperado)
    assert celula(tela.tabela, 0, 0) == next(iter(esperado))
