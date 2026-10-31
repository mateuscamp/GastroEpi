"""Fixtures da estatística: as referências do R, o oráculo v0.1.16 e a base do oráculo
convertida para o domínio estruturado (ADR-0004).

`referencias_r.json` sai de ferramentas/referencias_r/gerar.R no CI (job referencias-r),
com 15 algarismos significativos; por isso a tolerância relativa é 1e-9.
"""

import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from gastroepi.dominio.exame import Exame, Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.lesao import ADENOMAS_CONVENCIONAIS, Lesao
from gastroepi.dominio.listas import UF, Displasia, Histologia, Indicacao, Paris, Segmento, Sexo
from gastroepi.dominio.paciente import Paciente

FIXTURES = Path(__file__).parents[1] / "fixtures"
TOLERANCIA = 1e-9

type Json = Any  # JSON lido do disco: a forma é conferida pelos próprios testes


@cache
def referencias_r() -> Json:
    return json.loads((FIXTURES / "referencias_r.json").read_text(encoding="utf-8"))


@cache
def oraculo() -> Json:
    # json.loads aceita Infinity, que a v0.1.16 devolve de propósito.
    return json.loads((FIXTURES / "oraculo_rust_v0_1_16.json5").read_text(encoding="utf-8"))


def aprox(valor: object) -> object:
    return pytest.approx(valor, rel=TOLERANCIA, abs=1e-12)


# O texto livre da v0.1.16 vira a histologia da lista; o texto original fica no
# laudo_texto, que não entra em cálculo.
HISTOLOGIA_DO_TEXTO = {
    "adenoma tubular com displasia de baixo grau": Histologia.TUBULAR,
    "pólipo hiperplásico": Histologia.HIPERPLASICO,
    "adenoma tubuloviloso": Histologia.TUBULOVILOSO,
    "lesão serrilhada séssil": Histologia.SERRILHADA_SESSIL,
    "adenocarcinoma invasivo": Histologia.ADENOCARCINOMA,
    "mucosa colônica sem alterações; ausência de adenoma": Histologia.SEM_HISTOLOGIA,
    "adenoma viloso": Histologia.VILOSO,
}
SEM_EXAMINADOR = Examinador(nome="Não informado na v0.1.16", crm="999999", uf=UF.SP)


def _examinador(nome: str | None) -> Examinador:
    if not nome:
        return SEM_EXAMINADOR
    return Examinador(nome=nome, crm=str(100000 + len(nome)), uf=UF.SP)


def _lesoes(n: int, texto: str | None) -> tuple[Lesao, ...]:
    histologia = HISTOLOGIA_DO_TEXTO[texto.lower()] if texto else Histologia.SEM_HISTOLOGIA
    displasia = Displasia.BAIXO if histologia in ADENOMAS_CONVENCIONAIS else Displasia.NAO_SE_APLICA
    lesao = Lesao(
        segmento=Segmento.SIGMOIDE,
        tamanho_mm=5,
        paris=Paris.IS,
        histologia=histologia,
        displasia=displasia,
        laudo_texto=texto,
    )
    return (lesao,) * n


def ficha_do_oraculo(p: Json) -> Ficha:
    """Paciente da v0.1.16 → ficha com um exame. Nascimento no mesmo dia e mês do exame,
    para a idade no exame ser a idade digitada. Pólipo 0 com laudo (a incoerência do
    ADR-0004) vira exame sem lesão: o laudo sem lesão não tem onde morar."""
    exame_em = date.fromisoformat(p["data_exame"])
    indicacao = (
        Indicacao.RASTREIO_RISCO_MEDIO
        if p["indicacao_exame"] == "Rastreio"
        else Indicacao.DIAGNOSTICA_POR_SINTOMAS
    )
    paciente = Paciente(
        prontuario=p["numero_prontuario"],
        nome=p["nome"],
        sexo=Sexo(p["sexo"]),
        data_nascimento=exame_em.replace(year=exame_em.year - p["idade"]),
        comorbidades=tuple(p["comorbidades"]),
    )
    exame = Exame(
        data_exame=exame_em,
        indicacao=indicacao,
        examinador=_examinador(p["examinador"]),
        intubacao_cecal=True,
        sintomas=tuple(p["sintomas"]),
        lesoes=_lesoes(p["polipo"], p["resultado_histopatologico"]),
    )
    return Ficha(paciente=paciente, exames=(exame,))


@cache
def fichas_do_oraculo() -> tuple[Ficha, ...]:
    return tuple(ficha_do_oraculo(p) for p in oraculo()["pacientes_ficticios"])
