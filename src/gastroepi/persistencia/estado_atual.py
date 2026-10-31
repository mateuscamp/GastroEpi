"""Estado atual de cada registro, no mesmo formato do snapshot da auditoria."""

import sqlcipher3

from gastroepi.auditoria.cadeia import Entidade
from gastroepi.persistencia.catalogos import listar_examinadores, listar_itens, retrato_de_item
from gastroepi.persistencia.fichas import ler_fichas


def estados_atuais(conexao: sqlcipher3.Connection) -> dict[tuple[str, int], str | None]:
    estados: dict[tuple[str, int], str | None] = {}
    for paciente_id, ficha in ler_fichas(conexao).items():
        estados[(Entidade.PACIENTE, paciente_id)] = ficha.model_dump_json()
    for item_id, nome in listar_itens(conexao, "comorbidade"):
        estados[(Entidade.COMORBIDADE, item_id)] = retrato_de_item(nome)
    for item_id, nome in listar_itens(conexao, "sintoma"):
        estados[(Entidade.SINTOMA, item_id)] = retrato_de_item(nome)
    for examinador_id, examinador in listar_examinadores(conexao):
        estados[(Entidade.EXAMINADOR, examinador_id)] = examinador.model_dump_json()
    return estados
