from datetime import date

import pytest

from gastroepi.dominio.exame import Boston, Exame, Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
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
from gastroepi.estatistica.qualidade import (
    LIMIARES,
    Indicador,
    elegivel_para_deteccao,
    indicadores_por_examinador,
)
from gastroepi.estatistica.variaveis import ExameDoPaciente
from tests.estatistica.referencias import aprox, fichas_do_oraculo, oraculo, referencias_r

ANA = Examinador(nome="Dra. Ana Fictícia", crm="123", uf=UF.SP)
BRUNO = Examinador(nome="Dr. Bruno Fictício", crm="456", uf=UF.MG)
EXAME_EM = date(2026, 6, 15)
WILSON_R = {(c["casos"], c["total"], c["alfa"]): c["ic"] for c in referencias_r()["wilson"]}


def _lesao(histologia: Histologia, mm: int = 5, laudo: str | None = None) -> Lesao:
    adenoma = histologia in {Histologia.TUBULAR, Histologia.TUBULOVILOSO, Histologia.VILOSO}
    return Lesao(
        segmento=Segmento.CECO,
        tamanho_mm=mm,
        paris=Paris.IS,
        histologia=histologia,
        displasia=Displasia.BAIXO if adenoma else Displasia.NAO_SE_APLICA,
        laudo_texto=laudo,
    )


def _ficha(
    *lesoes: Lesao,
    idade: int = 60,
    indicacao: Indicacao = Indicacao.RASTREIO_RISCO_MEDIO,
    examinador: Examinador = ANA,
    intubacao: bool = True,
    preparo: Boston | None = None,
    tempo: float | None = None,
) -> Ficha:
    paciente = Paciente(
        prontuario="F-1",
        nome="Paciente Fictício",
        sexo=Sexo.FEMININO,
        data_nascimento=EXAME_EM.replace(year=EXAME_EM.year - idade),
    )
    exame = Exame(
        data_exame=EXAME_EM,
        indicacao=indicacao,
        examinador=examinador,
        preparo=preparo,
        intubacao_cecal=intubacao,
        motivo_nao_intubacao=None if intubacao else MotivoNaoIntubacao.DIFICULDADE_TECNICA,
        tempo_retirada_min=tempo,
        lesoes=lesoes,
    )
    return Ficha(paciente=paciente, exames=(exame,))


def _sem_lesao(n: int) -> list[Ficha]:
    return [_ficha() for _ in range(n)]


@pytest.mark.referencia
def test_taxa_de_adenoma_tem_o_ic_de_wilson_do_r() -> None:
    """5 adenomas em 10 exames elegíveis; R 4.5.1: prop.test(5, 10, correct = FALSE)."""
    fichas = [_ficha(_lesao(Histologia.TUBULAR)) for _ in range(5)] + _sem_lesao(5)
    (ana,) = indicadores_por_examinador(fichas)
    assert (ana.deteccao_adenoma.casos, ana.deteccao_adenoma.total) == (5, 10)
    assert ana.deteccao_adenoma.ic == aprox(WILSON_R[(5, 10, 0.05)])
    assert ana.deteccao_polipo.ic == aprox(WILSON_R[(5, 10, 0.05)])
    assert Indicador.DETECCAO_ADENOMA not in {a.indicador for a in ana.alertas}


@pytest.mark.referencia
def test_denominador_da_taxa_de_adenoma_e_o_da_acg_asge_2024() -> None:
    """Rex DK et al., Am J Gastroenterol 2024;119:1754-80: ≥ 45 anos, rastreio, vigilância
    ou diagnóstica; FIT positivo, DII (e "outra") fora. Emenda do ADR-0004 em 2026-10-31."""
    entram = [
        Indicacao.RASTREIO_RISCO_MEDIO,
        Indicacao.RASTREIO_RISCO_AUMENTADO,
        Indicacao.VIGILANCIA_POS_POLIPECTOMIA,
        Indicacao.DIAGNOSTICA_POR_SINTOMAS,
    ]
    fora = [Indicacao.SANGUE_OCULTO_POSITIVO, Indicacao.SEGUIMENTO_DII]
    fichas = [_ficha(_lesao(Histologia.TUBULAR), indicacao=i) for i in entram + fora]
    fichas.append(_ficha(_lesao(Histologia.TUBULAR), idade=44))
    (ana,) = indicadores_por_examinador(fichas)
    assert (ana.deteccao_adenoma.casos, ana.deteccao_adenoma.total) == (4, 4)
    assert ana.n_exames == 7
    registro = ExameDoPaciente(fichas[-1].paciente, fichas[-1].exames[0])
    assert not elegivel_para_deteccao(registro)


