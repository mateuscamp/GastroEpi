"""Gravação e leitura das entradas de auditoria. O elo é calculado por `auditoria`."""

import sqlcipher3

from gastroepi.auditoria.cadeia import ELO_INICIAL, EntradaDeAuditoria, Evento, calcular_elo


def ler_chave_de_auditoria(conexao: sqlcipher3.Connection) -> bytes:
    linha = conexao.execute("SELECT valor FROM metadados WHERE chave = 'chave_auditoria'")
    chave: bytes = linha.fetchone()[0]
    return chave


def registrar_evento(conexao: sqlcipher3.Connection, chave: bytes, evento: Evento) -> None:
    linha = conexao.execute("SELECT elo FROM auditoria ORDER BY id DESC LIMIT 1").fetchone()
    elo = calcular_elo(chave, ELO_INICIAL if linha is None else linha[0], evento)
    conexao.execute(
        "INSERT INTO auditoria (momento, usuario, acao, entidade, entidade_id, antes, depois, elo)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (evento.momento, evento.usuario, evento.acao, evento.entidade, evento.entidade_id,
         evento.antes, evento.depois, elo),
    )  # fmt: skip


def ler_entradas(conexao: sqlcipher3.Connection) -> tuple[EntradaDeAuditoria, ...]:
    cursor = conexao.execute(
        "SELECT id, momento, usuario, acao, entidade, entidade_id, antes, depois, elo"
        " FROM auditoria ORDER BY id"
    )
    return tuple(_entrada(linha) for linha in cursor)


def _entrada(linha: sqlcipher3.Row) -> EntradaDeAuditoria:
    evento = Evento(
        momento=linha["momento"],
        usuario=linha["usuario"],
        acao=linha["acao"],
        entidade=linha["entidade"],
        entidade_id=linha["entidade_id"],
        antes=linha["antes"],
        depois=linha["depois"],
    )
    return EntradaDeAuditoria(id=linha["id"], evento=evento, elo=linha["elo"])
