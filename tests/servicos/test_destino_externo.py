"""Destino externo opcional: pendrive ou pasta do Drive (ADR-0005, itens 9 e 10)."""

from datetime import timedelta
from pathlib import Path

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import destino_externo, durabilidade, integridade, pacientes
from gastroepi.servicos.acesso import (
    NOME_DA_CHAVE,
    NOME_DO_BANCO,
    SenhaIncorreta,
    Sessao,
    criar_cofre,
    desbloquear,
)
from gastroepi.servicos.destino_externo import (
    LIMITE_DE_ATRASO,
    PASTA_NO_DESTINO,
    DestinoAusente,
    DestinoDentroDoCofre,
    SemBackupLocal,
    SenhaFracaParaNuvem,
)
from gastroepi.servicos.durabilidade import INTERVALO_DO_BACKUP, BackupAutomatico
from tests.conftest import RelogioManual

FRASE = "cavalo bateria grampo correto"
CURTA = "senha123"
FICHAS = gerar_fichas(semente=3, quantidade=2)


def cofre(pasta: Path, senha: str, relogio: RelogioManual) -> Sessao:
    sessao, _ = criar_cofre(pasta, senha, senha, relogio)
    pacientes.cadastrar(sessao, FICHAS[0], "teste")
    return sessao


def test_sem_destino_nao_ha_aviso(tmp_path: Path) -> None:
    with cofre(tmp_path / "cofre", CURTA, RelogioManual()) as sessao:
        assert destino_externo.destino(sessao) is None
        assert destino_externo.situacao(sessao) is None
        assert destino_externo.copiar_se_presente(sessao) is None


def test_pendrive_aceita_senha_curta_e_recebe_a_copia_conferida(tmp_path: Path) -> None:
    pendrive = tmp_path / "E"
    pendrive.mkdir()
    relogio = RelogioManual()
    with cofre(tmp_path / "cofre", CURTA, relogio) as sessao:
        destino_externo.configurar(sessao, pendrive, CURTA)
        local = durabilidade.fazer_backup(sessao)

        copia = destino_externo.copiar_agora(sessao)
        de_novo = destino_externo.copiar_agora(sessao)

        situacao = destino_externo.situacao(sessao)
    assert copia.pasta == pendrive / PASTA_NO_DESTINO / local.pasta.name
    assert de_novo == copia
    assert {p.name for p in copia.pasta.iterdir()} == {NOME_DO_BANCO, NOME_DA_CHAVE}
    assert situacao is not None and situacao.ultima_copia == relogio.agora()
    with desbloquear(copia.pasta, CURTA) as aberta:
        assert integridade.verificar(aberta).ok


def test_destino_na_nuvem_exige_frase_longa(tmp_path: Path) -> None:
    drive = tmp_path / "Meu Drive"
    drive.mkdir()
    with cofre(tmp_path / "curta", CURTA, RelogioManual()) as sessao:
        with pytest.raises(SenhaFracaParaNuvem) as erro:
            destino_externo.configurar(sessao, drive, CURTA)
        assert erro.value.servico == "Google Drive"
        assert destino_externo.destino(sessao) is None
    with cofre(tmp_path / "frase", FRASE, RelogioManual()) as sessao:
        destino_externo.configurar(sessao, drive, FRASE)
        assert destino_externo.destino(sessao) == drive.resolve()


def test_configurar_confere_a_senha_e_recusa_destino_dentro_do_cofre(tmp_path: Path) -> None:
    with cofre(tmp_path / "cofre", CURTA, RelogioManual()) as sessao:
        with pytest.raises(SenhaIncorreta):
            destino_externo.configurar(sessao, tmp_path, "errada123")
        with pytest.raises(DestinoDentroDoCofre):
            destino_externo.configurar(sessao, tmp_path / "cofre" / "copias", CURTA)


def test_remover_desliga_o_destino(tmp_path: Path) -> None:
    with cofre(tmp_path / "cofre", CURTA, RelogioManual()) as sessao:
        destino_externo.configurar(sessao, tmp_path, CURTA)
        destino_externo.remover(sessao)

        assert destino_externo.situacao(sessao) is None


def test_pendrive_fora_ou_sem_backup_local(tmp_path: Path) -> None:
    pendrive = tmp_path / "E"
    pendrive.mkdir()
    with cofre(tmp_path / "cofre", CURTA, RelogioManual()) as sessao:
        destino_externo.configurar(sessao, pendrive, CURTA)
        with pytest.raises(SemBackupLocal):
            destino_externo.copiar_agora(sessao)
        pendrive.rmdir()
        with pytest.raises(DestinoAusente):
            destino_externo.copiar_agora(sessao)
        assert destino_externo.copiar_se_presente(sessao) is None


def test_backup_automatico_leva_a_copia_para_o_destino(tmp_path: Path) -> None:
    pendrive = tmp_path / "E"
    pendrive.mkdir()
    relogio = RelogioManual()
    with cofre(tmp_path / "cofre", CURTA, relogio) as sessao:
        destino_externo.configurar(sessao, pendrive, CURTA)
        automatico = BackupAutomatico(sessao, relogio)
        pacientes.cadastrar(sessao, FICHAS[1], "teste")
        relogio.avancar(INTERVALO_DO_BACKUP)

        local = automatico.tique()

    assert local is not None
    assert (pendrive / PASTA_NO_DESTINO / local.pasta.name / NOME_DO_BANCO).is_file()


def test_aviso_de_copia_externa_atrasada(tmp_path: Path) -> None:
    pendrive = tmp_path / "E"
    pendrive.mkdir()
    relogio = RelogioManual()
    with cofre(tmp_path / "cofre", CURTA, relogio) as sessao:
        destino_externo.configurar(sessao, pendrive, CURTA)
        nunca = destino_externo.situacao(sessao)
        assert nunca is not None and nunca.atrasada(relogio.agora())

        durabilidade.fazer_backup(sessao)
        destino_externo.copiar_agora(sessao)
        copiada = destino_externo.situacao(sessao)
    assert copiada is not None
    assert not copiada.atrasada(relogio.agora() + LIMITE_DE_ATRASO)
    assert copiada.atrasada(relogio.agora() + LIMITE_DE_ATRASO + timedelta(seconds=1))
