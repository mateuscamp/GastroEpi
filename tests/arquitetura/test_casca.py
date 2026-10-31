"""Fitness da casca Qt (Fase 5): o que o import-linter não mede.

- Nenhum `connect` recebe lambda ou função aninhada. Com o `self` capturado, o PySide 6.12
  derruba o processo (segfault) quando o Python recolhe a janela: achado da Fase 5, visto
  num `restaurar_pedido.connect(lambda: ...)`. Método ligado não tem o problema.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CASCA = RAIZ / "src" / "gastroepi" / "ui_qt"


def _funcoes_aninhadas(arvore: ast.Module) -> set[str]:
    nomes: set[str] = set()
    for externa in ast.walk(arvore):
        if isinstance(externa, ast.FunctionDef):
            nomes |= {n.name for n in ast.walk(externa) if isinstance(n, ast.FunctionDef)} - {
                externa.name
            }
    return nomes


def conexoes_com_closure(fonte: str) -> list[int]:
    arvore = ast.parse(fonte)
    aninhadas = _funcoes_aninhadas(arvore)
    linhas = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
            continue
        if no.func.attr != "connect" or not no.args:
            continue
        alvo = no.args[0]
        if isinstance(alvo, ast.Lambda) or (isinstance(alvo, ast.Name) and alvo.id in aninhadas):
            linhas.append(no.lineno)
    return linhas


def test_regra_acusa_lambda_e_funcao_aninhada() -> None:
    fonte = (
        "def f(self):\n"
        "    def g():\n"
        "        pass\n"
        "    self.b.clicked.connect(lambda: self.x())\n"
        "    self.b.clicked.connect(g)\n"
        "    self.b.clicked.connect(self.x)\n"
    )
    assert conexoes_com_closure(fonte) == [4, 5]


def test_casca_nao_conecta_closure_em_sinal() -> None:
    achados = [
        f"{caminho.relative_to(RAIZ)}:{linha}"
        for caminho in sorted(CASCA.glob("*.py"))
        for linha in conexoes_com_closure(caminho.read_text(encoding="utf-8"))
    ]
    assert not achados, "connect com lambda/closure (use um método):\n" + "\n".join(achados)
