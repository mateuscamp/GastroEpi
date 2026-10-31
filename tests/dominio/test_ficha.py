"""Ficha: paciente + exames; nenhum exame antes do nascimento."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from gastroepi.dominio.erros import Problema, problemas_de
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas

FICHA = gerar_fichas(semente=1, quantidade=1)[0]


def com_data_do_exame(dias_apos_nascer: int) -> Ficha:
    data = FICHA.paciente.data_nascimento + timedelta(days=dias_apos_nascer)
    exame = FICHA.exames[0].model_copy(update={"data_exame": data})
    return Ficha.model_validate({"paciente": FICHA.paciente, "exames": (FICHA.exames[0], exame)})


def test_ficha_sem_exames_e_valida() -> None:
    assert Ficha(paciente=FICHA.paciente).exames == ()


def test_exame_no_dia_do_nascimento_e_aceito() -> None:
    assert len(com_data_do_exame(0).exames) == 2


def test_exame_antes_do_nascimento_e_recusado_apontando_o_exame() -> None:
    with pytest.raises(ValidationError) as erro:
        com_data_do_exame(-1)

    assert problemas_de(erro.value) == (
        Problema(
            "exames.1.data_exame", "data_invalida", "Data inválida: exame antes do nascimento"
        ),
    )
