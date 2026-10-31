"""Governança do ADR-0005 (durabilidade do cofre): um teste por linha da tabela.

Aqui fica o comportamento visto pela porta das cascas (`servicos`). Linhas cobertas no
arquivo do módulo, com mais casos:
- rotação por data: `tests/persistencia/test_rotacao.py` (hypothesis);
- backup a cada 15 min e ao fechar: `tests/servicos/test_durabilidade.py`;
- heurística de pasta sincronizada no Windows e no Linux:
  `tests/persistencia/test_pasta_sincronizada.py`;
- frase longa e aviso de 7 dias: `tests/servicos/test_destino_externo.py`;
- "sem socket": contrato "Princípio I" do import-linter e `--disable-socket`;
- tempo da abertura: `ferramentas/medir_listagem.py` (manual).
"""

import os
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from gastroepi.cofre.recovery_key import ler_recovery_key
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.backups import gravar_backup
from gastroepi.servicos import destino_externo, durabilidade, integridade, pacientes
from gastroepi.servicos.acesso import (
    NOME_DA_CHAVE,
    NOME_DO_BANCO,
    BancoIlegivel,
    BancoSomenteLeitura,
    CopiaReprovada,
    PastaSincronizada,
    Sessao,
    criar_cofre,
    desbloquear,
    gerar_nova_recovery_key,
    restaurar_backup,
)
from gastroepi.servicos.destino_externo import PASTA_NO_DESTINO, SenhaFracaParaNuvem
from gastroepi.servicos.durabilidade import INTERVALO_DO_BACKUP, BackupAutomatico
from tests.conftest import RelogioManual

SENHA = "frase longa de teste"
FICHAS = gerar_fichas(semente=9, quantidade=41)


def corromper(banco: Path, posicao: int) -> None:
    bruto = bytearray(banco.read_bytes())
    bruto[posicao] ^= 0xFF
    banco.write_bytes(bytes(bruto))


