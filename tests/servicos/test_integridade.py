"""Verificar integridade: arquivo, cadeia e dados."""

from pathlib import Path

import sqlcipher3

from gastroepi.cofre.recovery_key import ler_recovery_key
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import Indicacao
from gastroepi.servicos import integridade, pacientes
from gastroepi.servicos.acesso import NOME_DO_BANCO, criar_cofre, desbloquear

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


def test_uso_de_outro_por_campo(tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=60)

    with desbloquear(tmp_path, SENHA) as sessao:
        usos = {uso.campo: uso for uso in integridade.uso_de_outro(sessao)}

    fichas = gerar_fichas(semente=9, quantidade=60)
    exames = [e for f in fichas for e in f.exames]
    lesoes = [x for e in exames for x in e.lesoes]
    indicacao = usos["indicação"]
    assert (indicacao.registros, indicacao.outros) == (
        len(exames),
        sum(e.indicacao is Indicacao.OUTRA for e in exames),
    )
    assert usos["histologia"].registros == len(lesoes)
    assert usos["motivo de não intubação"].registros == sum(not e.intubacao_cecal for e in exames)


def test_outro_acima_de_5_por_cento_e_acusado() -> None:
    assert integridade.UsoDeOutro("histologia", 100, 6).acima_do_limite
    assert not integridade.UsoDeOutro("histologia", 100, 5).acima_do_limite
    assert integridade.UsoDeOutro("histologia", 0, 0).fracao is None
    assert not integridade.UsoDeOutro("histologia", 0, 0).acima_do_limite
