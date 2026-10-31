"""Erros de validação em pt-BR, com o caminho do campo e sem o valor digitado."""

from typing import Annotated, Self

import pytest
from pydantic import Field, ValidationError, model_validator

from gastroepi.dominio.campos import CpfOpcional, ModeloDeDominio, TextoObrigatorio
from gastroepi.dominio.erros import ErroDeValidacao, Problema, problemas_de
from gastroepi.dominio.listas import Sexo


class Incoerente(ErroDeValidacao):
    codigo = "incoerente"


class Item(ModeloDeDominio):
    tamanho: Annotated[int, Field(ge=1)] = 1
    marcado: bool = False

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if self.marcado and self.tamanho > 5:
            raise Incoerente("Marcado só até 5", campo="marcado")
        return self


class Ficha(ModeloDeDominio):
    nome: TextoObrigatorio
    cpf: CpfOpcional = None
    sexo: Sexo = Sexo.FEMININO
    sigla: Annotated[str, Field(pattern=r"^[A-Z]+$")] = "A"
    itens: tuple[Item, ...] = ()


def problemas(modelo: type[ModeloDeDominio], **campos: object) -> tuple[Problema, ...]:
    with pytest.raises(ValidationError) as erro:
        modelo.model_validate(campos)
    return problemas_de(erro.value)


def problemas_do_json(json: str) -> tuple[Problema, ...]:
    with pytest.raises(ValidationError) as erro:
        Ficha.model_validate_json(json)
    return problemas_de(erro.value)


def test_campo_obrigatorio_ausente_vira_mensagem_em_portugues() -> None:
    assert problemas(Ficha) == (Problema("nome", "missing", "Preenchimento obrigatório"),)


def test_erro_do_dominio_mantem_codigo_e_mensagem() -> None:
    """Cenário 2: a casca mostra exatamente a mensagem do domínio."""
    assert problemas(Ficha, nome="Ana", cpf="111.111.111-11") == (
        Problema("cpf", "cpf_invalido", "CPF inválido: os 11 dígitos são iguais"),
    )


def test_limite_numerico_aparece_na_mensagem() -> None:
    assert problemas(Item, tamanho=0) == (
        Problema("tamanho", "greater_than_equal", "Deve ser maior ou igual a 1"),
    )


def test_true_em_campo_inteiro_diz_que_espera_inteiro() -> None:
    assert problemas(Item, tamanho=True) == (
        Problema("tamanho", "int_type", "Deve ser um número inteiro"),
    )


def test_texto_no_lugar_de_item_de_lista_pede_para_escolher() -> None:
    assert problemas(Ficha, nome="Ana", sexo="F") == (
        Problema("sexo", "is_instance_of", "Escolha um item da lista"),
    )


def test_erro_dentro_de_item_aponta_o_caminho_completo() -> None:
    assert problemas_do_json('{"nome": "Ana", "itens": [{"tamanho": 0}]}') == (
        Problema("itens.0.tamanho", "greater_than_equal", "Deve ser maior ou igual a 1"),
    )


def test_erro_entre_campos_aponta_o_campo_dentro_do_item() -> None:
    assert problemas_do_json('{"nome": "Ana", "itens": [{"tamanho": 9, "marcado": true}]}') == (
        Problema("itens.0.marcado", "incoerente", "Marcado só até 5"),
    )


def test_item_aninhado_como_dicionario_passa_pelas_mesmas_regras() -> None:
    assert problemas(Ficha, nome="Ana", itens=({"tamanho": True},)) == (
        Problema("itens.0.tamanho", "int_type", "Deve ser um número inteiro"),
    )
    assert problemas(Ficha, nome="Ana", itens=(3,)) == (
        Problema("itens.0", "model_type", "Formato inválido"),
    )


def test_tipos_comuns_tem_traducao() -> None:
    assert problemas(Ficha, nome=["Ana"])[0].mensagem == "Deve ser texto"
    assert problemas(Ficha, nome="Ana", itens="abc")[0].mensagem == "Deve ser uma lista de itens"
    assert problemas(Item, marcado="sim")[0].mensagem == "Deve ser sim ou não"


def test_tipo_de_erro_sem_traducao_vira_valor_invalido() -> None:
    assert problemas(Ficha, nome="Ana", sigla="abc") == (
        Problema("sigla", "string_pattern_mismatch", "Valor inválido"),
    )


def test_nenhum_problema_repete_o_cpf_digitado() -> None:
    assert "529" not in repr(problemas(Ficha, nome="Ana", cpf="529.982.247-24"))
