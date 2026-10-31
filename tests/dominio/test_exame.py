"""Exame (ADR-0004): qualidade, indicação, examinador e derivados.

Preparo adequado: Boston total ≥ 6 e cada segmento ≥ 2. Escala: Lai EJ et al.,
Gastrointest Endosc 2009;69:620-625. Limiar: Calderwood AH et al., Gastrointest Endosc
2014;80:269-276.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from gastroepi.dominio.erros import DataInvalida, Problema, problemas_de
from gastroepi.dominio.exame import Boston, Exame, Examinador, idade_no_exame
from gastroepi.dominio.lesao import Lesao
from gastroepi.dominio.listas import (
    UF,
    Displasia,
    Histologia,
    Indicacao,
    MotivoNaoIntubacao,
    Paris,
    Segmento,
    Sexo,
)
from gastroepi.dominio.paciente import Paciente

EXAMINADORA = Examinador(nome="Dra. Fictícia Souza", crm="123456", uf=UF.SP)


def lesao(histologia: Histologia = Histologia.TUBULAR) -> Lesao:
    displasia = Displasia.NAO_SE_APLICA if histologia is Histologia.AGUARDANDO else Displasia.BAIXO
    return Lesao(
        segmento=Segmento.CECO,
        tamanho_mm=4,
        paris=Paris.IIA,
        histologia=histologia,
        displasia=displasia,
    )


def exame(**campos: object) -> Exame:
    padrao: dict[str, object] = {
        "data_exame": "05/03/2026",
        "indicacao": Indicacao.RASTREIO_RISCO_MEDIO,
        "examinador": EXAMINADORA,
        "intubacao_cecal": True,
    }
    return Exame.model_validate(padrao | campos)


def problemas(**campos: object) -> tuple[Problema, ...]:
    with pytest.raises(ValidationError) as erro:
        exame(**campos)
    return problemas_de(erro.value)


@pytest.mark.parametrize(
    ("segmentos", "total", "adequado"),
    [
        ((2, 2, 2), 6, True),
        ((3, 3, 3), 9, True),
        ((3, 3, 1), 7, False),
        ((1, 2, 2), 5, False),
        ((0, 3, 3), 6, False),
    ],
)
def test_preparo_adequado_e_boston_6_ou_mais_com_cada_segmento_2_ou_mais(
    segmentos: tuple[int, int, int], total: int, adequado: bool
) -> None:
    """Calderwood et al., Gastrointest Endosc 2014;80:269-276."""
    direito, transverso, esquerdo = segmentos
    boston = Boston(direito=direito, transverso=transverso, esquerdo=esquerdo)
    assert (boston.total, boston.adequado) == (total, adequado)


@pytest.mark.parametrize("nota", [-1, 4, True])
def test_segmento_de_boston_fora_de_0_a_3_e_recusado(nota: int) -> None:
    with pytest.raises(ValidationError):
        Boston(direito=nota, transverso=2, esquerdo=2)


def test_exame_minimo_nao_tem_preparo_nem_retirada() -> None:
    """Escolha do dono: só a intubação cecal é obrigatória; Boston e retirada podem faltar."""
    novo = exame()
    assert (novo.preparo, novo.tempo_retirada_min, novo.preparo_adequado) == (None, None, None)
    assert novo.data_exame == date(2026, 3, 5)


def test_preparo_adequado_do_exame_vem_do_boston() -> None:
    preparo = Boston(direito=1, transverso=3, esquerdo=3)
    assert exame(preparo=preparo).preparo_adequado is False


def test_intubacao_cecal_e_obrigatoria() -> None:
    campos = {"data_exame": "05/03/2026", "indicacao": Indicacao.OUTRA, "examinador": EXAMINADORA}
    with pytest.raises(ValidationError) as erro:
        Exame.model_validate(campos)
    assert Problema("intubacao_cecal", "missing", "Preenchimento obrigatório") in problemas_de(
        erro.value
    )


def test_intubacao_cecal_nao_aceita_1_no_lugar_de_sim() -> None:
    assert problemas(intubacao_cecal=1)[0].codigo == "bool_type"


def test_ceco_nao_alcancado_exige_motivo() -> None:
    assert problemas(intubacao_cecal=False) == (
        Problema(
            "motivo_nao_intubacao",
            "campo_condicional",
            "Informe por que o ceco não foi alcançado",
        ),
    )


def test_motivo_com_ceco_alcancado_e_recusado() -> None:
    motivo = MotivoNaoIntubacao.COLITE_GRAVE
    assert problemas(motivo_nao_intubacao=motivo)[0].mensagem == (
        "Motivo só quando o ceco não foi alcançado"
    )


def test_motivo_outro_exige_descricao() -> None:
    campos = {"intubacao_cecal": False, "motivo_nao_intubacao": MotivoNaoIntubacao.OUTRO}
    assert problemas(**campos) == (
        Problema("motivo_outro", "campo_condicional", "Descreva o motivo quando for 'outro'"),
    )


def test_descricao_de_motivo_sem_outro_e_recusada() -> None:
    campos = {
        "intubacao_cecal": False,
        "motivo_nao_intubacao": MotivoNaoIntubacao.COLITE_GRAVE,
        "motivo_outro": "Paciente agitado",
    }
    assert problemas(**campos)[0].campo == "motivo_outro"


def test_indicacao_outra_exige_descricao_e_so_ela_aceita_descricao() -> None:
    assert problemas(indicacao=Indicacao.OUTRA)[0] == Problema(
        "indicacao_outra", "campo_condicional", "Descreva a indicação quando for 'outra'"
    )
    assert problemas(indicacao_outra="Pré-operatório")[0].campo == "indicacao_outra"
    assert exame(indicacao=Indicacao.OUTRA, indicacao_outra="Pré-op").indicacao_outra == "Pré-op"


@pytest.mark.parametrize(
    ("tempo", "codigo"), [(0, "greater_than"), (float("inf"), "finite_number")]
)
def test_tempo_de_retirada_precisa_ser_positivo_e_finito(tempo: float, codigo: str) -> None:
    assert problemas(tempo_retirada_min=tempo)[0].codigo == codigo


def test_tempo_de_retirada_aceita_decimal_e_inteiro() -> None:
    assert exame(tempo_retirada_min=6.5).tempo_retirada_min == 6.5
    assert exame(tempo_retirada_min=7).tempo_retirada_min == 7.0


def test_tempo_de_retirada_vazio_vira_none() -> None:
    assert exame(tempo_retirada_min="").tempo_retirada_min is None


def test_n_polipos_e_o_numero_de_lesoes() -> None:
    """ADR-0004: a v0.1.16 tinha examinadora com 0 pólipos e 2 adenomas; aqui não dá."""
    assert exame(lesoes=(lesao(), lesao())).n_polipos == 2
    assert exame().n_polipos == 0


def test_n_polipos_digitado_e_recusado_como_campo_desconhecido() -> None:
    assert problemas(n_polipos=3) == (
        Problema("n_polipos", "extra_forbidden", "Campo desconhecido"),
    )


def test_exame_aguarda_histologia_enquanto_alguma_lesao_aguarda() -> None:
    assert exame(lesoes=(lesao(), lesao(Histologia.AGUARDANDO))).aguardando_histologia
    assert not exame(lesoes=(lesao(),)).aguardando_histologia


def test_sintomas_repetidos_viram_um() -> None:
    assert exame(sintomas=("Hematoquezia", "hematoquezia ")).sintomas == ("Hematoquezia",)


def test_crm_so_com_digitos() -> None:
    assert Examinador(nome="Dr. Teste", crm=" 012345 ", uf=UF.RJ).crm == "012345"
    with pytest.raises(ValidationError) as erro:
        Examinador(nome="Dr. Teste", crm="12.345-SP", uf=UF.RJ)
    assert problemas_de(erro.value) == (
        Problema("crm", "crm_invalido", "CRM inválido: use de 1 a 8 dígitos, sem a UF"),
    )


def test_repr_nao_mostra_texto_livre() -> None:
    texto = repr(exame(observacao="Paciente Fulano relatou"))
    assert "Fulano" not in texto


def test_json_ida_e_volta_preserva_o_exame() -> None:
    original = exame(
        preparo=Boston(direito=2, transverso=3, esquerdo=3),
        tempo_retirada_min=8.5,
        sintomas=("Dor abdominal",),
        lesoes=(lesao(), lesao(Histologia.AGUARDANDO)),
        observacao="Sem intercorrências",
    )
    assert Exame.model_validate_json(original.model_dump_json()) == original


def test_idade_no_exame_sai_da_data_de_nascimento() -> None:
    paciente = Paciente(
        prontuario="F00001",
        nome="Ana Fictícia",
        sexo=Sexo.FEMININO,
        data_nascimento=date(1980, 3, 6),
    )
    assert idade_no_exame(paciente, exame()) == 45
    with pytest.raises(DataInvalida):
        idade_no_exame(paciente, exame(data_exame="05/03/1979"))
