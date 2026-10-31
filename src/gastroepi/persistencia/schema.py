"""Schema do banco (ADR-0004) e migrações.

Cada migração é uma função que recebe a conexão; `migrar` aplica, em ordem e cada uma
na sua transação, as que faltam para chegar em `VERSAO_DO_SCHEMA` (guardada em
`PRAGMA user_version`). Rodar de novo não faz nada: é idempotente.

As listas dos `CHECK` são literais, congeladas na migração que as criou. Se uma lista
do domínio mudar (`VERSAO_DAS_LISTAS`), `test_lista_do_check_e_a_lista_do_dominio`
acusa, e a mudança exige uma migração nova (AGENTS.md).

Os `CHECK` são a segunda linha: barram o valor absurdo gravado por fora. A regra
clínica fina (displasia coerente com a histologia) fica só no domínio; um registro
que a viola por fora aparece na verificação como ilegível.
"""

import secrets
from collections.abc import Callable

import sqlcipher3

from gastroepi.persistencia.conexao import transacao

_TEXTO = "CHECK (trim({0}) <> '')"
_DATA = "CHECK (date({0}) IS {0} AND {0} >= '1900-01-01')"

_TABELAS_1 = (
    "CREATE TABLE metadados (chave TEXT PRIMARY KEY, valor BLOB NOT NULL) STRICT",
    f"""CREATE TABLE comorbidade (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL {_TEXTO.format("nome")},
        nome_normalizado TEXT NOT NULL UNIQUE
    ) STRICT""",
    f"""CREATE TABLE sintoma (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL {_TEXTO.format("nome")},
        nome_normalizado TEXT NOT NULL UNIQUE
    ) STRICT""",
    f"""CREATE TABLE examinador (
        id INTEGER PRIMARY KEY,
        nome TEXT NOT NULL {_TEXTO.format("nome")},
        crm TEXT NOT NULL CHECK (length(crm) BETWEEN 1 AND 8 AND crm NOT GLOB '*[^0-9]*'),
        uf TEXT NOT NULL CHECK (uf IN ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO',
            'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR',
            'SC', 'SP', 'SE', 'TO')),
        UNIQUE (crm, uf)
    ) STRICT""",
    f"""CREATE TABLE paciente (
        id INTEGER PRIMARY KEY,
        prontuario TEXT NOT NULL UNIQUE {_TEXTO.format("prontuario")},
        cpf TEXT UNIQUE CHECK (cpf IS NULL OR (length(cpf) = 11 AND cpf NOT GLOB '*[^0-9]*')),
        nome TEXT NOT NULL {_TEXTO.format("nome")},
        sexo TEXT NOT NULL CHECK (sexo IN ('M', 'F')),
        data_nascimento TEXT NOT NULL {_DATA.format("data_nascimento")}
    ) STRICT""",
    """CREATE TABLE paciente_comorbidade (
        paciente_id INTEGER NOT NULL REFERENCES paciente (id) ON DELETE CASCADE,
        ordem INTEGER NOT NULL,
        comorbidade_id INTEGER NOT NULL REFERENCES comorbidade (id),
        PRIMARY KEY (paciente_id, ordem)
    ) STRICT""",
    """CREATE TABLE historico_familiar (
        paciente_id INTEGER NOT NULL REFERENCES paciente (id) ON DELETE CASCADE,
        ordem INTEGER NOT NULL,
        parentesco TEXT NOT NULL CHECK (parentesco IN ('pai', 'mae', 'irmao_irma',
            'filho_filha', 'avo', 'tio_tia', 'sobrinho_sobrinha', 'neto_neta',
            'meio_irmao_irma', 'primo_prima', 'bisavo', 'tio_avo')),
        idade_diagnostico INTEGER CHECK (idade_diagnostico BETWEEN 0 AND 120),
        PRIMARY KEY (paciente_id, ordem)
    ) STRICT""",
)

_EXAME_1 = f"""CREATE TABLE exame (
    id INTEGER PRIMARY KEY,
    paciente_id INTEGER NOT NULL REFERENCES paciente (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    data_exame TEXT NOT NULL {_DATA.format("data_exame")},
    indicacao TEXT NOT NULL CHECK (indicacao IN ('rastreio_risco_medio',
        'rastreio_risco_aumentado', 'vigilancia_pos_polipectomia', 'sangue_oculto_positivo',
        'diagnostica_por_sintomas', 'seguimento_dii', 'outra')),
    indicacao_outra TEXT,
    examinador_id INTEGER NOT NULL REFERENCES examinador (id),
    boston_direito INTEGER CHECK (boston_direito BETWEEN 0 AND 3),
    boston_transverso INTEGER CHECK (boston_transverso BETWEEN 0 AND 3),
    boston_esquerdo INTEGER CHECK (boston_esquerdo BETWEEN 0 AND 3),
    intubacao_cecal INTEGER NOT NULL CHECK (intubacao_cecal IN (0, 1)),
    motivo_nao_intubacao TEXT CHECK (motivo_nao_intubacao IN ('preparo_inadequado',
        'obstrucao_ou_estenose', 'dificuldade_tecnica', 'intolerancia_ou_sedacao',
        'colite_grave', 'intercorrencia_clinica', 'outro')),
    motivo_outro TEXT,
    tempo_retirada_min REAL CHECK (tempo_retirada_min > 0),
    observacao TEXT,
    UNIQUE (paciente_id, ordem),
    CHECK ((boston_direito IS NULL) = (boston_transverso IS NULL)
        AND (boston_transverso IS NULL) = (boston_esquerdo IS NULL)),
    CHECK ((indicacao = 'outra') = (indicacao_outra IS NOT NULL)),
    CHECK ((intubacao_cecal = 0) = (motivo_nao_intubacao IS NOT NULL)),
    CHECK ((motivo_nao_intubacao IS 'outro') = (motivo_outro IS NOT NULL))
) STRICT"""

