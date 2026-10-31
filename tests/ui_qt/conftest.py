"""Apoio dos testes da casca: cofre real, perguntas programadas e as capturas de tela.

Com `GASTROEPI_CAPTURAS=<pasta>`, cada `capturar` salva o PNG da tela ali; o CI guarda a
pasta como artefato para a revisão visual (PLANO, Fase 5).
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.aparencia import aplicar_aparencia
from tests.cofres_de_teste import cofre_com_fichas

type Capturar = Callable[[QWidget, str], None]


class PerguntasProgramadas:
    """As respostas que o usuário daria nas caixas modais, decididas pelo teste."""

    def __init__(self) -> None:
        self.confirma = True
        self.arquivo: Path | None = None
        self.pasta_escolhida: Path | None = None
        self.textos: list[str] = []

    def confirmar(self, pai: QWidget, titulo: str, texto: str) -> bool:
        self.textos.append(texto)
        return self.confirma

    def arquivo_para_salvar(self, pai: QWidget, titulo: str, sugestao: Path) -> Path | None:
        self.textos.append(titulo)
        return self.arquivo

    def pasta(self, pai: QWidget, titulo: str) -> Path | None:
        self.textos.append(titulo)
        return self.pasta_escolhida


@pytest.fixture(autouse=True)
def aparencia(qapp: QApplication) -> None:
    aplicar_aparencia(qapp)


@pytest.fixture
def perguntas() -> PerguntasProgramadas:
    return PerguntasProgramadas()


@pytest.fixture
def sessao(tmp_path: Path) -> Iterator[Sessao]:
    """Cofre com 30 pacientes fictícios (semente 9)."""
    aberta, _ = cofre_com_fichas(tmp_path / "cofre", quantidade=30)
    yield aberta
    aberta.fechar()


@pytest.fixture
def capturar(qtbot: QtBot) -> Capturar:
    pasta = os.environ.get("GASTROEPI_CAPTURAS")

    def capturar(widget: QWidget, nome: str) -> None:
        if widget.isWindow() and widget.width() < 900:
            widget.resize(1200, 780)
        widget.show()
        qtbot.waitExposed(widget)
        qtbot.wait(20)  # o layout assenta em mais de uma passada do laço
        imagem = widget.grab()
        assert not imagem.isNull()
        if pasta:
            Path(pasta).mkdir(parents=True, exist_ok=True)
            imagem.save(str(Path(pasta) / f"{nome}.png"))

    return capturar
