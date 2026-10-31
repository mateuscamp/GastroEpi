"""Exportar o CSV para análise (ADR-0004): a única saída do dado sem cifra (Princípio II).

Sai o arquivo pedido e, ao lado dele, o dicionário de dados (`<nome>-dicionario.csv`).
Sessão somente leitura não exporta (AGENTS.md): o banco não passou na checagem.
"""

from dataclasses import dataclass
from pathlib import Path

from gastroepi.exportacao.csv_analise import csv_de_analise, dicionario_de_dados
from gastroepi.persistencia.conexao import BancoSomenteLeitura
from gastroepi.servicos.sessao import Sessao, repositorio_de

__all__ = ["BancoSomenteLeitura", "Exportacao", "exportar_csv"]


@dataclass(frozen=True, slots=True)
class Exportacao:
    arquivo: Path
    dicionario: Path
    exames: int


def caminho_do_dicionario(arquivo: Path) -> Path:
    return arquivo.with_name(f"{arquivo.stem}-dicionario.csv")


def exportar_csv(sessao: Sessao, arquivo: Path) -> Exportacao:
    if sessao.somente_leitura:
        raise BancoSomenteLeitura
    fichas = list(repositorio_de(sessao).listar().values())
    dicionario = caminho_do_dicionario(arquivo)
    # newline="": as linhas já terminam em \r\n, como o Excel espera.
    arquivo.write_text(csv_de_analise(fichas), encoding="utf-8", newline="")
    dicionario.write_text(dicionario_de_dados(), encoding="utf-8", newline="")
    return Exportacao(arquivo, dicionario, sum(len(f.exames) for f in fichas))
