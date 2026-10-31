"""CPF: Cenário 2 da SPECIFICATION.md e paridade com o validarCPF da v0.1.16.

Algoritmo dos dígitos verificadores: Receita Federal, módulo 11 com pesos 10..2 e
11..2, e resto 10 ou 11 vira 0 (o mesmo do src/validation.ts congelado).
"""

import json
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from gastroepi.dominio.cpf import digitos_verificadores, formatar_cpf, normalizar_cpf
from gastroepi.dominio.erros import CpfInvalido

VETORES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "vetores_validacao_v0_1_16.json").read_text(
        encoding="utf-8"
    )
)["cpf"]


@st.composite
def cpf_valido(draw: st.DrawFn) -> str:
    base = draw(st.text(alphabet="0123456789", min_size=9, max_size=9))
    assume(len(set(base)) > 1)
    return base + digitos_verificadores(base)


def test_cpf_com_todos_os_digitos_iguais_e_recusado_com_mensagem_em_portugues() -> None:
    """Cenário 2: `111.111.111-11` passa no cálculo do DV, mas não é CPF emitido."""
    with pytest.raises(CpfInvalido) as erro:
        normalizar_cpf("111.111.111-11")

    assert str(erro.value) == "CPF inválido: os 11 dígitos são iguais"
    assert "111" not in str(erro.value)


def test_cpf_com_pontos_e_traco_normaliza_para_11_digitos() -> None:
    assert normalizar_cpf("529.982.247-25") == "52998224725"


def test_cpf_com_espacos_nas_bordas_normaliza() -> None:
    assert normalizar_cpf("  529.982.247-25 ") == "52998224725"


def test_cpf_com_digito_verificador_errado_e_recusado_sem_mostrar_o_numero() -> None:
    with pytest.raises(CpfInvalido) as erro:
        normalizar_cpf("529.982.247-24")

    assert str(erro.value) == "CPF inválido: dígito verificador não confere"


@pytest.mark.parametrize("entrada", ["123", "5299822472500", ""])
def test_cpf_sem_11_digitos_e_recusado(entrada: str) -> None:
    with pytest.raises(CpfInvalido) as erro:
        normalizar_cpf(entrada)

    assert str(erro.value) == "CPF inválido: esperado 11 dígitos (ex.: 000.000.000-00)"


def test_cpf_com_letra_e_recusado_em_vez_de_descartar_a_letra() -> None:
    """Mais estrito que a v0.1.16, que apagava qualquer não-dígito: `5299822472a5` passava."""
    with pytest.raises(CpfInvalido) as erro:
        normalizar_cpf("5299822472a5")

    assert str(erro.value) == "CPF inválido: use só dígitos, pontos e traço"


@pytest.mark.parametrize(
    "entrada", ["52998224²25", "\u0665\u0662\u0669\u0669\u0668\u0662\u0662\u0664\u0667\u0662\u0665"]
)
def test_cpf_com_digito_fora_do_ascii_e_recusado(entrada: str) -> None:
    """`str.isdigit` aceita `²` e dígitos arábicos; o CPF só tem 0-9."""
    with pytest.raises(CpfInvalido) as erro:
        normalizar_cpf(entrada)

    assert str(erro.value) == "CPF inválido: use só dígitos, pontos e traço"


def test_formatar_cpf_poe_pontos_e_traco() -> None:
    assert formatar_cpf("52998224725") == "529.982.247-25"


@pytest.mark.parametrize("vetor", VETORES, ids=[v["entrada"] or "vazio" for v in VETORES])
def test_vetores_do_validation_ts(vetor: dict[str, str | bool]) -> None:
    """Paridade com a v0.1.16. O `formatado` de entrada inválida é o eco do formatarCPF
    ingênuo; em Python a entrada inválida é recusada e não chega a ser formatada."""
    entrada = str(vetor["entrada"])
    if vetor["valido"]:
        assert formatar_cpf(normalizar_cpf(entrada)) == vetor["formatado"]
    else:
        with pytest.raises(CpfInvalido):
            normalizar_cpf(entrada)


@given(cpf_valido())
def test_todo_cpf_com_dv_calculado_e_aceito(cpf: str) -> None:
    assert normalizar_cpf(formatar_cpf(cpf)) == cpf


def esta_na_dobra_do_resto(cpf: str, posicao: int, novo: str) -> bool:
    """O DV vale 0 tanto para resto 0 quanto 1 (resto 10 e 11 → 0). Trocar a 1ª posição
    por ±1, ou a 6ª por ±2/±9, move o resto entre 0 e 1 sem mudar o DV (0,18% das trocas)."""
    delta = int(novo) - int(cpf[posicao])
    if posicao == 0:
        return cpf[9] == "0" and abs(delta) == 1
    return posicao == 5 and cpf[9:] == "00" and abs(delta) in {2, 9}


@given(cpf_valido(), st.integers(0, 10), st.sampled_from("0123456789"))
def test_um_digito_trocado_e_recusado_fora_da_dobra_do_resto(
    cpf: str, posicao: int, novo: str
) -> None:
    assume(novo != cpf[posicao])
    assume(not esta_na_dobra_do_resto(cpf, posicao, novo))
    trocado = cpf[:posicao] + novo + cpf[posicao + 1 :]

    with pytest.raises(CpfInvalido):
        normalizar_cpf(trocado)


def test_dobra_do_resto_aceita_dois_cpfs_que_diferem_em_um_digito() -> None:
    """Limite do algoritmo da Receita, não do código: os dois são CPFs válidos."""
    assert normalizar_cpf("704.999.622-06") == "70499962206"
    assert normalizar_cpf("804.999.622-06") == "80499962206"
