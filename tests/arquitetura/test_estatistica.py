"""Fitness functions da estatística (Princípio IV; ADR-0004, Governança).

- Toda função pública de `estatistica/` é chamada por ao menos um teste marcado
  `@pytest.mark.referencia`, cujo docstring cita o valor de referência (R, Epi Info, artigo).
- Nenhum arquivo de `estatistica/` lê texto livre (`observacao`, `laudo_texto`, "outra").

"Chamada" é sintática: o nome da função aparece numa chamada dentro do teste marcado.
Passar por outra função não conta, de propósito: cada rotina tem o seu valor citado.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESTATISTICA = RAIZ / "src" / "gastroepi" / "estatistica"
TESTES = RAIZ / "tests" / "estatistica"

# Arquivos sem rotina estatística. Toda entrada precisa de motivo.
ISENTOS = {
    "entrada.py": "exceções e conferência de entrada (test_entrada.py)",
    "variaveis.py": "só lê campos do domínio; não calcula nada",
}
TEXTO_LIVRE = {"observacao", "laudo_texto", "indicacao_outra", "motivo_outro", "histologia_outra"}


def funcoes_publicas(pasta: Path) -> dict[str, str]:
    """Nome → arquivo de cada função pública de módulo (as de classe ficam de fora)."""
    publicas: dict[str, str] = {}
    for caminho in sorted(pasta.glob("*.py")):
        if caminho.name in ISENTOS or caminho.name == "__init__.py":
            continue
        for no in ast.parse(caminho.read_text(encoding="utf-8")).body:
            if isinstance(no, ast.FunctionDef) and not no.name.startswith("_"):
                publicas[no.name] = caminho.name
    return publicas


def _marcado_referencia(funcao: ast.FunctionDef) -> bool:
    for decorador in funcao.decorator_list:
        alvo = decorador.func if isinstance(decorador, ast.Call) else decorador
        if isinstance(alvo, ast.Attribute) and alvo.attr == "referencia":
            return True
    return False


def _chamadas(funcao: ast.FunctionDef) -> set[str]:
    nomes: set[str] = set()
    for no in ast.walk(funcao):
        if isinstance(no, ast.Call):
            alvo = no.func
            nomes.add(alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", ""))
    return nomes


def chamadas_em_testes_de_referencia(pasta: Path) -> set[str]:
    chamadas: set[str] = set()
    for caminho in sorted(pasta.glob("test_*.py")):
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.FunctionDef) and _marcado_referencia(no):
                chamadas |= _chamadas(no)
    return chamadas


def funcoes_sem_referencia(fontes: Path, testes: Path) -> list[str]:
    cobertas = chamadas_em_testes_de_referencia(testes)
    return [
        f"{arq}: {nome}()" for nome, arq in funcoes_publicas(fontes).items() if nome not in cobertas
    ]


def test_toda_funcao_publica_da_estatistica_tem_teste_de_referencia() -> None:
    """Princípio IV: rotina estatística sem valor de referência citado não entra."""
    faltando = funcoes_sem_referencia(ESTATISTICA, TESTES)
    assert not faltando, "sem teste @pytest.mark.referencia:\n" + "\n".join(faltando)


def test_a_fitness_acusa_funcao_plantada_sem_teste(tmp_path: Path) -> None:
    fontes, testes = tmp_path / "estatistica", tmp_path / "testes"
    fontes.mkdir()
    testes.mkdir()
    (fontes / "media.py").write_text("def media(x):\n    return x\n\ndef _aux():\n    pass\n")
    (fontes / "plantada.py").write_text("def plantada():\n    return 1\n")
    (testes / "test_media.py").write_text(
        "import pytest\n\n@pytest.mark.referencia\ndef test_media():\n    assert media(1) == 1\n\n"
        "def test_sem_marca():\n    assert plantada() == 1\n"
    )
    assert funcoes_sem_referencia(fontes, testes) == ["plantada.py: plantada()"]


def test_estatistica_nao_le_texto_livre() -> None:
    """ADR-0004, Governança: texto livre é só consulta e nunca entra em cálculo."""
    acessos = []
    for caminho in sorted(ESTATISTICA.glob("*.py")):
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            nome = no.attr if isinstance(no, ast.Attribute) else getattr(no, "value", None)
            if nome in TEXTO_LIVRE:
                acessos.append(f"{caminho.name}:{getattr(no, 'lineno', '?')}: {nome}")
    assert not acessos, "estatistica lê texto livre:\n" + "\n".join(acessos)
