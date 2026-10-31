"""Relógio do sistema: o momento da auditoria é sempre em UTC."""

from datetime import UTC, timedelta

from gastroepi.persistencia.relogio import RelogioDoSistema


def test_relogio_do_sistema_devolve_instante_em_utc() -> None:
    agora = RelogioDoSistema().agora()

    assert agora.tzinfo is UTC
    assert agora.utcoffset() == timedelta(0)
