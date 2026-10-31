"""Janela principal: desbloquear, bloquear (botão e inatividade), backup e restauração."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import durabilidade, pacientes
from gastroepi.servicos.acesso import NOME_DO_BANCO, criar_cofre
from gastroepi.servicos.durabilidade import INTERVALO_DO_BACKUP
from gastroepi.servicos.sessao import PASTA_DE_BACKUPS
from gastroepi.ui_qt.janela_principal import JanelaPrincipal
from tests.cofres_de_teste import SENHA, cofre_com_fichas, corromper_a_pagina_1, corromper_o_meio
from tests.conftest import RelogioManual
from tests.ui_qt.conftest import Capturar, PerguntasProgramadas
from tests.ui_qt.formularios import clicar


@pytest.fixture
def janela(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas
) -> Iterator[JanelaPrincipal]:
    aberta = JanelaPrincipal(tmp_path, perguntas)
    qtbot.addWidget(aberta)
    yield aberta
    aberta.close()


def _entrar(qtbot: QtBot, janela: JanelaPrincipal) -> None:
    janela.desbloqueio.entrar.senha.setText(SENHA)
    clicar(qtbot, janela.desbloqueio.entrar.botao)


def test_criar_entrar_bloquear_e_entrar_de_novo(
    qtbot: QtBot, janela: JanelaPrincipal, capturar: Capturar
) -> None:
    capturar(janela, "00-janela-criar-senha")
    janela.desbloqueio.criar.senha.setText(SENHA)
    janela.desbloqueio.criar.confirmacao.setText(SENHA)
    clicar(qtbot, janela.desbloqueio.criar.botao)
    janela.desbloqueio.chave.anotei.setChecked(True)
    clicar(qtbot, janela.desbloqueio.chave.botao_entrar)
    assert janela.area is not None and janela.pilha.currentWidget() is janela.area
    capturar(janela, "05-janela-aberta")

    clicar(qtbot, janela.area.bloquear)
    assert janela.sessao is None and janela.pilha.currentWidget() is janela.desbloqueio
    capturar(janela, "06-janela-bloqueada")

    _entrar(qtbot, janela)
    assert janela.sessao is not None and not janela.sessao.somente_leitura


def test_inatividade_bloqueia(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas
) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()
    janela = JanelaPrincipal(tmp_path, perguntas, inatividade=timedelta(milliseconds=80))
    qtbot.addWidget(janela)
    _entrar(qtbot, janela)
    assert janela.sessao is not None

    qtbot.waitUntil(lambda: janela.sessao is None, timeout=2000)

    assert janela.pilha.currentWidget() is janela.desbloqueio
    janela.close()


def test_tique_e_fechar_fazem_o_backup(qtbot: QtBot, janela: JanelaPrincipal) -> None:
    relogio = RelogioManual()
    sessao, _ = criar_cofre(janela.pasta, SENHA, SENHA, relogio)
    janela.abrir_sessao(sessao)
    janela.tique_do_backup()
    assert durabilidade.backups_do_cofre(sessao) == []

    primeira, segunda = gerar_fichas(semente=1, quantidade=2)
    pacientes.cadastrar(sessao, primeira, "teste")
    relogio.avancar(INTERVALO_DO_BACKUP)
    janela.tique_do_backup()
    assert len(durabilidade.backups_do_cofre(sessao)) == 1

    pacientes.cadastrar(sessao, segunda, "teste")
    relogio.avancar(timedelta(days=1))
    janela.close()
    assert len(list((janela.pasta / PASTA_DE_BACKUPS).iterdir())) == 2


def test_backup_automatico_que_falha_avisa_na_faixa(qtbot: QtBot, janela: JanelaPrincipal) -> None:
    relogio = RelogioManual()
    sessao, _ = criar_cofre(janela.pasta, SENHA, SENHA, relogio)
    janela.abrir_sessao(sessao)
    pacientes.cadastrar(sessao, gerar_fichas(semente=1, quantidade=1)[0], "teste")
    (janela.pasta / PASTA_DE_BACKUPS).write_text("um arquivo no lugar da pasta")
    relogio.avancar(INTERVALO_DO_BACKUP)

    janela.tique_do_backup()

    assert janela.area is not None
    assert janela.area.faixa.text().startswith("O backup automático falhou")
    janela.close()  # o backup ao fechar também falha, e fechar não trava


def test_banco_com_defeito_oferece_restaurar_e_restaura(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas, capturar: Capturar
) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=40)
    with sessao:
        durabilidade.fazer_backup(sessao)
    corromper_o_meio(tmp_path)
    janela = JanelaPrincipal(tmp_path, perguntas)
    qtbot.addWidget(janela)

    _entrar(qtbot, janela)
    assistente = janela.assistente
    assert janela.sessao is not None and janela.sessao.somente_leitura and assistente is not None
    capturar(janela, "07-janela-somente-leitura")
    assistente.senha.setText(SENHA)
    clicar(qtbot, assistente.restaurar)

    assert janela.sessao is not None and not janela.sessao.somente_leitura
    assert len(pacientes.listar(janela.sessao)) == 40
    janela.close()


def test_pagina_1_estragada_abre_o_assistente_sem_sessao(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas
) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=3)
    with sessao:
        durabilidade.fazer_backup(sessao)
    corromper_a_pagina_1(tmp_path)
    janela = JanelaPrincipal(tmp_path, perguntas)
    qtbot.addWidget(janela)

    _entrar(qtbot, janela)

    assert janela.sessao is None and janela.assistente is not None
    assert janela.assistente.depois.text() == "Fechar"
    assert (tmp_path / NOME_DO_BANCO).exists()
    janela.close()


def test_botao_restaurar_da_faixa_abre_o_assistente(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas
) -> None:
    cofre_com_fichas(tmp_path, quantidade=40)[0].fechar()
    corromper_o_meio(tmp_path)
    janela = JanelaPrincipal(tmp_path, perguntas)
    qtbot.addWidget(janela)
    _entrar(qtbot, janela)
    assert janela.assistente is not None and janela.area is not None
    primeiro = janela.assistente
    clicar(qtbot, primeiro.depois)  # "Agora não": segue em somente leitura

    clicar(qtbot, janela.area.restaurar)

    assert janela.assistente is not primeiro and janela.assistente.isVisible()
    janela.encerrar_sessao()
    janela._restaurar_pedido()  # sem sessão não há o que oferecer
    janela.tique_do_backup()  # nem backup a fazer
    janela.close()