def corromper_o_meio(banco: Path) -> None:
    corromper(banco, banco.stat().st_size // 2 + 1000)


def cofre_com_backup(pasta: Path, relogio: RelogioManual | None = None) -> tuple[str, Sessao]:
    """Cofre com 40 fictícios e um backup; devolve a recovery key e a sessão já fechada."""
    sessao, recovery_key = criar_cofre(pasta, SENHA, SENHA, relogio)
    with sessao:
        for ficha in FICHAS[:40]:
            pacientes.cadastrar(sessao, ficha, usuario="teste")
        durabilidade.fazer_backup(sessao)
    return recovery_key, sessao


def test_bytes_corrompidos_no_meio_abrem_somente_leitura_e_oferecem_o_backup_valido(
    tmp_path: Path,
) -> None:
    sessao, _ = criar_cofre(tmp_path, SENHA, SENHA)
    with sessao:
        for ficha in FICHAS[:40]:
            pacientes.cadastrar(sessao, ficha, usuario="teste")
        backup = durabilidade.fazer_backup(sessao)
    corromper_o_meio(tmp_path / NOME_DO_BANCO)

    with desbloquear(tmp_path, SENHA) as aberta:
        assert aberta.somente_leitura
        assert aberta.backup_oferecido == backup
        with pytest.raises(BancoSomenteLeitura):
            pacientes.cadastrar(aberta, FICHAS[40], "teste")


def test_pagina_1_corrompida_com_a_senha_certa_e_banco_ilegivel_com_oferta(
    tmp_path: Path,
) -> None:
    cofre_com_backup(tmp_path)
    backup = durabilidade.listar_backups(tmp_path / "backups")[0]
    corromper(tmp_path / NOME_DO_BANCO, 100)

    with pytest.raises(BancoIlegivel) as erro:
        desbloquear(tmp_path, SENHA)

    assert erro.value.backup_oferecido == backup


def test_a_oferta_e_o_ultimo_backup_que_passa_na_checagem(tmp_path: Path) -> None:
    relogio = RelogioManual()
    cofre_com_backup(tmp_path, relogio)
    bom = durabilidade.listar_backups(tmp_path / "backups")[0]
    relogio.avancar(timedelta(days=1))
    with desbloquear(tmp_path, SENHA, relogio) as sessao:
        estragado = durabilidade.fazer_backup(sessao)
    corromper_o_meio(estragado.banco)
    corromper_o_meio(tmp_path / NOME_DO_BANCO)

    with desbloquear(tmp_path, SENHA, relogio) as aberta:
        assert aberta.backup_oferecido == bom


def test_restaurar_abre_o_backup_e_guarda_o_banco_estragado(tmp_path: Path) -> None:
    relogio = RelogioManual()
    cofre_com_backup(tmp_path, relogio)
    corromper_o_meio(tmp_path / NOME_DO_BANCO)
    estragado = (tmp_path / NOME_DO_BANCO).read_bytes()
    with desbloquear(tmp_path, SENHA, relogio) as aberta:
        oferta = aberta.backup_oferecido
    assert oferta is not None

    with restaurar_backup(tmp_path, oferta, SENHA, relogio) as restaurada:
        assert not restaurada.somente_leitura
        assert integridade.verificar(restaurada).ok
        assert list(pacientes.listar(restaurada).values()) == list(FICHAS[:40])
        pacientes.cadastrar(restaurada, FICHAS[40], "teste")

    guardados = list(tmp_path.glob(f"{NOME_DO_BANCO}.corrompido-*"))
    assert [g.read_bytes() for g in guardados] == [estragado]


def test_copia_ruim_nunca_ganha_o_nome_final(tmp_path: Path) -> None:
    cofre_com_backup(tmp_path)
    antes = {p.name: p for p in (tmp_path / "backups").iterdir()}
    chave = os.urandom(32)

    with pytest.raises(CopiaReprovada):
        gravar_backup(
            lambda destino: destino.write_bytes(os.urandom(4096)),
            tmp_path / NOME_DA_CHAVE,
            chave,
            tmp_path / "backups",
            RelogioManual().agora() + timedelta(days=1),
        )

    assert {p.name: p for p in (tmp_path / "backups").iterdir()} == antes
    with desbloquear(tmp_path, SENHA) as sessao:
        assert durabilidade.backups_do_cofre(sessao) != []


def test_backup_conferido_num_arquivo_so_abre_com_a_senha(tmp_path: Path) -> None:
    cofre_com_backup(tmp_path)
    backup = durabilidade.listar_backups(tmp_path / "backups")[0]

    assert sorted(p.name for p in backup.pasta.iterdir()) == [NOME_DA_CHAVE, NOME_DO_BANCO]
    with desbloquear(backup.pasta, SENHA) as copia:
        assert integridade.verificar(copia).ok


def test_um_dia_movimentado_nao_apaga_os_backups_dos_dias_anteriores(tmp_path: Path) -> None:
    relogio = RelogioManual()
    sessao, _ = criar_cofre(tmp_path, SENHA, SENHA, relogio)
    with sessao:
        anteriores = []
        for dia in range(3):
            pacientes.cadastrar(sessao, FICHAS[dia], "teste")
            anteriores.append(durabilidade.fazer_backup(sessao))
            relogio.avancar(timedelta(days=1))
        for ficha in FICHAS[3:23]:  # 20 aberturas e alterações no mesmo dia
            pacientes.cadastrar(sessao, ficha, "teste")
            ultimo = durabilidade.fazer_backup(sessao)
            relogio.avancar(timedelta(minutes=15))

        assert durabilidade.backups_do_cofre(sessao) == [ultimo, *reversed(anteriores)]


def test_backup_a_cada_15_min_so_se_alterou(tmp_path: Path) -> None:
    relogio = RelogioManual()
    sessao, _ = criar_cofre(tmp_path, SENHA, SENHA, relogio)
    with sessao:
        automatico = BackupAutomatico(sessao, relogio)
        relogio.avancar(INTERVALO_DO_BACKUP)
        assert automatico.tique() is None
        pacientes.cadastrar(sessao, FICHAS[0], "teste")
        assert automatico.tique() is not None
        pacientes.cadastrar(sessao, FICHAS[1], "teste")
        assert automatico.tique() is None
        assert automatico.ao_fechar() is not None


def test_nova_recovery_key_deixa_um_backup_na_chave_nova(tmp_path: Path) -> None:
    cofre_com_backup(tmp_path)

    with desbloquear(tmp_path, SENHA) as sessao:
        nova = ler_recovery_key(gerar_nova_recovery_key(sessao, SENHA))
        backups = durabilidade.backups_do_cofre(sessao)

    assert durabilidade.primeiro_backup_valido(backups, nova) == backups[0]
    assert durabilidade.primeiro_backup_valido(backups[1:], nova) is None


def test_instancia_unica_sem_socket(tmp_path: Path) -> None:
    with durabilidade.travar_instancia(tmp_path), pytest.raises(durabilidade.OutraInstanciaAberta):
        durabilidade.travar_instancia(tmp_path)


def test_cofre_em_pasta_sincronizada_e_recusado(tmp_path: Path) -> None:
    dentro = tmp_path / "OneDrive" / "GastroEpi"
    cofre_com_backup(tmp_path / "local")
    (tmp_path / "OneDrive").mkdir()
    (tmp_path / "local").rename(dentro)

    with pytest.raises(PastaSincronizada, match="OneDrive"):
        criar_cofre(tmp_path / "OneDrive" / "outro", SENHA, SENHA)
    with pytest.raises(PastaSincronizada):
        desbloquear(dentro, SENHA)
    assert not (tmp_path / "OneDrive" / "outro").exists()


def test_destino_externo_recebe_so_a_copia_conferida_e_nunca_a_recovery_key(
    tmp_path: Path,
) -> None:
    drive = tmp_path / "Google Drive"
    drive.mkdir()
    recovery_key, _ = cofre_com_backup(tmp_path / "cofre")
    chave = ler_recovery_key(recovery_key)

    with desbloquear(tmp_path / "cofre", SENHA) as sessao:
        destino_externo.configurar(sessao, drive, SENHA)
        copia = destino_externo.copiar_agora(sessao)

    # O banco em uso nunca fica no Drive: para abrir a cópia, ela sai de lá primeiro.
    with pytest.raises(PastaSincronizada):
        desbloquear(copia.pasta, SENHA)
    trazida = shutil.copytree(copia.pasta, tmp_path / "trazida")
    with desbloquear(trazida, SENHA) as aberta:
        assert integridade.verificar(aberta).ok
    segredos = [
        recovery_key.encode(),
        recovery_key.replace(" ", "").encode(),
        chave.hex().encode(),
        chave,
    ]
    arquivos = [p for p in drive.rglob("*") if p.is_file()]
    assert sorted(p.name for p in arquivos) == [NOME_DA_CHAVE, NOME_DO_BANCO]
    assert [s for p in arquivos for s in segredos if s in p.read_bytes()] == []
    assert (drive / PASTA_NO_DESTINO / copia.pasta.name).is_dir()


def test_destino_na_nuvem_exige_frase_longa_e_o_pendrive_nao(tmp_path: Path) -> None:
    (tmp_path / "Dropbox").mkdir()
    (tmp_path / "pendrive").mkdir()
    sessao, _ = criar_cofre(tmp_path / "cofre", "curta123", "curta123")
    with sessao:
        with pytest.raises(SenhaFracaParaNuvem):
            destino_externo.configurar(sessao, tmp_path / "Dropbox", "curta123")
        destino_externo.configurar(sessao, tmp_path / "pendrive", "curta123")


def test_aviso_quando_a_ultima_copia_externa_tem_mais_de_7_dias(tmp_path: Path) -> None:
    (tmp_path / "pendrive").mkdir()
    relogio = RelogioManual()
    cofre_com_backup(tmp_path / "cofre", relogio)
    with desbloquear(tmp_path / "cofre", SENHA, relogio) as sessao:
        destino_externo.configurar(sessao, tmp_path / "pendrive", SENHA)
        destino_externo.copiar_agora(sessao)
        situacao = destino_externo.situacao(sessao)

    assert situacao is not None
    assert not situacao.atrasada(relogio.agora() + timedelta(days=7))
    assert situacao.atrasada(relogio.agora() + timedelta(days=7, seconds=1))
