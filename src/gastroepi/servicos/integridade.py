"""Verificar integridade. O backup mora em `durabilidade` (ADR-0005).

A verificação tem três camadas, da mais física à mais semântica:
1. páginas: o HMAC de cada página do SQLCipher (`PRAGMA cipher_integrity_check`);
2. cadeia: o elo HMAC de cada entrada de auditoria;
3. dados: o estado atual de cada registro contra o seu último retrato auditado.
Com página corrompida, as camadas 2 e 3 não rodam: ler o banco levantaria erro.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from gastroepi.auditoria.cadeia import QuebraDaCadeia
from gastroepi.auditoria.conferencia import Divergencia, Motivo, RelatorioDeIntegridade
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.listas import Histologia, Indicacao, MotivoNaoIntubacao
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


# ADR-0004, "Aceito conscientemente": revisitar a lista se "outro" passar de 5%.
LIMITE_DE_OUTRO = 0.05


@dataclass(frozen=True, slots=True)
class UsoDeOutro:
    campo: str
    registros: int
    outros: int

    @property
    def fracao(self) -> float | None:
        return self.outros / self.registros if self.registros else None

    @property
    def acima_do_limite(self) -> bool:
        return self.fracao is not None and self.fracao > LIMITE_DE_OUTRO


def _contar(campo: str, valores: Iterable[object], outro: object) -> UsoDeOutro:
    lista = list(valores)
    return UsoDeOutro(campo, len(lista), sum(1 for v in lista if v == outro))


def _medicoes(fichas: list[Ficha]) -> list[tuple[str, Callable[[], Iterable[object]], object]]:
    exames = [exame for ficha in fichas for exame in ficha.exames]
    return [
        ("indicação", lambda: (e.indicacao for e in exames), Indicacao.OUTRA),
        ("histologia", lambda: (x.histologia for e in exames for x in e.lesoes), Histologia.OUTRO),
        (
            "motivo de não intubação",
            lambda: (e.motivo_nao_intubacao for e in exames if not e.intubacao_cecal),
            MotivoNaoIntubacao.OUTRO,
        ),
    ]


def uso_de_outro(sessao: Sessao) -> tuple[UsoDeOutro, ...]:
    """O % de "outro" em cada lista fechada que tem a válvula (`gastroepi verificar`)."""
    fichas = list(repositorio_de(sessao).listar().values())
    return tuple(_contar(campo, valores(), outro) for campo, valores, outro in _medicoes(fichas))
