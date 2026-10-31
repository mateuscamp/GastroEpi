"""Estado atual de cada registro, no formato do retrato gravado na auditoria."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.catalogos import resolver
from gastroepi.persistencia.conexao import abrir_conexao
from gastroepi.persistencia.estado_atual import estados_atuais
from gastroepi.persistencia.fichas import inserir_ficha
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


def test_estados_das_quatro_entidades_sao_os_retratos_da_gravacao(
    conexao: sqlcipher3.Connection,
) -> None:
    resolucao = resolver(conexao, FICHA)
    paciente_id = inserir_ficha(conexao, resolucao)

    estados = estados_atuais(conexao)

    esperados = {(n.entidade.value, n.id): n.retrato for n in resolucao.novos}
    esperados[("paciente", paciente_id)] = FICHA.model_dump_json()
    assert estados == esperados
    assert {entidade for entidade, _ in estados} == {
        "paciente",
        "comorbidade",
        "sintoma",
        "examinador",
    }
