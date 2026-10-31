"""Listas fechadas do ADR-0004, com as escolhas do dono em 2026-10-31.

Mudar uma lista exige migração (ADR-0004): este teste quebra de propósito quando um
item entra ou sai, para lembrar de subir VERSAO_DAS_LISTAS e escrever a migração.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gastroepi.dominio.listas import (
    UF,
    VERSAO_DAS_LISTAS,
    Displasia,
    Histologia,
    Indicacao,
    ListaFechada,
    MotivoNaoIntubacao,
    Parentesco,
    Paris,
    Segmento,
    Sexo,
)

LISTAS: list[type[ListaFechada]] = [
    Sexo, Parentesco, Segmento, Paris, Histologia, Displasia, Indicacao, MotivoNaoIntubacao,
]  # fmt: skip


def test_versao_das_listas_e_a_primeira() -> None:
    assert VERSAO_DAS_LISTAS == 1


@pytest.mark.parametrize(
    ("lista", "quantidade"),
    [
        (Sexo, 2), (Parentesco, 12), (Segmento, 8), (Paris, 8), (Histologia, 10),
        (Displasia, 3), (Indicacao, 7), (MotivoNaoIntubacao, 7),
    ],
)  # fmt: skip
def test_cada_lista_tem_os_itens_combinados(lista: type[ListaFechada], quantidade: int) -> None:
    assert len(lista) == quantidade


@pytest.mark.parametrize("lista", LISTAS, ids=[lista.__name__ for lista in LISTAS])
def test_todo_item_tem_rotulo_em_portugues(lista: type[ListaFechada]) -> None:
    sem_rotulo = [item for item in lista if not item.rotulo or item.rotulo == item.value]
    assert not sem_rotulo


@pytest.mark.parametrize(
    ("parentesco", "grau"),
    [
        (Parentesco.PAI, 1), (Parentesco.MAE, 1), (Parentesco.IRMAO_IRMA, 1),
        (Parentesco.FILHO_FILHA, 1), (Parentesco.AVO, 2), (Parentesco.TIO_TIA, 2),
        (Parentesco.SOBRINHO_SOBRINHA, 2), (Parentesco.NETO_NETA, 2),
        (Parentesco.MEIO_IRMAO_IRMA, 2), (Parentesco.PRIMO_PRIMA, 3),
        (Parentesco.BISAVO, 3), (Parentesco.TIO_AVO, 3),
    ],
)  # fmt: skip
def test_grau_sai_do_parentesco_pela_genetica_medica(parentesco: Parentesco, grau: int) -> None:
    """NCI Dictionary of Genetics Terms (first/second/third-degree relative): primo é 3º
    grau, e não 4º como no Código Civil, art. 1.594."""
    assert parentesco.grau == grau


@given(st.sampled_from(Parentesco))
def test_todo_parentesco_tem_grau_de_1_a_3(parentesco: Parentesco) -> None:
    assert parentesco.grau in {1, 2, 3}


def test_uf_do_crm_tem_as_27_unidades_federativas() -> None:
    assert len(UF) == 27
    assert {"SP", "DF", "TO"} <= {uf.value for uf in UF}
