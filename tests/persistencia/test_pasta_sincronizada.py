"""Heurística de pasta sincronizada (ADR-0005, item 8), com casos de Windows e Linux."""

import pytest

from gastroepi.persistencia.pasta_sincronizada import (
    DROPBOX,
    GOOGLE_DRIVE,
    ICLOUD,
    ONEDRIVE,
    servico_de_sincronizacao,
)

ONEDRIVE_DO_WINDOWS = {
    "OneDrive": r"C:\Users\Joao\OneDrive",
    "OneDriveCommercial": r"C:\Users\Joao\Clinica Ltda",  # conta comercial com nome livre
}


def nada_existe(caminho: str) -> bool:
    return False


@pytest.mark.parametrize(
    ("caminho", "servico"),
    [
        (r"C:\Users\Joao\OneDrive\Documentos\GastroEpi", ONEDRIVE),
        (r"c:\users\joao\onedrive\GastroEpi", ONEDRIVE),
        (r"C:\Users\Joao\Clinica Ltda\GastroEpi", ONEDRIVE),
        (r"c:\USERS\joao\CLINICA LTDA\GastroEpi", ONEDRIVE),  # o Windows ignora a caixa
        (r"D:\OneDrive - Hospital X\GastroEpi", ONEDRIVE),
        (r"G:\Meu Drive\GastroEpi", GOOGLE_DRIVE),
        (r"G:\My Drive\GastroEpi", GOOGLE_DRIVE),
        (r"G:\Drives compartilhados\Clinica\GastroEpi", GOOGLE_DRIVE),
        (r"C:\Users\Joao\Google Drive\GastroEpi", GOOGLE_DRIVE),
        (r"C:\Users\Joao\Dropbox\GastroEpi", DROPBOX),
        (r"C:\Users\Joao\Dropbox (Pessoal)\GastroEpi", DROPBOX),
        (r"C:\Users\Joao\iCloudDrive\GastroEpi", ICLOUD),
    ],
)
def test_windows_acusa_as_pastas_sincronizadas(caminho: str, servico: str) -> None:
    assert servico_de_sincronizacao(caminho, "win32", ONEDRIVE_DO_WINDOWS, nada_existe) == servico


@pytest.mark.parametrize(
    ("caminho", "servico"),
    [
        ("/home/joao/Dropbox/GastroEpi", DROPBOX),
        ("/home/joao/OneDrive/GastroEpi", ONEDRIVE),
        ("/home/joao/Google Drive/GastroEpi", GOOGLE_DRIVE),
        ("/run/user/1000/gvfs/google-drive:host=gmail.com,user=joao/GastroEpi", GOOGLE_DRIVE),
        ("/run/user/1000/gvfs/onedrive:host=x,user=joao/GastroEpi", ONEDRIVE),
        ("/home/joao/Library/Mobile Documents/com~apple~CloudDocs/GastroEpi", ICLOUD),
    ],
)
def test_linux_acusa_as_pastas_sincronizadas(caminho: str, servico: str) -> None:
    assert servico_de_sincronizacao(caminho, "linux", {}, nada_existe) == servico


@pytest.mark.parametrize(
    ("caminho", "sistema"),
    [
        (r"C:\Users\Joao\Documents\GastroEpi", "win32"),
        (r"C:\Users\Joao\OneDriveAntigo\GastroEpi", "win32"),  # nome só parecido
        (r"D:\GastroEpi", "win32"),
        ("/home/joao/GastroEpi", "linux"),
        ("/home/joao/drive-velho/GastroEpi", "linux"),
    ],
)
def test_pastas_comuns_nao_sao_acusadas(caminho: str, sistema: str) -> None:
    assert servico_de_sincronizacao(caminho, sistema, ONEDRIVE_DO_WINDOWS, nada_existe) is None


def test_dropbox_com_a_pasta_renomeada_e_achado_pelo_marcador() -> None:
    marcadores = {r"E:\Arquivos da clinica\.dropbox", "/home/joao/nuvem/.dropbox.cache"}

    def existe(caminho: str) -> bool:
        return caminho in marcadores

    assert servico_de_sincronizacao(r"E:\Arquivos da clinica\GastroEpi", "win32", {}, existe) == (
        DROPBOX
    )
    assert servico_de_sincronizacao("/home/joao/nuvem/a/GastroEpi", "linux", {}, existe) == DROPBOX


def test_variavel_vazia_do_onedrive_nao_acusa_tudo() -> None:
    ambiente = {"OneDrive": "", "OneDriveConsumer": "  "}

    assert servico_de_sincronizacao(r"C:\GastroEpi", "win32", ambiente, nada_existe) is None
