"""Tela de pacientes contra o cofre real: cadastrar, editar, excluir e buscar."""

from pathlib import Path

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import Sessao, desbloquear
from gastroepi.ui_qt.dialogo_exame import DialogoExame
from gastroepi.ui_qt.tela_pacientes import TelaPacientes
from gastroepi.ui_qt.textos import PARTE_ILEGIVEL
from tests.cofres_de_teste import SENHA, cofre_com_fichas, corromper_o_meio
from tests.ui_qt.conftest import Capturar, PerguntasProgramadas
from tests.ui_qt.formularios import clicar, digitar, preencher_exame, preencher_paciente, tecla


def _tela(qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas) -> TelaPacientes:
    tela = TelaPacientes(sessao, lambda: "Operadora Fictícia", perguntas)
    qtbot.addWidget(tela)
    tela.atualizar()
    return tela


def test_lista_busca_e_conta(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas, capturar: Capturar
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    capturar(tela, "10-pacientes")
    assert tela.contagem.text() == "30 pacientes"

    alvo = next(iter(pacientes.listar(sessao).values())).paciente
    digitar(qtbot, tela.busca, alvo.prontuario)

    assert tela.filtro.rowCount() == 1
    assert tela.contagem.text() == "30 pacientes (1 na busca)"


def test_cadastrar_pela_ficha_grava_com_o_usuario(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas
) -> None:
    tela = _tela(qtbot, sessao, perguntas)

    clicar(qtbot, tela.novo)
    dialogo = tela.dialogo
    assert dialogo is not None
    preencher_paciente(qtbot, dialogo.paciente, "T99999")
    dialogo.abas.setCurrentIndex(1)
    clicar(qtbot, dialogo.exames.adicionar)
    exame = dialogo.exames.dialogo
    assert isinstance(exame, DialogoExame)
    preencher_exame(qtbot, exame)
    clicar(qtbot, exame.guardar)
    clicar(qtbot, dialogo.botao_salvar)

    assert tela.aviso.text() == "Paciente cadastrado."
    assert tela.contagem.text() == "31 pacientes"
    achado = pacientes.buscar_por_prontuario(sessao, "T99999")
    assert achado is not None and len(achado[1].exames) == 1
    assert pacientes.listar_auditoria(sessao)[-1].evento.usuario == "Operadora Fictícia"


def test_editar_o_selecionado_e_salvar(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    clicar(qtbot, tela.editar)
    assert tela.aviso.text() == "Selecione um paciente na tabela."

    tela.tabela.selectRow(0)
    clicar(qtbot, tela.editar)
    dialogo = tela.dialogo
    assert dialogo is not None
    dialogo.paciente.nome.setText("Nome Editado Fictício")
    clicar(qtbot, dialogo.botao_salvar)

    assert tela.aviso.text() == "Ficha salva."
    nomes = {f.paciente.nome for f in pacientes.listar(sessao).values()}
    assert "Nome Editado Fictício" in nomes
    assert pacientes.listar_auditoria(sessao)[-1].evento.acao == "editar"


def test_excluir_pede_confirmacao(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    clicar(qtbot, tela.excluir)
    tela.tabela.selectRow(0)

    perguntas.confirma = False
    clicar(qtbot, tela.excluir)
    assert len(pacientes.listar(sessao)) == 30

    perguntas.confirma = True
    clicar(qtbot, tela.excluir)
    assert len(pacientes.listar(sessao)) == 29
    assert tela.aviso.text() == "Paciente excluído."
    assert "auditoria" in perguntas.textos[-1]


def test_somente_leitura_desliga_os_botoes_que_gravam(
    qtbot: QtBot, tmp_path: Path, perguntas: PerguntasProgramadas, capturar: Capturar
) -> None:
    cofre_com_fichas(tmp_path, quantidade=40)[0].fechar()
    corromper_o_meio(tmp_path)

    with desbloquear(tmp_path, SENHA) as sessao:
        assert sessao.somente_leitura
        tela = TelaPacientes(sessao, lambda: "Operadora Fictícia", perguntas)
        qtbot.addWidget(tela)
        tela._abrir(None)
        capturar(tela, "11-pacientes-somente-leitura")

        assert not tela.novo.isEnabled() and not tela.excluir.isEnabled()
        assert tela.dialogo is None  # nesta semente, o defeito cai no catálogo
        assert tela.aviso.text() == PARTE_ILEGIVEL


def test_enter_na_busca_abre_o_prontuario(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    paciente_id, ficha = next(iter(pacientes.listar(sessao).items()))

    digitar(qtbot, tela.busca, "F")
    tecla(qtbot, tela.busca, Qt.Key.Key_Return)
    assert tela.dialogo is None  # "F" não é um prontuário

    tela.busca.setText(ficha.paciente.prontuario)
    tecla(qtbot, tela.busca, Qt.Key.Key_Return)

    assert tela.dialogo is not None
    assert tela.dialogo.paciente.nome.text() == ficha.paciente.nome
    assert paciente_id in pacientes.listar(sessao)


def test_paciente_excluido_por_outra_via_avisa_ao_abrir(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    tela.tabela.selectRow(0)
    pacientes.excluir(sessao, tela.filtro.paciente_id(0), "teste")

    clicar(qtbot, tela.editar)

    assert tela.aviso.text() == "Este paciente não existe mais."
    assert tela.contagem.text() == "29 pacientes"


def test_excluir_quem_ja_saiu_mostra_o_erro(
    qtbot: QtBot, sessao: Sessao, perguntas: PerguntasProgramadas
) -> None:
    tela = _tela(qtbot, sessao, perguntas)
    tela.tabela.selectRow(0)
    paciente_id = tela.filtro.paciente_id(0)
    pacientes.excluir(sessao, paciente_id, "teste")

    clicar(qtbot, tela.excluir)

    assert str(paciente_id) in tela.aviso.text()
