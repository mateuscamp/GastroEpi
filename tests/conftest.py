"""Configuração comum da suíte e os fakes de I/O injetados (AGENTS.md, Testes)."""

import os
from datetime import UTC, datetime, timedelta

import pytest

# A casca Qt (Fase 5) roda sem display no CI e na máquina do agente.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Chave de dados só de teste: 256 bits fixos, nunca usada fora da suíte.
CHAVE_DE_TESTE = bytes(range(32))


class RelogioFalso:
    """Relógio injetado: começa num instante fixo e anda 1 s a cada leitura."""

    def __init__(self, inicio: datetime = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)) -> None:
        self._agora = inicio

    def agora(self) -> datetime:
        instante = self._agora
        self._agora += timedelta(seconds=1)
        return instante


class RelogioManual:
    """Relógio parado: só anda quando o teste manda (backup a cada 15 min, ADR-0005)."""

    def __init__(self, inicio: datetime = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)) -> None:
        self._agora = inicio

    def agora(self) -> datetime:
        return self._agora

    def avancar(self, intervalo: timedelta) -> None:
        self._agora += intervalo


@pytest.fixture
def relogio() -> RelogioFalso:
    return RelogioFalso()


@pytest.fixture
def chave_de_dados() -> bytes:
    return CHAVE_DE_TESTE
