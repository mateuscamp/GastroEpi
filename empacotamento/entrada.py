"""Ponto de entrada do `GastroEpi.exe` congelado (ADR-0006): o mesmo `main` da CLI.

Sem argumento abre o app; `--smoke` é o autoteste que o CI roda no executável instalado.
"""

import sys

from gastroepi.cli.principal import main

if __name__ == "__main__":
    sys.exit(main())
