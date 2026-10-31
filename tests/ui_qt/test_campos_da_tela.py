"""Campos de formulário: começam sem escolha e devolvem o item do domínio."""

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from gastroepi.dominio.listas import UF, Sexo
from gastroepi.ui_qt.campos_da_tela import (
    ComboDeLista,
    DecimalOpcional,
    InteiroOpcional,
    ListaDeMarcar,
    SimOuNao,
    rotulo_do_item,
)
from tests.ui_qt.formularios import clicar, digitar, tecla


def test_combo_de_lista_comeca_vazio_e_mostra_o_rotulo(qtbot: QtBot) -> None:
    combo = ComboDeLista(Sexo)
    qtbot.addWidget(combo)

    assert combo.valor() is None
    combo.definir(Sexo.FEMININO)
    assert (combo.valor(), combo.currentText()) == (Sexo.FEMININO, "Feminino")
    combo.definir(None)
    assert combo.valor() is None
    assert rotulo_do_item(UF.SP) == "SP"


def test_sim_ou_nao(qtbot: QtBot) -> None:
    campo = SimOuNao()
    qtbot.addWidget(campo)

    assert campo.valor() is None
    campo.definir(False)
    assert campo.valor() is False
    campo.definir(True)
    assert campo.valor() is True
    campo.definir(None)
    assert campo.valor() is None


def test_numeros_opcionais_tem_o_vazio_no_minimo(qtbot: QtBot) -> None:
    inteiro, decimal = InteiroOpcional(120), DecimalOpcional(60.0, " min")
    qtbot.addWidget(inteiro)
    qtbot.addWidget(decimal)

    assert (inteiro.valor(), decimal.valor()) == (None, None)
    assert (inteiro.text(), decimal.text()) == ("não sei", "não registrado")
    inteiro.definir(65)
    decimal.definir(7.5)
    assert (inteiro.valor(), decimal.valor()) == (65, 7.5)
    inteiro.definir(None)
    decimal.definir(None)
    assert (inteiro.valor(), decimal.valor()) == (None, None)


def test_lista_de_marcar_inclui_item_novo_marcado(qtbot: QtBot) -> None:
    lista = ListaDeMarcar("Outra")
    qtbot.addWidget(lista)
    lista.definir(("Asma", "Diabetes"), ("diabetes", "Gota"))

    assert lista.marcados() == ("Diabetes", "Gota")
    digitar(qtbot, lista.novo, "Tenesmo")
    tecla(qtbot, lista.novo, Qt.Key.Key_Return)
    digitar(qtbot, lista.novo, "   ")
    clicar(qtbot, lista.incluir)
    lista.marcar("Asma")

    assert lista.marcados() == ("Asma", "Diabetes", "Gota", "Tenesmo")
