"""Gravação e leitura das entradas de auditoria; o elo vem de `auditoria`."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.auditoria.cadeia import ELO_INICIAL, Evento, calcular_elo, verificar_cadeia
from gastroepi.persistencia.conexao import abrir_conexao
from gastroepi.persistencia.eventos import ler_chave_de_auditoria, ler_entradas, registrar_evento
from gastroepi.persistencia.schema import migrar


@pytest.fixture
def conexao(tmp_path: Path, chave_de_dados: bytes) -> Iterator[sqlcipher3.Connection]:
    conexao = abrir_conexao(tmp_path / "gastroepi.db", chave_de_dados)
    migrar(conexao)
    yield conexao
    conexao.close()


def evento(numero: int) -> Evento:
    return Evento(f"2026-10-31T12:00:0{numero}.000+00:00", "teste", "cadastrar", "sintoma",
                  numero, None, f'{{"nome": "S{numero}"}}')  # fmt: skip


def test_primeira_entrada_encadeia_no_elo_inicial(conexao: sqlcipher3.Connection) -> None:
    chave = ler_chave_de_auditoria(conexao)

    registrar_evento(conexao, chave, evento(1))

    (entrada,) = ler_entradas(conexao)
    assert entrada.evento == evento(1)
    assert entrada.elo == calcular_elo(chave, ELO_INICIAL, evento(1))


def test_entradas_voltam_em_ordem_e_encadeadas(conexao: sqlcipher3.Connection) -> None:
    chave = ler_chave_de_auditoria(conexao)
    for numero in range(1, 5):
        registrar_evento(conexao, chave, evento(numero))

    entradas = ler_entradas(conexao)

    assert [e.evento.entidade_id for e in entradas] == [1, 2, 3, 4]
    assert verificar_cadeia(chave, entradas) is None
