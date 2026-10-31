from datetime import date

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.estatistica.variaveis import (
    NENHUMA,
    Variavel,
    VariavelNumerica,
    categorias,
    exames_de,
    faixa_etaria,
    medida,
    rotulo_do_examinador,
)
from tests.estatistica.referencias import fichas_do_oraculo


def test_um_registro_por_exame() -> None:
    fichas = gerar_fichas(3, 40)
    assert len(exames_de(fichas)) == sum(len(f.exames) for f in fichas)


@pytest.mark.parametrize(
    ("idade", "faixa"), [(40, "40-49"), (49, "40-49"), (50, "50-59"), (9, "0-9")]
)
def test_faixa_etaria_e_a_decada(idade: int, faixa: str) -> None:
    assert faixa_etaria(idade) == faixa


def test_cada_variavel_le_um_campo_de_lista_fechada() -> None:
    registro = exames_de(fichas_do_oraculo()[1:2])[0]  # FICT-0002: 47 anos, F, 1 pólipo
    assert registro.exame.data_exame == date(2026, 2, 2)
    assert categorias(registro, Variavel.SEXO) == ("Feminino",)
    assert categorias(registro, Variavel.FAIXA_ETARIA) == ("40-49",)
    assert categorias(registro, Variavel.INDICACAO) == ("Rastreio de risco médio",)
    assert categorias(registro, Variavel.EXAMINADOR) == (rotulo_do_examinador(registro),)
    assert categorias(registro, Variavel.COMORBIDADE) == ("Obesidade",)
    assert categorias(registro, Variavel.SINTOMA) == ("Dor abdominal",)
    assert categorias(registro, Variavel.N_POLIPOS) == ("1",)
    assert medida(registro, VariavelNumerica.IDADE) == 47.0
    assert medida(registro, VariavelNumerica.N_POLIPOS) == 1.0
    assert medida(registro, VariavelNumerica.TEMPO_RETIRADA) is None


def test_exame_sem_sintoma_cai_em_nenhuma() -> None:
    registro = exames_de(fichas_do_oraculo()[3:4])[0]  # FICT-0004: sem sintomas
    assert categorias(registro, Variavel.SINTOMA) == (NENHUMA,)


def test_rotulo_do_examinador_leva_o_crm() -> None:
    registro = exames_de(gerar_fichas(1, 1))[0]
    rotulo = rotulo_do_examinador(registro)
    assert registro.exame.examinador.crm in rotulo
    assert rotulo.startswith(registro.exame.examinador.nome)


def test_toda_variavel_tem_leitor() -> None:
    registro = exames_de(fichas_do_oraculo()[:1])[0]
    assert all(categorias(registro, v) for v in Variavel)
    assert all(medida(registro, v) is not None for v in VariavelNumerica if v != "tempo_retirada")
