"""Textos da casca: rótulos de campo para o erro do domínio e números em pt-BR."""

import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.senha import SenhaCurta
from gastroepi.servicos.calculadoras import Intervalo, Proporcao
from gastroepi.ui_qt import textos


def test_rotulo_do_campo_aninhado() -> None:
    assert (
        textos.rotulo_do_campo("exames.0.lesoes.1.tamanho_mm") == "Exame 1, Lesão 2: Tamanho (mm)"
    )
    assert textos.rotulo_do_campo("paciente.cpf") == "CPF"
    assert textos.rotulo_do_campo("historico_familiar.0") == "Parente 1"
    assert textos.rotulo_do_campo("") == ""
    assert textos.rotulo_do_campo("campo_novo") == "campo_novo"


def test_erro_de_validacao_vira_lista_com_os_nomes_da_tela() -> None:
    with pytest.raises(ValidationError) as erro:
        Examinador.model_validate({"nome": "", "crm": "12a", "uf": None})

    mensagem = textos.mensagem_de_erro(erro.value)

    assert "Nome: Preenchimento obrigatório" in mensagem
    assert "CRM: CRM inválido" in mensagem
    assert mensagem.count("\n") == 2


def test_erros_do_nucleo_passam_com_a_mensagem_deles() -> None:
    assert textos.mensagem_de_erro(SenhaCurta("A senha é curta")) == "A senha é curta"
    assert textos.mensagem_de_erro(PermissionError("sem acesso")) == "sem acesso"
    assert textos.mensagem_de_erro(KeyError()) == "KeyError"


def test_numeros_no_formato_brasileiro() -> None:
    assert textos.numero(1234.5) == "1.234,50"
    assert textos.numero(0.125, 1) == "0,1"
    assert textos.numero(None) == textos.numero(math.nan) == "—"
    assert textos.numero(math.inf) == "∞"
    assert textos.numero(-math.inf) == "-∞"
    assert textos.percentual(0.3) == "30,0%"
    assert textos.percentual(None) == "—"
    assert textos.p_valor(0.0004) == "p < 0,001"
    assert textos.p_valor(0.0412) == "p = 0,041"


def test_intervalos_e_proporcoes() -> None:
    ic = Intervalo(0.179, 0.456)

    assert textos.intervalo(ic) == "0,18 a 0,46"
    assert textos.intervalo(ic, 1, em_percentual=True) == "17,9% a 45,6%"
    assert textos.proporcao(Proporcao(12, 40, ic)) == "12 de 40 = 30,0% (IC 95%: 17,9% a 45,6%)"
    assert textos.proporcao(Proporcao(0, 0, Intervalo(0, 1))) == "nenhum exame"
    assert textos.com_ic(2.5, Intervalo(1.2, 5.21)) == "2,50 (IC 95%: 1,20 a 5,21)"
    assert textos.qui_quadrado(3.84146, 0.05) == "3,841; p = 0,050"


def test_momento_local_usa_o_fuso_do_computador() -> None:
    momento = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    assert textos.momento_local(momento) == momento.astimezone().strftime("%d/%m/%Y %H:%M")
