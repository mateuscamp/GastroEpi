"""Tipos de campo do domínio: pydantic estrito com a normalização do Princípio V.

- Estrito: nenhuma conversão implícita (`True` não vira 1, `"3"` não vira 3).
- Texto é aparado nas bordas; opcional vazio ou só com espaço vira `None`.
- Data: quem digita usa dd/mm/aaaa; o JSON (banco, auditoria) usa ISO 8601.
"""

from datetime import date
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    ValidationInfo,
)

from gastroepi.dominio.cpf import normalizar_cpf
from gastroepi.dominio.datas import ANO_MINIMO, ler_data_br, ler_data_iso
from gastroepi.dominio.erros import CampoCondicional, DataInvalida


class ModeloDeDominio(BaseModel):
    """Estrito, imutável, sem campo extra e sem o valor digitado nas mensagens de erro,
    para CPF e nome não vazarem num log ou numa tela de erro."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)


def vazio_vira_none(valor: object) -> object:
    if not isinstance(valor, str):
        return valor
    return valor.strip() or None


def _ler_cpf(valor: object) -> object:
    valor = vazio_vira_none(valor)
    return normalizar_cpf(valor) if isinstance(valor, str) else valor


def _ler_data(valor: object, info: ValidationInfo) -> object:
    if not isinstance(valor, str):
        return valor
    return ler_data_iso(valor) if info.mode == "json" else ler_data_br(valor)


def _ano_plausivel(valor: date) -> date:
    if valor.year < ANO_MINIMO:
        raise DataInvalida(f"Data inválida: ano antes de {ANO_MINIMO}")
    return valor


def _sem_repetidos(itens: tuple[str, ...]) -> tuple[str, ...]:
    vistos: set[str] = set()
    unicos = []
    for item in itens:
        if item.casefold() not in vistos:
            vistos.add(item.casefold())
            unicos.append(item)
    return tuple(unicos)


def conferir_condicional(campo: str, valor: object, exigido: bool, falta: str, sobra: str) -> None:
    """Levanta `CampoCondicional` se o campo falta quando exigido ou sobra quando não."""
    if exigido and valor is None:
        raise CampoCondicional(falta, campo=campo)
    if not exigido and valor is not None:
        raise CampoCondicional(sobra, campo=campo)


TextoObrigatorio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TextoOpcional = Annotated[str | None, BeforeValidator(vazio_vira_none)]
CpfOpcional = Annotated[str | None, BeforeValidator(_ler_cpf)]
Data = Annotated[date, BeforeValidator(_ler_data), AfterValidator(_ano_plausivel)]
# Comorbidades e sintomas: nomes de catálogo, sem repetição e sem distinguir caixa.
ItensDeCatalogo = Annotated[tuple[TextoObrigatorio, ...], AfterValidator(_sem_repetidos)]
