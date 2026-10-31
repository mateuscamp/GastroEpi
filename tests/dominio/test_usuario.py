"""Usuário que opera o app: nome aparado e obrigatório."""

import pytest
from pydantic import ValidationError

from gastroepi.dominio.erros import problemas_de
from gastroepi.dominio.usuario import Usuario


def test_nome_e_aparado() -> None:
    assert Usuario(nome="  Ana Fictícia ").nome == "Ana Fictícia"


def test_nome_vazio_e_recusado_com_mensagem_pt_br() -> None:
    with pytest.raises(ValidationError) as erro:
        Usuario(nome=" ")

    assert problemas_de(erro.value)[0].mensagem == "Preenchimento obrigatório"
