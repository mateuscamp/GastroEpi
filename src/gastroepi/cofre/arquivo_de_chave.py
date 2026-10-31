"""gastroepi.chave: a chave de dados embrulhada pela senha (ADR-0003, itens 2 e 3).

    chave da senha = Argon2id(senha em NFC, sal de 16 bytes; t=3, m=64 MiB, p=4)
    embrulho       = AES-256-GCM(chave da senha, nonce de 12 bytes, chave de dados,
                                 dado associado = cabeçalho JSON)

O arquivo é JSON versionado. O cabeçalho (formato, versão, parâmetros e sal) entra
como dado associado do GCM: trocar qualquer byte dele invalida a etiqueta. Na leitura,
parâmetros diferentes de t=3, m=64 MiB e p=4 são recusados (AGENTS.md: nunca afrouxar).

Trocar a senha é embrulhar de novo a mesma chave de dados: o banco não muda. Nada aqui
grava a chave de dados, a senha ou a recovery key em claro.
"""

import base64
import os
import secrets
import unicodedata
from pathlib import Path
from typing import Annotated, Final, Literal

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import AfterValidator, Base64Bytes, BaseModel, ConfigDict, ValidationError

TAMANHO_DA_CHAVE = 32  # 256 bits
TAMANHO_DO_SAL = 16
TAMANHO_DO_NONCE = 12
ARGON2_TEMPO: Final = 3
ARGON2_MEMORIA_KIB: Final = 65536  # 64 MiB
ARGON2_PARALELISMO: Final = 4

_RIGIDO = ConfigDict(strict=True, frozen=True, extra="forbid")


def _com_tamanho(tamanho: int) -> AfterValidator:
    """Confere o tamanho depois de decodificar o base64 (o `Field` mediria o texto)."""

    def conferir(valor: bytes) -> bytes:
        if len(valor) != tamanho:
            raise ValueError(f"esperado {tamanho} bytes, recebido {len(valor)}")
        return valor

    return AfterValidator(conferir)


class _Kdf(BaseModel):
    model_config = _RIGIDO
    algoritmo: Literal["argon2id"] = "argon2id"
    t: Literal[3] = ARGON2_TEMPO
    m_kib: Literal[65536] = ARGON2_MEMORIA_KIB
    p: Literal[4] = ARGON2_PARALELISMO
    sal: Annotated[Base64Bytes, _com_tamanho(TAMANHO_DO_SAL)]


class _Embrulho(BaseModel):
    model_config = _RIGIDO
    algoritmo: Literal["aes-256-gcm"] = "aes-256-gcm"
    nonce: Annotated[Base64Bytes, _com_tamanho(TAMANHO_DO_NONCE)]
    chave: Base64Bytes  # chave de dados cifrada + etiqueta de 16 bytes


class _ArquivoDeChave(BaseModel):
    model_config = _RIGIDO
    formato: Literal["gastroepi.chave"] = "gastroepi.chave"
    versao: Literal[1] = 1
    kdf: _Kdf
    embrulho: _Embrulho

    def cabecalho(self) -> bytes:
        return self.model_dump_json(include={"formato", "versao", "kdf"}).encode()


class SenhaIncorreta(ValueError):
    def __init__(self) -> None:
        super().__init__("Senha incorreta")


class ArquivoDeChaveInvalido(ValueError):
    def __init__(self) -> None:
        super().__init__("O arquivo gastroepi.chave está ilegível ou não é deste app")


class ArquivoDeChaveAusente(FileNotFoundError):
    def __init__(self) -> None:
        super().__init__("O arquivo gastroepi.chave não foi encontrado")


def gerar_chave_de_dados() -> bytes:
    return secrets.token_bytes(TAMANHO_DA_CHAVE)


def _chave_da_senha(senha: str, kdf: _Kdf) -> bytes:
    """RFC 8265 (OpaqueString): a senha vai em NFC, para 'ç' composto e decomposto valerem igual."""
    return hash_secret_raw(
        unicodedata.normalize("NFC", senha).encode(),
        kdf.sal,
        time_cost=kdf.t,
        memory_cost=kdf.m_kib,
        parallelism=kdf.p,
        hash_len=TAMANHO_DA_CHAVE,
        type=Type.ID,
    )


def _b64(bruto: bytes) -> bytes:
    """Os campos `Base64Bytes` recebem o texto em base64 e guardam os bytes decodificados."""
    return base64.b64encode(bruto)


def embrulhar(chave_de_dados: bytes, senha: str) -> bytes:
    kdf = _Kdf(sal=_b64(secrets.token_bytes(TAMANHO_DO_SAL)))
    nonce = secrets.token_bytes(TAMANHO_DO_NONCE)
    sem_chave = _ArquivoDeChave(kdf=kdf, embrulho=_Embrulho(nonce=_b64(nonce), chave=b""))
    aes = AESGCM(_chave_da_senha(senha, kdf))
    cifrada = aes.encrypt(nonce, chave_de_dados, sem_chave.cabecalho())
    arquivo = _ArquivoDeChave(kdf=kdf, embrulho=_Embrulho(nonce=_b64(nonce), chave=_b64(cifrada)))
    return arquivo.model_dump_json(indent=2).encode()


def desembrulhar(conteudo: bytes, senha: str) -> bytes:
    try:
        arquivo = _ArquivoDeChave.model_validate_json(conteudo)
    except ValidationError:
        raise ArquivoDeChaveInvalido from None
    aes = AESGCM(_chave_da_senha(senha, arquivo.kdf))
    try:
        return aes.decrypt(arquivo.embrulho.nonce, arquivo.embrulho.chave, arquivo.cabecalho())
    except InvalidTag:
        raise SenhaIncorreta from None


def gravar_arquivo_de_chave(caminho: Path, conteudo: bytes) -> None:
    """Grava num temporário ao lado, força o disco e só então troca: um desligamento no
    meio deixa o arquivo antigo ou o novo, nunca um pedaço."""
    temporario = caminho.with_name(caminho.name + ".novo")
    with temporario.open("wb") as arquivo:
        arquivo.write(conteudo)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    os.replace(temporario, caminho)


def ler_arquivo_de_chave(caminho: Path) -> bytes:
    try:
        return caminho.read_bytes()
    except FileNotFoundError:
        raise ArquivoDeChaveAusente from None
