"""Ficha: o paciente e os seus exames, a unidade que o app grava e audita (ADR-0004).

Editar um exame ou acrescentar o laudo de uma lesão é editar a ficha: o evento de
auditoria guarda a ficha inteira, e a verificação dos dados compara a ficha gravada
com esse último retrato.

É o primeiro lugar onde paciente e exame estão juntos, então é aqui que se recusa o
exame anterior ao nascimento (a idade no exame seria negativa).
"""

from typing import Self

from pydantic import model_validator

from gastroepi.dominio.campos import ModeloDeDominio
from gastroepi.dominio.erros import DataInvalida
from gastroepi.dominio.exame import Exame
from gastroepi.dominio.paciente import Paciente


class Ficha(ModeloDeDominio):
    paciente: Paciente
    exames: tuple[Exame, ...] = ()

    @model_validator(mode="after")
    def _exames_depois_do_nascimento(self) -> Self:
        for indice, exame in enumerate(self.exames):
            if exame.data_exame < self.paciente.data_nascimento:
                mensagem = "Data inválida: exame antes do nascimento"
                raise DataInvalida(mensagem, campo=f"exames.{indice}.data_exame")
        return self
