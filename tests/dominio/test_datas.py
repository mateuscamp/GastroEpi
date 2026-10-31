"""Datas dd/mm/aaaa ↔ ISO 8601 (Princípio V) e paridade com o validation.ts da v0.1.16."""

import json
from datetime import date
from pathlib import Path

import pytest

from gastroepi.dominio.datas import formatar_data_br, idade_em, ler_data_br, ler_data_iso
from gastroepi.dominio.erros import DataInvalida

VETORES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "vetores_validacao_v0_1_16.json").read_text(
        encoding="utf-8"
    )
)


def test_data_br_vira_date() -> None:
    assert ler_data_br("05/03/2026") == date(2026, 3, 5)


def test_data_fora_do_formato_e_recusada_dizendo_o_formato() -> None:
    with pytest.raises(DataInvalida) as erro:
        ler_data_br("5/3/2026")

    assert str(erro.value) == "Data inválida: use dd/mm/aaaa (ex.: 05/03/2026)"


def test_data_com_digito_fora_do_ascii_e_recusada() -> None:
    """A regex `\\d` do Python casa dígitos arábicos; a data só tem 0-9."""
    with pytest.raises(DataInvalida):
        ler_data_br("\u0660\u0665/\u0660\u0663/\u0662\u0660\u0662\u0666")


def test_dia_que_nao_existe_no_calendario_e_recusado() -> None:
    with pytest.raises(DataInvalida) as erro:
        ler_data_br("29/02/2026")

    assert str(erro.value) == "Data inválida: esse dia não existe no calendário"


def test_ano_antes_de_1900_e_recusado_como_erro_de_digitacao() -> None:
    with pytest.raises(DataInvalida) as erro:
        ler_data_br("05/03/0026")

    assert str(erro.value) == "Data inválida: ano antes de 1900"


@pytest.mark.parametrize(
    "vetor", VETORES["data_exame"], ids=[v["entrada"] for v in VETORES["data_exame"]]
)
def test_vetores_de_data_do_validation_ts(vetor: dict[str, str | bool]) -> None:
    """O `iso` de entrada inválida é o eco do converterParaISO ingênuo (ex.: `2026-02-31`);
    em Python a entrada inválida é recusada e não vira ISO."""
    entrada = str(vetor["entrada"])
    if vetor["valida"]:
        assert ler_data_br(entrada).isoformat() == vetor["iso"]
    else:
        with pytest.raises(DataInvalida):
            ler_data_br(entrada)


def test_data_iso_vira_date() -> None:
    assert ler_data_iso("2024-02-29") == date(2024, 2, 29)


@pytest.mark.parametrize("entrada", ["2026/03/05", "20260305", "2026-W10-4", "2026-02-30", ""])
def test_data_iso_fora_do_aaaa_mm_dd_e_recusada(entrada: str) -> None:
    """`date.fromisoformat` aceita `20260305` e `2026-W10-4`; o banco só guarda AAAA-MM-DD."""
    with pytest.raises(DataInvalida):
        ler_data_iso(entrada)


@pytest.mark.parametrize(
    "vetor", VETORES["iso_para_br"], ids=[v["entrada"] or "vazio" for v in VETORES["iso_para_br"]]
)
def test_vetores_iso_para_br_do_validation_ts(vetor: dict[str, str]) -> None:
    """Divergência intencional: a v0.1.16 mostrava vazio para um valor fora do ISO e
    escondia o dado corrompido; em Python ele é recusado. Vazio continua sendo "sem data"."""
    entrada, esperado = vetor["entrada"], vetor["br"]
    if not entrada:
        assert formatar_data_br(None) == esperado
    elif esperado:
        assert formatar_data_br(ler_data_iso(entrada)) == esperado
    else:
        with pytest.raises(DataInvalida):
            ler_data_iso(entrada)


def test_idade_conta_anos_completos() -> None:
    assert idade_em(date(1970, 6, 15), date(2026, 6, 14)) == 55
    assert idade_em(date(1970, 6, 15), date(2026, 6, 15)) == 56


def test_nascido_em_29_de_fevereiro_completa_anos_em_1_de_marco() -> None:
    """Código Civil, art. 132, § 3º: sem dia correspondente, o prazo vence no dia seguinte."""
    assert idade_em(date(2000, 2, 29), date(2025, 2, 28)) == 24
    assert idade_em(date(2000, 2, 29), date(2025, 3, 1)) == 25


def test_referencia_antes_do_nascimento_e_recusada() -> None:
    with pytest.raises(DataInvalida) as erro:
        idade_em(date(1970, 6, 15), date(1969, 1, 1))

    assert str(erro.value) == "Data inválida: anterior à data de nascimento"
