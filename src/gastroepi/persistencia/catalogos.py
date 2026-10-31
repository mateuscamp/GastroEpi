"""Catálogos de comorbidade, sintoma e examinador.

A ficha cita os itens pelo nome (comorbidade, sintoma) ou pelo CRM + UF (examinador).
`resolver` troca cada nome pela grafia do catálogo e cria o item que faltar; o
repositório audita cada item novo na mesma transação da ficha. Comparar nomes por
`casefold` segue o domínio (`ItensDeCatalogo`), e não o NOCASE do SQLite, que só
ignora a caixa do ASCII ("Ã" ≠ "ã").
"""

import json
from dataclasses import dataclass, field
from typing import Literal

import sqlcipher3

from gastroepi.auditoria.cadeia import Entidade
from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.listas import UF

TabelaDeItens = Literal["comorbidade", "sintoma"]


class ExaminadorDivergente(ValueError):
    """CRM + UF já cadastrados com outro nome. CRM é registro público, não dado sensível."""

    def __init__(self, crm: str, uf: UF) -> None:
        super().__init__(f"CRM {crm}/{uf} já cadastrado com outro nome")
        self.crm, self.uf = crm, uf


@dataclass(frozen=True, slots=True)
class ItemNovo:
    entidade: Entidade
    id: int
    retrato: str = field(repr=False)  # snapshot JSON, o mesmo de `retrato_de_item`


@dataclass(frozen=True, slots=True)
class Resolucao:
    """A ficha com a grafia do catálogo e os ids que as linhas dela vão citar."""

    ficha: Ficha
    comorbidades: dict[str, int]
    sintomas: dict[str, int]
    examinadores: dict[tuple[str, UF], int]
    novos: tuple[ItemNovo, ...]


def retrato_de_item(nome: str) -> str:
    return json.dumps({"nome": nome}, ensure_ascii=False)


def buscar_item(
    conexao: sqlcipher3.Connection, tabela: TabelaDeItens, nome: str
) -> tuple[int, str] | None:
    linha = conexao.execute(
        f"SELECT id, nome FROM {tabela} WHERE nome_normalizado = ?", (nome.casefold(),)
    ).fetchone()
    return None if linha is None else (linha[0], linha[1])


def inserir_item(conexao: sqlcipher3.Connection, tabela: TabelaDeItens, nome: str) -> ItemNovo:
    cursor = conexao.execute(
        f"INSERT INTO {tabela} (nome, nome_normalizado) VALUES (?, ?)", (nome, nome.casefold())
    )
    return ItemNovo(Entidade(tabela), _id_inserido(cursor), retrato_de_item(nome))


def _id_inserido(cursor: sqlcipher3.Cursor) -> int:
    assert cursor.lastrowid is not None  # INSERT numa tabela com rowid sempre dá o id
    return cursor.lastrowid


def listar_itens(
    conexao: sqlcipher3.Connection, tabela: TabelaDeItens
) -> tuple[tuple[int, str], ...]:
    cursor = conexao.execute(f"SELECT id, nome FROM {tabela} ORDER BY nome_normalizado")
    return tuple((linha[0], linha[1]) for linha in cursor)


def listar_examinadores(conexao: sqlcipher3.Connection) -> tuple[tuple[int, Examinador], ...]:
    cursor = conexao.execute("SELECT id, nome, crm, uf FROM examinador ORDER BY nome, crm")
    return tuple((id_, Examinador(nome=nome, crm=crm, uf=UF(uf))) for id_, nome, crm, uf in cursor)


def inserir_examinador(conexao: sqlcipher3.Connection, examinador: Examinador) -> ItemNovo:
    cursor = conexao.execute(
        "INSERT INTO examinador (nome, crm, uf) VALUES (?, ?, ?)",
        (examinador.nome, examinador.crm, examinador.uf),
    )
    return ItemNovo(Entidade.EXAMINADOR, _id_inserido(cursor), examinador.model_dump_json())


def garantir_examinador(
    conexao: sqlcipher3.Connection, examinador: Examinador
) -> tuple[int, ItemNovo | None]:
    linha = conexao.execute(
        "SELECT id, nome FROM examinador WHERE crm = ? AND uf = ?", (examinador.crm, examinador.uf)
    ).fetchone()
    if linha is None:
        novo = inserir_examinador(conexao, examinador)
        return novo.id, novo
    if linha[1] != examinador.nome:
        raise ExaminadorDivergente(examinador.crm, examinador.uf)
    return linha[0], None


class _Resolvedor:
    def __init__(self, conexao: sqlcipher3.Connection) -> None:
        self.conexao = conexao
        self.ids: dict[TabelaDeItens, dict[str, int]] = {"comorbidade": {}, "sintoma": {}}
        self.examinadores: dict[tuple[str, UF], int] = {}
        self.novos: list[ItemNovo] = []

    def nome(self, tabela: TabelaDeItens, nome: str) -> str:
        achado = buscar_item(self.conexao, tabela, nome)
        if achado is None:
            novo = inserir_item(self.conexao, tabela, nome)
            self.novos.append(novo)
            achado = (novo.id, nome)
        self.ids[tabela][achado[1]] = achado[0]
        return achado[1]

    def examinador(self, examinador: Examinador) -> None:
        id_, novo = garantir_examinador(self.conexao, examinador)
        self.examinadores[(examinador.crm, examinador.uf)] = id_
        if novo is not None:
            self.novos.append(novo)


def resolver(conexao: sqlcipher3.Connection, ficha: Ficha) -> Resolucao:
    resolvedor = _Resolvedor(conexao)
    comorbidades = tuple(resolvedor.nome("comorbidade", c) for c in ficha.paciente.comorbidades)
    exames = []
    for exame in ficha.exames:
        resolvedor.examinador(exame.examinador)
        sintomas = tuple(resolvedor.nome("sintoma", s) for s in exame.sintomas)
        exames.append(exame.model_copy(update={"sintomas": sintomas}))
    paciente = ficha.paciente.model_copy(update={"comorbidades": comorbidades})
    return Resolucao(
        ficha=ficha.model_copy(update={"paciente": paciente, "exames": tuple(exames)}),
        comorbidades=resolvedor.ids["comorbidade"],
        sintomas=resolvedor.ids["sintoma"],
        examinadores=resolvedor.examinadores,
        novos=tuple(resolvedor.novos),
    )
