"""Catálogos: incluir comorbidade, sintoma e examinador, com a recusa do domínio."""

from pytestqt.qtbot import QtBot

from gastroepi.dominio.listas import UF
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.tela_catalogos import TelaCatalogos
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import clicar, digitar


def test_incluir_itens_e_examinador(qtbot: QtBot, sessao: Sessao, capturar: Capturar) -> None:
    tela = TelaCatalogos(sessao, lambda: "Operadora Fictícia")
    qtbot.addWidget(tela)
    tela.atualizar()
    antes = tela.comorbidades.lista.count()

    digitar(qtbot, tela.comorbidades.novo, "Asma")
    clicar(qtbot, tela.comorbidades.incluir)
    digitar(qtbot, tela.sintomas.novo, "Tenesmo")
    clicar(qtbot, tela.sintomas.incluir)
    digitar(qtbot, tela.examinadores.nome, "Dr. Novo Ficticio")
    digitar(qtbot, tela.examinadores.crm, "4242")
    tela.examinadores.uf.setCurrentIndex(list(UF).index(UF.BA))
    clicar(qtbot, tela.examinadores.incluir)
    capturar(tela, "20-catalogos")

    assert tela.comorbidades.lista.count() == antes + 1
    assert "Tenesmo" in pacientes.listar_sintomas(sessao)
    assert tela.aviso.text() == "Incluído: Dr. Novo Ficticio (CRM-BA 4242)."
    assert pacientes.listar_auditoria(sessao)[-1].evento.entidade == "examinador"


def test_recusas_aparecem_na_tela(qtbot: QtBot, sessao: Sessao) -> None:
    tela = TelaCatalogos(sessao, lambda: "Operadora Fictícia")
    qtbot.addWidget(tela)

    clicar(qtbot, tela.sintomas.incluir)
    assert tela.aviso.text() == "Nome: Preenchimento obrigatório"

    digitar(qtbot, tela.examinadores.nome, "Dr. Sem CRM")
    clicar(qtbot, tela.examinadores.incluir)
    assert "CRM" in tela.aviso.text() and "UF" in tela.aviso.text()
