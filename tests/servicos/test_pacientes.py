"""Casos de uso de pacientes e catálogos: a casca chega ao repositório só por aqui."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import UF
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import Sessao, criar_cofre
from gastroepi.servicos.pacientes import PacienteInexistente, ProntuarioJaCadastrado


@pytest.fixture
def sessao(tmp_path: Path) -> Iterator[Sessao]:
    sessao, _ = criar_cofre(tmp_path, "frase longa de teste", "frase longa de teste")
    with sessao:
        yield sessao


def test_cadastrar_editar_buscar_listar_e_excluir(sessao: Sessao) -> None:
    primeira, segunda = gerar_fichas(semente=2, quantidade=2)

    paciente_id = pacientes.cadastrar(sessao, primeira, usuario="teste")
    assert pacientes.buscar(sessao, paciente_id) == primeira
    pacientes.editar(sessao, paciente_id, segunda, usuario="teste")
    assert pacientes.listar(sessao) == {paciente_id: segunda}
    pacientes.excluir(sessao, paciente_id, usuario="teste")

    assert pacientes.buscar(sessao, paciente_id) is None
    assert [e.evento.acao for e in pacientes.listar_auditoria(sessao)][-3:] == [
        "cadastrar", "editar", "excluir",
    ]  # fmt: skip


def test_recusas_do_repositorio_chegam_tipadas(sessao: Sessao) -> None:
    ficha = gerar_fichas(semente=2, quantidade=1)[0]
    pacientes.cadastrar(sessao, ficha, usuario="teste")

    with pytest.raises(ProntuarioJaCadastrado):
        pacientes.cadastrar(sessao, ficha, usuario="teste")
    with pytest.raises(PacienteInexistente):
        pacientes.excluir(sessao, 999, usuario="teste")


def test_catalogos(sessao: Sessao) -> None:
    examinador = Examinador(nome="Dra. Teste Fictícia", crm="321", uf=UF.PE)

    pacientes.adicionar_comorbidade(sessao, ItemDeCatalogo(nome="Asma"), usuario="teste")
    pacientes.adicionar_sintoma(sessao, ItemDeCatalogo(nome="Tenesmo"), usuario="teste")
    pacientes.adicionar_examinador(sessao, examinador, usuario="teste")

    assert pacientes.listar_comorbidades(sessao) == ("Asma",)
    assert pacientes.listar_sintomas(sessao) == ("Tenesmo",)
    assert pacientes.listar_examinadores(sessao) == (examinador,)
