"""Ficha ↔ linhas: ida e volta na ordem da ficha; ficha que o domínio recusa vira None."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.catalogos import resolver
from gastroepi.persistencia.conexao import abrir_conexao
from gastroepi.persistencia.fichas import (
    apagar_ficha,
    atualizar_ficha,
    inserir_ficha,
    ler_fichas_ou_ilegiveis,
)
from gastroepi.persistencia.schema import migrar

FICHAS = gerar_fichas(semente=14, quantidade=6)


@pytest.fixture
def conexao(tmp_path: Path, chave_de_dados: bytes) -> Iterator[sqlcipher3.Connection]:
    conexao = abrir_conexao(tmp_path / "gastroepi.db", chave_de_dados)
    migrar(conexao)
    yield conexao
    conexao.close()


def test_ida_e_volta_de_todas_e_de_uma(conexao: sqlcipher3.Connection) -> None:
    ids = [inserir_ficha(conexao, resolver(conexao, ficha)) for ficha in FICHAS]

    assert ler_fichas_ou_ilegiveis(conexao) == dict(zip(ids, FICHAS, strict=True))
    assert ler_fichas_ou_ilegiveis(conexao, ids[2]) == {ids[2]: FICHAS[2]}


def test_atualizar_regrava_os_filhos_e_apagar_leva_tudo(conexao: sqlcipher3.Connection) -> None:
    paciente_id = inserir_ficha(conexao, resolver(conexao, FICHAS[0]))

    atualizar_ficha(conexao, paciente_id, resolver(conexao, FICHAS[1]))
    assert ler_fichas_ou_ilegiveis(conexao, paciente_id) == {paciente_id: FICHAS[1]}

    apagar_ficha(conexao, paciente_id)
    assert ler_fichas_ou_ilegiveis(conexao) == {}
    assert conexao.execute("SELECT count(*) FROM exame").fetchone()[0] == 0


def test_ficha_com_cpf_de_digito_errado_gravado_por_fora_vira_none(
    conexao: sqlcipher3.Connection,
) -> None:
    """O CHECK só confere 11 dígitos; o dígito verificador é regra do domínio."""
    ids = [inserir_ficha(conexao, resolver(conexao, ficha)) for ficha in FICHAS[:2]]
    conexao.execute("UPDATE paciente SET cpf = '12345678900' WHERE id = ?", (ids[1],))

    assert ler_fichas_ou_ilegiveis(conexao) == {ids[0]: FICHAS[0], ids[1]: None}
