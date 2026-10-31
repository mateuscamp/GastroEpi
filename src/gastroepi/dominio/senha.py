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


# ADR-0005, item 9: com cópias na nuvem, o Argon2id só atrasa a adivinhação.
PALAVRAS_DA_FRASE = 4
FRASE_MINIMA = 20


def e_frase_longa(senha: str) -> bool:
    """Pelo menos 4 palavras e 20 caracteres (em NFC), a senha exigida para copiar o cofre
    para uma pasta sincronizada."""
    normalizada = unicodedata.normalize("NFC", senha)
    return len(normalizada.split()) >= PALAVRAS_DA_FRASE and len(normalizada) >= FRASE_MINIMA
