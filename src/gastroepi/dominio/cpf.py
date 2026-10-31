"""CPF: normalização para 11 dígitos e dígitos verificadores.

Algoritmo da Receita Federal (o mesmo do validarCPF da v0.1.16): cada DV é
11 - (soma de dígito * peso) mod 11, com pesos 10..2 para o 1º e 11..2 para o 2º;
resto 10 ou 11 vira 0. Nenhuma mensagem de erro repete o número recebido.
"""

from gastroepi.dominio.erros import CpfInvalido

DIGITOS = frozenset("0123456789")
SEPARADORES = frozenset(".- ")


def _digito_verificador(digitos: str) -> str:
    peso_inicial = len(digitos) + 1
    soma = sum(int(d) * (peso_inicial - i) for i, d in enumerate(digitos))
    resto = 11 - soma % 11
    return "0" if resto >= 10 else str(resto)


def digitos_verificadores(base: str) -> str:
    """Os 2 DVs dos 9 primeiros dígitos."""
    primeiro = _digito_verificador(base)
    return primeiro + _digito_verificador(base + primeiro)


def formatar_cpf(cpf: str) -> str:
    """`52998224725` → `529.982.247-25`. Recebe o CPF já normalizado."""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def normalizar_cpf(texto: str) -> str:
    """Devolve os 11 dígitos de um CPF válido ou levanta `CpfInvalido`."""
    if any(c not in DIGITOS and c not in SEPARADORES for c in texto):
        raise CpfInvalido("CPF inválido: use só dígitos, pontos e traço")
    digitos = "".join(c for c in texto if c in DIGITOS)
    if len(digitos) != 11:
        raise CpfInvalido("CPF inválido: esperado 11 dígitos (ex.: 000.000.000-00)")
    if len(set(digitos)) == 1:
        raise CpfInvalido("CPF inválido: os 11 dígitos são iguais")
    if digitos[9:] != digitos_verificadores(digitos[:9]):
        raise CpfInvalido("CPF inválido: dígito verificador não confere")
    return digitos
