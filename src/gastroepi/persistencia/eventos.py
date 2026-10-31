"""Gravação e leitura das entradas de auditoria. O elo é calculado por `auditoria`."""

import sqlcipher3

from gastroepi.auditoria.cadeia import ELO_INICIAL, EntradaDeAuditoria, Evento, calcular_elo

# Preferências não colidem com chaves internas como `chave_auditoria`.
_PREFIXO = "preferencia."


def ler_chave_de_auditoria(conexao: sqlcipher3.Connection) -> bytes:
    linha = conexao.execute("SELECT valor FROM metadados WHERE chave = 'chave_auditoria'")
    chave: bytes = linha.fetchone()[0]
    return chave


def ler_metadado(conexao: sqlcipher3.Connection, nome: str) -> str | None:
    """Preferências do app (ex.: destino externo, ADR-0005). Não são dado clínico e não
    entram na auditoria; ficam no banco cifrado."""
    linha = conexao.execute("SELECT valor FROM metadados WHERE chave = ?", (_PREFIXO + nome,))
    encontrada = linha.fetchone()
    return None if encontrada is None else bytes(encontrada[0]).decode("utf-8")


def gravar_metadado(conexao: sqlcipher3.Connection, nome: str, valor: str | None) -> None:
    if valor is None:
        conexao.execute("DELETE FROM metadados WHERE chave = ?", (_PREFIXO + nome,))
        return
    conexao.execute(
        "INSERT OR REPLACE INTO metadados (chave, valor) VALUES (?, ?)",
        (_PREFIXO + nome, valor.encode("utf-8")),
    )


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
