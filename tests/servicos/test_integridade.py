"""Verificar integridade (arquivo, cadeia e dados) e backup com o arquivo de chave."""

from pathlib import Path

import sqlcipher3

from gastroepi.cofre.recovery_key import ler_recovery_key
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import integridade, pacientes
from gastroepi.servicos.acesso import NOME_DA_CHAVE, NOME_DO_BANCO, criar_cofre, desbloquear

SENHA = "frase longa de teste"


def cofre_com_fichas(pasta: Path, quantidade: int = 5) -> str:
    """Devolve a recovery key, que é a chave de dados (ADR-0003)."""
    sessao, recovery_key = criar_cofre(pasta, SENHA, SENHA)
    with sessao:
        for ficha in gerar_fichas(semente=9, quantidade=quantidade):
            pacientes.cadastrar(sessao, ficha, usuario="teste")
    return recovery_key


def test_cofre_integro_passa_nas_tres_verificacoes(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path)

    with desbloquear(tmp_path, SENHA) as sessao:
        verificacao = integridade.verificar(sessao)

    assert verificacao.ok
    assert verificacao.paginas_corrompidas == ()
    assert verificacao.auditoria is not None and verificacao.auditoria.ok


def test_alteracao_por_fora_reprova_a_verificacao(tmp_path: Path) -> None:
    chave = ler_recovery_key(cofre_com_fichas(tmp_path))
    externa = sqlcipher3.connect(str(tmp_path / NOME_DO_BANCO))
    externa.execute(f"PRAGMA key = \"x'{chave.hex()}'\"")
    externa.execute("UPDATE paciente SET nome = 'Outro' WHERE id = 2")
    externa.commit()
    externa.close()

    with desbloquear(tmp_path, SENHA) as sessao:
        verificacao = integridade.verificar(sessao)

    assert not verificacao.ok
    assert verificacao.auditoria is not None
    assert [(d.entidade, d.entidade_id) for d in verificacao.auditoria.dados] == [("paciente", 2)]


def test_pagina_corrompida_reprova_sem_tentar_ler_os_dados(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=40)
    banco = tmp_path / NOME_DO_BANCO
    bruto = bytearray(banco.read_bytes())
    bruto[len(bruto) - 4096 + 1000] ^= 0xFF
    banco.write_bytes(bytes(bruto))

    with desbloquear(tmp_path, SENHA) as sessao:
        verificacao = integridade.verificar(sessao)

    assert not verificacao.ok
    assert len(verificacao.paginas_corrompidas) == 1
    assert verificacao.auditoria is None


def test_backup_leva_o_banco_e_o_arquivo_de_chave_e_abre_com_a_mesma_senha(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path / "cofre")
    destino = tmp_path / "backup"

    with desbloquear(tmp_path / "cofre", SENHA) as sessao:
        integridade.fazer_backup(sessao, destino)
        originais = pacientes.listar(sessao)

    assert {p.name for p in destino.iterdir()} == {NOME_DO_BANCO, NOME_DA_CHAVE}
    with desbloquear(destino, SENHA) as copia:
        assert pacientes.listar(copia) == originais
        assert integridade.verificar(copia).ok
