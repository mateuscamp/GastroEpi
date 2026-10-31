"""Textos da casca: erros traduzidos para pt-BR e números no formato brasileiro.

A casca não revalida (AGENTS.md): ela só dá nome de tela ao campo que o domínio apontou.
"""

import math
from datetime import datetime

from pydantic import ValidationError

from gastroepi.dominio.erros import ErroDeValidacao, problemas_de
from gastroepi.servicos.calculadoras import Intervalo, Proporcao

PARTE_ILEGIVEL = (
    "Esta tela não conseguiu ler o banco: a parte com defeito está ilegível. Restaure o"
    " backup para voltar a ver tudo."
)
ROTULOS_DE_CAMPO = {
    "prontuario": "Prontuário",
    "cpf": "CPF",
    "nome": "Nome",
    "sexo": "Sexo",
    "data_nascimento": "Data de nascimento",
    "comorbidades": "Comorbidades",
    "parentesco": "Parentesco",
    "idade_diagnostico": "Idade no diagnóstico do parente",
    "data_exame": "Data do exame",
    "indicacao": "Indicação",
    "indicacao_outra": "Descrição da indicação",
    "examinador": "Examinador",
    "crm": "CRM",
    "uf": "UF",
    "preparo": "Preparo (Boston)",
    "direito": "Boston, cólon direito",
    "transverso": "Boston, transverso",
    "esquerdo": "Boston, cólon esquerdo",
    "intubacao_cecal": "Intubação cecal",
    "motivo_nao_intubacao": "Motivo de não alcançar o ceco",
    "motivo_outro": "Descrição do motivo",
    "tempo_retirada_min": "Tempo de retirada",
    "sintomas": "Sintomas",
    "segmento": "Segmento",
    "tamanho_mm": "Tamanho (mm)",
    "paris": "Morfologia (Paris)",
    "histologia": "Histologia",
    "displasia": "Displasia",
    "histologia_outra": "Descrição da histologia",
    "laudo_texto": "Laudo",
    "observacao": "Observação",
    "senha": "Senha",
    "confirmacao": "Confirmação da senha",
}
_GRUPOS = {"exames": "Exame", "lesoes": "Lesão", "historico_familiar": "Parente"}


def rotulo_do_campo(caminho: str) -> str:
    """`exames.0.lesoes.1.tamanho_mm` → `Exame 1, Lesão 2: Tamanho (mm)`."""
    partes = caminho.split(".") if caminho else []
    prefixos, campo = [], ""
    for indice, parte in enumerate(partes):
        if parte in _GRUPOS and indice + 1 < len(partes) and partes[indice + 1].isdigit():
            prefixos.append(f"{_GRUPOS[parte]} {int(partes[indice + 1]) + 1}")
        elif not parte.isdigit() and parte != "paciente":
            campo = ROTULOS_DE_CAMPO.get(parte, parte)
    return ", ".join(prefixos) + (": " if prefixos and campo else "") + campo


def mensagem_de_validacao(erro: ValidationError) -> str:
    linhas = []
    for problema in problemas_de(erro):
        rotulo = rotulo_do_campo(problema.campo)
        linhas.append(f"{rotulo}: {problema.mensagem}" if rotulo else problema.mensagem)
    return "\n".join(linhas)


def mensagem_de_erro(erro: Exception) -> str:
    """Os erros do núcleo já vêm em pt-BR e sem dado sensível; o de validação ganha os
    nomes dos campos como a tela os mostra."""
    if isinstance(erro, ValidationError):
        return mensagem_de_validacao(erro)
    if isinstance(erro, ErroDeValidacao):
        return str(erro)
    return str(erro) or type(erro).__name__


def numero(valor: float | None, casas: int = 2) -> str:
    if valor is None or math.isnan(valor):
        return "—"
    if math.isinf(valor):
        return "∞" if valor > 0 else "-∞"
    return f"{valor:,.{casas}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def percentual(fracao: float | None, casas: int = 1) -> str:
    return "—" if fracao is None else f"{numero(100 * fracao, casas)}%"


def intervalo(ic: Intervalo, casas: int = 2, em_percentual: bool = False) -> str:
    if em_percentual:
        return f"{percentual(ic.inferior, casas)} a {percentual(ic.superior, casas)}"
    return f"{numero(ic.inferior, casas)} a {numero(ic.superior, casas)}"


def proporcao(valor: Proporcao) -> str:
    """`12 de 40 = 30,0% (IC 95%: 17,9% a 45,6%)`; sem total, `nenhum exame`."""
    if not valor.total:
        return "nenhum exame"
    ic = intervalo(valor.ic, 1, em_percentual=True)
    return f"{valor.casos} de {valor.total} = {percentual(valor.estimativa)} (IC 95%: {ic})"


def p_valor(p: float) -> str:
    return "p < 0,001" if p < 0.001 else f"p = {numero(p, 3)}"


def momento_local(momento: datetime) -> str:
    """O instante em UTC mostrado no fuso do computador."""
    return momento.astimezone().strftime("%d/%m/%Y %H:%M")


def com_ic(valor: float, ic: Intervalo) -> str:
    """`2,50 (IC 95%: 1,20 a 5,21)`."""
    return f"{numero(valor)} (IC 95%: {intervalo(ic)})"


def qui_quadrado(estatistica: float, p: float) -> str:
    return f"{numero(estatistica, 3)}; {p_valor(p)}"
