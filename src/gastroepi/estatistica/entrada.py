"""Conferência da entrada e os erros da estatística. A mensagem diz o valor recebido e o
esperado; contagens não são dado sensível, e nenhum erro daqui carrega nome, CPF ou texto livre.
"""


class EntradaInvalida(ValueError):
    """Entrada fora do domínio da função (ex.: casos > total, alfa fora de (0, 1))."""


class SemObservacao(EntradaInvalida):
    """Nenhuma observação (tabela vazia, lista vazia): não há o que estimar."""


def conferir_alfa(alfa: float) -> None:
    if not 0.0 < alfa < 1.0:
        raise EntradaInvalida(f"alfa deve estar em (0, 1); recebido {alfa}")


def conferir_contagens(*contagens: int) -> None:
    negativas = [c for c in contagens if c < 0]
    if negativas:
        raise EntradaInvalida(f"contagens devem ser ≥ 0; recebido {negativas}")
