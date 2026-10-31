"""Schema (ADR-0004): triggers append-only, CHECK, FOREIGN KEY e migrações idempotentes."""

import re
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.auditoria.cadeia import Acao, Entidade
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import (
    UF,
    Displasia,
    Histologia,
    Indicacao,
    MotivoNaoIntubacao,
    Parentesco,
    Paris,
    Segmento,
    Sexo,
)
from gastroepi.persistencia.conexao import abrir_conexao
from gastroepi.persistencia.repositorio import Repositorio
from gastroepi.persistencia.schema import VERSAO_DO_SCHEMA, BancoMaisNovoQueOApp, migrar


@pytest.fixture
def caminho(tmp_path: Path, chave_de_dados: bytes) -> Path:
    """Banco com dois pacientes fictícios com histórico, Boston e lesões, cadastrados pelo app."""
    caminho = tmp_path / "gastroepi.db"
    completas = [
        f
        for f in gerar_fichas(semente=21, quantidade=100)
        if f.paciente.historico_familiar and all(e.preparo and e.lesoes for e in f.exames)
    ]
    with Repositorio.abrir(caminho, chave_de_dados) as repositorio:
        for ficha in completas[:2]:
            repositorio.cadastrar(ficha, usuario="teste")
    return caminho


@pytest.fixture
def externa(caminho: Path, chave_de_dados: bytes) -> Iterator[sqlcipher3.Connection]:
    """Conexão de uma ferramenta externa com a chave, sem passar pelo app."""
    conexao = sqlcipher3.connect(str(caminho), isolation_level=None)
    conexao.execute(f"PRAGMA key = \"x'{chave_de_dados.hex()}'\"")
    yield conexao
    conexao.close()


@pytest.mark.parametrize(
    "sql",
    ["UPDATE auditoria SET usuario = 'outro' WHERE id = 1", "DELETE FROM auditoria WHERE id = 1"],
)
def test_update_e_delete_em_auditoria_levantam_erro(
    externa: sqlcipher3.Connection, sql: str
) -> None:
    with pytest.raises(sqlcipher3.IntegrityError, match="append-only"):
        externa.execute(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE paciente SET sexo = 'X'",
        "UPDATE paciente SET nome = '  '",
        "UPDATE paciente SET prontuario = ''",
        "UPDATE paciente SET cpf = '1234567890a' WHERE id = 1",
        "UPDATE paciente SET cpf = '123' WHERE id = 1",
        "UPDATE paciente SET data_nascimento = '05/03/1960'",
        "UPDATE paciente SET data_nascimento = '1960-02-30'",
        "UPDATE paciente SET data_nascimento = '1960-13-01'",
        "UPDATE paciente SET data_nascimento = '1899-12-31'",
        "UPDATE historico_familiar SET parentesco = 'vizinho'",
        "UPDATE historico_familiar SET idade_diagnostico = 121",
        "UPDATE examinador SET uf = 'XX'",
        "UPDATE examinador SET crm = '12a'",
        "UPDATE exame SET indicacao = 'curiosidade'",
        "UPDATE exame SET boston_direito = 4",
        "UPDATE exame SET boston_direito = NULL WHERE boston_transverso IS NOT NULL",
        "UPDATE exame SET intubacao_cecal = 2",
        "UPDATE exame SET intubacao_cecal = 0, motivo_nao_intubacao = NULL",
        "UPDATE exame SET tempo_retirada_min = 0",
        "UPDATE lesao SET tamanho_mm = 0",
        "UPDATE lesao SET segmento = 'estomago'",
        "UPDATE lesao SET paris = '0-IV'",
        "UPDATE lesao SET histologia = 'carcinoide'",
        "UPDATE lesao SET displasia = 'moderada'",
        "UPDATE lesao SET histologia = 'outro', histologia_outra = NULL",
        "UPDATE auditoria SET acao = 'apagar'",
    ],
)
def test_check_recusa_valor_fora_do_dominio_mesmo_por_fora(
    externa: sqlcipher3.Connection, sql: str
) -> None:
    externa.execute("DROP TRIGGER IF EXISTS auditoria_sem_update")
    with pytest.raises(sqlcipher3.IntegrityError, match="CHECK constraint failed"):
        externa.execute(sql)


def test_exame_de_paciente_inexistente_e_recusado(externa: sqlcipher3.Connection) -> None:
    externa.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlcipher3.IntegrityError, match="FOREIGN KEY"):
        externa.execute("UPDATE exame SET paciente_id = 999 WHERE id = (SELECT min(id) FROM exame)")


