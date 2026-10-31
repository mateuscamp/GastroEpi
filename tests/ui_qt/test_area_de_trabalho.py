"""Área de trabalho: navegar por todas as telas (com a captura de cada uma) e a faixa."""

from datetime import timedelta
from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import destino_externo
from gastroepi.servicos.acesso import Sessao, desbloquear
from gastroepi.ui_qt.area_de_trabalho import COPIA_ATRASADA, SOMENTE_LEITURA, AreaDeTrabalho
from gastroepi.ui_qt.textos import PARTE_ILEGIVEL
from tests.cofres_de_teste import SENHA, cofre_com_fichas, corromper_o_meio
from tests.ui_qt.conftest import Capturar, PerguntasProgramadas
from tests.ui_qt.formularios import clicar


def test_cada_tela_abre_e_e_capturada(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas, capturar: Capturar
) -> None:
    area = AreaDeTrabalho(sessao, perguntas)
    qtbot.addWidget(area)

    for posicao, nome in enumerate(area.nomes):
        area.ir_para_tela(nome)
        capturar(area, f"9{posicao}-area-{nome.lower().replace('á', 'a')}")
        assert area.pilha.currentIndex() == posicao

    assert area.faixa.isHidden() and area.restaurar.isHidden()
    assert area.usuario.text() == "Usuário: Usuário do GastroEpi"
    area.auditoria.usuario_mudou.emit("Operadora Fictícia")
    assert area.usuario.text() == "Usuário: Operadora Fictícia"
    with qtbot.waitSignal(area.bloquear_pedido):
        clicar(qtbot, area.bloquear)


def test_copia_externa_atrasada_aparece_na_faixa(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas, tmp_path: Path
) -> None:
    pendrive = tmp_path / "pendrive"
    pendrive.mkdir()
    destino_externo.configurar(sessao, pendrive, SENHA)

    area = AreaDeTrabalho(sessao, perguntas)
    qtbot.addWidget(area)

    assert area.faixa.text() == COPIA_ATRASADA
    assert sessao.relogio.agora() - timedelta(days=8) < sessao.relogio.agora()


def test_somente_leitura_mostra_a_faixa_e_o_restaurar(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas, capturar: Capturar
) -> None:
    cofre_com_fichas(tmp_path, quantidade=40)[0].fechar()
    corromper_o_meio(tmp_path)

    with desbloquear(tmp_path, SENHA) as sessao:
        area = AreaDeTrabalho(sessao, perguntas)
        qtbot.addWidget(area)
        capturar(area, "99-area-somente-leitura")

        assert area.faixa.text() == PARTE_ILEGIVEL  # a lista de pacientes caiu no defeito
        area.ir_para_tela("Exportar")
        assert area.faixa.text() == SOMENTE_LEITURA and not area.restaurar.isHidden()
        with qtbot.waitSignal(area.restaurar_pedido):
            clicar(qtbot, area.restaurar)
