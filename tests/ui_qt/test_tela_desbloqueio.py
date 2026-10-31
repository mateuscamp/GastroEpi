"""Tela de desbloqueio dirigida pelo qtbot, contra o cofre real em tmp_path."""

import re
from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import durabilidade
from gastroepi.servicos.acesso import (
    NOME_DA_CHAVE,
    BancoIlegivel,
    Sessao,
    cofre_existe,
    desbloquear,
)
from gastroepi.ui_qt.tela_desbloqueio import TelaDesbloqueio
from tests.cofres_de_teste import SENHA, cofre_com_fichas, corromper_a_pagina_1
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar, digitar

BLOCO = re.compile(r"[0-9A-HJKMNP-TV-Z]{8}")


def test_cenario_1_senha_duas_vezes_mostra_a_recovery_key_em_blocos_de_8(
    qtbot: QtBot, tmp_path: Path
) -> None:
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)

    digitar(qtbot, tela.criar.senha, SENHA)
    digitar(qtbot, tela.criar.confirmacao, SENHA)
    clicar(qtbot, tela.criar.botao)

    blocos = tela.chave.blocos_mostrados()
    assert len(blocos) == 8
    assert all(BLOCO.fullmatch(bloco) for bloco in blocos)
    assert cofre_existe(tmp_path)
    assert not tela.chave.botao_entrar.isEnabled()

    tela.chave.anotei.setChecked(True)
    with qtbot.waitSignal(tela.desbloqueado, timeout=1000) as sinal:
        clicar(qtbot, tela.chave.botao_entrar)
    sessao = sinal.args[0]
    assert isinstance(sessao, Sessao)
    sessao.fechar()


def test_criar_mostra_a_tela_de_criar_e_a_captura(
    qtbot: QtBot, tmp_path: Path, capturar: Capturar
) -> None:
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)
    capturar(tela, "01-criar-senha")

    digitar(qtbot, tela.criar.senha, SENHA)
    digitar(qtbot, tela.criar.confirmacao, SENHA + "x")
    clicar(qtbot, tela.criar.botao)

    assert tela.criar.erro.text() == "As duas senhas digitadas não são iguais"
    assert not cofre_existe(tmp_path)

    tela.criar.confirmacao.clear()
    digitar(qtbot, tela.criar.confirmacao, SENHA)
    clicar(qtbot, tela.criar.botao)
    capturar(tela, "02-recovery-key")
    assert tela.criar.senha.text() == ""  # a senha não fica no campo
    tela.chave.anotei.setChecked(True)
    with qtbot.waitSignal(tela.desbloqueado) as sinal:
        clicar(qtbot, tela.chave.botao_entrar)
    sinal.args[0].fechar()
    assert tela.chave.blocos_mostrados() == [""] * 8  # a chave some da tela


def test_entrar_com_senha_errada_e_depois_certa(
    qtbot: QtBot, tmp_path: Path, capturar: Capturar
) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)
    assert tela.paginas.currentWidget() is tela.entrar

    digitar(qtbot, tela.entrar.senha, "senha errada")
    clicar(qtbot, tela.entrar.botao)
    capturar(tela, "03-senha-incorreta")
    assert tela.entrar.erro.text() == "Senha incorreta"
    assert tela.entrar.senha.text() == ""

    digitar(qtbot, tela.entrar.senha, SENHA)
    with qtbot.waitSignal(tela.desbloqueado) as sinal:
        clicar(qtbot, tela.entrar.botao)
    assert not sinal.args[0].somente_leitura
    sinal.args[0].fechar()


def test_esqueci_a_senha_entra_pela_recovery_key_e_troca_a_senha(
    qtbot: QtBot, tmp_path: Path, capturar: Capturar
) -> None:
    sessao, recovery_key = cofre_com_fichas(tmp_path, quantidade=1)
    sessao.fechar()
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)
    clicar(qtbot, tela.entrar.esqueci)
    capturar(tela, "04-recuperar")

    digitar(qtbot, tela.recuperar.recovery_key, "AAAAAAAA")
    digitar(qtbot, tela.recuperar.senha, "senha nova longa")
    digitar(qtbot, tela.recuperar.confirmacao, "senha nova longa")
    clicar(qtbot, tela.recuperar.botao)
    assert "8 blocos" in tela.recuperar.erro.text()

    tela.recuperar.recovery_key.setText(recovery_key.lower().replace(" ", ""))
    with qtbot.waitSignal(tela.desbloqueado) as sinal:
        clicar(qtbot, tela.recuperar.botao)
    sinal.args[0].fechar()
    with desbloquear(tmp_path, "senha nova longa"):
        pass


def test_voltar_da_recuperacao_para_a_senha(qtbot: QtBot, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)

    clicar(qtbot, tela.entrar.esqueci)
    clicar(qtbot, tela.recuperar.voltar)

    assert tela.paginas.currentWidget() is tela.entrar


def test_sem_arquivo_de_chave_leva_a_recuperacao(qtbot: QtBot, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()
    (tmp_path / NOME_DA_CHAVE).unlink()
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)

    digitar(qtbot, tela.entrar.senha, SENHA)
    clicar(qtbot, tela.entrar.botao)

    assert tela.paginas.currentWidget() is tela.recuperar
    assert "recovery key" in tela.recuperar.erro.text()


def test_pagina_1_estragada_avisa_a_janela_com_o_backup_oferecido(
    qtbot: QtBot, tmp_path: Path
) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=3)
    with sessao:
        durabilidade.fazer_backup(sessao)
    corromper_a_pagina_1(tmp_path)
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)

    digitar(qtbot, tela.entrar.senha, SENHA)
    with qtbot.waitSignal(tela.banco_ilegivel) as sinal:
        clicar(qtbot, tela.entrar.botao)

    assert isinstance(sinal.args[0], BancoIlegivel)
    assert sinal.args[0].backup_oferecido is not None


def test_blocos_da_recovery_key_cabem_inteiros(qtbot: QtBot, tmp_path: Path) -> None:
    """Achado na captura da Fase 5: com letra espaçada, o rótulo cortava o 1º caractere."""
    tela = TelaDesbloqueio(tmp_path)
    qtbot.addWidget(tela)
    tela.resize(1200, 780)
    tela.show()
    tela.criar.senha.setText(SENHA)
    tela.criar.confirmacao.setText(SENHA)
    clicar(qtbot, tela.criar.botao)
    qtbot.wait(20)

    for bloco in tela.chave.blocos:
        assert bloco.width() >= bloco.sizeHint().width(), bloco.text()
    tela.chave.anotei.setChecked(True)
    with qtbot.waitSignal(tela.desbloqueado) as sinal:
        clicar(qtbot, tela.chave.botao_entrar)
    sinal.args[0].fechar()
