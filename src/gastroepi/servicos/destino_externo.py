"""Destino externo opcional: pendrive ou pasta do Drive (ADR-0005, itens 9 e 10).

As três regras da conversa de 2026-10-24:
1. o banco em uso nunca fica na pasta sincronizada (`acesso` recusa abrir lá); para o
   destino vai só a cópia pronta e conferida, com o `gastroepi.chave`;
2. a recovery key nunca vai para o destino: nada no app a grava em disco;
3. destino numa pasta sincronizada exige senha de frase longa (`e_frase_longa`).

O destino e o momento da última cópia ficam no `metadados` do banco cifrado. Destino
ausente (pendrive fora) não é erro no backup automático: a cópia fica para a próxima, e
o aviso de 7 dias cobre o esquecimento.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from gastroepi.dominio.senha import e_frase_longa
from gastroepi.persistencia.backups import CopiaReprovada, listar_backups, rotacionar
from gastroepi.servicos.sessao import (
    Backup,
    Sessao,
    chave_pela_senha,
    repositorio_de,
    servico_que_sincroniza,
)

PASTA_NO_DESTINO = "GastroEpi-backups"
LIMITE_DE_ATRASO = timedelta(days=7)
_DESTINO = "destino_externo"
_ULTIMA_COPIA = "ultima_copia_externa"


class DestinoDentroDoCofre(ValueError):
    def __init__(self) -> None:
        super().__init__("O destino externo não pode ficar dentro da pasta do cofre")


class SenhaFracaParaNuvem(ValueError):
    def __init__(self, servico: str) -> None:
        super().__init__(
            f"Para copiar para o {servico}, a senha precisa ser uma frase de pelo menos"
            " 4 palavras: fora desta máquina, só ela protege as cópias"
        )
        self.servico = servico


class DestinoAusente(FileNotFoundError):
    def __init__(self) -> None:
        super().__init__("O destino externo não está disponível (pendrive fora?)")


class SemBackupLocal(LookupError):
    def __init__(self) -> None:
        super().__init__("Ainda não há backup local para copiar")


@dataclass(frozen=True, slots=True)
class SituacaoDaCopiaExterna:
    destino: Path
    ultima_copia: datetime | None

    def atrasada(self, agora: datetime) -> bool:
        """Nunca copiou, ou a última cópia tem mais de 7 dias (ADR-0005, item 10)."""
        return self.ultima_copia is None or agora - self.ultima_copia > LIMITE_DE_ATRASO


def configurar(sessao: Sessao, destino: Path, senha: str) -> None:
    """A senha é conferida no `gastroepi.chave` (levanta `SenhaIncorreta`) antes da regra
    da frase longa: a regra vale para a senha que protege as cópias, não para uma digitada."""
    chave_pela_senha(sessao.pasta, senha)
    destino = destino.resolve()
    if destino.is_relative_to(sessao.pasta.resolve()):
        raise DestinoDentroDoCofre
    servico = servico_que_sincroniza(destino)
    if servico is not None and not e_frase_longa(senha):
        raise SenhaFracaParaNuvem(servico)
    repositorio_de(sessao).gravar_preferencia(_DESTINO, str(destino))


def remover(sessao: Sessao) -> None:
    repositorio_de(sessao).gravar_preferencia(_DESTINO, None)


def destino(sessao: Sessao) -> Path | None:
    configurado = repositorio_de(sessao).ler_preferencia(_DESTINO)
    return None if configurado is None else Path(configurado)


def situacao(sessao: Sessao) -> SituacaoDaCopiaExterna | None:
    """None sem destino configurado: aí não há aviso."""
    pasta = destino(sessao)
    if pasta is None:
        return None
    ultima = repositorio_de(sessao).ler_preferencia(_ULTIMA_COPIA)
    return SituacaoDaCopiaExterna(pasta, None if ultima is None else datetime.fromisoformat(ultima))


def copiar_agora(sessao: Sessao) -> Backup:
    """Leva o backup local mais novo para `<destino>/GastroEpi-backups/`, conferido lá, e
    aplica a mesma rotação. Levanta `DestinoAusente` ou `SemBackupLocal`."""
    pasta = destino(sessao)
    if pasta is None or not pasta.is_dir():
        raise DestinoAusente
    locais = listar_backups(sessao.pasta_de_backups)
    if not locais:
        raise SemBackupLocal
    repositorio = repositorio_de(sessao)
    copia = repositorio.copiar_backup(locais[0], pasta / PASTA_NO_DESTINO)
    rotacionar(pasta / PASTA_NO_DESTINO)
    repositorio.gravar_preferencia(_ULTIMA_COPIA, sessao.relogio.agora().isoformat())
    return copia


def copiar_se_presente(sessao: Sessao) -> Backup | None:
    """O passo do backup automático: sem destino, destino fora ou cópia reprovada no
    destino, não copia e não interrompe o backup local."""
    try:
        return copiar_agora(sessao)
    except (DestinoAusente, CopiaReprovada, OSError):
        return None
