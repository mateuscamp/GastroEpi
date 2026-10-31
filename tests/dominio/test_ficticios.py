"""Gerador de fictícios: mesma semente, mesmos pacientes, todos válidos pelo domínio."""

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from gastroepi.dominio.cpf import normalizar_cpf
from gastroepi.dominio.exame import Exame, idade_no_exame
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import Histologia, Indicacao
from gastroepi.dominio.paciente import Paciente


def test_mesma_semente_gera_as_mesmas_fichas() -> None:
    assert gerar_fichas(semente=7, quantidade=30) == gerar_fichas(semente=7, quantidade=30)


def test_semente_diferente_gera_fichas_diferentes() -> None:
    assert gerar_fichas(semente=7, quantidade=30) != gerar_fichas(semente=8, quantidade=30)


def test_gerador_nao_depende_do_random_global() -> None:
    random.seed(1)
    primeira = gerar_fichas(semente=3, quantidade=10)
    random.seed(2)
    assert gerar_fichas(semente=3, quantidade=10) == primeira


def test_quantidade_e_prontuarios_unicos_marcados_como_ficticios() -> None:
    fichas = gerar_fichas(semente=1, quantidade=50)
    prontuarios = [f.paciente.prontuario for f in fichas]

    assert len(fichas) == 50
    assert len(set(prontuarios)) == 50
    assert all(p.startswith("F") for p in prontuarios)


def test_todo_cpf_gerado_e_valido() -> None:
    for ficha in gerar_fichas(semente=2, quantidade=100):
        assert ficha.paciente.cpf is not None
        assert normalizar_cpf(ficha.paciente.cpf) == ficha.paciente.cpf


def test_exames_em_ordem_e_o_retorno_e_vigilancia() -> None:
    for ficha in gerar_fichas(semente=4, quantidade=200):
        datas = [e.data_exame for e in ficha.exames]
        assert datas == sorted(datas)
        assert 40 <= idade_no_exame(ficha.paciente, ficha.exames[0]) <= 80
        assert all(e.indicacao is Indicacao.VIGILANCIA_POS_POLIPECTOMIA for e in ficha.exames[1:])


def test_duzentas_fichas_cobrem_todas_as_histologias_e_indicacoes() -> None:
    """A demo e a Fase 3 precisam de todo item de lista aparecendo ao menos uma vez."""
    exames = [e for f in gerar_fichas(semente=5, quantidade=200) for e in f.exames]

    assert {e.indicacao for e in exames} == set(Indicacao)
    assert {lesao.histologia for e in exames for lesao in e.lesoes} == set(Histologia)
    assert any(not e.intubacao_cecal for e in exames)
    assert any(e.preparo is None for e in exames)


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=0, max_value=2**32))
def test_toda_ficha_de_qualquer_semente_revalida_pelo_json(semente: int) -> None:
    for ficha in gerar_fichas(semente=semente, quantidade=3):
        assert isinstance(ficha, Ficha)
        assert Paciente.model_validate_json(ficha.paciente.model_dump_json()) == ficha.paciente
        for exame in ficha.exames:
            assert Exame.model_validate_json(exame.model_dump_json()) == exame
