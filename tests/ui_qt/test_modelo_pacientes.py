"""Modelo da tabela: células, ordenação pela chave e filtro pelo serviço, em 10 mil linhas."""

import time

from PySide6.QtCore import QModelIndex, Qt
from pytestqt.qtbot import QtBot

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.ui_qt.modelo_pacientes import COLUNAS, FiltroDePacientes, ModeloDePacientes

FICHAS = gerar_fichas(semente=11, quantidade=40)


def _modelo() -> tuple[ModeloDePacientes, FiltroDePacientes]:
    modelo = ModeloDePacientes()
    modelo.carregar({i * 10: f for i, f in enumerate(FICHAS, start=1)})
    return modelo, FiltroDePacientes(modelo)


def test_celulas_e_cabecalho(qtbot: QtBot) -> None:
    modelo, _ = _modelo()
    primeira = FICHAS[0]

    assert (modelo.rowCount(), modelo.columnCount()) == (40, len(COLUNAS))
    assert modelo.data(modelo.index(0, 1)) == primeira.paciente.nome
    assert modelo.data(modelo.index(0, 4), Qt.ItemDataRole.UserRole) == len(primeira.exames)
    assert modelo.data(modelo.index(0, 0), Qt.ItemDataRole.ToolTipRole) is None
    assert modelo.data(QModelIndex()) is None
    assert modelo.headerData(1, Qt.Orientation.Horizontal) == "Nome"
    assert modelo.headerData(1, Qt.Orientation.Vertical) is None
    assert modelo.rowCount(modelo.index(0, 0)) == modelo.columnCount(modelo.index(0, 0)) == 0
    assert modelo.paciente_id(0) == 10 and modelo.ficha(0) == primeira


def test_ordena_pela_data_e_nao_pelo_texto(qtbot: QtBot) -> None:
    _, filtro = _modelo()

    filtro.sort(3, Qt.SortOrder.AscendingOrder)

    nascimentos = [filtro.ficha(linha).paciente.data_nascimento for linha in range(40)]
    assert nascimentos == sorted(nascimentos)


def test_filtro_usa_a_busca_do_servico(qtbot: QtBot) -> None:
    _, filtro = _modelo()
    alvo = FICHAS[7].paciente

    filtro.definir_termo(alvo.prontuario)

    assert filtro.rowCount() == 1
    assert filtro.ficha(0).paciente == alvo and filtro.paciente_id(0) == 80
    filtro.definir_termo("")
    assert filtro.rowCount() == 40


def test_dez_mil_linhas_carregam_ordenam_e_filtram_rapido(qtbot: QtBot) -> None:
    """PLANO, Fase 5: a tabela aguenta 10 mil linhas. O teto é folgado para o CI."""
    fichas = {i: f for i, f in enumerate(gerar_fichas(semente=1, quantidade=10_000))}
    modelo = ModeloDePacientes()
    filtro = FiltroDePacientes(modelo)
    inicio = time.perf_counter()

    modelo.carregar(fichas)
    filtro.sort(1, Qt.SortOrder.AscendingOrder)
    filtro.definir_termo("ana")

    assert time.perf_counter() - inicio < 3.0
    assert 0 < filtro.rowCount() < 10_000
