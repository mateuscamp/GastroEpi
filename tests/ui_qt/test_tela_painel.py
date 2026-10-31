"""Painel: números e gráficos do banco; vazio avisa que não há exames."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import indicadores
from gastroepi.servicos.acesso import Sessao, criar_cofre
from gastroepi.servicos.indicadores import ItemFrequencia, Variavel
from gastroepi.ui_qt.tela_painel import TelaPainel, barras_de
from tests.cofres_de_teste import SENHA
from tests.ui_qt.conftest import Capturar


def test_painel_mostra_os_numeros_do_banco(
    qtbot: QtBot, sessao: Sessao, capturar: Capturar
) -> None:
    tela = TelaPainel(sessao)
    qtbot.addWidget(tela)
    tela.atualizar()
    capturar(tela, "30-painel")
    painel = indicadores.painel(sessao)

    assert tela.pacientes.valor.text() == "30"
    assert tela.exames.valor.text() == str(painel.n_exames)
    assert tela.vazio.isHidden()
    assert len(tela.graficos[Variavel.SEXO].barras()) == 2


def test_painel_vazio(qtbot: QtBot, tmp_path: Path) -> None:
    sessao, _ = criar_cofre(tmp_path, SENHA, SENHA)
    with sessao:
        tela = TelaPainel(sessao)
        qtbot.addWidget(tela)
        tela.atualizar()

        assert not tela.vazio.isHidden()
        assert tela.prevalencia.detalhe.text() == "nenhum exame"


def test_faixa_etaria_e_lesoes_ficam_em_ordem_do_valor() -> None:
    itens = (ItemFrequencia("60-69", 5, 50.0), ItemFrequencia("40-49", 3, 30.0))
    lesoes = (ItemFrequencia("10", 1, 10.0), ItemFrequencia("2", 9, 90.0))

    assert [b[0] for b in barras_de(Variavel.FAIXA_ETARIA, itens)] == ["40-49", "60-69"]
    assert [b[0] for b in barras_de(Variavel.N_POLIPOS, lesoes)] == ["2", "10"]
    assert barras_de(Variavel.SEXO, itens)[0] == ("60-69", 50.0, "5 (50,0%)")
