"""Heurística de pasta sincronizada (ADR-0005, item 8): OneDrive, Google Drive, Dropbox, iCloud.

O cliente de sincronização copia o `.db` no meio de uma escrita, separado do `-wal`, e
cria "cópias em conflito". Por isso o banco em uso nunca mora numa pasta dessas.

Pura: recebe o caminho já resolvido, o sistema (`sys.platform`), as variáveis de ambiente
e um teste de existência de arquivo. Assim os casos de Windows e Linux rodam em qualquer
sistema na suíte.
"""

from collections.abc import Callable, Mapping
from pathlib import PurePath, PurePosixPath, PureWindowsPath

ONEDRIVE = "OneDrive"
GOOGLE_DRIVE = "Google Drive"
DROPBOX = "Dropbox"
ICLOUD = "iCloud"

# Nome exato de um componente do caminho, sem a caixa.
_NOMES = {
    "onedrive": ONEDRIVE,
    "google drive": GOOGLE_DRIVE,
    "googledrive": GOOGLE_DRIVE,
    "my drive": GOOGLE_DRIVE,
    "meu drive": GOOGLE_DRIVE,
    "shared drives": GOOGLE_DRIVE,
    "drives compartilhados": GOOGLE_DRIVE,
    "dropbox": DROPBOX,
    "icloud drive": ICLOUD,
    "iclouddrive": ICLOUD,
    "mobile documents": ICLOUD,
}
# Começo de um componente: "OneDrive - Empresa", "Dropbox (Pessoal)", montagens do gvfs.
_PREFIXOS = {
    "onedrive - ": ONEDRIVE,
    "dropbox (": DROPBOX,
    "google-drive:": GOOGLE_DRIVE,
    "onedrive:": ONEDRIVE,
}
# O Windows define estas variáveis com a raiz de cada conta do OneDrive.
_VARIAVEIS_DO_ONEDRIVE = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")
# A raiz do Dropbox tem este marcador, mesmo com a pasta renomeada. O `.dropbox` não
# serve: no Linux, `~/.dropbox` é a configuração do cliente e acusaria a home inteira.
_MARCADORES_DO_DROPBOX = (".dropbox.cache",)


def _por_nome(caminho: PurePath) -> str | None:
    for parte in (p.casefold() for p in caminho.parts):
        if parte in _NOMES:
            return _NOMES[parte]
        prefixo = next((p for p in _PREFIXOS if parte.startswith(p)), None)
        if prefixo is not None:
            return _PREFIXOS[prefixo]
    return None


def _por_variavel(caminho: PurePath, ambiente: Mapping[str, str]) -> str | None:
    raizes = (ambiente.get(v, "").strip() for v in _VARIAVEIS_DO_ONEDRIVE)
    if any(caminho.is_relative_to(PureWindowsPath(r)) for r in raizes if r):
        return ONEDRIVE
    return None


def _por_marcador(caminho: PurePath, existe: Callable[[str], bool]) -> str | None:
    for pasta in (caminho, *caminho.parents):
        if any(existe(str(pasta / m)) for m in _MARCADORES_DO_DROPBOX):
            return DROPBOX
    return None


def servico_de_sincronizacao(
    caminho: str, sistema: str, ambiente: Mapping[str, str], existe: Callable[[str], bool]
) -> str | None:
    """O nome do serviço que sincroniza `caminho`, ou None. `caminho` já vem resolvido
    (sem link simbólico), porque o cliente sincroniza o destino do link."""
    if sistema == "win32":
        janelas = PureWindowsPath(caminho)
        return (
            _por_variavel(janelas, ambiente) or _por_nome(janelas) or _por_marcador(janelas, existe)
        )
    posix = PurePosixPath(caminho)
    return _por_nome(posix) or _por_marcador(posix, existe)
