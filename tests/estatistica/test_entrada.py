import pytest

from gastroepi.estatistica.entrada import (
    EntradaInvalida,
    SemObservacao,
    conferir_alfa,
    conferir_contagens,
)


@pytest.mark.parametrize("alfa", [0.0, 1.0, -0.1, 2.0])
def test_alfa_fora_de_zero_um_e_recusado_com_o_valor(alfa: float) -> None:
    with pytest.raises(EntradaInvalida, match=str(alfa)):
        conferir_alfa(alfa)


def test_contagem_negativa_e_recusada_com_os_valores() -> None:
    conferir_contagens(0, 1, 2)
    with pytest.raises(EntradaInvalida, match=r"\[-1, -3\]"):
        conferir_contagens(1, -1, -3)


def test_sem_observacao_e_entrada_invalida() -> None:
    """A casca pode tratar as duas pelo mesmo `except EntradaInvalida`."""
    assert issubclass(SemObservacao, EntradaInvalida)
    assert issubclass(EntradaInvalida, ValueError)
