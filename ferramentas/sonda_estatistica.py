"""Sonda do peso da estatística no executável congelado (ADR-0002: instalador ≤ 250 MB).

O CI congela este script com PyInstaller em windows-latest, roda o executável e mede a
pasta. Com `--3b`, também carrega o statsmodels (e o pandas que ele puxa) e ajusta uma
regressão logística mínima: é a projeção do peso da Fase 3b, que vai usá-los.
Usa só a base fictícia com semente; sai com 0 se os cálculos rodam, 1 se não.
"""

import importlib
import sys

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.estatistica.qualidade import indicadores_por_examinador
from gastroepi.estatistica.tabela_2x2 import tabela_2x2


def sondar_3b() -> None:
    """Import dinâmico: o mypy não precisa dos tipos do statsmodels, e o PyInstaller o
    recebe por --hidden-import no job."""
    numpy = importlib.import_module("numpy")
    api = importlib.import_module("statsmodels.api")
    x = api.add_constant(numpy.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]))
    y = numpy.array([0, 0, 1, 0, 1, 0, 1, 1])
    print(
        f"statsmodels {api.__version__ if hasattr(api, '__version__') else ''} logit ok:",
        api.Logit(y, x).fit(disp=0).params.round(3).tolist(),
    )


def main(argumentos: list[str]) -> int:
    indicadores = indicadores_por_examinador(gerar_fichas(1, 200))
    fisher = tabela_2x2(3, 1, 1, 3).p_valor_fisher
    if len(indicadores) != 4 or abs(fisher - 0.4857) > 1e-4:
        print("sonda FALHOU: cálculo inesperado", file=sys.stderr)
        return 1
    if "--3b" in argumentos:
        sondar_3b()
    print(f"sonda ok: {len(indicadores)} examinadores, Fisher {fisher:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