_FILHOS_DO_EXAME_1 = (
    """CREATE TABLE exame_sintoma (
        exame_id INTEGER NOT NULL REFERENCES exame (id) ON DELETE CASCADE,
        ordem INTEGER NOT NULL,
        sintoma_id INTEGER NOT NULL REFERENCES sintoma (id),
        PRIMARY KEY (exame_id, ordem)
    ) STRICT""",
    """CREATE TABLE lesao (
        exame_id INTEGER NOT NULL REFERENCES exame (id) ON DELETE CASCADE,
        ordem INTEGER NOT NULL,
        segmento TEXT NOT NULL CHECK (segmento IN ('ceco', 'ascendente', 'flexura_hepatica',
            'transverso', 'flexura_esplenica', 'descendente', 'sigmoide', 'reto')),
        tamanho_mm INTEGER NOT NULL CHECK (tamanho_mm >= 1),
        paris TEXT NOT NULL CHECK (paris IN ('0-Ip', '0-Isp', '0-Is', '0-IIa', '0-IIb',
            '0-IIc', '0-III', 'nao_classificada')),
        histologia TEXT NOT NULL CHECK (histologia IN ('adenoma_tubular',
            'adenoma_tubuloviloso', 'adenoma_viloso', 'lesao_serrilhada_sessil',
            'adenoma_serrilhado_tradicional', 'hiperplasico', 'adenocarcinoma', 'outro',
            'aguardando', 'sem_histologia')),
        displasia TEXT NOT NULL CHECK (displasia IN ('baixo', 'alto', 'nao_se_aplica')),
        histologia_outra TEXT,
        laudo_texto TEXT,
        PRIMARY KEY (exame_id, ordem),
        CHECK ((histologia = 'outro') = (histologia_outra IS NOT NULL))
    ) STRICT""",
)

_AUDITORIA_1 = (
    """CREATE TABLE auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        momento TEXT NOT NULL,
        usuario TEXT NOT NULL,
        acao TEXT NOT NULL CHECK (acao IN ('cadastrar', 'editar', 'excluir')),
        entidade TEXT NOT NULL CHECK (entidade IN ('paciente', 'comorbidade', 'sintoma',
            'examinador')),
        entidade_id INTEGER NOT NULL,
        antes TEXT,
        depois TEXT,
        elo TEXT NOT NULL
    ) STRICT""",
    # Princípio III: append-only garantido pelo banco, não só pelo app.
    """CREATE TRIGGER auditoria_sem_update BEFORE UPDATE ON auditoria
        BEGIN SELECT RAISE(ABORT, 'auditoria é append-only: UPDATE proibido'); END""",
    """CREATE TRIGGER auditoria_sem_delete BEFORE DELETE ON auditoria
        BEGIN SELECT RAISE(ABORT, 'auditoria é append-only: DELETE proibido'); END""",
    "CREATE INDEX exame_por_paciente ON exame (paciente_id)",
    "CREATE INDEX auditoria_por_entidade ON auditoria (entidade, entidade_id)",
)


def _migracao_1(conexao: sqlcipher3.Connection) -> None:
    for comando in (*_TABELAS_1, _EXAME_1, *_FILHOS_DO_EXAME_1, *_AUDITORIA_1):
        conexao.execute(comando)
    # ADR-0003: chave HMAC da auditoria separada da chave de dados, dentro do banco cifrado.
    conexao.execute(
        "INSERT INTO metadados (chave, valor) VALUES ('chave_auditoria', ?)",
        (secrets.token_bytes(32),),
    )


_MIGRACOES: tuple[Callable[[sqlcipher3.Connection], None], ...] = (_migracao_1,)
VERSAO_DO_SCHEMA = len(_MIGRACOES)


class BancoMaisNovoQueOApp(RuntimeError):
    """O banco foi gravado por uma versão mais nova do app; abrir aqui arriscaria o dado."""

    def __init__(self, versao_do_banco: int) -> None:
        conhecida = VERSAO_DO_SCHEMA
        super().__init__(f"Banco no schema {versao_do_banco}; este app conhece até o {conhecida}")
        self.versao_do_banco = versao_do_banco


def _versao(conexao: sqlcipher3.Connection) -> int:
    versao: int = conexao.execute("PRAGMA user_version").fetchone()[0]
    if versao > VERSAO_DO_SCHEMA:
        raise BancoMaisNovoQueOApp(versao)
    return versao


def migrar(conexao: sqlcipher3.Connection) -> None:
    """A versão é relida dentro de cada transação: outra instância pode ter migrado antes."""
    for numero, migracao in enumerate(_MIGRACOES, start=1):
        if _versao(conexao) >= numero:
            continue
        with transacao(conexao):
            if _versao(conexao) < numero:
                migracao(conexao)
                conexao.execute(f"PRAGMA user_version = {numero}")
