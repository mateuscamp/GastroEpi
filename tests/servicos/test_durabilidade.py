"""Backup conferido e rotacionado, backup automático e instância única (ADR-0005)."""

from datetime import timedelta
from pathlib import Path

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import durabilidade, integridade, pacientes
from gastroepi.servicos.acesso import NOME_DA_CHAVE, NOME_DO_BANCO, Sessao, criar_cofre, desbloquear
from gastroepi.servicos.durabilidade import (
    INTERVALO_DO_BACKUP,
    BackupAutomatico,
    OutraInstanciaAberta,
)
from tests.conftest import RelogioManual

SENHA = "frase longa de teste"
FICHAS = gerar_fichas(semente=11, quantidade=6)


def cofre(pasta: Path, relogio: RelogioManual) -> Sessao:
    sessao, _ = criar_cofre(pasta, SENHA, SENHA, relogio)
    return sessao


def test_backup_leva_o_banco_e_o_arquivo_de_chave_e_abre_com_a_mesma_senha(
    tmp_path: Path,
) -> None:
    with cofre(tmp_path, RelogioManual()) as sessao:
        pacientes.cadastrar(sessao, FICHAS[0], "teste")
        backup = durabilidade.fazer_backup(sessao)
        originais = pacientes.listar(sessao)

    assert {p.name for p in backup.pasta.iterdir()} == {NOME_DO_BANCO, NOME_DA_CHAVE}
    with desbloquear(backup.pasta, SENHA) as copia:
        assert pacientes.listar(copia) == originais
        assert integridade.verificar(copia).ok


def test_backup_rotaciona_depois_de_copiar(tmp_path: Path) -> None:
    relogio = RelogioManual()
    with cofre(tmp_path, relogio) as sessao:
        pacientes.cadastrar(sessao, FICHAS[0], "teste")
        for _ in range(5):
            ultimo = durabilidade.fazer_backup(sessao)
            relogio.avancar(timedelta(minutes=15))

        assert durabilidade.backups_do_cofre(sessao) == [ultimo]


def test_sem_alteracao_nao_copia_nem_depois_de_15_min(tmp_path: Path) -> None:
    relogio = RelogioManual()
    with cofre(tmp_path, relogio) as sessao:
        automatico = BackupAutomatico(sessao, relogio)
        relogio.avancar(INTERVALO_DO_BACKUP * 3)

        assert automatico.tique() is None
        assert automatico.ao_fechar() is None
        assert durabilidade.backups_do_cofre(sessao) == []


def test_com_alteracao_copia_so_depois_de_15_min(tmp_path: Path) -> None:
    relogio = RelogioManual()
    with cofre(tmp_path, relogio) as sessao:
        automatico = BackupAutomatico(sessao, relogio)
        pacientes.cadastrar(sessao, FICHAS[0], "teste")
        relogio.avancar(INTERVALO_DO_BACKUP - timedelta(seconds=1))
        assert automatico.tique() is None

        relogio.avancar(timedelta(seconds=1))
        backup = automatico.tique()

        assert backup is not None
        assert durabilidade.backups_do_cofre(sessao) == [backup]
        relogio.avancar(INTERVALO_DO_BACKUP)
        assert automatico.tique() is None  # nada mudou desde a cópia


def test_a_janela_de_15_min_conta_da_ultima_copia(tmp_path: Path) -> None:
    relogio = RelogioManual()
    with cofre(tmp_path, relogio) as sessao:
        automatico = BackupAutomatico(sessao, relogio)
        pacientes.cadastrar(sessao, FICHAS[0], "teste")
        relogio.avancar(INTERVALO_DO_BACKUP)
        assert automatico.tique() is not None

        pacientes.cadastrar(sessao, FICHAS[1], "teste")
        relogio.avancar(INTERVALO_DO_BACKUP / 2)
        assert automatico.tique() is None
        relogio.avancar(INTERVALO_DO_BACKUP / 2)
        assert automatico.tique() is not None


def test_fechar_copia_se_houve_alteracao(tmp_path: Path) -> None:
    relogio = RelogioManual()
    with cofre(tmp_path, relogio) as sessao:
        automatico = BackupAutomatico(sessao, relogio)
        pacientes.cadastrar(sessao, FICHAS[0], "teste")

        backup = automatico.ao_fechar()

    assert backup is not None
    with desbloquear(backup.pasta, SENHA) as copia:
        assert list(pacientes.listar(copia).values()) == [FICHAS[0]]


def test_somente_leitura_nunca_copia(tmp_path: Path) -> None:
    relogio = RelogioManual()
    with cofre(tmp_path, relogio) as sessao:
        for ficha in FICHAS:
            pacientes.cadastrar(sessao, ficha, "teste")
        durabilidade.fazer_backup(sessao)
    banco = tmp_path / NOME_DO_BANCO
    bruto = bytearray(banco.read_bytes())
    bruto[len(bruto) // 2 + 1000] ^= 0xFF
    banco.write_bytes(bytes(bruto))

    with desbloquear(tmp_path, SENHA, relogio) as aberta:
        automatico = BackupAutomatico(aberta, relogio)
        automatico._marca_copiada = -1  # força "houve alteração"
        relogio.avancar(INTERVALO_DO_BACKUP)

        assert aberta.somente_leitura
        assert automatico.tique() is None
        assert automatico.ao_fechar() is None
        with pytest.raises(durabilidade.BancoSomenteLeitura):
            durabilidade.fazer_backup(aberta)
        assert len(durabilidade.backups_do_cofre(aberta)) == 1


def test_segunda_instancia_no_mesmo_cofre_e_recusada(tmp_path: Path) -> None:
    with durabilidade.travar_instancia(tmp_path / "novo"), pytest.raises(OutraInstanciaAberta):
        durabilidade.travar_instancia(tmp_path / "novo")
    with durabilidade.travar_instancia(tmp_path / "novo"):
        pass
