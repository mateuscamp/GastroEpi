"""gastroepi.chave: a chave de dados embrulhada em AES-256-GCM pela chave da senha (Argon2id)."""

import base64
import json
from pathlib import Path

import pytest

from gastroepi.cofre.arquivo_de_chave import (
    ArquivoDeChaveAusente,
    ArquivoDeChaveInvalido,
    SenhaIncorreta,
    desembrulhar,
    embrulhar,
    gerar_chave_de_dados,
    gravar_arquivo_de_chave,
    ler_arquivo_de_chave,
)
from gastroepi.cofre.recovery_key import formatar_recovery_key

CHAVE = bytes(range(32))
SENHA = "frase longa de teste"


@pytest.fixture(scope="module")
def embrulhada() -> bytes:
    return embrulhar(CHAVE, SENHA)


def test_chave_de_dados_tem_256_bits_aleatorios() -> None:
    chaves = {gerar_chave_de_dados() for _ in range(4)}

    assert len(chaves) == 4
    assert all(len(chave) == 32 for chave in chaves)


def test_senha_certa_desembrulha_a_chave(embrulhada: bytes) -> None:
    assert desembrulhar(embrulhada, SENHA) == CHAVE


def test_senha_errada_levanta_senha_incorreta(embrulhada: bytes) -> None:
    with pytest.raises(SenhaIncorreta):
        desembrulhar(embrulhada, SENHA + "x")


def test_senha_em_nfd_e_nfc_e_a_mesma() -> None:
    """Teclados diferentes podem mandar 'ç' composto ou decomposto (RFC 8265)."""
    embrulhada = embrulhar(CHAVE, "maçã-do-amor")

    assert desembrulhar(embrulhada, "maçã-do-amor") == CHAVE


def test_arquivo_e_json_versionado_com_argon2id_t3_m64mib_p4(embrulhada: bytes) -> None:
    conteudo = json.loads(embrulhada)

    assert (conteudo["formato"], conteudo["versao"]) == ("gastroepi.chave", 1)
    assert {k: v for k, v in conteudo["kdf"].items() if k != "sal"} == {
        "algoritmo": "argon2id", "t": 3, "m_kib": 65536, "p": 4,
    }  # fmt: skip
    assert len(base64.b64decode(conteudo["kdf"]["sal"])) == 16
    assert conteudo["embrulho"]["algoritmo"] == "aes-256-gcm"
    assert len(base64.b64decode(conteudo["embrulho"]["nonce"])) == 12


def test_cada_embrulho_tem_sal_e_nonce_novos() -> None:
    um, outro = json.loads(embrulhar(CHAVE, SENHA)), json.loads(embrulhar(CHAVE, SENHA))

    assert um["kdf"]["sal"] != outro["kdf"]["sal"]
    assert um["embrulho"]["nonce"] != outro["embrulho"]["nonce"]


def test_arquivo_nao_contem_a_chave_nem_a_senha_em_forma_alguma(embrulhada: bytes) -> None:
    formas = [CHAVE, CHAVE.hex().encode(), base64.b64encode(CHAVE),
              formatar_recovery_key(CHAVE).encode(), SENHA.encode()]  # fmt: skip

    assert not [forma for forma in formas if forma in embrulhada]


def _alterado(embrulhada: bytes, secao: str, campo: str, valor: object) -> bytes:
    conteudo = json.loads(embrulhada)
    conteudo[secao][campo] = valor
    return json.dumps(conteudo).encode()


@pytest.mark.parametrize(
    "secao, campo, valor",
    [("kdf", "t", 1), ("kdf", "m_kib", 1024), ("kdf", "p", 1), ("kdf", "algoritmo", "pbkdf2")],
)
def test_parametros_afrouxados_sao_recusados(
    embrulhada: bytes, secao: str, campo: str, valor: object
) -> None:
    with pytest.raises(ArquivoDeChaveInvalido):
        desembrulhar(_alterado(embrulhada, secao, campo, valor), SENHA)


def test_cabecalho_adulterado_nao_desembrulha(embrulhada: bytes) -> None:
    """O cabeçalho entra como dado associado do GCM: trocar o sal invalida a etiqueta."""
    outro_sal = base64.b64encode(bytes(16)).decode()

    with pytest.raises(SenhaIncorreta):
        desembrulhar(_alterado(embrulhada, "kdf", "sal", outro_sal), SENHA)


def test_sal_de_tamanho_errado_e_recusado(embrulhada: bytes) -> None:
    sal_curto = base64.b64encode(bytes(8)).decode()

    with pytest.raises(ArquivoDeChaveInvalido):
        desembrulhar(_alterado(embrulhada, "kdf", "sal", sal_curto), SENHA)


@pytest.mark.parametrize("conteudo", [b"", b"{}", b"nao e json", b'{"formato": "outro"}'])
def test_arquivo_malformado_levanta_arquivo_invalido(conteudo: bytes) -> None:
    with pytest.raises(ArquivoDeChaveInvalido):
        desembrulhar(conteudo, SENHA)


def test_gravar_e_ler_ida_e_volta_sem_sobra_temporaria(tmp_path: Path, embrulhada: bytes) -> None:
    caminho = tmp_path / "gastroepi.chave"
    caminho.write_bytes(b"versao antiga")

    gravar_arquivo_de_chave(caminho, embrulhada)

    assert ler_arquivo_de_chave(caminho) == embrulhada
    assert [p.name for p in tmp_path.iterdir()] == ["gastroepi.chave"]


def test_ler_arquivo_ausente_levanta_arquivo_ausente(tmp_path: Path) -> None:
    with pytest.raises(ArquivoDeChaveAusente):
        ler_arquivo_de_chave(tmp_path / "gastroepi.chave")
