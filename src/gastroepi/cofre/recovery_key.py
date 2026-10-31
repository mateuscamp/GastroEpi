"""Recovery key: a própria chave de dados, legível para um leigo copiar no papel (ADR-0003).

Formato: 8 blocos de 8 caracteres separados por espaço. Cada bloco tem 7 símbolos de
dados e 1 dígito de verificação, como os 8 blocos da chave de recuperação do BitLocker:
um erro de digitação aponta o bloco, e a tela pode dizer "confira o bloco 3".

- Alfabeto base32 de Crockford (sem I, L, O e U). Na leitura, O vale 0 e I/L valem 1.
- 56 símbolos de dados = 280 bits: os 256 da chave e 24 de enchimento, que devem ser zero.
- Dígito de verificação: Luhn mod 32 sobre os 7 símbolos do bloco. Detecta toda
  substituição de um caractere e 99,8% das trocas de dois vizinhos (medido em 2026-10-31).

Nenhuma mensagem de erro repete o que foi digitado: a recovery key abre o banco.
"""

ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CONFUNDIVEIS = str.maketrans({"O": "0", "I": "1", "L": "1"})
_SEPARADORES = str.maketrans("", "", " -\t\r\n")
BLOCOS = 8
DADOS_POR_BLOCO = 7
TAMANHO_DA_CHAVE = 32
_BITS_DE_DADOS = BLOCOS * DADOS_POR_BLOCO * 5
_ENCHIMENTO = _BITS_DE_DADOS - TAMANHO_DA_CHAVE * 8


class RecoveryKeyInvalida(ValueError):
    """`bloco` (1 a 8) aponta onde está o erro; `None` quando falta ou sobra caractere."""

    def __init__(self, bloco: int | None = None) -> None:
        if bloco is None:
            mensagem = "Recovery key inválida: são 8 blocos de 8 caracteres"
        else:
            mensagem = f"Recovery key com erro de digitação no bloco {bloco}"
        super().__init__(mensagem)
        self.bloco = bloco


def digito_de_verificacao(bloco: str) -> str:
    """Luhn mod N com N = 32 (o dígito vai à direita, então o fator começa em 2)."""
    fator, soma = 2, 0
    for simbolo in reversed(bloco):
        parcela = fator * ALFABETO.index(simbolo)
        soma += parcela // 32 + parcela % 32
        fator = 3 - fator
    return ALFABETO[-soma % 32]


def formatar_recovery_key(chave: bytes) -> str:
    if len(chave) != TAMANHO_DA_CHAVE:
        raise ValueError(f"Chave de {len(chave)} bytes; esperado {TAMANHO_DA_CHAVE}")
    numero = int.from_bytes(chave, "big") << _ENCHIMENTO
    simbolos = [
        ALFABETO[(numero >> deslocamento) & 31]
        for deslocamento in range(_BITS_DE_DADOS - 5, -1, -5)
    ]
    blocos = (
        "".join(simbolos[i : i + DADOS_POR_BLOCO]) for i in range(0, len(simbolos), DADOS_POR_BLOCO)
    )
    return " ".join(bloco + digito_de_verificacao(bloco) for bloco in blocos)


def _conferir_bloco(numero: int, bloco: str) -> str:
    dados, digito = bloco[:DADOS_POR_BLOCO], bloco[DADOS_POR_BLOCO:]
    if any(simbolo not in ALFABETO for simbolo in bloco) or digito_de_verificacao(dados) != digito:
        raise RecoveryKeyInvalida(numero)
    return dados


def ler_recovery_key(texto: str) -> bytes:
    limpo = texto.upper().translate(_SEPARADORES).translate(_CONFUNDIVEIS)
    if len(limpo) != BLOCOS * (DADOS_POR_BLOCO + 1):
        raise RecoveryKeyInvalida
    tamanho = DADOS_POR_BLOCO + 1
    dados = "".join(
        _conferir_bloco(n, limpo[(n - 1) * tamanho : n * tamanho]) for n in range(1, BLOCOS + 1)
    )
    numero = 0
    for simbolo in dados:
        numero = numero << 5 | ALFABETO.index(simbolo)
    if numero & ((1 << _ENCHIMENTO) - 1):
        raise RecoveryKeyInvalida(BLOCOS)
    return (numero >> _ENCHIMENTO).to_bytes(TAMANHO_DA_CHAVE, "big")
