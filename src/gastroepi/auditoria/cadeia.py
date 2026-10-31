"""Elo HMAC-SHA256 da cadeia de auditoria, só `v2` (ADR-0003, Princípio III).

Cada entrada guarda `v2:<hex>` = HMAC(chave da auditoria, versão + elo anterior + evento).
A mensagem é um array JSON compacto: sem ambiguidade de separador, mesmo que o snapshot
contenha qualquer caractere. A primeira entrada encadeia em `ELO_INICIAL`.

Nenhum `repr` mostra os snapshots: eles têm nome, CPF e laudo.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from enum import StrEnum

VERSAO_DO_ELO = "v2"
ELO_INICIAL = f"{VERSAO_DO_ELO}:{'0' * 64}"


class Acao(StrEnum):
    CADASTRAR = "cadastrar"
    EDITAR = "editar"
    EXCLUIR = "excluir"


class Entidade(StrEnum):
    PACIENTE = "paciente"
    COMORBIDADE = "comorbidade"
    SINTOMA = "sintoma"
    EXAMINADOR = "examinador"


@dataclass(frozen=True, slots=True)
class Evento:
    """O que a entrada afirma. `acao` e `entidade` são texto: a verificação lê o que
    está gravado, mesmo que alguém tenha posto ali um valor fora das listas."""

    momento: str  # ISO 8601 em UTC
    usuario: str
    acao: str
    entidade: str
    entidade_id: int
    antes: str | None = field(default=None, repr=False)  # snapshot JSON
    depois: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class EntradaDeAuditoria:
    id: int
    evento: Evento
    elo: str


def calcular_elo(chave: bytes, anterior: str, evento: Evento) -> str:
    partes = [
        VERSAO_DO_ELO,
        anterior,
        evento.momento,
        evento.usuario,
        evento.acao,
        evento.entidade,
        evento.entidade_id,
        evento.antes,
        evento.depois,
    ]
    mensagem = json.dumps(partes, ensure_ascii=False, separators=(",", ":")).encode()
    return f"{VERSAO_DO_ELO}:{hmac.new(chave, mensagem, hashlib.sha256).hexdigest()}"
