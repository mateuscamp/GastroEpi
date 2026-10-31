"""Conexão SQLCipher (ADR-0003): ordem dos PRAGMAs, chave errada, rekey e cópia cifrada."""

import sqlite3
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.persistencia.conexao import (
    ChaveIncorreta,
    abrir_conexao,
    copiar_banco,
    paginas_corrompidas,
    transacao,
    trocar_chave,
)

OUTRA_CHAVE = bytes(range(32, 64))


@pytest.fixture
def caminho(tmp_path: Path, chave_de_dados: bytes) -> Path:
    caminho = tmp_path / "gastroepi.db"
    conexao = abrir_conexao(caminho, chave_de_dados)
    conexao.execute("CREATE TABLE t (v TEXT)")
    conexao.execute("INSERT INTO t VALUES ('segredo-de-teste')")
    conexao.close()
    return caminho


def test_primeira_instrucao_de_toda_conexao_e_o_pragma_key(
    caminho: Path, chave_de_dados: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    instrucoes: list[str] = []
    conectar = sqlcipher3.connect

    def conectar_rastreando(*args: object, **kwargs: object) -> sqlcipher3.Connection:
        conexao = conectar(*args, **kwargs)  # type: ignore[arg-type]  # repasse fiel dos argumentos
        conexao.set_trace_callback(instrucoes.append)
        return conexao

    monkeypatch.setattr(sqlcipher3, "connect", conectar_rastreando)
    abrir_conexao(caminho, chave_de_dados).close()

    assert instrucoes[0].startswith("PRAGMA key = \"x'")


def test_conexao_guarda_temporarios_na_memoria_com_chaves_estrangeiras_e_wal(
    caminho: Path, chave_de_dados: bytes
) -> None:
    conexao = abrir_conexao(caminho, chave_de_dados)
    pragmas = [
        conexao.execute(f"PRAGMA {p}").fetchone()[0]
        for p in ("temp_store", "foreign_keys", "journal_mode")
    ]
    conexao.close()

    assert pragmas == [2, 1, "wal"]  # temp_store 2 = MEMORY


def test_chave_errada_levanta_chave_incorreta_sem_escrever_no_stderr(
    caminho: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Sem cipher_log_level = NONE, o SQLCipher 4.19 escreve 'ERROR CORE … hmac check failed'
    no stderr do processo, que o app já traduz em ChaveIncorreta (decisão da Fase 2)."""
    with pytest.raises(ChaveIncorreta):
        abrir_conexao(caminho, OUTRA_CHAVE)

    assert capfd.readouterr().err == ""


def test_chave_com_tamanho_errado_e_recusada_antes_de_abrir(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="16 bytes"):
        abrir_conexao(tmp_path / "x.db", bytes(16))
    assert not (tmp_path / "x.db").exists()


def test_sqlite3_da_stdlib_nao_abre_e_o_cabecalho_nao_e_de_sqlite(caminho: Path) -> None:
    assert not caminho.read_bytes().startswith(b"SQLite format 3")
    comum = sqlite3.connect(caminho)
    with pytest.raises(sqlite3.DatabaseError, match="not a database"):
        comum.execute("SELECT * FROM sqlite_master").fetchall()
    comum.close()


def test_trocar_chave_recifra_o_banco_e_a_antiga_deixa_de_abrir(
    caminho: Path, chave_de_dados: bytes
) -> None:
    conexao = abrir_conexao(caminho, chave_de_dados)
    trocar_chave(conexao, OUTRA_CHAVE)
    conexao.close()

    with pytest.raises(ChaveIncorreta):
        abrir_conexao(caminho, chave_de_dados)
    nova = abrir_conexao(caminho, OUTRA_CHAVE)
    assert nova.execute("SELECT v FROM t").fetchone()[0] == "segredo-de-teste"
    nova.close()


def test_logo_apos_trocar_a_chave_todas_as_paginas_conferem(
    caminho: Path, chave_de_dados: bytes
) -> None:
    """Em WAL, o rekey escreve as páginas recifradas no -wal; sem checkpoint, o .db
    continua com páginas da chave antiga e o cipher_integrity_check as acusa."""
    conexao = abrir_conexao(caminho, chave_de_dados)
    conexao.executemany("INSERT INTO t VALUES (?)", [("x" * 500,)] * 200)

    trocar_chave(conexao, OUTRA_CHAVE)

    assert paginas_corrompidas(conexao) == ()
    conexao.close()


def test_copia_do_banco_sai_cifrada_com_a_mesma_chave(
    caminho: Path, chave_de_dados: bytes, tmp_path: Path
) -> None:
    destino = tmp_path / "copia.db"
    conexao = abrir_conexao(caminho, chave_de_dados)
    copiar_banco(conexao, destino, chave_de_dados)
    conexao.close()

    assert b"segredo-de-teste" not in destino.read_bytes()
    copia = abrir_conexao(destino, chave_de_dados)
    assert copia.execute("SELECT v FROM t").fetchone()[0] == "segredo-de-teste"
    copia.close()


def test_transacao_desfaz_tudo_quando_algo_falha(caminho: Path, chave_de_dados: bytes) -> None:
    conexao = abrir_conexao(caminho, chave_de_dados)

    with pytest.raises(RuntimeError), transacao(conexao):
        conexao.execute("INSERT INTO t VALUES ('meio-caminho')")
        raise RuntimeError("falha no meio da mutação")

    assert conexao.execute("SELECT count(*) FROM t").fetchone()[0] == 1
    conexao.close()


def test_erro_de_restricao_dentro_da_transacao_nao_vira_banco_corrompido(
    caminho: Path, chave_de_dados: bytes
) -> None:
    conexao = abrir_conexao(caminho, chave_de_dados)
    conexao.execute("CREATE TABLE u (v TEXT NOT NULL)")

    with pytest.raises(sqlcipher3.IntegrityError), transacao(conexao):
        conexao.execute("INSERT INTO u VALUES (NULL)")
    conexao.close()


def test_erro_que_ja_desfez_a_transacao_nao_e_mascarado_pelo_rollback(
    caminho: Path, chave_de_dados: bytes
) -> None:
    """RAISE(ROLLBACK) desfaz a transação inteira dentro do SQLite; um segundo ROLLBACK
    levantaria 'no transaction is active' e esconderia o erro original."""
    conexao = abrir_conexao(caminho, chave_de_dados)
    conexao.execute(
        "CREATE TEMP TRIGGER desfaz BEFORE INSERT ON t"
        " BEGIN SELECT RAISE(ROLLBACK, 'desfeito pelo gatilho'); END"
    )

    with (
        pytest.raises(sqlcipher3.IntegrityError, match="desfeito pelo gatilho"),
        transacao(conexao),
    ):
        conexao.execute("INSERT INTO t VALUES ('x')")
    assert not conexao.in_transaction
    conexao.close()
