"""Verificar integridade. O backup mora em `durabilidade` (ADR-0005).

A verificação tem três camadas, da mais física à mais semântica:
1. páginas: o HMAC de cada página do SQLCipher (`PRAGMA cipher_integrity_check`);
2. cadeia: o elo HMAC de cada entrada de auditoria;
3. dados: o estado atual de cada registro contra o seu último retrato auditado.
Com página corrompida, as camadas 2 e 3 não rodam: ler o banco levantaria erro.
"""

from dataclasses import dataclass

from gastroepi.auditoria.cadeia import QuebraDaCadeia
from gastroepi.auditoria.conferencia import Divergencia, Motivo, RelatorioDeIntegridade
from gastroepi.servicos.sessao import Sessao, repositorio_de

__all__ = ["Divergencia", "Motivo", "QuebraDaCadeia", "RelatorioDeIntegridade"]


@dataclass(frozen=True, slots=True)
class Verificacao:
    paginas_corrompidas: tuple[str, ...]
    auditoria: RelatorioDeIntegridade | None  # None quando as páginas impedem a leitura

    @property
    def ok(self) -> bool:
        return not self.paginas_corrompidas and self.auditoria is not None and self.auditoria.ok


def verificar(sessao: Sessao) -> Verificacao:
    repositorio = repositorio_de(sessao)
    paginas = repositorio.verificar_paginas()
    if paginas:
        return Verificacao(paginas, None)
    return Verificacao((), repositorio.verificar())
