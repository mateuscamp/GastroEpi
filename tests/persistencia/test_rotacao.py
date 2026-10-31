"""Rotação por data (ADR-0005, item 5): 7 diários, 4 semanais e 12 mensais."""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from gastroepi.persistencia.rotacao import DIARIOS, MENSAIS, SEMANAIS, a_manter

INICIO = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def manter(momentos: list[datetime]) -> list[datetime]:
    return a_manter(momentos, lambda m: m)


def test_vinte_copias_num_dia_ocupam_so_a_vaga_daquele_dia() -> None:
    """O defeito da v0.1.16: 5 aberturas num dia apagavam todo o histórico."""
    ontem = [INICIO - timedelta(days=d) for d in range(1, 4)]
    hoje = [INICIO + timedelta(minutes=15 * i) for i in range(20)]

    mantidos = manter(ontem + hoje)

    assert mantidos == [hoje[-1], *ontem]


def test_um_ano_de_copias_diarias_guarda_7_dias_4_semanas_e_12_meses() -> None:
    diarios = [INICIO - timedelta(days=d) for d in range(400)]

    mantidos = manter(diarios)

    assert mantidos[:DIARIOS] == diarios[:DIARIOS]
    semanas = {m.isocalendar()[:2] for m in mantidos}
    meses = {(m.year, m.month) for m in mantidos}
    assert len(semanas) >= SEMANAIS
    assert len(meses) == MENSAIS
    assert len(mantidos) <= DIARIOS + SEMANAIS + MENSAIS


def test_um_mes_sem_abrir_o_app_nao_apaga_as_copias_antigas() -> None:
    antigas = [INICIO - timedelta(days=60 + d) for d in range(5)]

    assert manter(antigas) == antigas


def test_sem_copias_nao_ha_o_que_manter() -> None:
    assert manter([]) == []


momentos = st.lists(
    st.datetimes(
        min_value=datetime(2024, 1, 1), max_value=datetime(2026, 12, 31), timezones=st.just(UTC)
    ),
    max_size=80,
)


@given(momentos)
def test_cada_periodo_recente_guarda_a_sua_copia_mais_nova(lista: list[datetime]) -> None:
    mantidos = set(manter(lista))
    periodos = (
        (lambda m: m.date(), DIARIOS),
        (lambda m: m.isocalendar()[:2], SEMANAIS),
        (lambda m: (m.year, m.month), MENSAIS),
    )
    for periodo, quantos in periodos:
        mais_novo_de: dict[object, datetime] = {}
        for momento in lista:
            chave = periodo(momento)
            mais_novo_de[chave] = max(momento, mais_novo_de.get(chave, momento))
        recentes = sorted(mais_novo_de.values(), reverse=True)[:quantos]
        assert set(recentes) <= mantidos
    assert len(mantidos) <= 1 + DIARIOS + SEMANAIS + MENSAIS
    assert not lista or max(lista) in mantidos


@given(momentos)
def test_nada_e_mantido_se_nao_for_a_mais_nova_do_seu_dia(lista: list[datetime]) -> None:
    for momento in manter(lista):
        assert momento == max(m for m in lista if m.date() == momento.date())
