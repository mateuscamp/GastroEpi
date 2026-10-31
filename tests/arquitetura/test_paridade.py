"""Paridade com a v0.1.16 (PLANO, Fase 5): os 35 comandos Tauri têm destino em `servicos`
e são alcançáveis por uma tela.

"Alcançável" aqui é verificável por máquina: a função de destino existe no módulo de
`servicos` e a casca `ui_qt` importa esse módulo e cita a função. Quem percorre cada tela
de verdade são os testes de tests/ui_qt.

Três comandos não têm função própria, de propósito:
- `esta_desbloqueado`: na casca, desbloqueado é ter uma `Sessao` aberta.
- as três verificações da v0.1.16 viraram `integridade.verificar`, que roda páginas
  (física), cadeia e dados de uma vez.
- `buscar_paciente_por_termo`: o filtro da tabela aplica `corresponde_ao_termo`, a mesma
  regra de `pacientes.buscar_por_termo`, sem reler o banco a cada tecla.
"""

import ast
import importlib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CASCA = RAIZ / "src" / "gastroepi" / "ui_qt"

# comando da v0.1.16 → (módulo de servicos, função ou classe que a casca usa)
PARIDADE: dict[str, tuple[str, str]] = {
    # Acesso (7)
    "tem_senha_configurada": ("acesso", "cofre_existe"),
    "configurar_senha": ("acesso", "criar_cofre"),
    "desbloquear": ("acesso", "desbloquear"),
    "desbloquear_com_chave": ("acesso", "recuperar_acesso"),
    "esta_desbloqueado": ("acesso", "Sessao"),
    "obter_nome_usuario": ("acesso", "nome_do_usuario"),
    "definir_nome_usuario": ("acesso", "definir_nome_do_usuario"),
    # Pacientes (7)
    "listar_pacientes": ("pacientes", "listar"),
    "buscar_paciente": ("pacientes", "buscar"),
    "buscar_paciente_por_prontuario": ("pacientes", "buscar_por_prontuario"),
    "buscar_paciente_por_termo": ("pacientes", "corresponde_ao_termo"),
    "cadastrar_paciente": ("pacientes", "cadastrar"),
    "editar_paciente": ("pacientes", "editar"),
    "excluir_paciente": ("pacientes", "excluir"),
    # Catálogos (4)
    "listar_comorbidades_catalogo": ("pacientes", "listar_comorbidades"),
    "adicionar_comorbidade_catalogo": ("pacientes", "adicionar_comorbidade"),
    "listar_sintomas_catalogo": ("pacientes", "listar_sintomas"),
    "adicionar_sintoma_catalogo": ("pacientes", "adicionar_sintoma"),
    # Integridade (5)
    "listar_auditoria": ("pacientes", "listar_auditoria"),
    "verificar_integridade": ("integridade", "verificar"),
    "verificar_integridade_dados": ("integridade", "verificar"),
    "diagnosticar_integridade_fisica": ("integridade", "verificar"),
    "realizar_backup": ("durabilidade", "fazer_backup"),
    # Calculadoras (7)
    "calcular_tabela_2x2": ("calculadoras", "calcular_tabela_2x2"),
    "calcular_teste_diagnostico": ("calculadoras", "calcular_teste_diagnostico"),
    "calcular_amostra_survey": ("calculadoras", "calcular_amostra_inquerito"),
    "calcular_amostra_comparativa": ("calculadoras", "calcular_amostra_comparativa"),
    "calcular_tendencia_cochran_armitage": ("calculadoras", "calcular_tendencia"),
    "calcular_mantel_haenszel": ("calculadoras", "calcular_mantel_haenszel"),
    "calcular_qui_quadrado_geral": ("calculadoras", "calcular_qui_quadrado_geral"),
    # Estatística do banco (4)
    "obter_indicadores_qualidade": ("indicadores", "indicadores_de_qualidade"),
    "obter_frequencias": ("indicadores", "painel"),
    "obter_estratificacao": ("indicadores", "estratificacao"),
    "obter_prevalencia_polipo": ("indicadores", "prevalencia_polipo"),
    # Exportação (1)
    "exportar_pacientes_csv": ("exportar", "exportar_csv"),
}


def _nomes_e_modulos_da_casca() -> tuple[set[str], set[str]]:
    nomes: set[str] = set()
    modulos: set[str] = set()
    for caminho in CASCA.glob("*.py"):
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Attribute):
                nomes.add(no.attr)
            elif isinstance(no, ast.ImportFrom) and no.module:
                modulos.add(no.module)
                nomes |= {a.name for a in no.names}
                modulos |= {f"{no.module}.{a.name}" for a in no.names}
    return nomes, modulos


NOMES, MODULOS = _nomes_e_modulos_da_casca()


def test_sao_os_35_comandos_da_v0_1_16() -> None:
    comandos_rust = (RAIZ / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    registrados = {
        linha.strip().rstrip(",").removeprefix("commands::")
        for linha in comandos_rust.splitlines()
        if linha.strip().startswith("commands::")
    }
    assert len(PARIDADE) == 35
    assert set(PARIDADE) == registrados


@pytest.mark.parametrize(("comando", "destino"), sorted(PARIDADE.items()))
def test_comando_tem_destino_em_servicos_alcancavel_pela_casca(
    comando: str, destino: tuple[str, str]
) -> None:
    modulo, funcao = destino
    caminho = f"gastroepi.servicos.{modulo}"

    assert hasattr(importlib.import_module(caminho), funcao), f"{comando}: {caminho}.{funcao}"
    assert caminho in MODULOS, f"{comando}: a casca não importa {caminho}"
    assert funcao in NOMES, f"{comando}: a casca não usa {funcao}"
