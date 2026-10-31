"""Aparência: o papel escolhe o estilo e o aviso some quando vazio."""

from PySide6.QtWidgets import QApplication, QPushButton
from pytestqt.qtbot import QtBot

from gastroepi.ui_qt.aparencia import FOLHA_DE_ESTILO, Aviso, aplicar_aparencia, com_papel, rotulo


def test_aplicar_aparencia_poe_a_folha_e_letra_de_11(qapp: QApplication) -> None:
    aplicar_aparencia(qapp)

    assert qapp.styleSheet() == FOLHA_DE_ESTILO
    assert qapp.font().pointSize() == 11


def test_papel_e_rotulo(qtbot: QtBot) -> None:
    botao = com_papel(QPushButton("Salvar"), "principal")
    qtbot.addWidget(botao)
    etiqueta = rotulo("Texto", "titulo")
    qtbot.addWidget(etiqueta)

    assert botao.property("papel") == "principal"
    assert etiqueta.property("papel") == "titulo" and etiqueta.wordWrap()
    assert rotulo("Sem papel").property("papel") is None


def test_aviso_mostra_o_tipo_e_some_ao_limpar(qtbot: QtBot) -> None:
    aviso = Aviso()
    qtbot.addWidget(aviso)
    aviso.show()

    for metodo, papel in (
        (aviso.erro, "erro"),
        (aviso.sucesso, "sucesso"),
        (aviso.alerta, "alerta"),
    ):
        metodo("mensagem")
        assert (aviso.text(), aviso.property("papel"), aviso.isVisible()) == (
            "mensagem",
            papel,
            True,
        )
    aviso.limpar()

    assert (aviso.text(), aviso.isVisible()) == ("", False)
