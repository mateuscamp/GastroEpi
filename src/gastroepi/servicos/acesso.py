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

from gastroepi.cofre.arquivo_de_chave import (
    ArquivoDeChaveAusente,
    ArquivoDeChaveInvalido,
    SenhaIncorreta,
    embrulhar,
    gerar_chave_de_dados,
    gravar_arquivo_de_chave,
)
from gastroepi.cofre.recovery_key import (
    RecoveryKeyInvalida,
    formatar_recovery_key,
    ler_recovery_key,
)
from gastroepi.dominio.senha import conferir_nova_senha
from gastroepi.persistencia.backups import (
    CopiaReprovada,
    listar_backups,
    primeiro_backup_valido,
    restaurar,
)
from gastroepi.persistencia.conexao import BancoCorrompido, BancoSomenteLeitura, ChaveIncorreta
from gastroepi.persistencia.relogio import Relogio, RelogioDoSistema
from gastroepi.persistencia.repositorio import Repositorio
from gastroepi.persistencia.schema import BancoMaisNovoQueOApp
from gastroepi.servicos.durabilidade import fazer_backup
from gastroepi.servicos.sessao import (
    NOME_DA_CHAVE,
    NOME_DO_BANCO,
    PASTA_DE_BACKUPS,
    Backup,
    Sessao,
    chave_pela_senha,
    repositorio_de,
    servico_que_sincroniza,
)

__all__ = [
    "NOME_DA_CHAVE",
    "NOME_DO_BANCO",
    "ArquivoDeChaveAusente",
    "ArquivoDeChaveInvalido",
    "Backup",
    "BancoCorrompido",
    "BancoIlegivel",
    "BancoMaisNovoQueOApp",
    "BancoSomenteLeitura",
    "ChaveIncorreta",
    "CofreJaExiste",
    "CopiaReprovada",
    "PastaSincronizada",
    "RecoveryKeyInvalida",
    "SenhaIncorreta",
    "Sessao",
    "cofre_existe",
    "criar_cofre",
    "desbloquear",
    "gerar_nova_recovery_key",
    "recuperar_acesso",
    "restaurar_backup",
    "trocar_senha",
]


class CofreJaExiste(FileExistsError):
    def __init__(self) -> None:
        super().__init__("Já existe um cofre nesta pasta")


class PastaSincronizada(PermissionError):
    """ADR-0005, item 8: o cliente de sincronização corrompe o banco em uso."""

    def __init__(self, servico: str) -> None:
        super().__init__(
            f"A pasta do cofre está dentro do {servico}. Escolha uma pasta fora dele;"
            " as cópias podem ir para lá pelo destino externo"
        )
        self.servico = servico


class BancoIlegivel(BancoCorrompido):
    """A senha abriu o `gastroepi.chave` (o GCM autentica o embrulho), mas a chave não abre
    o banco: a página 1 está estragada (ADR-0005, item 2). Traz o backup oferecido."""

    def __init__(self, backup_oferecido: Backup | None) -> None:
        super().__init__()
        self.backup_oferecido = backup_oferecido


def _recusar_pasta_sincronizada(pasta: Path) -> None:
    servico = servico_que_sincroniza(pasta)
    if servico is not None:
        raise PastaSincronizada(servico)


def cofre_existe(pasta: Path) -> bool:
    return (pasta / NOME_DO_BANCO).exists()


def _abrir(pasta: Path, chave: bytes, relogio: Relogio | None) -> Sessao:
    """Banco que não passa no `quick_check` abre em somente leitura, com a oferta do
    último backup bom (ADR-0005, item 1)."""
    relogio = relogio or RelogioDoSistema()
    repositorio = Repositorio.abrir(pasta / NOME_DO_BANCO, chave, relogio)
    if not repositorio.somente_leitura:
        return Sessao(pasta, repositorio, relogio)
    return Sessao(pasta, repositorio, relogio, _oferta(pasta, chave))


def _oferta(pasta: Path, chave: bytes) -> Backup | None:
    return primeiro_backup_valido(listar_backups(pasta / PASTA_DE_BACKUPS), chave)


def criar_cofre(
    pasta: Path, senha: str, confirmacao: str, relogio: Relogio | None = None
) -> tuple[Sessao, str]:
    """Cenário 1: a senha digitada duas vezes. Devolve a sessão e a recovery key, que a
    tela mostra uma única vez e nunca vai para o disco."""
    conferir_nova_senha(senha, confirmacao)
    _recusar_pasta_sincronizada(pasta)
    if cofre_existe(pasta):
        raise CofreJaExiste
    pasta.mkdir(parents=True, exist_ok=True)
    chave = gerar_chave_de_dados()
    gravar_arquivo_de_chave(pasta / NOME_DA_CHAVE, embrulhar(chave, senha))
    return _abrir(pasta, chave, relogio), formatar_recovery_key(chave)


def desbloquear(pasta: Path, senha: str, relogio: Relogio | None = None) -> Sessao:
    """Banco estragado no meio abre em somente leitura, com `backup_oferecido`; na página 1,
    levanta `BancoIlegivel` com a mesma oferta (ADR-0005, itens 1 e 2)."""
    _recusar_pasta_sincronizada(pasta)
    chave = chave_pela_senha(pasta, senha)
    try:
        return _abrir(pasta, chave, relogio)
    except ChaveIncorreta:
        raise BancoIlegivel(_oferta(pasta, chave)) from None


def restaurar_backup(
    pasta: Path, backup: Backup, senha: str, relogio: Relogio | None = None
) -> Sessao:
    """Põe `backup` no lugar do banco e abre o cofre. O banco estragado fica guardado como
    `gastroepi.db.corrompido-<momento>`, e o `gastroepi.chave` atual não muda: o backup
    oferecido está na mesma chave de dados. A sessão somente leitura tem de estar fechada."""
    _recusar_pasta_sincronizada(pasta)
    chave = chave_pela_senha(pasta, senha)
    momento = (relogio or RelogioDoSistema()).agora()
    restaurar(backup, pasta / NOME_DO_BANCO, chave, momento)
    return _abrir(pasta, chave, relogio)


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
    _recusar_pasta_sincronizada(pasta)
    chave = ler_recovery_key(recovery_key)
    sessao = _abrir(pasta, chave, relogio)
    gravar_arquivo_de_chave(pasta / NOME_DA_CHAVE, embrulhar(chave, nova_senha))
    return sessao


def trocar_senha(pasta: Path, senha_atual: str, nova_senha: str, confirmacao: str) -> None:
    """Só re-embrulha a chave de dados: o banco não é aberto nem recifrado."""
    conferir_nova_senha(nova_senha, confirmacao)
    chave = chave_pela_senha(pasta, senha_atual)
    gravar_arquivo_de_chave(pasta / NOME_DA_CHAVE, embrulhar(chave, nova_senha))


def gerar_nova_recovery_key(sessao: Sessao, senha: str) -> str:
    """Chave de dados nova + `PRAGMA rekey`: a recovery key antiga deixa de abrir o banco.
    Backups feitos antes continuam na chave antiga; por isso sai um backup na chave nova
    logo depois (ADR-0005, item 6)."""
    chave_pela_senha(sessao.pasta, senha)
    nova = gerar_chave_de_dados()
    gravar_arquivo_de_chave(sessao.pasta / NOME_DA_CHAVE, embrulhar(nova, senha))
    repositorio_de(sessao).trocar_chave(nova)
    fazer_backup(sessao)  # uma cópia na chave nova, a única que a restauração oferece
    return formatar_recovery_key(nova)
