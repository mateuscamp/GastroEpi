"""Governança do ADR-0003 (SQLCipher, chave de dados separada da senha): um teste por linha.

A linha "só persistencia abre o banco" é contrato do import-linter (pyproject.toml); a
linha "empacotável no Windows" é o job da sonda congelada (.github/workflows/python.yml).
"""

import hashlib
import secrets
import sqlite3
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.cofre.recovery_key import formatar_recovery_key, ler_recovery_key
from gastroepi.dominio.cpf import formatar_cpf
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import durabilidade, integridade, pacientes
from gastroepi.servicos.acesso import (
    NOME_DA_CHAVE,
    NOME_DO_BANCO,
    BancoCorrompido,
    ChaveIncorreta,
    SenhaIncorreta,
    criar_cofre,
    desbloquear,
    gerar_nova_recovery_key,
    recuperar_acesso,
    trocar_senha,
)

SENHA = "frase longa de teste"
NOVA = "outra frase longa"


def com_textos_livres(ficha: Ficha, numero: int) -> Ficha:
    """Laudo e observação com marcadores únicos: texto livre também não pode vazar."""
    exames = []
    for exame in ficha.exames:
        lesoes = tuple(
            lesao.model_copy(update={"laudo_texto": f"LAUDO-FICTICIO-{numero}-{i}"})
            for i, lesao in enumerate(exame.lesoes)
        )
        exames.append(
            exame.model_copy(update={"lesoes": lesoes, "observacao": f"OBS-FICTICIA-{numero}"})
        )
    return ficha.model_copy(update={"exames": tuple(exames)})


def textos_sensiveis(fichas: list[Ficha]) -> set[str]:
    textos: set[str] = set()
    for ficha in fichas:
        p = ficha.paciente
        textos |= {p.nome, p.prontuario, p.data_nascimento.isoformat(), *p.comorbidades}
        textos |= {p.cpf, formatar_cpf(p.cpf)} if p.cpf else set()
        for exame in ficha.exames:
            textos |= {exame.examinador.nome, *exame.sintomas, str(exame.observacao)}
            textos |= {str(lesao.laudo_texto) for lesao in exame.lesoes}
    return textos


def cofre_com_fichas(pasta: Path, quantidade: int = 20) -> tuple[str, list[Ficha]]:
    sessao, recovery_key = criar_cofre(pasta, SENHA, SENHA)
    fichas = [
        com_textos_livres(f, n)
        for n, f in enumerate(gerar_fichas(semente=31, quantidade=quantidade))
    ]
    with sessao:
        for ficha in fichas:
            pacientes.cadastrar(sessao, ficha, usuario="teste")
    return recovery_key, fichas


def hash_do_banco(pasta: Path) -> str:
    return hashlib.sha256((pasta / NOME_DO_BANCO).read_bytes()).hexdigest()


def test_nada_legivel_no_db_no_wal_nos_backups_e_no_arquivo_de_chave(tmp_path: Path) -> None:
    pasta = tmp_path / "cofre"
    sessao, recovery_key = criar_cofre(pasta, SENHA, SENHA)
    fichas = [
        com_textos_livres(f, n) for n, f in enumerate(gerar_fichas(semente=32, quantidade=30))
    ]
    with sessao:
        for ficha in fichas:
            pacientes.cadastrar(sessao, ficha, usuario="teste")
        backup = durabilidade.fazer_backup(sessao).pasta
        # Com a sessão aberta o WAL ainda tem as páginas novas: é ele que se examina.
        wal = pasta / f"{NOME_DO_BANCO}-wal"
        assert wal.stat().st_size > 0
        arquivos = [pasta / NOME_DO_BANCO, wal, pasta / NOME_DA_CHAVE,
                    backup / NOME_DO_BANCO, backup / NOME_DA_CHAVE]  # fmt: skip
        conteudos = {f"{a.parent.name}/{a.name}": a.read_bytes() for a in arquivos}
    chave = ler_recovery_key(recovery_key)
    segredos = {*textos_sensiveis(fichas), recovery_key, chave.hex(), SENHA}
    formas = [s.encode() for s in segredos] + [s.encode("utf-16-le") for s in segredos] + [chave]

    achados = [
        (nome, forma[:12])
        for nome, bruto in conteudos.items()
        for forma in formas
        if forma in bruto
    ]

    assert achados == []


