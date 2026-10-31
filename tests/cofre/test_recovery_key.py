"""Recovery key: a própria chave de dados em base32 Crockford, 8 blocos de 8 com dígito."""

import re
import secrets

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gastroepi.cofre.recovery_key import (
    ALFABETO,
    RecoveryKeyInvalida,
    digito_de_verificacao,
    formatar_recovery_key,
    ler_recovery_key,
)

CHAVE = bytes(range(32))
CHAVES = st.binary(min_size=32, max_size=32)


def test_formato_e_8_blocos_de_8_sem_caracteres_ambiguos() -> None:
    assert re.fullmatch(
        r"([0-9A-HJKMNP-TV-Z]{8} ){7}[0-9A-HJKMNP-TV-Z]{8}", formatar_recovery_key(CHAVE)
    )
    assert not set("ILOU") & set(ALFABETO)


@given(CHAVES)
def test_ler_desfaz_formatar(chave: bytes) -> None:
    assert ler_recovery_key(formatar_recovery_key(chave)) == chave


def test_leitura_tolera_caixa_espacos_hifens_e_letras_confundiveis() -> None:
    """Crockford: O vale 0; I e L valem 1 — o que um leigo copia do papel."""
    formatada = formatar_recovery_key(CHAVE)
    digitada = formatada.lower().replace(" ", "-").replace("0", "o").replace("1", "l")

    assert ler_recovery_key(f"  {digitada}\n") == CHAVE


@given(CHAVES, st.integers(min_value=0, max_value=63), st.sampled_from(ALFABETO))
def test_um_caractere_trocado_aponta_o_bloco(chave: bytes, posicao: int, trocado: str) -> None:
    simbolos = list(formatar_recovery_key(chave).replace(" ", ""))
    if simbolos[posicao] == trocado:
        return
    simbolos[posicao] = trocado

    with pytest.raises(RecoveryKeyInvalida) as erro:
        ler_recovery_key("".join(simbolos))
    assert erro.value.bloco == posicao // 8 + 1


@pytest.mark.parametrize("texto", ["", "ABCD", formatar_recovery_key(CHAVE) + " 0"])
def test_tamanho_errado_e_recusado_sem_bloco(texto: str) -> None:
    with pytest.raises(RecoveryKeyInvalida, match="8 blocos de 8") as erro:
        ler_recovery_key(texto)
    assert erro.value.bloco is None


def test_caractere_fora_do_alfabeto_aponta_o_bloco() -> None:
    simbolos = list(formatar_recovery_key(CHAVE).replace(" ", ""))
    simbolos[20] = "U"

    with pytest.raises(RecoveryKeyInvalida) as erro:
        ler_recovery_key("".join(simbolos))
    assert erro.value.bloco == 3


def test_bits_de_enchimento_diferentes_de_zero_sao_recusados() -> None:
    """56 símbolos têm 280 bits; os 24 que sobram da chave de 256 são zero."""
    blocos = formatar_recovery_key(CHAVE).split()
    ultimo = blocos[-1][:6] + "Z"  # liga bits de enchimento, com o dígito recalculado
    blocos[-1] = ultimo + digito_de_verificacao(ultimo)
    with pytest.raises(RecoveryKeyInvalida):
        ler_recovery_key(" ".join(blocos))


def test_mensagem_nunca_repete_o_que_foi_digitado() -> None:
    formatada = formatar_recovery_key(secrets.token_bytes(32))
    errada = formatada[:9] + ("0" if formatada[9] != "0" else "1") + formatada[10:]

    with pytest.raises(RecoveryKeyInvalida) as erro:
        ler_recovery_key(errada)
    assert not any(bloco in str(erro.value) for bloco in errada.split())


def test_chave_de_tamanho_errado_nao_e_formatada() -> None:
    with pytest.raises(ValueError, match="16 bytes"):
        formatar_recovery_key(bytes(16))
