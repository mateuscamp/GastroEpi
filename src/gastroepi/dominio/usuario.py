"""Usuário que opera o app: o nome que vai para cada entrada da auditoria.

Não é o examinador do exame. Sem nome definido, a auditoria grava `USUARIO_PADRAO`.
"""

from gastroepi.dominio.campos import ModeloDeDominio, TextoObrigatorio

USUARIO_PADRAO = "Usuário do GastroEpi"


class Usuario(ModeloDeDominio):
    nome: TextoObrigatorio