def test_sqlite3_da_stdlib_nao_abre_e_o_cabecalho_nao_e_de_sqlite(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path / "cofre", quantidade=2)
    with desbloquear(tmp_path / "cofre", SENHA) as sessao:
        backup = durabilidade.fazer_backup(sessao)

    for banco in (tmp_path / "cofre" / NOME_DO_BANCO, backup.banco):
        assert not banco.read_bytes().startswith(b"SQLite format 3")
        comum = sqlite3.connect(banco)
        with pytest.raises(sqlite3.DatabaseError, match="not a database"):
            comum.execute("SELECT name FROM sqlite_master").fetchall()
        comum.close()


def pagina_raiz(pasta: Path, chave: bytes, tabela: str) -> int:
    externa = sqlcipher3.connect(str(pasta / NOME_DO_BANCO))
    externa.execute(f"PRAGMA key = \"x'{chave.hex()}'\"")
    raiz: int = externa.execute(
        "SELECT rootpage FROM sqlite_master WHERE name = ?", (tabela,)
    ).fetchone()[0]
    externa.close()
    return raiz


def test_um_byte_trocado_e_acusado_na_leitura_e_no_cipher_integrity_check(tmp_path: Path) -> None:
    recovery_key, _ = cofre_com_fichas(tmp_path, quantidade=40)
    raiz = pagina_raiz(tmp_path, ler_recovery_key(recovery_key), "auditoria")
    banco = tmp_path / NOME_DO_BANCO
    bruto = bytearray(banco.read_bytes())
    bruto[(raiz - 1) * 4096 + 4096 // 2] ^= 0x01  # meio da página: dado, não cabeçalho
    banco.write_bytes(bytes(bruto))

    with desbloquear(tmp_path, SENHA) as sessao:
        assert integridade.verificar(sessao).paginas_corrompidas
        with pytest.raises(BancoCorrompido):
            pacientes.listar_auditoria(sessao)


def test_senha_errada_e_recovery_key_errada_nao_abrem(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)

    with pytest.raises(SenhaIncorreta):
        desbloquear(tmp_path, SENHA + "x")
    with pytest.raises(ChaveIncorreta):
        recuperar_acesso(tmp_path, formatar_recovery_key(secrets.token_bytes(32)), NOVA, NOVA)


def test_recovery_key_abre_sem_o_arquivo_de_chave_e_recria_com_senha_nova(tmp_path: Path) -> None:
    recovery_key, fichas = cofre_com_fichas(tmp_path, quantidade=3)
    (tmp_path / NOME_DA_CHAVE).unlink()

    with recuperar_acesso(tmp_path, recovery_key, NOVA, NOVA) as sessao:
        assert list(pacientes.listar(sessao).values()) == fichas

    with desbloquear(tmp_path, NOVA) as sessao:
        assert integridade.verificar(sessao).ok
    with pytest.raises(SenhaIncorreta):
        desbloquear(tmp_path, SENHA)


def test_trocar_a_senha_nao_recifra_o_banco(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=3)
    antes = hash_do_banco(tmp_path)

    trocar_senha(tmp_path, SENHA, NOVA, NOVA)

    assert hash_do_banco(tmp_path) == antes
    with desbloquear(tmp_path, NOVA) as sessao:
        assert len(pacientes.listar(sessao)) == 3
    with pytest.raises(SenhaIncorreta):
        desbloquear(tmp_path, SENHA)


def test_nova_recovery_key_recifra_preserva_a_cadeia_e_invalida_a_antiga(tmp_path: Path) -> None:
    antiga, fichas = cofre_com_fichas(tmp_path, quantidade=5)
    antes = hash_do_banco(tmp_path)

    with desbloquear(tmp_path, SENHA) as sessao:
        nova = gerar_nova_recovery_key(sessao, SENHA)
        assert integridade.verificar(sessao).ok

    assert nova != antiga
    assert hash_do_banco(tmp_path) != antes
    with pytest.raises(ChaveIncorreta):
        recuperar_acesso(tmp_path, antiga, NOVA, NOVA)
    with desbloquear(tmp_path, SENHA) as sessao:
        assert list(pacientes.listar(sessao).values()) == fichas
        assert integridade.verificar(sessao).ok
    with recuperar_acesso(tmp_path, nova, NOVA, NOVA) as sessao:
        assert integridade.verificar(sessao).ok
