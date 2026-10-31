"""Cofres reais em tmp_path para os testes de serviços, da casca e da CLI (só fictícios)."""

from pathlib import Path

import sqlcipher3

from gastroepi.cofre.recovery_key import ler_recovery_key
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import NOME_DO_BANCO, Sessao, criar_cofre

SENHA = "frase longa de teste"


def cofre_com_fichas(pasta: Path, quantidade: int = 5, semente: int = 9) -> tuple[Sessao, str]:
    """Sessão aberta e a recovery key mostrada na criação."""
    sessao, recovery_key = criar_cofre(pasta, SENHA, SENHA)
    for ficha in gerar_fichas(semente=semente, quantidade=quantidade):
        pacientes.cadastrar(sessao, ficha, usuario="teste")
    return sessao, recovery_key


def corromper_o_meio(pasta: Path) -> None:
    """Uma página do meio estragada: o banco abre, mas em somente leitura (ADR-0005)."""
    banco = pasta / NOME_DO_BANCO
    bruto = bytearray(banco.read_bytes())
    bruto[len(bruto) // 2 + 1000] ^= 0xFF
    banco.write_bytes(bytes(bruto))


def corromper_a_pagina_1(pasta: Path) -> None:
    """A página 1 estragada: a chave não abre o banco (`BancoIlegivel`, ADR-0005)."""
    banco = pasta / NOME_DO_BANCO
    bruto = bytearray(banco.read_bytes())
    bruto[100] ^= 0xFF
    banco.write_bytes(bytes(bruto))


def adulterar_um_nome(pasta: Path, recovery_key: str) -> None:
    """Cenário 3: alguém com a chave muda um nome por fora do app."""
    chave = ler_recovery_key(recovery_key)
    externa = sqlcipher3.connect(str(pasta / NOME_DO_BANCO))
    externa.execute(f"PRAGMA key = \"x'{chave.hex()}'\"")
    externa.execute("UPDATE paciente SET nome = 'Outro Nome' WHERE id = 2")
    externa.commit()
    externa.close()
