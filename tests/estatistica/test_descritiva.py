import math

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.estatistica.descritiva import (
    Descritivas,
    ItemFrequencia,
    descritivas,
    estratificar,
    frequencias,
    prevalencia_polipo,
    tabular_cruzado,
)
from gastroepi.estatistica.entrada import EntradaInvalida, SemObservacao
from gastroepi.estatistica.variaveis import NENHUMA, Variavel, VariavelNumerica
from tests.estatistica.referencias import Json, aprox, fichas_do_oraculo, oraculo, referencias_r

BASE_R = referencias_r()["base_do_oraculo"]
SEXO = {"F": "Feminino", "M": "Masculino"}
INDICACAO = {"Rastreio": "Rastreio de risco médio", "Diagnóstico": "Diagnóstica por sintomas"}


def _sem_valores(caso: Json) -> Descritivas:
    return Descritivas(**{k: v for k, v in caso.items() if k != "valores"})


def _contagens(variavel: Variavel) -> dict[str, int]:
    return _como_dict(frequencias(fichas_do_oraculo(), variavel))


def _como_dict(itens: tuple[ItemFrequencia, ...]) -> dict[str, int]:
    return {i.valor: i.contagem for i in itens}


@pytest.mark.referencia
@pytest.mark.parametrize("caso", referencias_r()["descritivas"], ids=str)
def test_descritivas_batem_com_mean_sd_e_quantile_do_r(caso: Json) -> None:
    """R 4.5.1: mean, sd, quantile(type = 7), min, max. Com um valor, sd é NA no R e 0 aqui."""
    assert descritivas(caso["valores"]) == aprox(_sem_valores(caso))


@pytest.mark.parametrize("caso", oraculo()["descritivas"], ids=str)
def test_descritivas_batem_com_o_oraculo(caso: Json) -> None:
    if "Err" in caso["saida"]:
        with pytest.raises(SemObservacao):
            descritivas(caso["entrada"])
    else:
        assert descritivas(caso["entrada"]) == aprox(Descritivas(**caso["saida"]["Ok"]))


def test_descritivas_recusam_nan() -> None:
    with pytest.raises(EntradaInvalida):
        descritivas([1.0, math.nan])


@pytest.mark.referencia
def test_frequencias_da_base_do_oraculo_batem_com_o_table_do_r() -> None:
    """R 4.5.1: table() sobre os 24 pacientes do oráculo (um exame cada)."""
    sexo = _como_dict(frequencias(fichas_do_oraculo(), Variavel.SEXO))
    assert sexo == {SEXO[k]: v for k, v in BASE_R["frequencia_sexo"].items()}
    assert _contagens(Variavel.N_POLIPOS) == BASE_R["frequencia_polipos"]
    assert _contagens(Variavel.INDICACAO) == {
        INDICACAO[k]: v for k, v in BASE_R["frequencia_indicacao"].items()
    }
    sintomas = _contagens(Variavel.SINTOMA)
    assert {k: sintomas[k] for k in BASE_R["frequencia_sintomas"]} == BASE_R["frequencia_sintomas"]


def test_frequencias_ordenam_e_dividem_pelo_numero_de_exames() -> None:
    """Paridade com o oráculo, com duas divergências de propósito:
    - exames sem comorbidade aparecem como "Nenhuma" (a v0.1.16 os omitia);
    - o percentual é dos exames (aqui igual por coincidência: 24 menções em 24 exames)."""
    esperado = {i["valor"]: i for i in oraculo()["frequencias"][4]["saida"]}
    itens = frequencias(fichas_do_oraculo(), Variavel.COMORBIDADE)
    assert {i.valor: i.contagem for i in itens}[NENHUMA] == 6
    for item in (i for i in itens if i.valor != NENHUMA):
        assert (item.contagem, item.percentual) == aprox(
            (esperado[item.valor]["contagem"], esperado[item.valor]["percentual"])
        )
    assert [i.contagem for i in itens] == sorted((i.contagem for i in itens), reverse=True)


def test_examinador_sem_nome_nao_se_divide_em_dois() -> None:
    """Divergência (ADR-0004): a v0.1.16 contava "" e "Sem examinador" como dois médicos.
    No domínio o examinador é obrigatório; a conversão junta os 8 exames num só."""
    oraculo_examinador = {i["valor"]: i["contagem"] for i in oraculo()["frequencias"][3]["saida"]}
    assert oraculo_examinador[""] + oraculo_examinador["Sem examinador"] == 8
    assert sorted(_contagens(Variavel.EXAMINADOR).values()) == [8, 8, 8]


@pytest.mark.referencia
def test_estratificar_bate_com_tapply_do_r() -> None:
    """R 4.5.1: split(idade, sexo) e split(polipo, indicacao) com mean, sd e quantile."""
    por_sexo = estratificar(fichas_do_oraculo(), Variavel.SEXO, VariavelNumerica.IDADE)
    for sigla, caso in BASE_R["idade_por_sexo"].items():
        assert por_sexo[SEXO[sigla]] == aprox(_sem_valores(caso))
    por_indicacao = estratificar(
        fichas_do_oraculo(), Variavel.INDICACAO, VariavelNumerica.N_POLIPOS
    )
    for nome, caso in BASE_R["polipos_por_indicacao"].items():
        assert por_indicacao[INDICACAO[nome]] == aprox(_sem_valores(caso))


def test_estratificar_pula_exame_sem_a_medida() -> None:
    fichas = gerar_fichas(7, 60)
    por_sexo = estratificar(fichas, Variavel.SEXO, VariavelNumerica.TEMPO_RETIRADA)
    com_tempo = sum(1 for f in fichas for e in f.exames if e.tempo_retirada_min is not None)
    assert sum(d.n for d in por_sexo.values()) == com_tempo


@pytest.mark.referencia
def test_tabular_cruzado_bate_com_o_table_do_r() -> None:
    """R 4.5.1: table(sexo, indicacao) na base do oráculo; igual ao tabular_cruzado da v0.1.16."""
    tabela = tabular_cruzado(fichas_do_oraculo(), Variavel.SEXO, Variavel.INDICACAO)
    assert tabela == {
        SEXO[s]: {INDICACAO[i]: n for i, n in linha.items()}
        for s, linha in BASE_R["sexo_por_indicacao"].items()
    }


@pytest.mark.referencia
def test_prevalencia_de_polipo_bate_com_o_prop_test_do_r_e_o_oraculo() -> None:
    """R 4.5.1: prop.test(12, 24, correct = FALSE); oráculo: 12/24, IC igual."""
    r, antiga = BASE_R["prevalencia_polipo"], oraculo()["prevalencia_polipo"][0]["saida"]["Ok"]
    resultado = prevalencia_polipo(fichas_do_oraculo())
    assert (resultado.casos, resultado.total) == (r["casos"], r["total"]) == (12, 24)
    assert resultado.ic == aprox(r["ic"])
    assert resultado.ic == aprox((antiga["ic_inferior"], antiga["ic_superior"]))


def test_prevalencia_sem_exame_nao_trava() -> None:
    """A v0.1.16 dava erro; aqui a estimativa é None e o IC é [0, 1]."""
    vazia = prevalencia_polipo([])
    assert vazia.estimativa is None
    assert vazia.ic == (0.0, 1.0)
    assert frequencias([], Variavel.SEXO) == ()
