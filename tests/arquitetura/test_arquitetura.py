"""Fitness functions atômicas do projeto.

Cada teste aqui verifica uma DECISÃO registrada em docs/adr/, não o domínio.
Falha aqui significa que a arquitetura foi atravessada, não que a feature quebrou.
As fronteiras entre módulos ficam nos contratos do import-linter (pyproject.toml);
aqui fica o que o import-linter não mede.

Ao ajustar um limite, ajustar também o ADR correspondente: número que muda sem
registro é número que não governa nada.
"""

from __future__ import annotations

import ast
import importlib
import socket
from pathlib import Path

import pytest
from pytest_socket import SocketBlockedError

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = "gastroepi"
SRC = RAIZ / "src" / PACOTE

LIMITE_LINHAS_ARQUIVO = 400  # ADR-0002: cabe em uma leitura do agente
LIMITE_LINHAS_FUNCAO = 40  # ADR-0002: teto duro; o alvo no AGENTS.md é 20

# Nome genérico devolve dezenas de hits no grep e obriga o agente a ler todos.
NOMES_PROIBIDOS = {
    "dados", "dado", "info", "util", "utils", "helper", "helpers", "manager",
    "handler", "processar", "base", "comum", "item", "obj", "data", "service",
}  # fmt: skip

# ADR-0002: as fronteiras são exatamente estas pastas. Pacote novo exige ADR antes.
FRONTEIRAS = {
    "dominio", "cofre", "auditoria", "persistencia", "estatistica", "exportacao",
    "servicos", "ui_qt", "cli",
}  # fmt: skip

# Exceções conscientes. Toda entrada precisa de motivo e ADR.
ISENCOES: dict[str, str] = {}


def relativo(caminho: Path) -> str:
    return caminho.relative_to(RAIZ).as_posix()


def arquivos_python() -> list[Path]:
    return [c for c in sorted(SRC.rglob("*.py")) if relativo(c) not in ISENCOES]


def arvores() -> list[tuple[Path, ast.Module]]:
    return [
        (caminho, ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho)))
        for caminho in arquivos_python()
    ]


def modulo_importado(no: ast.AST) -> str | None:
    """Devolve o caminho interno (ex.: 'dominio/cpf') de um import do pacote."""
    nome: str | None = None
    if isinstance(no, ast.Import):
        nome = next((a.name for a in no.names if a.name.startswith(f"{PACOTE}.")), None)
    elif isinstance(no, ast.ImportFrom) and no.module and no.module.startswith(f"{PACOTE}."):
        nome = no.module
    return nome[len(PACOTE) + 1 :].replace(".", "/") if nome else None


def grafo_de_imports() -> dict[str, set[str]]:
    grafo: dict[str, set[str]] = {}
    for caminho, arvore in arvores():
        modulo = caminho.relative_to(SRC).with_suffix("").as_posix()
        grafo[modulo] = {alvo for no in ast.walk(arvore) if (alvo := modulo_importado(no))}
    return grafo


def ciclos_em(grafo: dict[str, set[str]]) -> list[str]:
    ciclos: list[str] = []
    pilha: list[str] = []
    vistos: set[str] = set()

    def visitar(no: str) -> None:
        if no in pilha:
            ciclos.append(" → ".join([*pilha[pilha.index(no) :], no]))
            return
        if no in vistos or no not in grafo:
            return
        pilha.append(no)
        for vizinho in grafo[no]:
            visitar(vizinho)
        pilha.pop()
        vistos.add(no)

    for modulo in grafo:
        visitar(modulo)
    return sorted(set(ciclos))


def tokens_do_nome(nome: str) -> list[str]:
    """Quebra CamelCase e snake_case em palavras minúsculas."""
    palavras: list[str] = []
    for pedaco in nome.split("_"):
        atual = ""
        for letra in pedaco:
            if letra.isupper() and atual:
                palavras.append(atual.lower())
                atual = letra
            else:
                atual += letra
        if atual:
            palavras.append(atual.lower())
    return palavras


def test_fronteiras_da_arvore_sao_as_do_adr() -> None:
    """Regra 8 da skill: fronteira que não aparece na árvore de diretórios não é fronteira."""
    pastas = {p.name for p in SRC.iterdir() if (p / "__init__.py").is_file()}
    assert pastas == FRONTEIRAS, f"sobrando: {pastas - FRONTEIRAS}; faltando: {FRONTEIRAS - pastas}"


@pytest.mark.parametrize("fronteira", sorted(FRONTEIRAS))
def test_cada_fronteira_declara_o_seu_contrato(fronteira: str) -> None:
    modulo = importlib.import_module(f"{PACOTE}.{fronteira}")
    assert modulo.__doc__, f"{PACOTE}.{fronteira} sem docstring dizendo o que pode importar"


def test_arquivos_cabem_em_uma_leitura() -> None:
    """ADR-0002: arquivo grande obriga o agente a paginar e fragmenta o raciocínio."""
    grandes = [
        f"{relativo(c)}: {n} linhas (limite {LIMITE_LINHAS_ARQUIVO})"
        for c in arquivos_python()
        if (n := len(c.read_text(encoding="utf-8").splitlines())) > LIMITE_LINHAS_ARQUIVO
    ]
    assert not grandes, "\n" + "\n".join(grandes)


def test_funcoes_dentro_do_teto() -> None:
    longas = []
    for caminho, arvore in arvores():
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
                tamanho = (no.end_lineno or no.lineno) - no.lineno + 1
                if tamanho > LIMITE_LINHAS_FUNCAO:
                    longas.append(
                        f"{relativo(caminho)}:{no.lineno}: {no.name}() tem "
                        f"{tamanho} linhas (teto {LIMITE_LINHAS_FUNCAO})"
                    )
    assert not longas, "\n" + "\n".join(longas)


def test_nomes_publicos_sao_grepaveis() -> None:
    ruins = []
    for caminho, arvore in arvores():
        for no in ast.walk(arvore):
            if not isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            palavras = tokens_do_nome(no.name)
            if not no.name.startswith("_") and palavras and set(palavras) <= NOMES_PROIBIDOS:
                ruins.append(f"{relativo(caminho)}:{no.lineno}: nome genérico '{no.name}'")
    assert not ruins, "\n" + "\n".join(ruins)


def test_sem_ciclo_entre_modulos() -> None:
    """Ciclo é acoplamento que nenhum refactor local resolve."""
    ciclos = ciclos_em(grafo_de_imports())
    assert not ciclos, "ciclos de import:\n" + "\n".join(ciclos)


@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket")
def test_suite_roda_sem_rede() -> None:
    """Princípio I: se alguém tirar --disable-socket do pyproject, este teste acusa."""
    with pytest.raises(SocketBlockedError):
        socket.socket()
