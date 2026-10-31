"""Assistente de restauração: explica o defeito, pede a senha e restaura (ADR-0005)."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import durabilidade, pacientes
from gastroepi.servicos.acesso import desbloquear
from gastroepi.ui_qt.assistente_restauracao import AssistenteDeRestauracao, explicacao_do_defeito
from tests.cofres_de_teste import SENHA, cofre_com_fichas, corromper_o_meio
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar


def test_restaura_o_backup_oferecido_e_guarda_o_estragado(
    qtbot: QtBot, tmp_path: Path, capturar: Capturar
) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=40)
    with sessao:
        durabilidade.fazer_backup(sessao)
    corromper_o_meio(tmp_path)
    with desbloquear(tmp_path, SENHA) as somente_leitura:
        oferecido = somente_leitura.backup_oferecido
    assert oferecido is not None
    fechadas: list[bool] = []
    assistente = AssistenteDeRestauracao(
        tmp_path, oferecido, abriu=True, antes_de_restaurar=lambda: fechadas.append(True)
    )
    qtbot.addWidget(assistente)
    capturar(assistente, "80-restaurar")

    assistente.senha.setText("senha errada")
    clicar(qtbot, assistente.restaurar)
    assert assistente.erro.text() == "Senha incorreta"

    assistente.senha.setText(SENHA)
    with qtbot.waitSignal(assistente.restaurado) as sinal:
        clicar(qtbot, assistente.restaurar)

    restaurada = sinal.args[0]
    assert not restaurada.somente_leitura and len(pacientes.listar(restaurada)) == 40
    restaurada.fechar()
    assert fechadas == [True, True]
    assert any(p.name.startswith("gastroepi.db.corrompido-") for p in tmp_path.iterdir())


def test_sem_backup_bom_so_explica(qtbot: QtBot, tmp_path: Path) -> None:
    assistente = AssistenteDeRestauracao(tmp_path, None, abriu=False)
    qtbot.addWidget(assistente)

    assert assistente.restaurar.isHidden() and assistente.senha.isHidden()
    assert assistente.depois.text() == "Fechar"
    assert "não abre" in explicacao_do_defeito(None, abriu=False)
    assert "só para leitura" in explicacao_do_defeito(None, abriu=True)
