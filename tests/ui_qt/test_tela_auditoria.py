"""Auditoria: nome do usuário, verificação em frases e a lista de eventos."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from gastroepi.servicos import acesso, pacientes
from gastroepi.servicos.acesso import Sessao, desbloquear
from gastroepi.servicos.integridade import (
    Divergencia,
    Motivo,
    QuebraDaCadeia,
    RelatorioDeIntegridade,
    Verificacao,
)
from gastroepi.ui_qt.tela_auditoria import (
    ENTRADAS_MOSTRADAS,
    TelaAuditoria,
    frase_da_divergencia,
    frases_da_verificacao,
)
from tests.cofres_de_teste import SENHA, adulterar_um_nome, cofre_com_fichas
from tests.ui_qt.conftest import Capturar
from tests.ui_qt.formularios import celula, clicar


def _tela(qtbot: QtBot, sessao: Sessao) -> TelaAuditoria:
    tela = TelaAuditoria(sessao, lambda: acesso.nome_do_usuario(sessao))
    qtbot.addWidget(tela)
    tela.atualizar()
    return tela


def test_cofre_integro_e_lista(qtbot: QtBot, sessao: Sessao, capturar: Capturar) -> None:
    tela = _tela(qtbot, sessao)

    clicar(qtbot, tela.verificar)
    capturar(tela, "50-auditoria")

    assert tela.aviso.text().startswith("Tudo certo")
    entradas = pacientes.listar_auditoria(sessao)
    assert tela.tabela.rowCount() == min(ENTRADAS_MOSTRADAS, len(entradas))
    assert celula(tela.tabela, 0, 0) == str(entradas[-1].id)  # a mais nova primeiro


def test_salvar_nome_vai_para_a_auditoria(qtbot: QtBot, sessao: Sessao) -> None:
    tela = _tela(qtbot, sessao)
    tela.nome.setText("   ")
    clicar(qtbot, tela.salvar_nome)
    assert tela.aviso.text() == "Nome: Preenchimento obrigatório"

    tela.nome.setText("  Operadora Fictícia ")
    with qtbot.waitSignal(tela.usuario_mudou) as sinal:
        clicar(qtbot, tela.salvar_nome)

    assert sinal.args == ["Operadora Fictícia"]
    assert acesso.nome_do_usuario(sessao) == "Operadora Fictícia"


def test_adulteracao_por_fora_aparece_em_frase(
    qtbot: QtBot, tmp_path: Path, capturar: Capturar
) -> None:
    sessao, recovery_key = cofre_com_fichas(tmp_path, quantidade=5)
    sessao.fechar()
    adulterar_um_nome(tmp_path, recovery_key)

    with desbloquear(tmp_path, SENHA) as aberta:
        tela = _tela(qtbot, aberta)
        clicar(qtbot, tela.verificar)
        capturar(tela, "51-auditoria-adulterada")

    assert "O registro paciente nº 2 foi alterado por fora do app" in tela.aviso.text()


def test_frases_de_cada_camada() -> None:
    paginas = Verificacao(("página 7",), None)
    assert "1 página(s) com defeito" in frases_da_verificacao(paginas)[0]
    sem_entrada = Divergencia("paciente", 3, Motivo.SEM_EVENTO, None, None)
    assert frase_da_divergencia(sem_entrada) == (
        "O registro paciente nº 3 existe sem nenhum registro na auditoria."
    )


def test_frase_da_cadeia_quebrada() -> None:
    quebra = QuebraDaCadeia(7, "2026-10-31T12:00:00+00:00")
    verificacao = Verificacao((), RelatorioDeIntegridade(quebra, ()))

    (frase,) = frases_da_verificacao(verificacao)

    assert frase.startswith("A cadeia de auditoria quebra na entrada nº 7")
