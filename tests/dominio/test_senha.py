"""Senha nova: digitada duas vezes, iguais, com pelo menos 8 caracteres (FR-1.1)."""

import pytest

from gastroepi.dominio.senha import SenhaCurta, SenhasDiferentes, conferir_nova_senha


def test_senha_igual_a_confirmacao_e_longa_passa() -> None:
    conferir_nova_senha("oito car", "oito car")


def test_confirmacao_diferente_e_recusada_sem_repetir_as_senhas() -> None:
    with pytest.raises(SenhasDiferentes, match="não são iguais") as erro:
        conferir_nova_senha("segredo-um", "segredo-dois")

    assert "segredo" not in str(erro.value)


def test_senha_com_menos_de_8_caracteres_e_recusada() -> None:
    with pytest.raises(SenhaCurta, match="8 caracteres"):
        conferir_nova_senha("1234567", "1234567")


def test_tamanho_conta_caracteres_e_nao_bytes_nem_acentos_decompostos() -> None:
    """'ção' decomposto tem 5 pontos de código, mas são 3 caracteres (NFC)."""
    decomposta = "ção" + "abcd"  # 7 caracteres em NFC, 9 pontos de código
    with pytest.raises(SenhaCurta):
        conferir_nova_senha(decomposta, decomposta)
