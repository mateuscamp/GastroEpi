"""Schema do banco (ADR-0004) e migrações."""

import secrets

import sqlcipher3

from gastroepi.persistencia.conexao import transacao

_MIGRACAO_1 = """
CREATE TABLE metadados (chave TEXT PRIMARY KEY, valor BLOB NOT NULL) STRICT;

CREATE TABLE comorbidade (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE sintoma (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE examinador (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    crm TEXT NOT NULL,
    uf TEXT NOT NULL,
    UNIQUE (crm, uf)
) STRICT;

CREATE TABLE paciente (
    id INTEGER PRIMARY KEY,
    prontuario TEXT NOT NULL UNIQUE,
    cpf TEXT UNIQUE,
    nome TEXT NOT NULL,
    sexo TEXT NOT NULL,
    data_nascimento TEXT NOT NULL
) STRICT;

CREATE TABLE paciente_comorbidade (
    paciente_id INTEGER NOT NULL REFERENCES paciente (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    comorbidade_id INTEGER NOT NULL REFERENCES comorbidade (id),
    PRIMARY KEY (paciente_id, ordem)
) STRICT;

CREATE TABLE historico_familiar (
    paciente_id INTEGER NOT NULL REFERENCES paciente (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    parentesco TEXT NOT NULL,
    idade_diagnostico INTEGER,
    PRIMARY KEY (paciente_id, ordem)
) STRICT;

CREATE TABLE exame (
    id INTEGER PRIMARY KEY,
    paciente_id INTEGER NOT NULL REFERENCES paciente (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    data_exame TEXT NOT NULL,
    indicacao TEXT NOT NULL,
    indicacao_outra TEXT,
    examinador_id INTEGER NOT NULL REFERENCES examinador (id),
    boston_direito INTEGER,
    boston_transverso INTEGER,
    boston_esquerdo INTEGER,
    intubacao_cecal INTEGER NOT NULL,
    motivo_nao_intubacao TEXT,
    motivo_outro TEXT,
    tempo_retirada_min REAL,
    observacao TEXT,
    UNIQUE (paciente_id, ordem)
) STRICT;

CREATE TABLE exame_sintoma (
    exame_id INTEGER NOT NULL REFERENCES exame (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    sintoma_id INTEGER NOT NULL REFERENCES sintoma (id),
    PRIMARY KEY (exame_id, ordem)
) STRICT;

CREATE TABLE lesao (
    exame_id INTEGER NOT NULL REFERENCES exame (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    segmento TEXT NOT NULL,
    tamanho_mm INTEGER NOT NULL,
    paris TEXT NOT NULL,
    histologia TEXT NOT NULL,
    displasia TEXT NOT NULL,
    histologia_outra TEXT,
    laudo_texto TEXT,
    PRIMARY KEY (exame_id, ordem)
) STRICT;

CREATE TABLE auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento TEXT NOT NULL,
    usuario TEXT NOT NULL,
    acao TEXT NOT NULL,
    entidade TEXT NOT NULL,
    entidade_id INTEGER NOT NULL,
    antes TEXT,
    depois TEXT,
    elo TEXT NOT NULL
) STRICT;

CREATE INDEX exame_por_paciente ON exame (paciente_id);
CREATE INDEX auditoria_por_entidade ON auditoria (entidade, entidade_id);
"""


def migrar(conexao: sqlcipher3.Connection) -> None:
    if conexao.execute("PRAGMA user_version").fetchone()[0] == 1:
        return
    with transacao(conexao):
        for comando in _MIGRACAO_1.split(";"):
            conexao.execute(comando)
        conexao.execute(
            "INSERT INTO metadados (chave, valor) VALUES ('chave_auditoria', ?)",
            (secrets.token_bytes(32),),
        )
        conexao.execute("PRAGMA user_version = 1")
