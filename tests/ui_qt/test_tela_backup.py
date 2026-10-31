"""Backup: o manual, a lista e o destino externo, contra o cofre real."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import destino_externo, durabilidade
from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.tela_backup import TelaBackup
from tests.cofres_de_teste import SENHA
from tests.ui_qt.conftest import Capturar, PerguntasProgramadas
from tests.ui_qt.formularios import clicar


def _tela(qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas) -> TelaBackup:
    tela = TelaBackup(sessao, perguntas)
    qtbot.addWidget(tela)
    tela.atualizar()
    return tela


def test_backup_manual_entra_na_lista(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas, capturar: Capturar
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    assert tela.lista.count() == 0 and not tela.copiar.isEnabled()

    clicar(qtbot, tela.fazer)
    capturar(tela, "60-backup")

    assert tela.lista.count() == len(durabilidade.backups_do_cofre(sessao)) == 1
    assert tela.aviso.text() == "Backup feito e conferido."
    assert tela.situacao.text() == "Nenhuma pasta de destino escolhida."


def test_destino_externo_escolher_copiar_e_parar(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas, tmp_path: Path
) -> None:
    pendrive = tmp_path / "pendrive"
    pendrive.mkdir()
    tela = _tela(qtbot, sessao, perguntas)

    clicar(qtbot, tela.escolher)  # cancelou a escolha da pasta
    perguntas.pasta_escolhida = pendrive
    tela.senha.setText("senha errada")
    clicar(qtbot, tela.escolher)
    assert tela.aviso.text() == "Senha incorreta"

    tela.senha.setText(SENHA)
    clicar(qtbot, tela.escolher)
    assert "Última cópia: nunca" in tela.situacao.text()
    clicar(qtbot, tela.copiar)
    assert tela.aviso.text() == "Ainda não há backup local para copiar"

    clicar(qtbot, tela.fazer)
    clicar(qtbot, tela.copiar)
    assert tela.aviso.text().startswith("Último backup copiado")
    assert any((pendrive / destino_externo.PASTA_NO_DESTINO).iterdir())

    clicar(qtbot, tela.remover)
    assert destino_externo.situacao(sessao) is None
