"""Estatística sobre o banco: os serviços leem as fichas e entregam à `estatistica`."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.estatistica import descritiva, qualidade
from gastroepi.servicos import indicadores, pacientes
from gastroepi.servicos.acesso import Sessao, criar_cofre
from gastroepi.servicos.indicadores import Variavel, VariavelNumerica

FICHAS = gerar_fichas(semente=5, quantidade=30)


@pytest.fixture
def sessao(tmp_path: Path) -> Iterator[Sessao]:
    sessao, _ = criar_cofre(tmp_path, "frase longa de teste", "frase longa de teste")
    with sessao:
        yield sessao


@pytest.fixture
def sessao_com_fichas(sessao: Sessao) -> Sessao:
    for ficha in FICHAS:
        pacientes.cadastrar(sessao, ficha, usuario="teste")
    return sessao


def test_indicadores_do_banco_sao_os_da_estatistica(sessao_com_fichas: Sessao) -> None:
    sessao = sessao_com_fichas

    assert indicadores.indicadores_de_qualidade(sessao) == qualidade.indicadores_por_examinador(
        FICHAS
    )
    assert indicadores.frequencias(sessao, Variavel.SEXO) == descritiva.frequencias(
        FICHAS, Variavel.SEXO
    )
    assert indicadores.estratificacao(
        sessao, Variavel.SEXO, VariavelNumerica.IDADE
    ) == descritiva.estratificar(FICHAS, Variavel.SEXO, VariavelNumerica.IDADE)
    assert indicadores.prevalencia_polipo(sessao) == descritiva.prevalencia_polipo(FICHAS)


def test_painel_le_o_banco_uma_vez(sessao_com_fichas: Sessao) -> None:
    painel = indicadores.painel(sessao_com_fichas)
    exames = [exame for ficha in FICHAS for exame in ficha.exames]

    assert painel.n_pacientes == 30
    assert painel.n_exames == len(exames)
    assert painel.aguardando_histologia == sum(e.aguardando_histologia for e in exames)
    assert set(painel.frequencias) == set(indicadores.VARIAVEIS_DO_PAINEL)


def test_painel_vazio_nao_tem_grafico(sessao: Sessao) -> None:
    painel = indicadores.painel(sessao)

    assert (painel.n_pacientes, painel.n_exames, painel.frequencias) == (0, 0, {})
    assert painel.prevalencia_polipo.estimativa is None
