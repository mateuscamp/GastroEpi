"""Paciente e histórico familiar (ADR-0004), com o Cenário 2 da SPECIFICATION.md."""

from datetime import date

import pytest
from pydantic import ValidationError

from gastroepi.dominio.erros import Problema, problemas_de
from gastroepi.dominio.listas import Parentesco, Sexo
from gastroepi.dominio.paciente import HistoricoFamiliar, Paciente

NOME = "Ana Fictícia da Silva"


def paciente(**campos: object) -> Paciente:
    padrao: dict[str, object] = {
        "prontuario": "F00001",
        "nome": NOME,
        "sexo": Sexo.FEMININO,
        "data_nascimento": "15/06/1970",
    }
    return Paciente.model_validate(padrao | campos)


def problemas(**campos: object) -> tuple[Problema, ...]:
    with pytest.raises(ValidationError) as erro:
        paciente(**campos)
    return problemas_de(erro.value)


def test_cenario_2_cpf_111_e_recusado_com_mensagem_em_portugues() -> None:
    """SPECIFICATION.md, Cenário 2: o cadastro falha com erro pt-BR e não chega ao banco."""
    with pytest.raises(ValidationError) as erro:
        paciente(cpf="111.111.111-11")

    assert problemas_de(erro.value) == (
        Problema("cpf", "cpf_invalido", "CPF inválido: os 11 dígitos são iguais"),
    )
    assert "111" not in str(erro.value)
    assert NOME not in str(erro.value)


def test_paciente_minimo_tem_cpf_vazio_e_listas_vazias() -> None:
    novo = paciente(cpf="")
    assert novo.cpf is None
    assert novo.comorbidades == ()
    assert novo.historico_familiar == ()
    assert novo.data_nascimento == date(1970, 6, 15)


def test_cpf_valido_e_guardado_so_com_digitos() -> None:
    assert paciente(cpf="529.982.247-25").cpf == "52998224725"


@pytest.mark.parametrize("campo", ["prontuario", "nome"])
def test_prontuario_e_nome_so_com_espaco_sao_recusados(campo: str) -> None:
    assert problemas(**{campo: "   "}) == (
        Problema(campo, "string_too_short", "Preenchimento obrigatório"),
    )


def test_data_de_nascimento_e_obrigatoria() -> None:
    """ADR-0004: a idade no exame sai da data de nascimento, então ela não pode faltar."""
    campos = {"prontuario": "F00001", "nome": NOME, "sexo": Sexo.FEMININO}
    with pytest.raises(ValidationError) as erro:
        Paciente.model_validate(campos)

    assert problemas_de(erro.value) == (
        Problema("data_nascimento", "missing", "Preenchimento obrigatório"),
    )


def test_repr_nao_mostra_dado_identificador() -> None:
    """AGENTS.md: nome, CPF e prontuário nunca vão para log; um repr num traceback vazaria."""
    texto = repr(paciente(cpf="529.982.247-25"))
    for sensivel in [NOME, "52998224725", "F00001", "1970"]:
        assert sensivel not in texto


def test_json_ida_e_volta_preserva_o_paciente() -> None:
    original = paciente(
        cpf="529.982.247-25",
        comorbidades=("HAS", "DM2"),
        historico_familiar=(HistoricoFamiliar(parentesco=Parentesco.PAI, idade_diagnostico=60),),
    )
    assert Paciente.model_validate_json(original.model_dump_json()) == original


def test_grau_do_historico_sai_do_parentesco() -> None:
    """ADR-0004: grau e parentesco não podem se contradizer, então o grau não é digitado."""
    assert HistoricoFamiliar(parentesco=Parentesco.PRIMO_PRIMA).grau == 3


def test_grau_digitado_e_recusado_como_campo_desconhecido() -> None:
    with pytest.raises(ValidationError) as erro:
        HistoricoFamiliar.model_validate({"parentesco": Parentesco.PAI, "grau": 1})

    assert problemas_de(erro.value) == (Problema("grau", "extra_forbidden", "Campo desconhecido"),)


def test_idade_ao_diagnostico_vazia_vira_none() -> None:
    historico = HistoricoFamiliar.model_validate(
        {"parentesco": Parentesco.MAE, "idade_diagnostico": "  "}
    )
    assert historico.idade_diagnostico is None


@pytest.mark.parametrize(
    ("idade", "codigo"), [(-1, "greater_than_equal"), (121, "less_than_equal")]
)
def test_idade_ao_diagnostico_fora_de_0_a_120_e_recusada(idade: int, codigo: str) -> None:
    with pytest.raises(ValidationError) as erro:
        HistoricoFamiliar(parentesco=Parentesco.MAE, idade_diagnostico=idade)

    assert [p.codigo for p in problemas_de(erro.value)] == [codigo]
