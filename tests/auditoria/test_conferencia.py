"""Verificação dos dados: o estado atual de cada registro contra o seu último snapshot."""

from gastroepi.auditoria.cadeia import EntradaDeAuditoria, Evento
from gastroepi.auditoria.conferencia import (
    Divergencia,
    Motivo,
    RelatorioDeIntegridade,
    conferir_dados,
)

_ids = iter(range(1, 1000))


def entrada(
    acao: str, entidade_id: int, antes: str | None, depois: str | None
) -> EntradaDeAuditoria:
    numero = next(_ids)
    ev = Evento(f"2026-10-31T12:{numero:02d}:00.000+00:00", "teste", acao, "paciente", entidade_id,
                antes, depois)  # fmt: skip
    return EntradaDeAuditoria(id=numero, evento=ev, elo="v2:" + "0" * 64)


def divergencia(e: EntradaDeAuditoria, motivo: Motivo) -> Divergencia:
    return Divergencia("paciente", e.evento.entidade_id, motivo, e.id, e.evento.momento)


def test_estado_igual_ao_ultimo_snapshot_nao_diverge() -> None:
    entradas = [entrada("cadastrar", 1, None, "a"), entrada("editar", 1, "a", "b")]

    assert conferir_dados(entradas, {("paciente", 1): "b"}) == ()


def test_estado_igual_a_um_snapshot_antigo_diverge_do_ultimo() -> None:
    editar = entrada("editar", 1, "a", "b")
    entradas = [entrada("cadastrar", 1, None, "a"), editar]

    assert conferir_dados(entradas, {("paciente", 1): "a"}) == (
        divergencia(editar, Motivo.ALTERADO),
    )


def test_registro_ilegivel_diverge_como_alterado() -> None:
    cadastro = entrada("cadastrar", 1, None, "a")

    assert conferir_dados([cadastro], {("paciente", 1): None}) == (
        divergencia(cadastro, Motivo.ALTERADO),
    )


def test_registro_sem_evento_diverge_sem_entrada() -> None:
    assert conferir_dados([], {("paciente", 7): "x"}) == (
        Divergencia("paciente", 7, Motivo.SEM_EVENTO, None, None),
    )


def test_registro_auditado_que_sumiu_diverge_como_ausente() -> None:
    cadastro = entrada("cadastrar", 1, None, "a")

    assert conferir_dados([cadastro], {}) == (divergencia(cadastro, Motivo.AUSENTE),)


def test_exclusao_auditada_com_registro_ausente_nao_diverge() -> None:
    entradas = [entrada("cadastrar", 1, None, "a"), entrada("excluir", 1, "a", None)]

    assert conferir_dados(entradas, {}) == ()


def test_registro_presente_apesar_da_exclusao_auditada_diverge() -> None:
    excluir = entrada("excluir", 1, "a", None)
    entradas = [entrada("cadastrar", 1, None, "a"), excluir]

    assert conferir_dados(entradas, {("paciente", 1): "a"}) == (
        divergencia(excluir, Motivo.EXCLUIDO_PRESENTE),
    )


def test_divergencias_saem_em_ordem_de_entidade_e_id() -> None:
    entradas = [entrada("cadastrar", 9, None, "a"), entrada("cadastrar", 2, None, "b")]

    resultado = conferir_dados(entradas, {("comorbidade", 5): "c"})

    assert [(d.entidade, d.entidade_id) for d in resultado] == [
        ("comorbidade", 5), ("paciente", 2), ("paciente", 9),
    ]  # fmt: skip


def test_relatorio_ok_so_sem_quebra_e_sem_divergencia() -> None:
    assert RelatorioDeIntegridade(cadeia=None, dados=()).ok
    assert not RelatorioDeIntegridade(
        cadeia=None, dados=conferir_dados([], {("paciente", 1): "x"})
    ).ok


def test_antes_diferente_do_depois_anterior_aponta_a_entrada_que_interrompe() -> None:
    """Alteração por fora seguida de edição pelo app: o estado atual confere com a última
    entrada, mas o 'antes' dela não é o 'depois' da anterior."""
    edicao = entrada("editar", 1, "a-alterado-por-fora", "b")
    entradas = [entrada("cadastrar", 1, None, "a"), edicao, entrada("editar", 1, "b", "c")]

    assert conferir_dados(entradas, {("paciente", 1): "c"}) == (
        divergencia(edicao, Motivo.HISTORICO_INTERROMPIDO),
    )
