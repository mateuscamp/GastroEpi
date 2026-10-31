"""Datas digitadas em dd/mm/aaaa e guardadas em ISO 8601 AAAA-MM-DD (Princípio V).

Nenhuma mensagem de erro repete a data recebida: a de nascimento é dado pessoal.
"""

import re
from datetime import date

from gastroepi.dominio.erros import DataInvalida

ANO_MINIMO = 1900  # abaixo disso é erro de digitação (05/03/0026), não paciente

# [0-9] e não \d: em Python, \d casa também dígitos arábicos e devanágaris.
_DATA_BR = re.compile(r"([0-9]{2})/([0-9]{2})/([0-9]{4})")
_DATA_ISO = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def _montar(ano: str, mes: str, dia: str) -> date:
    if int(ano) < ANO_MINIMO:
        raise DataInvalida(f"Data inválida: ano antes de {ANO_MINIMO}")
    try:
        return date(int(ano), int(mes), int(dia))
    except ValueError:
        raise DataInvalida("Data inválida: esse dia não existe no calendário") from None


def ler_data_br(texto: str) -> date:
    """`05/03/2026` → `date(2026, 3, 5)`. Exige 2 dígitos no dia e no mês, como a v0.1.16."""
    casamento = _DATA_BR.fullmatch(texto)
    if casamento is None:
        raise DataInvalida("Data inválida: use dd/mm/aaaa (ex.: 05/03/2026)")
    dia, mes, ano = casamento.groups()
    return _montar(ano, mes, dia)


def ler_data_iso(texto: str) -> date:
    """Lê só AAAA-MM-DD, que é o que o banco guarda (`date.fromisoformat` aceita mais)."""
    casamento = _DATA_ISO.fullmatch(texto)
    if casamento is None:
        raise DataInvalida("Data inválida: esperado AAAA-MM-DD")
    ano, mes, dia = casamento.groups()
    return _montar(ano, mes, dia)


def formatar_data_br(data: date | None) -> str:
    """`date(2026, 3, 5)` → `05/03/2026`; sem data → vazio."""
    # f-string e não strftime: na glibc, %Y não completa com zeros um ano < 1000.
    return "" if data is None else f"{data.day:02d}/{data.month:02d}/{data.year:04d}"


def idade_em(nascimento: date, referencia: date) -> int:
    """Anos completos na data de referência.

    Quem nasceu em 29/02 completa anos em 01/03 nos anos não bissextos (Código Civil,
    art. 132, § 3º): a comparação por (mês, dia) já dá esse resultado.
    """
    if referencia < nascimento:
        raise DataInvalida("Data inválida: anterior à data de nascimento")
    ainda_nao_fez = (referencia.month, referencia.day) < (nascimento.month, nascimento.day)
    return referencia.year - nascimento.year - int(ainda_nao_fez)
