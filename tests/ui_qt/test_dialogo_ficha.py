"""Diálogo da ficha: abas Paciente e Exames; o erro de gravação fica no diálogo."""

from pytestqt.qtbot import QtBot

from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import Parentesco
from gastroepi.servicos.pacientes import ProntuarioJaCadastrado
from gastroepi.ui_qt.campos_da_tela import ComboDeLista, InteiroOpcional
from gastroepi.ui_qt.dialogo_exame import DialogoExame
from gastroepi.ui_qt.dialogo_ficha import DialogoFicha
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import CATALOGOS, clicar, preencher_exame, preencher_paciente


def test_ficha_nova_com_parente_e_exame(qtbot: QtBot, capturar: Capturar) -> None:
    salvas: list[Ficha] = []
    dialogo = DialogoFicha(CATALOGOS, None, salvas.append)
    qtbot.addWidget(dialogo)
    preencher_paciente(qtbot, dialogo.paciente)
    dialogo.paciente.comorbidades.marcar("Asma")
    clicar(qtbot, dialogo.paciente.parentes.adicionar)
    parentesco = dialogo.paciente.parentes.tabela.cellWidget(0, 0)
    idade = dialogo.paciente.parentes.tabela.cellWidget(0, 1)
    assert isinstance(parentesco, ComboDeLista) and isinstance(idade, InteiroOpcional)
    parentesco.definir(Parentesco.MAE)
    idade.definir(62)
    capturar(dialogo, "ficha-paciente")
    dialogo.abas.setCurrentIndex(1)
    clicar(qtbot, dialogo.exames.adicionar)
    exame = dialogo.exames.dialogo
    assert isinstance(exame, DialogoExame)
    preencher_exame(qtbot, exame)
    clicar(qtbot, exame.guardar)
    capturar(dialogo, "ficha-exames")

    with qtbot.waitSignal(dialogo.accepted):
        clicar(qtbot, dialogo.botao_salvar)

    (ficha,) = salvas
    assert ficha.paciente.cpf == "52998224725" and ficha.paciente.comorbidades == ("Asma",)
    assert ficha.paciente.historico_familiar[0].grau == 1
    assert len(ficha.exames) == 1


def test_erro_do_dominio_e_do_servico_aparecem_no_dialogo(qtbot: QtBot) -> None:
    def recusar(ficha: Ficha) -> None:
        raise ProntuarioJaCadastrado

    dialogo = DialogoFicha(CATALOGOS, None, recusar)
    qtbot.addWidget(dialogo)

    clicar(qtbot, dialogo.botao_salvar)
    assert "Prontuário: Preenchimento obrigatório" in dialogo.erro.text()
    assert "Data de nascimento" in dialogo.erro.text()

    preencher_paciente(qtbot, dialogo.paciente)
    clicar(qtbot, dialogo.botao_salvar)
    assert dialogo.erro.text() == str(ProntuarioJaCadastrado())
    assert dialogo.isVisible() or not dialogo.result()


def test_editar_preenche_e_remover_parente(qtbot: QtBot) -> None:
    ficha = next(f for f in gerar_fichas(semente=9, quantidade=30) if f.paciente.historico_familiar)
    salvas: list[Ficha] = []
    dialogo = DialogoFicha(CATALOGOS, ficha, salvas.append)
    qtbot.addWidget(dialogo)
    assert dialogo.windowTitle() == "Editar paciente"
    assert dialogo.paciente.cpf.text().count(".") == 2

    clicar(qtbot, dialogo.botao_salvar)
    clicar(qtbot, dialogo.paciente.parentes.remover)
    dialogo.paciente.parentes.tabela.setCurrentCell(-1, -1)
    clicar(qtbot, dialogo.paciente.parentes.remover)
    clicar(qtbot, dialogo.botao_salvar)

    assert salvas[0] == ficha
    assert len(salvas[1].paciente.historico_familiar) < len(ficha.paciente.historico_familiar)
