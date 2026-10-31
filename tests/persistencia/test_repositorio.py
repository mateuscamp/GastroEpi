"""Repositório: cada mutação e o seu evento de auditoria na mesma transação."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.auditoria.conferencia import Divergencia, Motivo
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.relogio import Relogio
from gastroepi.persistencia.repositorio import Repositorio


@pytest.fixture
def caminho(tmp_path: Path) -> Path:
    return tmp_path / "gastroepi.db"


@pytest.fixture
def repositorio(caminho: Path, chave_de_dados: bytes, relogio: Relogio) -> Iterator[Repositorio]:
    repositorio = Repositorio.abrir(caminho, chave_de_dados, relogio)
    yield repositorio
    repositorio.fechar()


def ficha(numero: int = 1, semente: int = 11) -> Ficha:
    return gerar_fichas(semente=semente, quantidade=numero)[-1]


def alterar_por_fora(caminho: Path, chave: bytes, sql: str, *parametros: object) -> None:
    """Uma ferramenta externa com a chave (DB Browser for SQLCipher), sem passar pelo app."""
    conexao = sqlcipher3.connect(str(caminho))
    conexao.execute(f"PRAGMA key = \"x'{chave.hex()}'\"")
    conexao.execute(sql, parametros)
    conexao.commit()
    conexao.close()


def test_cenario_3_linha_de_paciente_alterada_por_fora_acusa_id_e_momento_da_entrada(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    paciente_id = repositorio.cadastrar(ficha(), usuario="teste")
    entrada = repositorio.listar_auditoria()[-1]
    repositorio.fechar()

    alterar_por_fora(
        caminho, chave_de_dados, "UPDATE paciente SET nome = 'Outro Nome' WHERE id = ?", paciente_id
    )

    with Repositorio.abrir(caminho, chave_de_dados) as reaberto:
        relatorio = reaberto.verificar()
    assert relatorio.dados == (
        Divergencia(
            entidade="paciente",
            entidade_id=paciente_id,
            motivo=Motivo.ALTERADO,
            entrada_id=entrada.id,
            momento=entrada.evento.momento,
        ),
    )


def ficha_completa() -> Ficha:
    """A primeira ficha da semente com exames, lesões, sintomas, comorbidades e histórico."""
    return next(
        f
        for f in gerar_fichas(semente=3, quantidade=200)
        if f.paciente.comorbidades
        and f.paciente.historico_familiar
        and len(f.exames) > 1
        and any(e.sintomas for e in f.exames)
        and any(len(e.lesoes) > 1 for e in f.exames)
    )


def test_buscar_devolve_a_ficha_cadastrada_com_exames_lesoes_e_historico(
    repositorio: Repositorio,
) -> None:
    original = ficha_completa()

    paciente_id = repositorio.cadastrar(original, usuario="teste")

    assert repositorio.buscar(paciente_id) == original


def test_buscar_paciente_inexistente_devolve_none(repositorio: Repositorio) -> None:
    assert repositorio.buscar(99) is None


def test_banco_sem_alteracao_por_fora_nao_acusa_nada(repositorio: Repositorio) -> None:
    for original in gerar_fichas(semente=5, quantidade=30):
        repositorio.cadastrar(original, usuario="teste")

    assert repositorio.verificar().dados == ()
