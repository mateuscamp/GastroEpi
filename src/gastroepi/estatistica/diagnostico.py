"""Teste diagnóstico: sensibilidade, especificidade e valores preditivos (IC de Wilson)
e razões de verossimilhança com IC pelo método log.

Simel DL, Samsa GP, Matchar DB. Likelihood ratios with confidence: sample size
estimation for diagnostic test studies. J Clin Epidemiol 1991;44:763-770.
Referência no R: `prop.test(correct = FALSE)` e a fórmula de Simel em
ferramentas/referencias_r/gerar.R.
"""

import math
from typing import NamedTuple

from gastroepi.estatistica.entrada import SemObservacao, conferir_contagens
from gastroepi.estatistica.proporcoes import Intervalo, Proporcao, proporcao, quantil_normal, razao

SEM_LIMITE = Intervalo(0.0, math.inf)


class ResultadoDiagnostico(NamedTuple):
    sensibilidade: Proporcao
    especificidade: Proporcao
    vpp: Proporcao
    vpn: Proporcao
    lr_positivo: float
    lr_positivo_ic: Intervalo
    lr_negativo: float
    lr_negativo_ic: Intervalo


def _ic_razao(lr: float, erro_padrao: float, z: float) -> Intervalo:
    return Intervalo(lr * math.exp(-z * erro_padrao), lr * math.exp(z * erro_padrao))


def _erro_padrao_log(acertos: int, doentes: int, erros: int, saudaveis: int) -> float:
    return math.sqrt(1 / acertos - 1 / doentes + 1 / erros - 1 / saudaveis)


def desempenho_diagnostico(
    vp: int, fp: int, fn: int, vn: int, alfa: float = 0.05
) -> ResultadoDiagnostico:
    """LR+ = sens/(1 - esp) e LR- = (1 - sens)/esp, com x/0 = ∞ e 0/0 = NaN.

    O IC das razões só existe com as quatro células usadas > 0; senão é [0, ∞), como na
    v0.1.16 (o log de zero não tem erro padrão).
    """
    conferir_contagens(vp, fp, fn, vn)
    if vp + fp + fn + vn == 0:
        raise SemObservacao("tabela do teste diagnóstico vazia: VP + FP + FN + VN = 0")
    z = quantil_normal(alfa)
    doentes, saudaveis = vp + fn, fp + vn
    sens, espe = razao(vp, doentes), razao(vn, saudaveis)
    lr_pos, lr_neg = razao(sens, 1 - espe), razao(1 - sens, espe)
    ic_pos = ic_neg = SEM_LIMITE
    if vp and fp:
        ic_pos = _ic_razao(lr_pos, _erro_padrao_log(vp, doentes, fp, saudaveis), z)
    if fn and vn:
        ic_neg = _ic_razao(lr_neg, _erro_padrao_log(fn, doentes, vn, saudaveis), z)
    return ResultadoDiagnostico(
        sensibilidade=proporcao(vp, doentes, alfa),
        especificidade=proporcao(vn, saudaveis, alfa),
        vpp=proporcao(vp, vp + fp, alfa),
        vpn=proporcao(vn, fn + vn, alfa),
        lr_positivo=lr_pos,
        lr_positivo_ic=ic_pos,
        lr_negativo=lr_neg,
        lr_negativo_ic=ic_neg,
    )
