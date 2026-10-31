"""Backups: cópia conferida antes do nome final, listagem, oferta e restauração (ADR-0005)."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.backups import (
    NOME_DA_CHAVE,
    NOME_DO_BANCO,
    Backup,
    CopiaReprovada,
    gravar_backup,
    listar_backups,
    nome_do_backup,
    primeiro_backup_valido,
    restaurar,
    rotacionar,
)
from gastroepi.persistencia.conexao import copia_integra
from gastroepi.persistencia.repositorio import Repositorio

MOMENTO = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
OUTRA_CHAVE = bytes(range(1, 33))


@pytest.fixture
def cofre(tmp_path: Path, chave_de_dados: bytes) -> Path:
    """Pasta com um banco de 20 fictícios e um arquivo de chave de mentira."""
    pasta = tmp_path / "cofre"
    pasta.mkdir()
    with Repositorio.abrir(pasta / NOME_DO_BANCO, chave_de_dados) as repositorio:
        for ficha in gerar_fichas(semente=4, quantidade=20):
            repositorio.cadastrar(ficha, usuario="teste")
    (pasta / NOME_DA_CHAVE).write_text('{"formato": "teste"}')
    return pasta


def backup_de(cofre: Path, chave: bytes, momento: datetime = MOMENTO) -> Backup:
    with Repositorio.abrir(cofre / NOME_DO_BANCO, chave) as repositorio:
        return repositorio.fazer_backup(cofre / "backups", cofre / NOME_DA_CHAVE, momento)


def corromper_o_meio(banco: Path) -> None:
    bruto = bytearray(banco.read_bytes())
    bruto[len(bruto) // 2 + 1000] ^= 0xFF
    banco.write_bytes(bytes(bruto))


def test_backup_e_um_arquivo_so_conferido_e_com_o_arquivo_de_chave(
    cofre: Path, chave_de_dados: bytes
) -> None:
    backup = backup_de(cofre, chave_de_dados)

    assert backup == Backup(cofre / "backups" / "gastroepi-2026-10-31-120000", MOMENTO)
    assert sorted(p.name for p in backup.pasta.iterdir()) == [NOME_DA_CHAVE, NOME_DO_BANCO]
    assert (backup.pasta / NOME_DA_CHAVE).read_text() == '{"formato": "teste"}'
    assert copia_integra(backup.banco, chave_de_dados)


def test_conferir_nao_muda_um_byte_da_copia(cofre: Path, chave_de_dados: bytes) -> None:
    backup = backup_de(cofre, chave_de_dados)
    antes = backup.banco.read_bytes()

    assert copia_integra(backup.banco, chave_de_dados)
    assert backup.banco.read_bytes() == antes
    assert sorted(p.name for p in backup.pasta.iterdir()) == [NOME_DA_CHAVE, NOME_DO_BANCO]


def test_copia_reprovada_nao_ganha_nome_e_nao_toca_nas_antigas(
    cofre: Path, chave_de_dados: bytes
) -> None:
    antiga = backup_de(cofre, chave_de_dados)

    def copia_estragada(destino: Path) -> None:
        destino.write_bytes(os.urandom(8192))

    with pytest.raises(CopiaReprovada):
        gravar_backup(
            copia_estragada,
            cofre / NOME_DA_CHAVE,
            chave_de_dados,
            cofre / "backups",
            MOMENTO + timedelta(days=1),
        )

    assert [p.name for p in (cofre / "backups").iterdir()] == [antiga.pasta.name]
    assert copia_integra(antiga.banco, chave_de_dados)


def test_temporario_de_uma_queda_e_apagado_no_backup_seguinte(
    cofre: Path, chave_de_dados: bytes
) -> None:
    sobra = cofre / "backups" / ".temp-gastroepi-2026-10-30-120000"
    sobra.mkdir(parents=True)
    (sobra / NOME_DO_BANCO).write_bytes(b"pela metade")

    backup_de(cofre, chave_de_dados)

    assert not sobra.exists()
    assert listar_backups(cofre / "backups") == [
        Backup(cofre / "backups" / "gastroepi-2026-10-31-120000", MOMENTO)
    ]


def test_dois_backups_no_mesmo_segundo_ganham_nomes_diferentes(
    cofre: Path, chave_de_dados: bytes
) -> None:
    primeiro = backup_de(cofre, chave_de_dados)
    segundo = backup_de(cofre, chave_de_dados)

    assert primeiro.pasta.name == "gastroepi-2026-10-31-120000"
    assert segundo.pasta.name == "gastroepi-2026-10-31-120000-2"
    assert listar_backups(cofre / "backups") == [segundo, primeiro]


def test_listar_ignora_o_que_nao_e_backup_e_ordena_do_mais_novo(tmp_path: Path) -> None:
    for nome in ("gastroepi-2026-10-01-080000", "gastroepi-2026-10-02-080000", "fotos"):
        (tmp_path / nome).mkdir()
    (tmp_path / "gastroepi-2026-10-03-080000").write_text("arquivo, não pasta")

    assert [b.pasta.name for b in listar_backups(tmp_path)] == [
        "gastroepi-2026-10-02-080000",
        "gastroepi-2026-10-01-080000",
    ]
    assert listar_backups(tmp_path / "nao-existe") == []


def test_nome_do_backup_e_o_momento_em_utc() -> None:
    brasilia = datetime(2026, 10, 31, 22, 30, tzinfo=UTC) - timedelta(hours=3)
    assert nome_do_backup(brasilia.astimezone(UTC)) == "gastroepi-2026-10-31-193000"


def test_oferta_pula_o_backup_corrompido_e_o_de_outra_chave(
    cofre: Path, chave_de_dados: bytes
) -> None:
    bom = backup_de(cofre, chave_de_dados, MOMENTO)
    estragado = backup_de(cofre, chave_de_dados, MOMENTO + timedelta(days=1))
    corromper_o_meio(estragado.banco)
    outra = cofre / "backups" / "gastroepi-2026-11-05-120000"
    outra.mkdir()
    with Repositorio.abrir(outra / NOME_DO_BANCO, OUTRA_CHAVE):
        pass

    backups = listar_backups(cofre / "backups")

    assert backups[0].pasta == outra
    assert primeiro_backup_valido(backups, chave_de_dados) == bom
    assert primeiro_backup_valido([], chave_de_dados) is None


def test_restaurar_guarda_o_estragado_e_tira_o_wal_do_caminho(
    cofre: Path, chave_de_dados: bytes
) -> None:
    backup = backup_de(cofre, chave_de_dados)
    banco = cofre / NOME_DO_BANCO
    corromper_o_meio(banco)
    estragado = banco.read_bytes()
    (cofre / f"{NOME_DO_BANCO}-wal").write_bytes(b"wal velho")

    restaurar(backup, banco, chave_de_dados, MOMENTO + timedelta(hours=1))

    sufixo = "corrompido-2026-10-31-130000"
    assert (cofre / f"{NOME_DO_BANCO}.{sufixo}").read_bytes() == estragado
    assert (cofre / f"{NOME_DO_BANCO}-wal.{sufixo}").read_bytes() == b"wal velho"
    assert not (cofre / f"{NOME_DO_BANCO}-wal").exists()
    assert copia_integra(banco, chave_de_dados)


def test_restaurar_um_backup_estragado_nao_mexe_no_banco(
    cofre: Path, chave_de_dados: bytes
) -> None:
    backup = backup_de(cofre, chave_de_dados)
    corromper_o_meio(backup.banco)
    banco = cofre / NOME_DO_BANCO
    antes = banco.read_bytes()

    with pytest.raises(CopiaReprovada):
        restaurar(backup, banco, chave_de_dados, MOMENTO)

    assert banco.read_bytes() == antes
    assert sorted(p.name for p in cofre.iterdir()) == ["backups", NOME_DA_CHAVE, NOME_DO_BANCO]


def test_restaurar_sem_link_copia_o_estragado(
    cofre: Path, chave_de_dados: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FAT32 não tem link: o estragado é copiado, e fica do mesmo jeito."""
    backup = backup_de(cofre, chave_de_dados)
    banco = cofre / NOME_DO_BANCO
    antes = banco.read_bytes()

    def sem_link(origem: Path, destino: Path) -> None:
        raise OSError("sem link")

    monkeypatch.setattr(os, "link", sem_link)
    restaurar(backup, banco, chave_de_dados, MOMENTO)

    assert (cofre / f"{NOME_DO_BANCO}.corrompido-2026-10-31-120000").read_bytes() == antes


def test_rotacionar_apaga_so_o_que_a_rotacao_nao_guarda(cofre: Path, chave_de_dados: bytes) -> None:
    do_dia = [backup_de(cofre, chave_de_dados, MOMENTO + timedelta(hours=h)) for h in range(3)]

    apagados = rotacionar(cofre / "backups")

    assert apagados == [do_dia[1], do_dia[0]]
    assert listar_backups(cofre / "backups") == [do_dia[2]]