def test_exame_aguardando_histologia_fica_fora_ate_o_laudo() -> None:
    """Escolha do dono (2026-10-31): o pendente não conta como "sem adenoma"."""
    fichas = [_ficha(_lesao(Histologia.AGUARDANDO)), _ficha(_lesao(Histologia.TUBULAR))]
    (ana,) = indicadores_por_examinador(fichas)
    assert ana.aguardando_histologia == 1
    assert (ana.deteccao_adenoma.casos, ana.deteccao_adenoma.total) == (1, 1)
    assert (ana.deteccao_polipo.casos, ana.deteccao_polipo.total) == (2, 2)


def test_ausencia_de_adenoma_no_laudo_nao_vira_adenoma() -> None:
    """ADR-0004, Governança: o texto da v0.1.16 no laudo_texto não muda nenhum indicador."""
    texto = "Mucosa colônica sem alterações; ausência de adenoma"
    com_texto = indicadores_por_examinador([_ficha(_lesao(Histologia.HIPERPLASICO, laudo=texto))])
    sem_texto = indicadores_por_examinador([_ficha(_lesao(Histologia.HIPERPLASICO))])
    assert com_texto == sem_texto
    assert com_texto[0].deteccao_adenoma.casos == 0


def test_oraculo_diverge_de_proposito_nos_indicadores() -> None:
    """ADR-0004: a v0.1.16 dava à Dra. Ana 0 pólipos e 2 adenomas (texto do laudo, todos os
    exames no denominador). No domínio, adenoma é lesão: nunca há mais exames com adenoma
    que com pólipo, e o pólipo 0 com laudo some (não há lesão onde pôr a histologia)."""
    antiga = {i["examinador"]: i for i in oraculo()["indicadores_por_examinador"][0]["saida"]}
    assert (antiga["Dra. Ana"]["n_polipos"], antiga["Dra. Ana"]["n_adenomas"]) == (0, 2)
    for indicadores in indicadores_por_examinador(fichas_do_oraculo()):
        assert indicadores.deteccao_adenoma.casos <= indicadores.deteccao_polipo.casos
        if indicadores.examinador.nome == "Dra. Ana":
            assert indicadores.deteccao_adenoma.casos == indicadores.deteccao_polipo.casos == 0


@pytest.mark.referencia
def test_alerta_so_e_confirmado_quando_o_ic_inteiro_fica_abaixo_da_meta() -> None:
    """ACG/ASGE 2024: meta de adenoma 35%. R: prop.test(0, 10) vai até 0,2775 (< 0,35,
    confirmado); 1 em 3 (33%) fica abaixo da meta, mas o IC chega a 0,79."""
    (zero_em_dez,) = indicadores_por_examinador(_sem_lesao(10))
    alerta = next(a for a in zero_em_dez.alertas if a.indicador is Indicador.DETECCAO_ADENOMA)
    assert alerta.limiar == LIMIARES[Indicador.DETECCAO_ADENOMA] == 0.35
    assert alerta.ic_abaixo
    assert zero_em_dez.deteccao_adenoma.ic == aprox(WILSON_R[(0, 10, 0.05)])
    poucos = indicadores_por_examinador([_ficha(_lesao(Histologia.TUBULAR)), *_sem_lesao(2)])
    alerta = next(a for a in poucos[0].alertas if a.indicador is Indicador.DETECCAO_ADENOMA)
    assert not alerta.ic_abaixo


