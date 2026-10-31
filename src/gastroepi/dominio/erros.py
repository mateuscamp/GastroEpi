"""Erros de validação do domínio, com mensagem em pt-BR e sem dado sensível.

`problemas_de` traduz um `ValidationError` do pydantic (mensagens em inglês) para a
lista que a casca mostra: o caminho do campo, um código estável e a mensagem em pt-BR.
Nenhuma mensagem repete o valor digitado (CPF, nome, data de nascimento).
"""

from typing import ClassVar, NamedTuple

from pydantic import ValidationError
from pydantic_core import ErrorDetails


class ErroDeValidacao(ValueError):
    """Base dos erros do domínio. A mensagem diz o formato esperado, nunca o valor sensível.

    `campo` aponta o campo culpado quando a regra envolve mais de um (validação do modelo).
    """

    codigo: ClassVar[str] = "valor_invalido"

    def __init__(self, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.campo = campo


class CpfInvalido(ErroDeValidacao):
    codigo = "cpf_invalido"


class DataInvalida(ErroDeValidacao):
    codigo = "data_invalida"


class CampoCondicional(ErroDeValidacao):
    """Campo que só existe (ou só falta) conforme outro: 'outra' com texto, motivo etc."""

    codigo = "campo_condicional"


class CrmInvalido(ErroDeValidacao):
    codigo = "crm_invalido"


class DisplasiaIncoerente(ErroDeValidacao):
    codigo = "displasia_incoerente"


class Problema(NamedTuple):
    campo: str  # caminho, ex.: "lesoes.0.tamanho_mm"
    codigo: str  # estável, para a casca escolher o rótulo do campo
    mensagem: str  # pt-BR, sem o valor digitado


_MENSAGENS = {
    "missing": "Preenchimento obrigatório",
    "string_too_short": "Preenchimento obrigatório",
    "string_type": "Deve ser texto",
    "int_type": "Deve ser um número inteiro",
    "float_type": "Deve ser um número",
    "finite_number": "Deve ser um número finito",
    "bool_type": "Deve ser sim ou não",
    "date_type": "Data inválida: use dd/mm/aaaa (ex.: 05/03/2026)",
    "tuple_type": "Deve ser uma lista de itens",
    "is_instance_of": "Escolha um item da lista",
    "enum": "Escolha um item da lista",
    "model_type": "Formato inválido",
    "extra_forbidden": "Campo desconhecido",
    "greater_than": "Deve ser maior que {gt}",
    "greater_than_equal": "Deve ser maior ou igual a {ge}",
    "less_than_equal": "Deve ser menor ou igual a {le}",
}


def _traduzir(detalhe: ErrorDetails) -> Problema:
    contexto = detalhe.get("ctx", {})
    caminho = [str(parte) for parte in detalhe["loc"]]
    causa = contexto.get("error")
    if isinstance(causa, ErroDeValidacao):
        campo = ".".join([*caminho, causa.campo] if causa.campo else caminho)
        return Problema(campo, causa.codigo, str(causa))
    modelo = _MENSAGENS.get(detalhe["type"], "Valor inválido")
    return Problema(".".join(caminho), detalhe["type"], modelo.format(**contexto))


def problemas_de(erro: ValidationError) -> tuple[Problema, ...]:
    detalhes = erro.errors(include_url=False, include_input=False)
    return tuple(_traduzir(detalhe) for detalhe in detalhes)
