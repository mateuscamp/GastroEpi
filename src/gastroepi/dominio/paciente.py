"""Paciente e histórico familiar (ADR-0004).

O paciente não guarda idade: ela é calculada da data de nascimento na data de cada
exame (`exame.idade_no_exame`). O grau do parente sai do parentesco, nunca é digitado.
"""

from typing import Annotated

from pydantic import BeforeValidator, Field

from gastroepi.dominio.campos import (
    CpfOpcional,
    Data,
    ItensDeCatalogo,
    ModeloDeDominio,
    TextoObrigatorio,
    vazio_vira_none,
)
from gastroepi.dominio.listas import Parentesco, Sexo

IdadeOpcional = Annotated[
    Annotated[int, Field(ge=0, le=120)] | None, BeforeValidator(vazio_vira_none)
]


class HistoricoFamiliar(ModeloDeDominio):
    """Parente com câncer colorretal."""

    parentesco: Parentesco
    idade_diagnostico: IdadeOpcional = None

    @property
    def grau(self) -> int:
        return self.parentesco.grau


class Paciente(ModeloDeDominio):
    """O repr esconde os dados identificadores: um traceback ou log não os mostra."""

    prontuario: TextoObrigatorio = Field(repr=False)
    cpf: CpfOpcional = Field(default=None, repr=False)
    nome: TextoObrigatorio = Field(repr=False)
    sexo: Sexo
    data_nascimento: Data = Field(repr=False)
    comorbidades: ItensDeCatalogo = ()
    historico_familiar: tuple[HistoricoFamiliar, ...] = ()
