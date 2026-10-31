"""Diálogo da lesão: o domínio recusa o incoerente e a tela mostra por quê."""

from pytestqt.qtbot import QtBot

from gastroepi.dominio.lesao import Lesao
from gastroepi.dominio.listas import Displasia, Histologia, Paris, Segmento
from gastroepi.ui_qt.dialogo_lesao import DialogoLesao
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar, preencher_lesao


def test_lesao_vazia_e_recusada_com_os_campos_que_faltam(qtbot: QtBot, capturar: Capturar) -> None:
    dialogo = DialogoLesao()
    qtbot.addWidget(dialogo)

    dialogo.botoes.accepted.emit()
    capturar(dialogo, "lesao-recusada")

    assert dialogo.lesao is None
    assert "Segmento: Escolha um item da lista" in dialogo.erro.text()
    assert "Tamanho (mm): Deve ser maior ou igual a 1" in dialogo.erro.text()


def test_displasia_incoerente_e_recusada(qtbot: QtBot) -> None:
    dialogo = DialogoLesao()
    qtbot.addWidget(dialogo)
    preencher_lesao(qtbot, dialogo, Histologia.HIPERPLASICO)

    dialogo.botoes.accepted.emit()

    assert dialogo.lesao is None
    assert "não se aplica" in dialogo.erro.text()


def test_histologia_outra_libera_a_descricao_e_guarda(qtbot: QtBot) -> None:
    dialogo = DialogoLesao()
    qtbot.addWidget(dialogo)
    assert not dialogo.histologia_outra.isEnabled()
    preencher_lesao(qtbot, dialogo, Histologia.OUTRO)
    dialogo.displasia.definir(Displasia.NAO_SE_APLICA)
    dialogo.histologia_outra.setText("Pólipo inflamatório")  # keyClicks só digita ASCII

    with qtbot.waitSignal(dialogo.accepted):
        dialogo.botoes.accepted.emit()

    assert dialogo.lesao is not None
    assert dialogo.lesao.histologia_outra == "Pólipo inflamatório"


def test_editar_preenche_os_campos(qtbot: QtBot) -> None:
    lesao = Lesao(
        segmento=Segmento.RETO,
        tamanho_mm=4,
        paris=Paris.IIA,
        histologia=Histologia.TUBULAR,
        displasia=Displasia.BAIXO,
        laudo_texto="ausência de displasia de alto grau",
    )
    dialogo = DialogoLesao(lesao)
    qtbot.addWidget(dialogo)

    with qtbot.waitSignal(dialogo.accepted):
        clicar(qtbot, dialogo.botoes.buttons()[0])

    assert dialogo.lesao == lesao
