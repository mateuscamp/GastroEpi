"""Casos de uso de pacientes, catálogos e da lista de auditoria.

`usuario` é quem opera o app (vai para a auditoria), não o examinador do exame.
"""

from gastroepi.auditoria.cadeia import EntradaDeAuditoria
from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.persistencia.catalogos import ExaminadorDivergente
from gastroepi.persistencia.repositorio import (
    CpfJaCadastrado,
    FichaIlegivel,
    PacienteInexistente,
    ProntuarioJaCadastrado,
)
from gastroepi.servicos.acesso import Sessao, repositorio_de

__all__ = [
    "CpfJaCadastrado",
    "EntradaDeAuditoria",
    "ExaminadorDivergente",
    "FichaIlegivel",
    "PacienteInexistente",
    "ProntuarioJaCadastrado",
]


def cadastrar(sessao: Sessao, ficha: Ficha, usuario: str) -> int:
    return repositorio_de(sessao).cadastrar(ficha, usuario)


def editar(sessao: Sessao, paciente_id: int, ficha: Ficha, usuario: str) -> None:
    repositorio_de(sessao).editar(paciente_id, ficha, usuario)


def excluir(sessao: Sessao, paciente_id: int, usuario: str) -> None:
    repositorio_de(sessao).excluir(paciente_id, usuario)


def buscar(sessao: Sessao, paciente_id: int) -> Ficha | None:
    return repositorio_de(sessao).buscar(paciente_id)


def listar(sessao: Sessao) -> dict[int, Ficha]:
    return repositorio_de(sessao).listar()


def adicionar_comorbidade(sessao: Sessao, item: ItemDeCatalogo, usuario: str) -> str:
    return repositorio_de(sessao).adicionar_comorbidade(item, usuario)


def adicionar_sintoma(sessao: Sessao, item: ItemDeCatalogo, usuario: str) -> str:
    return repositorio_de(sessao).adicionar_sintoma(item, usuario)


def adicionar_examinador(sessao: Sessao, examinador: Examinador, usuario: str) -> None:
    repositorio_de(sessao).adicionar_examinador(examinador, usuario)


def listar_comorbidades(sessao: Sessao) -> tuple[str, ...]:
    return repositorio_de(sessao).listar_comorbidades()


def listar_sintomas(sessao: Sessao) -> tuple[str, ...]:
    return repositorio_de(sessao).listar_sintomas()


def listar_examinadores(sessao: Sessao) -> tuple[Examinador, ...]:
    return repositorio_de(sessao).listar_examinadores()


def listar_auditoria(sessao: Sessao) -> tuple[EntradaDeAuditoria, ...]:
    return repositorio_de(sessao).listar_auditoria()
