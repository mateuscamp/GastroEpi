"""Ponto de entrada da casca: a QApplication, a trava de instância e a janela.

A trava é segurada enquanto o app vive (ADR-0005, item 7). Uma segunda instância no
mesmo cofre recebe o aviso e sai com 1, sem abrir nada.
"""

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from gastroepi.servicos import acesso, durabilidade
from gastroepi.servicos.acesso import Sessao
from gastroepi.servicos.durabilidade import OutraInstanciaAberta
from gastroepi.ui_qt.aparencia import aplicar_aparencia
from gastroepi.ui_qt.janela_principal import JanelaPrincipal


def aplicacao_qt() -> QApplication:
    existente = QApplication.instance()
    if isinstance(existente, QApplication):
        return existente
    return QApplication(sys.argv[:1])


def rodar(
    pasta: Path | None = None,
    sessao: Sessao | None = None,
    ao_abrir: Callable[[JanelaPrincipal], None] | None = None,
    avisar_erro: Callable[[str], None] | None = None,
    laco_de_eventos: Callable[[], int] | None = None,
) -> int:
    """Abre o app no cofre `pasta` (padrão: `acesso.pasta_padrao()`). Com `sessao`, já
    entra desbloqueado (a demo). `ao_abrir` recebe a janela antes do laço de eventos.

    Os testes trocam o laço (`laco_de_eventos`): sair do `exec()` da QApplication deixa o
    despachante interrompido, e os timers dos testes seguintes param de disparar."""
    aplicacao = aplicacao_qt()
    aplicar_aparencia(aplicacao)
    pasta = pasta or acesso.pasta_padrao()
    try:
        trava = durabilidade.travar_instancia(pasta)
    except OutraInstanciaAberta as erro:
        if sessao is not None:
            sessao.fechar()
        (avisar_erro or _caixa_de_erro)(f"{erro}. Use a janela que já está aberta.")
        return 1
    with trava:
        janela = JanelaPrincipal(pasta)
        if sessao is not None:
            janela.abrir_sessao(sessao)
        janela.show()
        if ao_abrir is not None:
            ao_abrir(janela)
        return (laco_de_eventos or aplicacao.exec)()


def processar_eventos() -> int:
    """Laço de uma volta: desenha o que está pendente e devolve 0 (o `--smoke`)."""
    QApplication.processEvents()
    return 0


def _caixa_de_erro(texto: str) -> None:
    QMessageBox.critical(None, "GastroEpi", texto)