LISTAS_POR_COLUNA: dict[str, type[StrEnum]] = {
    "sexo": Sexo,
    "parentesco": Parentesco,
    "uf": UF,
    "indicacao": Indicacao,
    "motivo_nao_intubacao": MotivoNaoIntubacao,
    "segmento": Segmento,
    "paris": Paris,
    "histologia": Histologia,
    "displasia": Displasia,
    "acao": Acao,
    "entidade": Entidade,
}


@pytest.mark.parametrize("coluna", sorted(LISTAS_POR_COLUNA))
def test_lista_do_check_e_a_lista_do_dominio(externa: sqlcipher3.Connection, coluna: str) -> None:
    """Lista mudou no domínio (VERSAO_DAS_LISTAS) sem migração: este teste acusa."""
    ddl = " ".join(
        linha[0] for linha in externa.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
    )
    achado = re.search(rf"\b{coluna} IN \(([^)]*)\)", ddl)

    assert achado is not None, f"sem CHECK de lista para {coluna}"
    assert set(re.findall(r"'([^']*)'", achado[1])) == {str(v) for v in LISTAS_POR_COLUNA[coluna]}


def test_schema_nao_tem_coluna_digitavel_de_contagem_nem_de_grau(
    externa: sqlcipher3.Connection,
) -> None:
    """ADR-0004: nº de pólipos e grau do parente são derivados, nunca gravados."""
    tabelas = [
        linha[0] for linha in externa.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    ]
    colunas = {c[1] for t in tabelas for c in externa.execute(f"PRAGMA table_info({t})")}

    assert not colunas & {"n_polipos", "polipos", "grau", "grau_parentesco"}


def test_migrar_banco_vazio_chega_na_versao_atual(tmp_path: Path, chave_de_dados: bytes) -> None:
    """O banco da versão anterior à 1 é o arquivo vazio."""
    conexao = abrir_conexao(tmp_path / "novo.db", chave_de_dados)
    assert conexao.execute("PRAGMA user_version").fetchone()[0] == 0

    migrar(conexao)

    assert conexao.execute("PRAGMA user_version").fetchone()[0] == VERSAO_DO_SCHEMA == 1
    conexao.close()


def test_migrar_de_novo_nao_muda_schema_nem_dados(caminho: Path, chave_de_dados: bytes) -> None:
    conexao = abrir_conexao(caminho, chave_de_dados)
    retrato = "SELECT (SELECT group_concat(sql) FROM sqlite_master), (SELECT valor FROM metadados)"
    antes = tuple(conexao.execute(retrato).fetchone())

    migrar(conexao)
    migrar(conexao)

    assert tuple(conexao.execute(retrato).fetchone()) == antes
    assert conexao.execute("SELECT count(*) FROM paciente").fetchone()[0] == 2
    conexao.close()


def test_banco_de_versao_mais_nova_que_o_app_e_recusado(
    externa: sqlcipher3.Connection, caminho: Path, chave_de_dados: bytes
) -> None:
    externa.execute(f"PRAGMA user_version = {VERSAO_DO_SCHEMA + 1}")
    conexao = abrir_conexao(caminho, chave_de_dados)

    with pytest.raises(BancoMaisNovoQueOApp, match=str(VERSAO_DO_SCHEMA + 1)):
        migrar(conexao)
    conexao.close()


def test_chave_da_auditoria_tem_256_bits_e_nao_e_a_chave_de_dados(
    externa: sqlcipher3.Connection, chave_de_dados: bytes
) -> None:
    chave = externa.execute(
        "SELECT valor FROM metadados WHERE chave = 'chave_auditoria'"
    ).fetchone()[0]

    assert isinstance(chave, bytes)
    assert len(chave) == 32
    assert chave != chave_de_dados


def test_migracao_feita_por_outra_instancia_entre_a_checagem_e_o_begin_nao_repete(
    tmp_path: Path, chave_de_dados: bytes
) -> None:
    """Duas aberturas ao mesmo tempo: a segunda relê a versão já com a trava na mão."""
    caminho = tmp_path / "novo.db"
    primeira, segunda = (
        abrir_conexao(caminho, chave_de_dados),
        abrir_conexao(caminho, chave_de_dados),
    )

    def outra_instancia_migra_antes(instrucao: str) -> None:
        if instrucao.startswith("BEGIN IMMEDIATE"):
            segunda.set_trace_callback(None)
            primeira_migracao_feita.append(True)
            migrar(primeira)

    primeira_migracao_feita: list[bool] = []
    segunda.set_trace_callback(outra_instancia_migra_antes)
    migrar(segunda)

    assert primeira_migracao_feita == [True]
    assert segunda.execute("SELECT count(*) FROM metadados").fetchone()[0] == 1
    primeira.close()
    segunda.close()
