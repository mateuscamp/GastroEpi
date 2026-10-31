"""Mede quanto tempo o app leva para listar 10 mil pacientes fictícios (PLANO, Fase 2).

Cria um cofre temporário pela porta das cascas (`servicos`), cadastra os fictícios um a
um (cada cadastro na sua transação, com o evento de auditoria) e cronometra listar,
buscar e verificar. Desde a Fase 4, também a abertura (Argon2id + `quick_check`) e o
backup conferido (ADR-0005). Uso:

    uv run python ferramentas/medir_listagem.py [quantidade] [pasta-base]

A pasta-base importa para o cadastro: num tmpfs o fsync de cada transação não custa nada.
"""

import platform
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import durabilidade, integridade, pacientes
from gastroepi.servicos.acesso import NOME_DO_BANCO, criar_cofre, desbloquear

SENHA = "senha da medição"
REPETICOES = 3


def cronometrar(rotulo: str, acao: Callable[[], object]) -> None:
    tempos = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        acao()
        tempos.append(time.perf_counter() - inicio)
    print(f"{rotulo}: mediana {statistics.median(tempos):.3f} s (de {REPETICOES})")


def medir(pasta: Path, quantidade: int) -> None:
    fichas = gerar_fichas(semente=2026, quantidade=quantidade)
    sessao, _ = criar_cofre(pasta, SENHA, SENHA)
    with sessao:
        inicio = time.perf_counter()
        for ficha in fichas:
            pacientes.cadastrar(sessao, ficha, usuario="medicao")
        gasto = time.perf_counter() - inicio
        print(f"cadastrar {quantidade}: {gasto:.1f} s ({1000 * gasto / quantidade:.2f} ms cada)")
        exames = sum(len(f.exames) for f in fichas)
        lesoes = sum(len(e.lesoes) for f in fichas for e in f.exames)
        print(f"base: {quantidade} pacientes, {exames} exames, {lesoes} lesões")
        cronometrar(f"listar {quantidade} fichas completas", lambda: pacientes.listar(sessao))
        cronometrar("buscar 1 ficha", lambda: pacientes.buscar(sessao, quantidade // 2))
        cronometrar("verificar (páginas, cadeia e dados)", lambda: integridade.verificar(sessao))
        cronometrar("backup conferido + rotação", lambda: durabilidade.fazer_backup(sessao))
    cronometrar("abrir (Argon2id + quick_check)", lambda: desbloquear(pasta, SENHA).fechar())
    tamanho = (pasta / NOME_DO_BANCO).stat().st_size / 2**20
    print(f"gastroepi.db: {tamanho:.1f} MiB")


def principal() -> int:
    quantidade = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    base = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"Python {platform.python_version()}, {platform.system()} {platform.machine()}")
    with tempfile.TemporaryDirectory(dir=base, prefix="medicao-") as pasta:
        medir(Path(pasta), quantidade)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