@pytest.mark.referencia
def test_serrilhada_conta_so_a_sessil_contra_a_meta_de_6_porcento() -> None:
    """ACG/ASGE 2024: SSLDR ≥ 6%. 1 séssil em 100; R: prop.test(1, 100) → até 0,0545."""
    fichas = [_ficha(_lesao(Histologia.SERRILHADA_SESSIL))]
    fichas += [_ficha(_lesao(Histologia.SERRILHADO_TRADICIONAL)), *_sem_lesao(98)]
    (ana,) = indicadores_por_examinador(fichas)
    assert ana.serrilhada_sessil.ic == aprox(WILSON_R[(1, 100, 0.05)])
    alerta = next(a for a in ana.alertas if a.indicador is Indicador.SERRILHADA_SESSIL)
    assert alerta.ic_abaixo


def test_adenoma_avancado_e_adenomas_por_exame() -> None:
    """Avançado (USMSTF 2020): ≥ 10 mm, viloso ou alto grau. 3 adenomas em 2 exames."""
    fichas = [
        _ficha(_lesao(Histologia.TUBULAR, mm=12), _lesao(Histologia.TUBULAR)),
        _ficha(_lesao(Histologia.TUBULAR)),
    ]
    (ana,) = indicadores_por_examinador(fichas)
    assert ana.adenoma_avancado.casos == 1
    assert ana.adenomas_por_exame.n == 2
    assert ana.adenomas_por_exame.media == pytest.approx(1.5)


def test_qualidade_do_procedimento_usa_todos_os_exames() -> None:
    """Intubação cecal (≥ 95%) e preparo (≥ 90%) sobre todos os exames do examinador;
    retirada (≥ 8 min) é a média dos exames sem lesão com o tempo registrado."""
    bom, ruim = (
        Boston(direito=3, transverso=3, esquerdo=3),
        Boston(direito=1, transverso=2, esquerdo=2),
    )
    fichas = [
        _ficha(
            idade=30, indicacao=Indicacao.SEGUIMENTO_DII, intubacao=False, preparo=ruim, tempo=6.0
        ),
        _ficha(preparo=bom, tempo=7.0),
        _ficha(_lesao(Histologia.HIPERPLASICO), tempo=20.0),
    ]
    (ana,) = indicadores_por_examinador(fichas)
    assert (ana.intubacao_cecal.casos, ana.intubacao_cecal.total) == (2, 3)
    assert (ana.preparo_adequado.casos, ana.preparo_adequado.total) == (1, 2)
    assert ana.tempo_retirada.media == pytest.approx(6.5)
    disparados = {a.indicador for a in ana.alertas}
    assert {
        Indicador.INTUBACAO_CECAL,
        Indicador.PREPARO_ADEQUADO,
        Indicador.TEMPO_RETIRADA,
    } <= disparados


def test_examinador_sem_exame_elegivel_nao_tem_taxa_nem_alerta() -> None:
    (ana,) = indicadores_por_examinador([_ficha(idade=30)])
    assert ana.deteccao_adenoma.estimativa is None
    assert ana.deteccao_adenoma.ic == (0.0, 1.0)
    assert ana.tempo_retirada.media is None
    assert Indicador.DETECCAO_ADENOMA not in {a.indicador for a in ana.alertas}


def test_um_item_por_crm_em_ordem_de_nome() -> None:
    fichas = [_ficha(examinador=ANA), _ficha(examinador=BRUNO), _ficha(examinador=ANA)]
    resultado = indicadores_por_examinador(fichas)
    assert [(i.examinador, i.n_exames) for i in resultado] == [(BRUNO, 1), (ANA, 2)]


def test_base_ficticia_de_300_pacientes_roda_sem_travar() -> None:
    resultado = indicadores_por_examinador(gerar_fichas(11, 300))
    assert len(resultado) == 4
    assert sum(i.n_exames for i in resultado) == sum(len(f.exames) for f in gerar_fichas(11, 300))
