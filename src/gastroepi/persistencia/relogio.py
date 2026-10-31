"""Relógio injetado: a auditoria grava o momento lido daqui (AGENTS.md, Testes)."""

from datetime import UTC, datetime
from typing import Protocol


class Relogio(Protocol):
    def agora(self) -> datetime: ...


class RelogioDoSistema:
    def agora(self) -> datetime:
        return datetime.now(UTC)
