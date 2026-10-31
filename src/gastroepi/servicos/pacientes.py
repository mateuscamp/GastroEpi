"""Casos de uso de pacientes, catálogos e da lista de auditoria.

`usuario` é quem opera o app (vai para a auditoria), não o examinador do exame.
"""

import unicodedata

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
from gastroepi.servicos.sessao import Sessao, repositorio_de

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


def buscar_por_prontuario(sessao: Sessao, prontuario: str) -> tuple[int, Ficha] | None:
    """O prontuário é único; compara aparado, como o domínio grava."""
    procurado = prontuario.strip()
    for paciente_id, ficha in listar(sessao).items():
        if ficha.paciente.prontuario == procurado:
            return paciente_id, ficha
    return None


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def corresponde_ao_termo(ficha: Ficha, termo: str) -> bool:
    """Busca da tela de pacientes: parte do nome (sem acento nem caixa), do prontuário
    ou dos dígitos do CPF. Termo vazio aceita todos."""
    procurado = _sem_acento(termo.strip())
    if not procurado:
        return True
    paciente = ficha.paciente
    if procurado in _sem_acento(paciente.nome) or procurado in paciente.prontuario.casefold():
        return True
    digitos = "".join(c for c in procurado if c.isdigit())
    return bool(digitos) and paciente.cpf is not None and digitos in paciente.cpf


def buscar_por_termo(sessao: Sessao, termo: str) -> dict[int, Ficha]:
    return {i: f for i, f in listar(sessao).items() if corresponde_ao_termo(f, termo)}


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
