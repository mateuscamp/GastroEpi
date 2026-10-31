"""Backups do cofre (ADR-0005): uma pasta por cópia, com o banco e o arquivo de chave.

    backups/gastroepi-2026-10-31-120000/{gastroepi.db, gastroepi.chave}

O nome é o momento da cópia em UTC; se repetir no mesmo segundo, ganha `-2`, `-3`…
Só pastas com esse nome contam como backup. Uma `.temp-…` é uma cópia em andamento,
ou que sobrou de uma queda, e nunca é oferecida.
"""

import os
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gastroepi.persistencia.conexao import copia_integra
from gastroepi.persistencia.rotacao import a_manter

NOME_DO_BANCO = "gastroepi.db"
NOME_DA_CHAVE = "gastroepi.chave"
PASTA_DE_BACKUPS = "backups"

_FORMATO_DO_MOMENTO = "%Y-%m-%d-%H%M%S"
_NOME = re.compile(r"gastroepi-(\d{4}-\d{2}-\d{2}-\d{6})(?:-\d+)?")


@dataclass(frozen=True, slots=True)
class Backup:
    pasta: Path
    momento: datetime  # UTC, lido do nome da pasta

    @property
    def banco(self) -> Path:
        return self.pasta / NOME_DO_BANCO


def nome_do_backup(momento: datetime) -> str:
    return f"gastroepi-{momento.astimezone(UTC).strftime(_FORMATO_DO_MOMENTO)}"


def _backup_de(pasta: Path) -> Backup | None:
    casamento = _NOME.fullmatch(pasta.name)
    if casamento is None or not pasta.is_dir():
        return None
    momento = datetime.strptime(casamento[1], _FORMATO_DO_MOMENTO).replace(tzinfo=UTC)
    return Backup(pasta, momento)


def listar_backups(pasta_de_backups: Path) -> list[Backup]:
    """Do mais novo para o mais antigo."""
    if not pasta_de_backups.is_dir():
        return []
    backups = [b for p in pasta_de_backups.iterdir() if (b := _backup_de(p)) is not None]
    return sorted(backups, key=lambda b: (b.momento, b.pasta.name), reverse=True)


def primeiro_backup_valido(backups: list[Backup], chave: bytes) -> Backup | None:
    """O mais novo que abre com `chave` e passa na conferência (ADR-0005, item 1)."""
    return next((b for b in backups if copia_integra(b.banco, chave)), None)


class CopiaReprovada(RuntimeError):
    """A cópia não passou na conferência e foi descartada: nada ganhou o nome final."""

    def __init__(self, nome: str) -> None:
        super().__init__(f"A cópia {nome} não passou na conferência e foi descartada")
        self.nome = nome


def copiar_com_fsync(origem: Path, destino: Path) -> None:
    shutil.copyfile(origem, destino)
    _fsync(destino)


def _fsync(arquivo: Path) -> None:
    with arquivo.open("rb+") as aberto:
        os.fsync(aberto.fileno())


def _fsync_da_pasta(pasta: Path) -> None:
    """Grava a renomeação no disco. O Windows não abre pasta como arquivo; lá o NTFS
    registra a renomeação no journal dele."""
    if os.name == "nt":  # pragma: no cover - roda no CI Windows
        return
    descritor = os.open(pasta, os.O_RDONLY)
    try:
        os.fsync(descritor)
    finally:
        os.close(descritor)


def _apagar_temporarios(pasta_de_backups: Path) -> None:
    for sobra in pasta_de_backups.glob(".temp-*"):
        shutil.rmtree(sobra, ignore_errors=True)


def _nome_livre(pasta_de_backups: Path, momento: datetime) -> Path:
    base = nome_do_backup(momento)
    candidato, numero = pasta_de_backups / base, 1
    while candidato.exists():
        numero += 1
        candidato = pasta_de_backups / f"{base}-{numero}"
    return candidato


def gravar_backup(
    copiar_banco: Callable[[Path], object],
    arquivo_de_chave: Path,
    chave: bytes,
    pasta_de_backups: Path,
    momento: datetime,
) -> Backup:
    """Cópia numa `.temp-…`, conferida, com fsync, e só então renomeada (ADR-0005, item 4).

    `copiar_banco` grava o banco no caminho que recebe: a API de backup, para o backup
    local, ou a cópia de um backup pronto, para o destino externo.
    """
    pasta_de_backups.mkdir(parents=True, exist_ok=True)
    _apagar_temporarios(pasta_de_backups)
    temporaria = pasta_de_backups / f".temp-{nome_do_backup(momento)}"
    temporaria.mkdir()
    try:
        copiar_banco(temporaria / NOME_DO_BANCO)
        copiar_com_fsync(arquivo_de_chave, temporaria / NOME_DA_CHAVE)
        if not copia_integra(temporaria / NOME_DO_BANCO, chave):
            raise CopiaReprovada(temporaria.name)
        _fsync(temporaria / NOME_DO_BANCO)
        final = _nome_livre(pasta_de_backups, momento)
        os.replace(temporaria, final)
    except BaseException:
        shutil.rmtree(temporaria, ignore_errors=True)
        raise
    _fsync_da_pasta(pasta_de_backups)
    return Backup(final, momento.astimezone(UTC).replace(microsecond=0))


def rotacionar(pasta_de_backups: Path) -> list[Backup]:
    """Apaga as cópias que a rotação por data não guarda; devolve as apagadas. As datas
    são as do fuso local (ADR-0005, item 5)."""
    backups = listar_backups(pasta_de_backups)
    manter = set(a_manter(backups, lambda b: b.momento.astimezone()))
    apagados = [b for b in backups if b not in manter]
    for backup in apagados:
        shutil.rmtree(backup.pasta)
    return apagados


def _guardar_ao_lado(arquivo: Path, guardado: Path) -> None:
    """Link para o banco estragado ficar guardado sem sair do lugar; cópia se o sistema de
    arquivos não tem link (FAT32)."""
    try:
        os.link(arquivo, guardado)
    except OSError:
        shutil.copy2(arquivo, guardado)


def restaurar(backup: Backup, banco: Path, chave: bytes, momento: datetime) -> None:
    """Põe o backup no lugar do banco sem apagar o estragado (ADR-0005, item 3).

    Ordem, pensando numa queda no meio:
    1. o backup vai para um temporário ao lado do banco e é conferido lá;
    2. o banco estragado ganha um nome `….corrompido-<momento>` (link), sem sair do lugar:
       o cofre nunca fica sem `gastroepi.db`, ou o app ofereceria criar um cofre novo;
    3. o `-wal` e o `-shm` saem do caminho: aplicados ao banco restaurado, o corromperiam;
    4. o temporário substitui o banco num `os.replace`.
    """
    temporario = banco.with_name(f".{banco.name}.restaurando")
    copiar_com_fsync(backup.banco, temporario)
    if not copia_integra(temporario, chave):
        temporario.unlink()
        raise CopiaReprovada(backup.pasta.name)
    sufixo = f"corrompido-{nome_do_backup(momento).removeprefix('gastroepi-')}"
    _guardar_ao_lado(banco, banco.with_name(f"{banco.name}.{sufixo}"))
    for anexo in (banco.with_name(f"{banco.name}-wal"), banco.with_name(f"{banco.name}-shm")):
        if anexo.exists():
            os.replace(anexo, anexo.with_name(f"{anexo.name}.{sufixo}"))
    os.replace(temporario, banco)
    _fsync_da_pasta(banco.parent)
