"""Ficha: o paciente e os seus exames, a unidade que o app grava e audita (ADR-0004).

Editar um exame ou acrescentar o laudo de uma lesão é editar a ficha: o evento de
auditoria guarda a ficha inteira, e a verificação dos dados compara a ficha gravada
com esse último retrato.
"""

from gastroepi.dominio.campos import ModeloDeDominio
from gastroepi.dominio.exame import Exame
from gastroepi.dominio.paciente import Paciente


class Ficha(ModeloDeDominio):
    paciente: Paciente
    exames: tuple[Exame, ...] = ()
