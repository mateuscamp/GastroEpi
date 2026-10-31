"""Tipos de campo: pydantic estrito com a normalização do Princípio V."""

from datetime import date

import pytest
from pydantic import ValidationError

from gastroepi.dominio.campos import (
    CpfOpcional,
    Data,
    ItensDeCatalogo,
    ModeloDeDominio,
    TextoObrigatorio,
    TextoOpcional,
)


class ModeloDeTeste(ModeloDeDominio):
    texto: TextoObrigatorio = "x"
    opcional: TextoOpcional = None
    cpf: CpfOpcional = None
    data: Data = date(2000, 1, 1)
    inteiro: int = 0
    itens: ItensDeCatalogo = ()


def tipos_de_erro(erro: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    return [e["type"] for e in erro.value.errors()]


def test_true_em_campo_inteiro_e_recusado() -> None:
    """Princípio V: sem conversão implícita de booleano para inteiro."""
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste(inteiro=True)

    assert tipos_de_erro(erro) == ["int_type"]


def test_texto_numerico_em_campo_inteiro_e_recusado() -> None:
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste.model_validate({"inteiro": "3"})

    assert tipos_de_erro(erro) == ["int_type"]


@pytest.mark.parametrize("vazio", ["", "   ", "\t\n"])
def test_texto_opcional_vazio_ou_so_espaco_vira_none(vazio: str) -> None:
    assert ModeloDeTeste(opcional=vazio).opcional is None


def test_texto_e_aparado_nas_bordas() -> None:
    modelo = ModeloDeTeste(texto="  Ana  ", opcional=" nota ")
    assert (modelo.texto, modelo.opcional) == ("Ana", "nota")


def test_texto_obrigatorio_so_com_espaco_e_recusado() -> None:
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste(texto="   ")

    assert tipos_de_erro(erro) == ["string_too_short"]


@pytest.mark.parametrize("vazio", ["", "  "])
def test_cpf_vazio_vira_none(vazio: str) -> None:
    assert ModeloDeTeste(cpf=vazio).cpf is None


def test_cpf_e_guardado_com_11_digitos() -> None:
    assert ModeloDeTeste(cpf="529.982.247-25").cpf == "52998224725"


def test_data_digitada_em_dd_mm_aaaa_vira_date() -> None:
    assert ModeloDeTeste.model_validate({"data": "05/03/2026"}).data == date(2026, 3, 5)


def test_data_iso_digitada_e_recusada() -> None:
    """Vetor `2026-12-31` da v0.1.16: quem digita usa dd/mm/aaaa."""
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste.model_validate({"data": "2026-12-31"})

    assert tipos_de_erro(erro) == ["value_error"]


def test_json_guarda_e_le_a_data_em_iso() -> None:
    """O que vai para o banco e para a auditoria é ISO 8601 (Princípio V)."""
    modelo = ModeloDeTeste(data=date(2026, 3, 5))
    json = modelo.model_dump_json()

    assert '"data":"2026-03-05"' in json
    assert ModeloDeTeste.model_validate_json(json) == modelo


def test_date_antes_de_1900_e_recusado_mesmo_sem_passar_pelo_texto() -> None:
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste(data=date(26, 3, 5))

    assert tipos_de_erro(erro) == ["value_error"]


def test_itens_de_catalogo_repetidos_sem_diferenca_de_caixa_viram_um() -> None:
    """FR-2.4 da v0.1.16: a lista de comorbidades não distingue maiúsculas."""
    assert ModeloDeTeste(itens=("HAS", " has ", "DM2")).itens == ("HAS", "DM2")


def test_campo_desconhecido_e_recusado() -> None:
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste.model_validate({"polipo": 3})

    assert tipos_de_erro(erro) == ["extra_forbidden"]


def test_modelo_e_imutavel() -> None:
    modelo = ModeloDeTeste()
    with pytest.raises(ValidationError):
        modelo.texto = "outro"  # type: ignore[misc]  # o teste é justamente a atribuição


def test_mensagem_de_erro_nao_repete_o_valor_digitado() -> None:
    with pytest.raises(ValidationError) as erro:
        ModeloDeTeste(cpf="529.982.247-24")

    assert "529" not in str(erro.value)
