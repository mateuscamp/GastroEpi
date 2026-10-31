"""Item de catálogo: nome aparado, obrigatório, comparado sem distinguir caixa."""

import pytest
from pydantic import ValidationError

from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.erros import problemas_de


def test_nome_e_aparado() -> None:
    assert ItemDeCatalogo(nome="  Tenesmo ").nome == "Tenesmo"


def test_nome_vazio_e_recusado_com_mensagem_pt_br() -> None:
    with pytest.raises(ValidationError) as erro:
        ItemDeCatalogo(nome="   ")

    assert problemas_de(erro.value)[0].mensagem == "Preenchimento obrigatório"
