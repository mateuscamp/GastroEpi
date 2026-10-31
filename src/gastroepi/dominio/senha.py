"""Senha nova do cofre: digitada duas vezes, iguais, com pelo menos 8 caracteres (FR-1.1).

A regra mora no domínio para a casca não reimplementá-la (Princípio V). O tamanho conta
caracteres em NFC, a mesma forma que o cofre usa para derivar a chave. Nenhuma
mensagem repete a senha.
"""

import unicodedata

from gastroepi.dominio.erros import ErroDeValidacao

SENHA_MINIMA = 8


class SenhaCurta(ErroDeValidacao):
    codigo = "senha_curta"


class SenhasDiferentes(ErroDeValidacao):
    codigo = "senhas_diferentes"


def conferir_nova_senha(senha: str, confirmacao: str) -> None:
    if senha != confirmacao:
        raise SenhasDiferentes("As duas senhas digitadas não são iguais", campo="confirmacao")
    if len(unicodedata.normalize("NFC", senha)) < SENHA_MINIMA:
        mensagem = f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres"
        raise SenhaCurta(mensagem, campo="senha")
