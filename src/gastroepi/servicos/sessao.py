"""Sessão: o cofre aberto, e o que os módulos de `servicos` compartilham sobre ele.

Mora à parte de `acesso` para `durabilidade` e `destino_externo` usarem a sessão sem
importar `acesso`, que por sua vez faz backup depois do rekey (ADR-0005, item 6).
"""

import os
import sys
from pathlib import Path
from types import TracebackType
from typing import Self

from gastroepi.cofre.arquivo_de_chave import desembrulhar, ler_arquivo_de_chave
from gastroepi.persistencia.backups import NOME_DA_CHAVE, NOME_DO_BANCO, PASTA_DE_BACKUPS, Backup
from gastroepi.persistencia.pasta_sincronizada import servico_de_sincronizacao
from gastroepi.persistencia.relogio import Relogio
from gastroepi.persistencia.repositorio import Repositorio

__all__ = ["NOME_DA_CHAVE", "NOME_DO_BANCO", "PASTA_DE_BACKUPS", "Backup", "Sessao"]


class Sessao:
    """Cofre aberto. A chave de dados fica na memória até `fechar` (ADR-0003, aceito).

    `somente_leitura`: o banco não passou no `quick_check` da abertura (ADR-0005, item 1).
    Nesse caso, `backup_oferecido` é o último backup que abre com esta chave e passa na
    checagem, ou None se nenhum passa.
    """

    def __init__(
        self,
        pasta: Path,
        repositorio: Repositorio,
        relogio: Relogio,
        backup_oferecido: Backup | None = None,
    ) -> None:
        self.pasta = pasta
        self.relogio = relogio
        self.backup_oferecido = backup_oferecido
        self._repositorio = repositorio

    @property
    def somente_leitura(self) -> bool:
        return self._repositorio.somente_leitura

    @property
    def pasta_de_backups(self) -> Path:
        return self.pasta / PASTA_DE_BACKUPS

    def fechar(self) -> None:
        self._repositorio.fechar()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.fechar()


def repositorio_de(sessao: Sessao) -> Repositorio:
    """Só para os módulos de `servicos`: a casca recebe a sessão e não vê o repositório."""
    return sessao._repositorio


def chave_pela_senha(pasta: Path, senha: str) -> bytes:
    return desembrulhar(ler_arquivo_de_chave(pasta / NOME_DA_CHAVE), senha)


def servico_que_sincroniza(pasta: Path) -> str | None:
    """OneDrive, Google Drive, Dropbox ou iCloud, se `pasta` estiver dentro de um deles."""
    return servico_de_sincronizacao(str(pasta.resolve()), sys.platform, os.environ, os.path.exists)
