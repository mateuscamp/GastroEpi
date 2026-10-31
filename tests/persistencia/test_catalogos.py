"""Resolução dos catálogos: grafia existente sem distinguir caixa, item novo à parte."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.catalogos import (
    ExaminadorDivergente,
    inserir_item,
    listar_itens,
    resolver,
)
from gastroepi.persistencia.conexao import abrir_conexao
from gastroepi.persistencia.schema import migrar

FICHA = next(
    f for f in gerar_fichas(semente=3, quantidade=100)
    if f.paciente.comorbidades and any(e.sintomas for e in f.exames)
)  # fmt: skip


@pytest.fixture
def conexao(tmp_path: Path, chave_de_dados: bytes) -> Iterator[sqlcipher3.Connection]:
    conexao = abrir_conexao(tmp_path / "gastroepi.db", chave_de_dados)
    migrar(conexao)
    yield conexao
    conexao.close()


def test_itens_novos_saem_em_novos_com_retrato(conexao: sqlcipher3.Connection) -> None:
    resolucao = resolver(conexao, FICHA)

    comorbidades = [n for n in resolucao.novos if n.entidade == "comorbidade"]
    assert [n.retrato for n in comorbidades] == [
        f'{{"nome": "{nome}"}}' for nome in FICHA.paciente.comorbidades
    ]
    assert resolucao.ficha == FICHA


def test_nome_existente_com_outra_caixa_usa_a_grafia_do_catalogo(
    conexao: sqlcipher3.Connection,
) -> None:
    primeira = FICHA.paciente.comorbidades[0]
    inserir_item(conexao, "comorbidade", primeira.upper())

    resolucao = resolver(conexao, FICHA)

    assert resolucao.ficha.paciente.comorbidades[0] == primeira.upper()
    assert all(n.retrato != f'{{"nome": "{primeira}"}}' for n in resolucao.novos)
    ids_por_nome = {nome: item_id for item_id, nome in listar_itens(conexao, "comorbidade")}
    assert resolucao.comorbidades[primeira.upper()] == ids_por_nome[primeira.upper()]


def test_resolver_de_novo_nao_cria_nada(conexao: sqlcipher3.Connection) -> None:
    resolver(conexao, FICHA)

    assert resolver(conexao, FICHA).novos == ()


def test_examinador_com_outro_nome_para_o_mesmo_crm_e_recusado(
    conexao: sqlcipher3.Connection,
) -> None:
    resolver(conexao, FICHA)
    exame = FICHA.exames[0]
    outro = exame.model_copy(
        update={"examinador": exame.examinador.model_copy(update={"nome": "X"})}
    )

    with pytest.raises(ExaminadorDivergente, match=f"{exame.examinador.crm}/{exame.examinador.uf}"):
        resolver(conexao, FICHA.model_copy(update={"exames": (outro,)}))
