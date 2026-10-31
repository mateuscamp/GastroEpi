"""Diálogo do exame: campos condicionais, Boston e a validação do domínio."""

from pytestqt.qtbot import QtBot

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import Displasia, Histologia, Indicacao, MotivoNaoIntubacao
from gastroepi.ui_qt.dialogo_exame import DialogoExame, rotulo_do_examinador
from gastroepi.ui_qt.dialogo_lesao import DialogoLesao
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import (
    CATALOGOS,
    EXAMINADOR,
    clicar,
    digitar,
    preencher_exame,
    preencher_lesao,
)


def test_exame_com_lesao_e_boston(qtbot: QtBot, capturar: Capturar) -> None:
    dialogo = DialogoExame(CATALOGOS)
    qtbot.addWidget(dialogo)
    preencher_exame(qtbot, dialogo)
    dialogo.boston.registrado.setChecked(True)
    for nota, valor in zip(dialogo.boston.notas, (3, 2, 2), strict=True):
        nota.setValue(valor)
    dialogo.retirada.definir(9.5)
    dialogo.sintomas.marcar("Dor abdominal")
    clicar(qtbot, dialogo.lesoes.adicionar)
    lesao = dialogo.lesoes.dialogo
    assert isinstance(lesao, DialogoLesao)
    preencher_lesao(qtbot, lesao, Histologia.AGUARDANDO)
    lesao.displasia.definir(Displasia.NAO_SE_APLICA)
    lesao.botoes.accepted.emit()
    capturar(dialogo, "exame")

    with qtbot.waitSignal(dialogo.accepted):
        clicar(qtbot, dialogo.guardar)

    exame = dialogo.exame
    assert exame is not None
    assert (exame.examinador, exame.n_polipos, exame.preparo_adequado) == (EXAMINADOR, 1, True)
    assert exame.aguardando_histologia and exame.sintomas == ("Dor abdominal",)
    assert exame.tempo_retirada_min == 9.5


def test_campos_condicionais_so_valem_com_outra_ou_sem_ceco(qtbot: QtBot) -> None:
    dialogo = DialogoExame(CATALOGOS)
    qtbot.addWidget(dialogo)
    assert not dialogo.indicacao_outra.isEnabled() and not dialogo.motivo.isEnabled()

    dialogo.indicacao.definir(Indicacao.OUTRA)
    dialogo.intubacao.definir(False)
    dialogo.motivo.definir(MotivoNaoIntubacao.OUTRO)
    assert dialogo.indicacao_outra.isEnabled() and dialogo.motivo_outro.isEnabled()

    digitar(qtbot, dialogo.motivo_outro, "texto")
    dialogo.intubacao.definir(True)
    assert dialogo.motivo.valor() is None and dialogo.motivo_outro.text() == ""


def test_exame_vazio_e_recusado(qtbot: QtBot, capturar: Capturar) -> None:
    dialogo = DialogoExame(CATALOGOS)
    qtbot.addWidget(dialogo)

    clicar(qtbot, dialogo.guardar)
    capturar(dialogo, "exame-recusado")

    assert dialogo.exame is None
    texto = dialogo.erro.text()
    assert "Data do exame" in texto and "Examinador" in texto and "Intubação cecal" in texto


def test_editar_exame_existente_inclui_examinador_fora_do_catalogo(qtbot: QtBot) -> None:
    exame = next(e for f in gerar_fichas(semente=5, quantidade=20) for e in f.exames if e.lesoes)
    dialogo = DialogoExame(CATALOGOS, exame)
    qtbot.addWidget(dialogo)

    assert dialogo.examinador.currentText() == rotulo_do_examinador(exame.examinador)
    with qtbot.waitSignal(dialogo.accepted):
        clicar(qtbot, dialogo.guardar)

    assert dialogo.exame == exame
