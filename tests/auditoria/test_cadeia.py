"""Cadeia HMAC-SHA256 v2: cada elo depende da chave, do elo anterior e do evento."""

import dataclasses
import re

import pytest

from gastroepi.auditoria.cadeia import (
    ELO_INICIAL,
    EntradaDeAuditoria,
    Evento,
    QuebraDaCadeia,
    calcular_elo,
    verificar_cadeia,
)

CHAVE = b"k" * 32


def evento(numero: int) -> Evento:
    return Evento(
        momento=f"2026-10-31T12:00:{numero:02d}.000+00:00",
        usuario="teste",
        acao="cadastrar",
        entidade="paciente",
        entidade_id=numero,
        antes=None,
        depois=f'{{"nome": "Paciente {numero}"}}',
    )


def encadear(eventos: list[Evento], chave: bytes = CHAVE) -> list[EntradaDeAuditoria]:
    entradas, anterior = [], ELO_INICIAL
    for numero, ev in enumerate(eventos, start=1):
        anterior = calcular_elo(chave, anterior, ev)
        entradas.append(EntradaDeAuditoria(id=numero, evento=ev, elo=anterior))
    return entradas


def test_elo_e_v2_com_64_digitos_hexadecimais() -> None:
    assert re.fullmatch(r"v2:[0-9a-f]{64}", calcular_elo(CHAVE, ELO_INICIAL, evento(1)))


def test_elo_e_deterministico() -> None:
    assert calcular_elo(CHAVE, ELO_INICIAL, evento(1)) == calcular_elo(
        CHAVE, ELO_INICIAL, evento(1)
    )


ALTERACOES = {
    "momento": dataclasses.replace(evento(1), momento="2026-10-31T12:00:01.001+00:00"),
    "usuario": dataclasses.replace(evento(1), usuario="outro"),
    "acao": dataclasses.replace(evento(1), acao="editar"),
    "entidade": dataclasses.replace(evento(1), entidade="sintoma"),
    "entidade_id": dataclasses.replace(evento(1), entidade_id=2),
    "antes": dataclasses.replace(evento(1), antes="{}"),
    "depois": dataclasses.replace(evento(1), depois='{"nome": "X"}'),
}


@pytest.mark.parametrize("campo", sorted(ALTERACOES))
def test_mudar_qualquer_campo_do_evento_muda_o_elo(campo: str) -> None:
    alterado = ALTERACOES[campo]

    assert calcular_elo(CHAVE, ELO_INICIAL, alterado) != calcular_elo(CHAVE, ELO_INICIAL, evento(1))


def test_outra_chave_ou_outro_elo_anterior_muda_o_elo() -> None:
    original = calcular_elo(CHAVE, ELO_INICIAL, evento(1))

    assert calcular_elo(b"j" * 32, ELO_INICIAL, evento(1)) != original
    assert calcular_elo(CHAVE, original, evento(1)) != original


def test_separador_dentro_do_texto_nao_forja_outro_evento() -> None:
    """Na v0.1.16 as partes eram unidas por NUL: ("a\\0b", "c") e ("a", "b\\0c") colidiam."""
    um = dataclasses.replace(evento(1), usuario="a\x00b", acao="c")
    outro = dataclasses.replace(evento(1), usuario="a", acao="b\x00c")

    assert calcular_elo(CHAVE, ELO_INICIAL, um) != calcular_elo(CHAVE, ELO_INICIAL, outro)


def test_repr_do_evento_nao_mostra_os_snapshots() -> None:
    assert "Paciente 1" not in repr(evento(1))
    assert "Paciente 1" not in repr(encadear([evento(1)])[0])


def test_cadeia_intacta_nao_tem_quebra() -> None:
    assert verificar_cadeia(CHAVE, encadear([evento(n) for n in range(1, 6)])) is None


def test_cadeia_vazia_nao_tem_quebra() -> None:
    assert verificar_cadeia(CHAVE, []) is None


def test_snapshot_alterado_aponta_id_e_momento_da_primeira_entrada_quebrada() -> None:
    entradas = encadear([evento(n) for n in range(1, 6)])
    terceira = entradas[2]
    entradas[2] = dataclasses.replace(
        terceira, evento=dataclasses.replace(terceira.evento, depois='{"nome": "Forjado"}')
    )

    assert verificar_cadeia(CHAVE, entradas) == QuebraDaCadeia(3, terceira.evento.momento)


def test_entrada_apagada_quebra_a_seguinte() -> None:
    entradas = encadear([evento(n) for n in range(1, 6)])
    del entradas[1]

    assert verificar_cadeia(CHAVE, entradas) == QuebraDaCadeia(3, entradas[1].evento.momento)


def test_cadeia_feita_com_outra_chave_quebra_na_primeira() -> None:
    entradas = encadear([evento(1), evento(2)], chave=b"j" * 32)

    assert verificar_cadeia(CHAVE, entradas) == QuebraDaCadeia(1, entradas[0].evento.momento)


def test_elo_sem_prefixo_v2_quebra_a_cadeia() -> None:
    """Sem caminho legado: o SHA-256 puro da v0.1.16 não é aceito."""
    entradas = encadear([evento(1)])
    entradas[0] = dataclasses.replace(entradas[0], elo=entradas[0].elo.removeprefix("v2:"))

    assert verificar_cadeia(CHAVE, entradas) == QuebraDaCadeia(1, entradas[0].evento.momento)
