"""Os fixtures do oráculo v0.1.16 existem e são legíveis (ADR-0002, Fase 0).

São a referência dos testes de paridade das Fases 1 e 3. O código que os gerou saiu no
corte (Fase 7) e não está neste repositório; a fonte de cada um é a v0.1.16
(`ferramentas/oraculo_rust/` para math/, `src/validation.ts` no Node). Não são regerados.
"""

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

GRUPOS_ESTATISTICOS = {
    "wilson_ci", "fisher_exact_2x2", "tabela_2x2", "analise_teste_diagnostico",
    "amostra_survey", "amostra_comparativa", "tendencia_cochran_armitage",
    "mantel_haenszel", "analisar_contingencia_geral", "descritivas",
    "prevalencia_polipo", "frequencias", "estratificar", "tabular_cruzado",
    "indicadores_por_examinador",
}  # fmt: skip


def test_oraculo_estatistico_cobre_todas_as_funcoes_de_math() -> None:
    # json.loads aceita Infinity/NaN, que a v0.1.16 devolve de propósito.
    oraculo = json.loads((FIXTURES / "oraculo_rust_v0_1_16.json5").read_text(encoding="utf-8"))

    assert oraculo["versao"] == "v0.1.16"
    assert {g for g in GRUPOS_ESTATISTICOS if oraculo.get(g)} == GRUPOS_ESTATISTICOS
    assert len(oraculo["pacientes_ficticios"]) == 24


def test_vetores_de_validacao_vem_do_validation_ts() -> None:
    vetores = json.loads((FIXTURES / "vetores_validacao_v0_1_16.json").read_text(encoding="utf-8"))

    assert vetores["origem"].startswith("src/validation.ts")
    assert any(v["valido"] for v in vetores["cpf"])
    assert not all(v["valido"] for v in vetores["cpf"])
    assert {"entrada", "valida", "iso"} <= vetores["data_exame"][0].keys()
