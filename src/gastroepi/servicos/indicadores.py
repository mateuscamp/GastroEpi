"""Estatística sobre o banco: indicadores de qualidade, frequências, estratificação e
prevalência. Lê as fichas pelo repositório e entrega a `estatistica`, que nunca lê o banco.
"""

from dataclasses import dataclass

from gastroepi.dominio.ficha import Ficha
from gastroepi.estatistica import descritiva, qualidade
from gastroepi.estatistica.descritiva import Descritivas, ItemFrequencia
from gastroepi.estatistica.proporcoes import Proporcao
from gastroepi.estatistica.qualidade import (
    LIMIARES,
    Alerta,
    Indicador,
    IndicadoresDoExaminador,
    Media,
)
from gastroepi.estatistica.variaveis import Variavel, VariavelNumerica
from gastroepi.servicos.sessao import Sessao, repositorio_de

__all__ = [
    "LIMIARES",
    "Alerta",
    "Descritivas",
    "Indicador",
    "IndicadoresDoExaminador",
    "ItemFrequencia",
    "Media",
    "Proporcao",
    "Variavel",
    "VariavelNumerica",
]

# Os gráficos do painel, na ordem em que aparecem.
VARIAVEIS_DO_PAINEL = (
    Variavel.SEXO,
    Variavel.FAIXA_ETARIA,
    Variavel.N_POLIPOS,
    Variavel.INDICACAO,
    Variavel.COMORBIDADE,
    Variavel.SINTOMA,
)


def _fichas(sessao: Sessao) -> list[Ficha]:
    return list(repositorio_de(sessao).listar().values())


def indicadores_de_qualidade(sessao: Sessao) -> tuple[IndicadoresDoExaminador, ...]:
    return qualidade.indicadores_por_examinador(_fichas(sessao))


def frequencias(sessao: Sessao, variavel: Variavel) -> tuple[ItemFrequencia, ...]:
    return descritiva.frequencias(_fichas(sessao), variavel)


def estratificacao(
    sessao: Sessao, grupo: Variavel, valor: VariavelNumerica
) -> dict[str, Descritivas]:
    return descritiva.estratificar(_fichas(sessao), grupo, valor)


def prevalencia_polipo(sessao: Sessao) -> Proporcao:
    return descritiva.prevalencia_polipo(_fichas(sessao))


@dataclass(frozen=True, slots=True)
class Painel:
    n_pacientes: int
    n_exames: int
    prevalencia_polipo: Proporcao
    aguardando_histologia: int  # exames com alguma lesão sem o laudo
    frequencias: dict[Variavel, tuple[ItemFrequencia, ...]]


def painel(sessao: Sessao) -> Painel:
    """Tudo o que a tela do painel mostra, numa leitura só do banco."""
    fichas = _fichas(sessao)
    exames = [exame for ficha in fichas for exame in ficha.exames]
    return Painel(
        n_pacientes=len(fichas),
        n_exames=len(exames),
        prevalencia_polipo=descritiva.prevalencia_polipo(fichas),
        aguardando_histologia=sum(1 for exame in exames if exame.aguardando_histologia),
        frequencias={v: descritiva.frequencias(fichas, v) for v in VARIAVEIS_DO_PAINEL if exames},
    )
