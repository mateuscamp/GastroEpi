"""Exportar: o aviso de que sai sem cifra está na tela, e o arquivo sai anônimo."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.tela_exportar import AVISO_SEM_CIFRA, TelaExportar
from tests.ui_qt.conftest import Capturar, PerguntasProgramadas
from tests.ui_qt.formularios import clicar


def test_aviso_sem_cifra_e_exportacao(
    qtbot: QtBot,
    sessao: Sessao,
    perguntas: PerguntasProgramadas,
    tmp_path: Path,
    capturar: Capturar,
) -> None:
    tela = TelaExportar(sessao, perguntas, tmp_path / "sugestao.csv")
    qtbot.addWidget(tela)
    tela.atualizar()
    capturar(tela, "70-exportar")
    assert "NÃO é cifrado" in AVISO_SEM_CIFRA

    clicar(qtbot, tela.exportar)  # cancelou a escolha do arquivo
    assert tela.aviso.isHidden()

    perguntas.arquivo = tmp_path / "exames.csv"
    clicar(qtbot, tela.exportar)

    texto = perguntas.arquivo.read_bytes().decode("utf-8")
    assert all(f.paciente.nome not in texto for f in pacientes.listar(sessao).values())
    assert (tmp_path / "exames-dicionario.csv").exists()
    assert "não é cifrado" in tela.aviso.text()


def test_erro_ao_gravar_aparece(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas, tmp_path: Path
) -> None:
    tela = TelaExportar(sessao, perguntas)
    qtbot.addWidget(tela)
    perguntas.arquivo = tmp_path / "pasta-que-nao-existe" / "exames.csv"

    clicar(qtbot, tela.exportar)

    assert "No such file" in tela.aviso.text() or "Errno" in tela.aviso.text()
