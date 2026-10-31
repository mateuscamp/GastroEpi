"""CSV para análise (ADR-0004): uma linha por exame, sem identificar o paciente.

Escolha do dono (2026-10-31): a exportação da tela é só esta, anônima. Saem nome, CPF,
prontuário, data de nascimento e todo texto livre (observação, laudo e as descrições de
"outra"), que pode conter um nome. A data do exame vira o ano. O paciente vira um número
sequencial, que só serve para ligar os exames do mesmo paciente dentro do arquivo.

Formato pt-BR, que o Excel abre direto: UTF-8 com BOM, `;` separando colunas, vírgula
decimal. Toda célula passa por `proteger_celula` (injeção de fórmula, OWASP "CSV
Injection").
"""

from collections.abc import Callable, Iterable

from gastroepi.dominio.exame import Exame, idade_no_exame
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.paciente import Paciente

SEPARADOR = ";"
BOM = "﻿"
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")

type Coluna = tuple[str, str, Callable[[Paciente, Exame], str]]


def _sim_nao(valor: bool | None) -> str:
    return "" if valor is None else ("sim" if valor else "não")


def _decimal(valor: float | None) -> str:
    return "" if valor is None else f"{valor:g}".replace(".", ",")


def _boston(exame: Exame, segmento: str) -> str:
    return "" if exame.preparo is None else str(getattr(exame.preparo, segmento))


def _maior_lesao(exame: Exame) -> str:
    return str(max(lesao.tamanho_mm for lesao in exame.lesoes)) if exame.lesoes else ""


def _primeiro_grau(paciente: Paciente) -> bool:
    return any(parente.grau == 1 for parente in paciente.historico_familiar)


COLUNAS: tuple[Coluna, ...] = (
    ("sexo", "M ou F", lambda p, e: p.sexo.value),
    ("idade_no_exame", "Anos completos na data do exame", lambda p, e: str(idade_no_exame(p, e))),
    ("ano_exame", "Ano do exame (a data completa não sai)", lambda p, e: str(e.data_exame.year)),
    ("indicacao", "Código da indicação (lista fechada)", lambda p, e: e.indicacao.value),
    (
        "examinador_crm",
        "CRM-UF do examinador",
        lambda p, e: f"{e.examinador.crm}-{e.examinador.uf}",
    ),
    (
        "historico_familiar",
        "Algum parente com câncer colorretal",
        lambda p, e: _sim_nao(bool(p.historico_familiar)),
    ),
    (
        "historico_1o_grau",
        "Parente de 1º grau com câncer colorretal",
        lambda p, e: _sim_nao(_primeiro_grau(p)),
    ),
    (
        "boston_direito",
        "Boston, cólon direito (0-3; vazio se não registrado)",
        lambda p, e: _boston(e, "direito"),
    ),
    ("boston_transverso", "Boston, transverso (0-3)", lambda p, e: _boston(e, "transverso")),
    ("boston_esquerdo", "Boston, cólon esquerdo (0-3)", lambda p, e: _boston(e, "esquerdo")),
    (
        "preparo_adequado",
        "Boston ≥ 6 e cada segmento ≥ 2",
        lambda p, e: _sim_nao(e.preparo_adequado),
    ),
    ("intubacao_cecal", "Ceco alcançado", lambda p, e: _sim_nao(e.intubacao_cecal)),
    (
        "motivo_nao_intubacao",
        "Código do motivo, se o ceco não foi alcançado",
        lambda p, e: e.motivo_nao_intubacao or "",
    ),
    (
        "tempo_retirada_min",
        "Minutos (vazio se não registrado)",
        lambda p, e: _decimal(e.tempo_retirada_min),
    ),
    ("n_polipos", "Lesões registradas", lambda p, e: str(e.n_polipos)),
    (
        "n_adenomas",
        "Adenomas convencionais",
        lambda p, e: str(sum(x.adenoma_convencional for x in e.lesoes)),
    ),
    (
        "adenoma_avancado",
        "Algum adenoma avançado (USMSTF 2020)",
        lambda p, e: _sim_nao(any(x.adenoma_avancado for x in e.lesoes)),
    ),
    (
        "serrilhada",
        "Alguma lesão serrilhada",
        lambda p, e: _sim_nao(any(x.serrilhada for x in e.lesoes)),
    ),
    ("maior_lesao_mm", "Tamanho da maior lesão (mm)", lambda p, e: _maior_lesao(e)),
    (
        "aguardando_histologia",
        "Alguma lesão sem o laudo",
        lambda p, e: _sim_nao(e.aguardando_histologia),
    ),
)


def proteger_celula(texto: str) -> str:
    """Célula que começa como fórmula ganha um apóstrofo; com `;`, aspas ou quebra de
    linha, vai entre aspas (RFC 4180, aspas dobradas)."""
    if texto.startswith(_INICIO_DE_FORMULA):
        texto = "'" + texto
    if any(c in texto for c in (SEPARADOR, '"', "\n", "\r")):
        texto = '"' + texto.replace('"', '""') + '"'
    return texto


def _linha(celulas: Iterable[str]) -> str:
    return SEPARADOR.join(proteger_celula(c) for c in celulas) + "\r\n"


def _nomes(fichas: Iterable[Ficha], campo: Callable[[Ficha], Iterable[str]]) -> list[str]:
    return sorted({nome for ficha in fichas for nome in campo(ficha)}, key=str.casefold)


def _comorbidades(ficha: Ficha) -> tuple[str, ...]:
    return ficha.paciente.comorbidades


def _sintomas(ficha: Ficha) -> tuple[str, ...]:
    return tuple(s for exame in ficha.exames for s in exame.sintomas)


def csv_de_analise(fichas: Iterable[Ficha]) -> str:
    """O arquivo inteiro. Comorbidades e sintomas viram uma coluna sim/não por item visto."""
    fichas = list(fichas)
    comorbidades, sintomas = _nomes(fichas, _comorbidades), _nomes(fichas, _sintomas)
    cabecalho = ["paciente", "exame", *(c[0] for c in COLUNAS)]
    cabecalho += [f"comorbidade: {n}" for n in comorbidades] + [f"sintoma: {n}" for n in sintomas]
    partes = [BOM + _linha(cabecalho)]
    for numero, ficha in enumerate(fichas, start=1):
        for ordem, exame in enumerate(ficha.exames, start=1):
            celulas = [str(numero), str(ordem), *(c[2](ficha.paciente, exame) for c in COLUNAS)]
            celulas += [_sim_nao(n in ficha.paciente.comorbidades) for n in comorbidades]
            celulas += [_sim_nao(n in exame.sintomas) for n in sintomas]
            partes.append(_linha(celulas))
    return "".join(partes)


def dicionario_de_dados() -> str:
    """O que cada coluna significa, no mesmo formato do CSV."""
    linhas = [
        ("paciente", "Número sequencial do paciente neste arquivo (não é o prontuário)"),
        ("exame", "Ordem do exame do paciente (1 = o primeiro registrado)"),
        *((nome, descricao) for nome, descricao, _ in COLUNAS),
        ("comorbidade: <nome>", "sim/não, uma coluna por comorbidade do catálogo"),
        ("sintoma: <nome>", "sim/não, uma coluna por sintoma do exame"),
    ]
    return BOM + _linha(["coluna", "significado"]) + "".join(_linha(par) for par in linhas)
