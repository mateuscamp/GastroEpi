"""Ficha ↔ linhas das tabelas (ADR-0004).

Gravar: a ficha já resolvida contra os catálogos (`catalogos.resolver`). Editar troca a
linha do paciente e regrava os filhos (exames, lesões, histórico), sempre na ordem da
ficha: a coluna `ordem` faz a leitura devolver exatamente a ficha gravada.

Ler: poucas consultas para o banco inteiro, agrupadas em Python, em vez de uma por
paciente. As linhas passam de novo pelo domínio: um valor alterado por fora que o
domínio recusa vira `ValidationError`, e não um paciente inválido na tela.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date

import sqlcipher3

from gastroepi.dominio.exame import Boston, Exame
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.lesao import Lesao
from gastroepi.dominio.listas import (
    Displasia,
    Histologia,
    Indicacao,
    MotivoNaoIntubacao,
    Parentesco,
    Paris,
    Segmento,
    Sexo,
)
from gastroepi.dominio.paciente import HistoricoFamiliar, Paciente
from gastroepi.persistencia.catalogos import Resolucao, listar_examinadores

_LINHA_DO_PACIENTE = "prontuario = ?, cpf = ?, nome = ?, sexo = ?, data_nascimento = ?"


def _colunas_do_paciente(paciente: Paciente) -> tuple[object, ...]:
    return (paciente.prontuario, paciente.cpf, paciente.nome, paciente.sexo,
            paciente.data_nascimento.isoformat())  # fmt: skip


def inserir_ficha(conexao: sqlcipher3.Connection, resolucao: Resolucao) -> int:
    cursor = conexao.execute(
        "INSERT INTO paciente (prontuario, cpf, nome, sexo, data_nascimento)"
        " VALUES (?, ?, ?, ?, ?)",
        _colunas_do_paciente(resolucao.ficha.paciente),
    )
    assert cursor.lastrowid is not None  # INSERT numa tabela com rowid sempre dá o id
    _gravar_filhos(conexao, cursor.lastrowid, resolucao)
    return cursor.lastrowid


def atualizar_ficha(conexao: sqlcipher3.Connection, paciente_id: int, resolucao: Resolucao) -> None:
    conexao.execute(
        f"UPDATE paciente SET {_LINHA_DO_PACIENTE} WHERE id = ?",
        (*_colunas_do_paciente(resolucao.ficha.paciente), paciente_id),
    )
    for tabela in ("paciente_comorbidade", "historico_familiar", "exame"):
        conexao.execute(f"DELETE FROM {tabela} WHERE paciente_id = ?", (paciente_id,))
    _gravar_filhos(conexao, paciente_id, resolucao)


def apagar_ficha(conexao: sqlcipher3.Connection, paciente_id: int) -> None:
    """Exames, lesões, histórico e vínculos com catálogos saem em cascata (FOREIGN KEY)."""
    conexao.execute("DELETE FROM paciente WHERE id = ?", (paciente_id,))


def _gravar_filhos(conexao: sqlcipher3.Connection, paciente_id: int, resolucao: Resolucao) -> None:
    paciente = resolucao.ficha.paciente
    conexao.executemany(
        "INSERT INTO paciente_comorbidade (paciente_id, ordem, comorbidade_id) VALUES (?, ?, ?)",
        [(paciente_id, ordem, resolucao.comorbidades[nome])
         for ordem, nome in enumerate(paciente.comorbidades)],
    )  # fmt: skip
    conexao.executemany(
        "INSERT INTO historico_familiar (paciente_id, ordem, parentesco, idade_diagnostico)"
        " VALUES (?, ?, ?, ?)",
        [(paciente_id, ordem, h.parentesco, h.idade_diagnostico)
         for ordem, h in enumerate(paciente.historico_familiar)],
    )  # fmt: skip
    for ordem, exame in enumerate(resolucao.ficha.exames):
        _inserir_exame(conexao, paciente_id, ordem, exame, resolucao)


def _inserir_exame(
    conexao: sqlcipher3.Connection, paciente_id: int, ordem: int, exame: Exame, resolucao: Resolucao
) -> None:
    examinador_id = resolucao.examinadores[(exame.examinador.crm, exame.examinador.uf)]
    boston = exame.preparo
    cursor = conexao.execute(
        "INSERT INTO exame (paciente_id, ordem, data_exame, indicacao, indicacao_outra,"
        " examinador_id, boston_direito, boston_transverso, boston_esquerdo, intubacao_cecal,"
        " motivo_nao_intubacao, motivo_outro, tempo_retirada_min, observacao)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (paciente_id, ordem, exame.data_exame.isoformat(), exame.indicacao,
         exame.indicacao_outra, examinador_id,
         boston and boston.direito, boston and boston.transverso, boston and boston.esquerdo,
         int(exame.intubacao_cecal), exame.motivo_nao_intubacao, exame.motivo_outro,
         exame.tempo_retirada_min, exame.observacao),
    )  # fmt: skip
    exame_id = cursor.lastrowid
    conexao.executemany(
        "INSERT INTO exame_sintoma (exame_id, ordem, sintoma_id) VALUES (?, ?, ?)",
        [(exame_id, i, resolucao.sintomas[nome]) for i, nome in enumerate(exame.sintomas)],
    )
    conexao.executemany(
        "INSERT INTO lesao (exame_id, ordem, segmento, tamanho_mm, paris, histologia,"
        " displasia, histologia_outra, laudo_texto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(exame_id, i, lesao.segmento, lesao.tamanho_mm, lesao.paris, lesao.histologia,
          lesao.displasia, lesao.histologia_outra, lesao.laudo_texto)
         for i, lesao in enumerate(exame.lesoes)],
    )  # fmt: skip


def _filtro(coluna: str, paciente_id: int | None) -> tuple[str, tuple[int, ...]]:
    return ("", ()) if paciente_id is None else (f"WHERE {coluna} = ?", (paciente_id,))


def _agrupar[T](pares: Iterable[tuple[int, T]]) -> dict[int, list[T]]:
    grupos: dict[int, list[T]] = defaultdict(list)
    for chave, valor in pares:
        grupos[chave].append(valor)
    return grupos


def _linhas_por(
    conexao: sqlcipher3.Connection, coluna: str, sql: str, paciente_id: int | None, filtro_em: str
) -> dict[int, list[sqlcipher3.Row]]:
    filtro, parametros = _filtro(filtro_em, paciente_id)
    return _agrupar(
        (linha[coluna], linha) for linha in conexao.execute(sql.format(filtro), parametros)
    )


class _Linhas:
    """As linhas de um ou de todos os pacientes, agrupadas, ainda sem passar pelo domínio."""

    def __init__(self, conexao: sqlcipher3.Connection, paciente_id: int | None) -> None:
        self.comorbidades = _linhas_por(conexao, "paciente_id",
            "SELECT v.paciente_id, c.nome FROM paciente_comorbidade v"
            " JOIN comorbidade c ON c.id = v.comorbidade_id {} ORDER BY v.paciente_id, v.ordem",
            paciente_id, "v.paciente_id")  # fmt: skip
        self.historicos = _linhas_por(conexao, "paciente_id",
            "SELECT * FROM historico_familiar {} ORDER BY paciente_id, ordem",
            paciente_id, "paciente_id")  # fmt: skip
        self.exames = _linhas_por(
            conexao,
            "paciente_id",
            "SELECT * FROM exame {} ORDER BY paciente_id, ordem",
            paciente_id,
            "paciente_id",
        )
        self.sintomas = _linhas_por(conexao, "exame_id",
            "SELECT v.exame_id, s.nome FROM exame_sintoma v JOIN sintoma s ON s.id = v.sintoma_id"
            " JOIN exame e ON e.id = v.exame_id {} ORDER BY v.exame_id, v.ordem",
            paciente_id, "e.paciente_id")  # fmt: skip
        self.lesoes = _linhas_por(conexao, "exame_id",
            "SELECT l.* FROM lesao l JOIN exame e ON e.id = l.exame_id {}"
            " ORDER BY l.exame_id, l.ordem", paciente_id, "e.paciente_id")  # fmt: skip
        self.examinadores = dict(listar_examinadores(conexao))


def _lesao(linha: sqlcipher3.Row) -> Lesao:
    return Lesao(
        segmento=Segmento(linha["segmento"]),
        tamanho_mm=linha["tamanho_mm"],
        paris=Paris(linha["paris"]),
        histologia=Histologia(linha["histologia"]),
        displasia=Displasia(linha["displasia"]),
        histologia_outra=linha["histologia_outra"],
        laudo_texto=linha["laudo_texto"],
    )


def _boston(linha: sqlcipher3.Row) -> Boston | None:
    if linha["boston_direito"] is None:
        return None
    return Boston(
        direito=linha["boston_direito"],
        transverso=linha["boston_transverso"],
        esquerdo=linha["boston_esquerdo"],
    )


def _exame(linha: sqlcipher3.Row, linhas: _Linhas) -> Exame:
    motivo = linha["motivo_nao_intubacao"]
    return Exame(
        data_exame=date.fromisoformat(linha["data_exame"]),
        indicacao=Indicacao(linha["indicacao"]),
        indicacao_outra=linha["indicacao_outra"],
        examinador=linhas.examinadores[linha["examinador_id"]],
        preparo=_boston(linha),
        intubacao_cecal=bool(linha["intubacao_cecal"]),
        motivo_nao_intubacao=None if motivo is None else MotivoNaoIntubacao(motivo),
        motivo_outro=linha["motivo_outro"],
        tempo_retirada_min=linha["tempo_retirada_min"],
        sintomas=tuple(s["nome"] for s in linhas.sintomas.get(linha["id"], [])),
        lesoes=tuple(_lesao(lesao) for lesao in linhas.lesoes.get(linha["id"], [])),
        observacao=linha["observacao"],
    )


def _ficha(linha: sqlcipher3.Row, linhas: _Linhas) -> Ficha:
    pid = linha["id"]
    historico = tuple(
        HistoricoFamiliar(
            parentesco=Parentesco(h["parentesco"]), idade_diagnostico=h["idade_diagnostico"]
        )
        for h in linhas.historicos.get(pid, [])
    )
    paciente = Paciente(
        prontuario=linha["prontuario"],
        cpf=linha["cpf"],
        nome=linha["nome"],
        sexo=Sexo(linha["sexo"]),
        data_nascimento=date.fromisoformat(linha["data_nascimento"]),
        comorbidades=tuple(c["nome"] for c in linhas.comorbidades.get(pid, [])),
        historico_familiar=historico,
    )
    exames = tuple(_exame(exame, linhas) for exame in linhas.exames.get(pid, []))
    return Ficha(paciente=paciente, exames=exames)


def ler_fichas_ou_ilegiveis(
    conexao: sqlcipher3.Connection, paciente_id: int | None = None
) -> dict[int, Ficha | None]:
    """Todas as fichas por id, ou só a de `paciente_id`. `None` marca a ficha que o domínio
    recusa: um valor alterado por fora que passou no CHECK (ex.: displasia incoerente)."""
    linhas = _Linhas(conexao, paciente_id)
    filtro, parametros = _filtro("id", paciente_id)
    fichas: dict[int, Ficha | None] = {}
    for linha in conexao.execute(f"SELECT * FROM paciente {filtro} ORDER BY id", parametros):
        try:
            fichas[linha["id"]] = _ficha(linha, linhas)
        except ValueError:  # ValidationError, valor fora do Enum, data inválida
            fichas[linha["id"]] = None
    return fichas
