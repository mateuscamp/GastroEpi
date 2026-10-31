# PyInstaller, modo onedir e janela (ADR-0006). Rodar da raiz do repositório:
#   uv run --group empacotamento pyinstaller --noconfirm empacotamento/gastroepi.spec
# Onefile não: descompactaria ~270 MB no %TEMP% a cada abertura e dispara mais antivírus.
# Os hooks do PyInstaller já acham Qt, numpy, scipy e sqlcipher3. Import que o congelado não
# achar entra em `hiddenimports`, com o motivo ao lado; o `--smoke` do CI é o portão.

from pathlib import Path

PASTA = Path(SPECPATH)  # noqa: F821 (definido pelo PyInstaller)

analise = Analysis(  # noqa: F821
    [str(PASTA / "entrada.py")],
    hiddenimports=[],
    # O app usa só QtCore, QtGui e QtWidgets; o resto do Qt nem é importado.
    excludes=["tkinter", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick"],
    noarchive=False,
)
pyz = PYZ(analise.pure)  # noqa: F821
executavel = EXE(  # noqa: F821
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="GastroEpi",
    console=False,
    upx=False,  # UPX aumenta o falso positivo de antivírus
    icon=str(PASTA / "icone.ico"),
)
COLLECT(  # noqa: F821
    executavel,
    analise.binaries,
    analise.datas,
    name="GastroEpi",
    upx=False,
)
