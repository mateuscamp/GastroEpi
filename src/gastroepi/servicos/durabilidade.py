"""Backup conferido e rotacionado, backup automático e instância única (ADR-0005).

O timer de verdade é da casca: ela chama `BackupAutomatico.tique()` de tempos em tempos
(a cada minuto basta) e `ao_fechar()` antes de fechar a sessão. Aqui só se decide se
copia, com o relógio injetado.
"""

from datetime import timedelta
from pathlib import Path

from gastroepi.persistencia.backups import (
    CopiaReprovada,
    listar_backups,
    primeiro_backup_valido,
    rotacionar,
)
from gastroepi.persistencia.conexao import BancoSomenteLeitura
from gastroepi.persistencia.relogio import Relogio
from gastroepi.persistencia.trava import NOME_DA_TRAVA, OutraInstanciaAberta, Trava
from gastroepi.servicos import destino_externo
from gastroepi.servicos.sessao import NOME_DA_CHAVE, Backup, Sessao, repositorio_de

__all__ = [
    "INTERVALO_DO_BACKUP",
    "Backup",
    "BackupAutomatico",
    "BancoSomenteLeitura",
    "CopiaReprovada",
    "OutraInstanciaAberta",
    "Trava",
    "backups_do_cofre",
    "fazer_backup",
    "listar_backups",
    "primeiro_backup_valido",
    "travar_instancia",
]

INTERVALO_DO_BACKUP = timedelta(minutes=15)


def fazer_backup(sessao: Sessao) -> Backup:
    """Cópia conferida em `backups/` e, só depois dela, a rotação por data. Se a cópia não
    passa, levanta `CopiaReprovada` e nenhuma cópia antiga sai."""
    backup = repositorio_de(sessao).fazer_backup(
        sessao.pasta_de_backups, sessao.pasta / NOME_DA_CHAVE, sessao.relogio.agora()
    )
    rotacionar(sessao.pasta_de_backups)
    return backup


def backups_do_cofre(sessao: Sessao) -> list[Backup]:
    """Do mais novo para o mais antigo."""
    return listar_backups(sessao.pasta_de_backups)


def travar_instancia(pasta: Path) -> Trava:
    """A casca segura a trava enquanto o app vive (ADR-0005, item 7)."""
    pasta.mkdir(parents=True, exist_ok=True)
    return Trava(pasta / NOME_DA_TRAVA)


class BackupAutomatico:
    """A cada 15 min, se houve alteração, e ao fechar, se houve alteração (ADR-0005, item 6).

    A alteração é medida pela marca do repositório (o maior id da auditoria). A janela de
    15 min conta da última cópia ou, antes dela, da criação do agendador. Depois de cada
    cópia local, a cópia vai para o destino externo, se houver um configurado e presente.
    """

    def __init__(
        self, sessao: Sessao, relogio: Relogio, intervalo: timedelta = INTERVALO_DO_BACKUP
    ) -> None:
        self._sessao = sessao
        self._relogio = relogio
        self._intervalo = intervalo
        self._ultima = relogio.agora()
        self._marca_copiada = self._marca()

    def tique(self) -> Backup | None:
        if self._relogio.agora() - self._ultima < self._intervalo:
            return None
        return self._copiar_se_alterou()

    def ao_fechar(self) -> Backup | None:
        return self._copiar_se_alterou()

    def _marca(self) -> int:
        return repositorio_de(self._sessao).marca_de_alteracao()

    def _copiar_se_alterou(self) -> Backup | None:
        if self._sessao.somente_leitura:
            return None
        marca = self._marca()
        if marca == self._marca_copiada:
            return None
        backup = fazer_backup(self._sessao)
        self._ultima = self._relogio.agora()
        self._marca_copiada = marca
        destino_externo.copiar_se_presente(self._sessao)
        return backup
