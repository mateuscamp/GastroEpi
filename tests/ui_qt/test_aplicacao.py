"""Ponto de entrada: abre a janela com a trava e recusa a segunda instância."""

from pathlib import Path

from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from gastroepi.servicos import durabilidade
from gastroepi.servicos.durabilidade import OutraInstanciaAberta
from gastroepi.ui_qt.aplicacao import aplicacao_qt, rodar
from gastroepi.ui_qt.janela_principal import JanelaPrincipal
from tests.cofres_de_teste import cofre_com_fichas


def test_rodar_abre_desbloqueado_com_a_sessao_e_segura_a_trava(
    qtbot: QtBot, tmp_path: Path
) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=2)
    janelas: list[JanelaPrincipal] = []
    travado_durante: list[bool] = []

    def laco() -> int:
        try:
            durabilidade.travar_instancia(tmp_path).soltar()
        except OutraInstanciaAberta:
            travado_durante.append(True)
        return 0

    codigo = rodar(tmp_path, sessao, ao_abrir=janelas.append, laco_de_eventos=laco)

    assert codigo == 0 and travado_durante == [True]
    (janela,) = janelas
    qtbot.addWidget(janela)
    assert janela.sessao is sessao and janela.isVisible()
    janela.close()
    assert janela.sessao is None
    assert aplicacao_qt() is QApplication.instance()


def test_segunda_instancia_e_recusada(qtbot: QtBot, tmp_path: Path) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=1)
    avisos: list[str] = []

    with durabilidade.travar_instancia(tmp_path):
        codigo = rodar(tmp_path, sessao, avisar_erro=avisos.append)

    assert codigo == 1
    assert avisos == ["O GastroEpi já está aberto com este cofre. Use a janela que já está aberta."]
