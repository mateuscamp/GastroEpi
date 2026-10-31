"""Lesão por lesão (ADR-0004): coerência da histologia e classificações derivadas.

Referências das regras derivadas:
- adenoma convencional e serrilhada: WHO Classification of Tumours, Digestive System
  Tumours, 5ª ed., 2019 (tubular, tubuloviloso, viloso; SSL e TSA);
- adenoma avançado: Gupta S et al., Recommendations for Follow-Up After Colonoscopy and
  Polypectomy (US Multi-Society Task Force), Gastroenterology 2020;158:1131-1153:
  adenoma ≥ 10 mm, componente viloso (tubuloviloso ou viloso) ou displasia de alto grau.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from gastroepi.dominio.erros import Problema, problemas_de
from gastroepi.dominio.lesao import Lesao
from gastroepi.dominio.listas import Displasia, Histologia, Paris, Segmento

ADENOMAS = [Histologia.TUBULAR, Histologia.TUBULOVILOSO, Histologia.VILOSO]
SERRILHADAS = [Histologia.SERRILHADA_SESSIL, Histologia.SERRILHADO_TRADICIONAL]
SEM_DISPLASIA = [Histologia.HIPERPLASICO, Histologia.AGUARDANDO, Histologia.SEM_HISTOLOGIA]


PADRAO: dict[str, object] = {
    "segmento": Segmento.SIGMOIDE,
    "tamanho_mm": 5,
    "paris": Paris.IS,
    "histologia": Histologia.TUBULAR,
    "displasia": Displasia.BAIXO,
}


def lesao(
    histologia: Histologia = Histologia.TUBULAR,
    displasia: Displasia = Displasia.BAIXO,
    tamanho_mm: int = 5,
    **campos: object,
) -> Lesao:
    escolhidos = {"histologia": histologia, "displasia": displasia, "tamanho_mm": tamanho_mm}
    return Lesao.model_validate(PADRAO | escolhidos | campos)


def problemas(**campos: object) -> tuple[Problema, ...]:
    with pytest.raises(ValidationError) as erro:
        Lesao.model_validate(PADRAO | campos)
    return problemas_de(erro.value)


@pytest.mark.parametrize("tamanho", [0, -3])
def test_tamanho_menor_que_1_mm_e_recusado(tamanho: int) -> None:
    assert problemas(tamanho_mm=tamanho)[0].codigo == "greater_than_equal"


def test_tamanho_true_e_recusado() -> None:
    assert problemas(tamanho_mm=True)[0].codigo == "int_type"


@pytest.mark.parametrize("histologia", ADENOMAS)
def test_adenoma_convencional_sem_grau_de_displasia_e_recusado(histologia: Histologia) -> None:
    assert problemas(histologia=histologia, displasia=Displasia.NAO_SE_APLICA) == (
        Problema(
            "displasia",
            "displasia_incoerente",
            "Displasia: adenoma convencional exige baixo ou alto grau",
        ),
    )


@pytest.mark.parametrize("histologia", SEM_DISPLASIA)
def test_lesao_sem_displasia_com_grau_e_recusada(histologia: Histologia) -> None:
    assert problemas(histologia=histologia, displasia=Displasia.BAIXO) == (
        Problema(
            "displasia",
            "displasia_incoerente",
            f"Displasia: {histologia.rotulo.lower()} exige 'não se aplica'",
        ),
    )


@pytest.mark.parametrize("histologia", [*SERRILHADAS, Histologia.ADENOCARCINOMA, Histologia.OUTRO])
@pytest.mark.parametrize("displasia", list(Displasia))
def test_serrilhada_adenocarcinoma_e_outra_aceitam_qualquer_grau(
    histologia: Histologia, displasia: Displasia
) -> None:
    extra: dict[str, object] = {}
    if histologia is Histologia.OUTRO:
        extra["histologia_outra"] = "Lipoma"
    assert lesao(histologia, displasia, 5, **extra).displasia is displasia


def test_histologia_outra_exige_a_descricao() -> None:
    assert problemas(histologia=Histologia.OUTRO, histologia_outra="  ") == (
        Problema(
            "histologia_outra", "campo_condicional", "Descreva a histologia quando for 'outra'"
        ),
    )


def test_descricao_de_histologia_sem_outra_e_recusada() -> None:
    assert problemas(histologia_outra="Lipoma") == (
        Problema(
            "histologia_outra",
            "campo_condicional",
            "Descrição da histologia só quando ela for 'outra'",
        ),
    )


@pytest.mark.parametrize("histologia", ADENOMAS)
def test_tubular_tubuloviloso_e_viloso_sao_adenoma_convencional(histologia: Histologia) -> None:
    assert lesao(histologia).adenoma_convencional


@pytest.mark.parametrize("histologia", [*SERRILHADAS, *SEM_DISPLASIA, Histologia.ADENOCARCINOMA])
def test_demais_histologias_nao_sao_adenoma_convencional(histologia: Histologia) -> None:
    displasia = Displasia.NAO_SE_APLICA
    assert not lesao(histologia, displasia).adenoma_convencional


@pytest.mark.parametrize(
    ("histologia", "displasia", "tamanho_mm", "avancado"),
    [
        (Histologia.TUBULAR, Displasia.BAIXO, 9, False),
        (Histologia.TUBULAR, Displasia.BAIXO, 10, True),
        (Histologia.TUBULAR, Displasia.ALTO, 3, True),
        (Histologia.TUBULOVILOSO, Displasia.BAIXO, 3, True),
        (Histologia.VILOSO, Displasia.BAIXO, 3, True),
        (Histologia.SERRILHADA_SESSIL, Displasia.ALTO, 15, False),
        (Histologia.ADENOCARCINOMA, Displasia.NAO_SE_APLICA, 25, False),
    ],
)
def test_adenoma_avancado_pela_definicao_da_usmstf_2020(
    histologia: Histologia, displasia: Displasia, tamanho_mm: int, avancado: bool
) -> None:
    """Gupta et al., Gastroenterology 2020;158:1131-1153. Serrilhada grande e carcinoma
    ficam fora: a definição é de adenoma convencional."""
    assert lesao(histologia, displasia, tamanho_mm).adenoma_avancado is avancado


@pytest.mark.parametrize("histologia", SERRILHADAS)
def test_ssl_e_tsa_sao_serrilhadas(histologia: Histologia) -> None:
    assert lesao(histologia).serrilhada


def test_hiperplasico_nao_e_serrilhada_pela_definicao_do_adr_0004() -> None:
    assert not lesao(Histologia.HIPERPLASICO, Displasia.NAO_SE_APLICA).serrilhada


def test_so_aguardando_deixa_a_lesao_pendente() -> None:
    assert lesao(Histologia.AGUARDANDO, Displasia.NAO_SE_APLICA).aguardando_histologia
    assert not lesao(Histologia.SEM_HISTOLOGIA, Displasia.NAO_SE_APLICA).aguardando_histologia


def test_repr_nao_mostra_texto_livre() -> None:
    texto = repr(lesao(laudo_texto="Paciente Fulano, laudo nº 123"))
    assert "Fulano" not in texto


@st.composite
def lesao_coerente(draw: st.DrawFn) -> Lesao:
    histologia = draw(st.sampled_from(Histologia))
    if histologia in ADENOMAS:
        displasia = draw(st.sampled_from([Displasia.BAIXO, Displasia.ALTO]))
    elif histologia in SEM_DISPLASIA:
        displasia = Displasia.NAO_SE_APLICA
    else:
        displasia = draw(st.sampled_from(Displasia))
    extra: dict[str, object] = {}
    if histologia is Histologia.OUTRO:
        extra["histologia_outra"] = "Lipoma"
    return lesao(histologia, displasia, draw(st.integers(1, 80)), **extra)


def classificacao(item: Lesao) -> tuple[bool, bool, bool]:
    return item.adenoma_convencional, item.adenoma_avancado, item.serrilhada


@given(lesao_coerente(), st.text(max_size=80))
def test_laudo_texto_nunca_muda_a_classificacao(base: Lesao, laudo: str) -> None:
    """ADR-0004: "ausência de adenoma" no texto não vira adenoma, nem o contrário."""
    texto = f"Ausência de adenoma. {laudo}"
    com_texto = Lesao.model_validate(base.model_dump() | {"laudo_texto": texto})
    assert classificacao(com_texto) == classificacao(base)


@given(lesao_coerente())
def test_avancado_implica_convencional_e_serrilhada_exclui_convencional(item: Lesao) -> None:
    assert not item.adenoma_avancado or item.adenoma_convencional
    assert not (item.serrilhada and item.adenoma_convencional)
