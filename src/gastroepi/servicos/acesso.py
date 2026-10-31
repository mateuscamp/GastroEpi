"""Acesso ao cofre: criar, desbloquear (senha ou recovery key), trocar senha e chave.

O cofre é uma pasta com dois arquivos (ADR-0003): `gastroepi.db`, cifrado pelo SQLCipher
com a chave de dados, e `gastroepi.chave`, com essa chave embrulhada pela senha.

Ordem das gravações, pensando num desligamento no meio:
- criar: grava o arquivo de chave antes do banco. Se o banco não chegar a existir, o
  cofre não existe e criar de novo sobrescreve o arquivo de chave órfão.
- nova recovery key: grava o arquivo de chave com a chave nova antes do `PRAGMA rekey`.
  Se cair entre os dois, a senha deixa de abrir, mas a recovery key antiga (no papel)
  ainda abre o banco e `recuperar_acesso` refaz o arquivo. Na ordem inversa, o banco
  ficaria com uma chave que ninguém viu.

Os erros que a casca precisa tratar são reexportados daqui: ela não importa `cofre` nem
`persistencia` (ADR-0002).
"""

from pathlib import Path
from types import TracebackType
from typing import Self

from gastroepi.cofre.arquivo_de_chave import (
    ArquivoDeChaveAusente,
    ArquivoDeChaveInvalido,
    SenhaIncorreta,
    desembrulhar,
    embrulhar,
    gerar_chave_de_dados,
    gravar_arquivo_de_chave,
    ler_arquivo_de_chave,
)
from gastroepi.cofre.recovery_key import (
    RecoveryKeyInvalida,
    formatar_recovery_key,
    ler_recovery_key,
)
from gastroepi.dominio.senha import conferir_nova_senha
from gastroepi.persistencia.conexao import BancoCorrompido, ChaveIncorreta
from gastroepi.persistencia.relogio import Relogio
from gastroepi.persistencia.repositorio import Repositorio
from gastroepi.persistencia.schema import BancoMaisNovoQueOApp

NOME_DO_BANCO = "gastroepi.db"
NOME_DA_CHAVE = "gastroepi.chave"

__all__ = [
    "NOME_DA_CHAVE",
    "NOME_DO_BANCO",
    "ArquivoDeChaveAusente",
    "ArquivoDeChaveInvalido",
    "BancoCorrompido",
    "BancoMaisNovoQueOApp",
    "ChaveIncorreta",
    "CofreJaExiste",
    "RecoveryKeyInvalida",
    "SenhaIncorreta",
    "Sessao",
    "cofre_existe",
    "criar_cofre",
    "desbloquear",
    "gerar_nova_recovery_key",
    "recuperar_acesso",
    "trocar_senha",
]


class CofreJaExiste(FileExistsError):
    def __init__(self) -> None:
        super().__init__("Já existe um cofre nesta pasta")


class Sessao:
    """Cofre aberto. A chave de dados fica na memória até `fechar` (ADR-0003, aceito)."""

    def __init__(self, pasta: Path, repositorio: Repositorio) -> None:
        self.pasta = pasta
        self._repositorio = repositorio

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


def cofre_existe(pasta: Path) -> bool:
    return (pasta / NOME_DO_BANCO).exists()


def _abrir(pasta: Path, chave: bytes, relogio: Relogio | None) -> Sessao:
    return Sessao(pasta, Repositorio.abrir(pasta / NOME_DO_BANCO, chave, relogio))


def criar_cofre(
    pasta: Path, senha: str, confirmacao: str, relogio: Relogio | None = None
) -> tuple[Sessao, str]:
    """Cenário 1: a senha digitada duas vezes. Devolve a sessão e a recovery key, que a
    tela mostra uma única vez e nunca vai para o disco."""
    conferir_nova_senha(senha, confirmacao)
    if cofre_existe(pasta):
        raise CofreJaExiste
    pasta.mkdir(parents=True, exist_ok=True)
    chave = gerar_chave_de_dados()
    gravar_arquivo_de_chave(pasta / NOME_DA_CHAVE, embrulhar(chave, senha))
    return _abrir(pasta, chave, relogio), formatar_recovery_key(chave)


def _chave_pela_senha(pasta: Path, senha: str) -> bytes:
    return desembrulhar(ler_arquivo_de_chave(pasta / NOME_DA_CHAVE), senha)


def desbloquear(pasta: Path, senha: str, relogio: Relogio | None = None) -> Sessao:
    return _abrir(pasta, _chave_pela_senha(pasta, senha), relogio)


def recuperar_acesso(
    pasta: Path,
    recovery_key: str,
    nova_senha: str,
    confirmacao: str,
    relogio: Relogio | None = None,
) -> Sessao:
    """Abre pela recovery key (mesmo sem o `gastroepi.chave`) e recria o arquivo de chave
    com a senha nova. O arquivo só é regravado depois que a chave abriu o banco."""
    conferir_nova_senha(nova_senha, confirmacao)
    chave = ler_recovery_key(recovery_key)
    sessao = _abrir(pasta, chave, relogio)
    gravar_arquivo_de_chave(pasta / NOME_DA_CHAVE, embrulhar(chave, nova_senha))
    return sessao


def trocar_senha(pasta: Path, senha_atual: str, nova_senha: str, confirmacao: str) -> None:
    """Só re-embrulha a chave de dados: o banco não é aberto nem recifrado."""
    conferir_nova_senha(nova_senha, confirmacao)
    chave = _chave_pela_senha(pasta, senha_atual)
    gravar_arquivo_de_chave(pasta / NOME_DA_CHAVE, embrulhar(chave, nova_senha))


def gerar_nova_recovery_key(sessao: Sessao, senha: str) -> str:
    """Chave de dados nova + `PRAGMA rekey`: a recovery key antiga deixa de abrir o banco.
    Backups feitos antes continuam na chave antiga (rotação e validade: ADR-0005)."""
    _chave_pela_senha(sessao.pasta, senha)
    nova = gerar_chave_de_dados()
    gravar_arquivo_de_chave(sessao.pasta / NOME_DA_CHAVE, embrulhar(nova, senha))
    repositorio_de(sessao).trocar_chave(nova)
    return formatar_recovery_key(nova)
