"""Exame de colonoscopia (ADR-0004): qualidade, indicação, examinador e lesões.

Derivados, nunca digitados:
- `n_polipos` é o número de lesões registradas;
- preparo adequado: Boston total ≥ 6 e cada segmento ≥ 2 (escala: Lai EJ et al.,
  Gastrointest Endosc 2009;69:620-625; limiar: Calderwood AH et al., Gastrointest
  Endosc 2014;80:269-276);
- idade no exame: anos completos entre o nascimento e a data do exame.

Escolha do dono (2026-10-31): só a intubação cecal é obrigatória entre os campos de
qualidade; Boston (os 3 segmentos ou nenhum) e tempo de retirada podem faltar.
"""

import re
from typing import Annotated, Self

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from gastroepi.dominio.campos import (
    Data,
    ItensDeCatalogo,
    ModeloDeDominio,
    TextoObrigatorio,
    TextoOpcional,
    conferir_condicional,
    vazio_vira_none,
)
from gastroepi.dominio.datas import idade_em
from gastroepi.dominio.erros import CrmInvalido
from gastroepi.dominio.lesao import Lesao
from gastroepi.dominio.listas import UF, Indicacao, MotivoNaoIntubacao
from gastroepi.dominio.paciente import Paciente

BOSTON_TOTAL_ADEQUADO = 6
BOSTON_SEGMENTO_ADEQUADO = 2
_CRM = re.compile(r"[0-9]{1,8}")

NotaBoston = Annotated[int, Field(ge=0, le=3)]
MinutosOpcionais = Annotated[
    Annotated[float, Field(gt=0, allow_inf_nan=False)] | None, BeforeValidator(vazio_vira_none)
]


def _conferir_crm(crm: str) -> str:
    if _CRM.fullmatch(crm) is None:
        raise CrmInvalido("CRM inválido: use de 1 a 8 dígitos, sem a UF")
    return crm


class Examinador(ModeloDeDominio):
    """Cadastro do médico que fez o exame; não é o usuário que opera o app."""

    nome: TextoObrigatorio
    crm: Annotated[TextoObrigatorio, AfterValidator(_conferir_crm)]
    uf: UF


class Boston(ModeloDeDominio):
    """Escala de Boston, 0 a 3 por segmento do cólon."""

    direito: NotaBoston
    transverso: NotaBoston
    esquerdo: NotaBoston

    @property
    def total(self) -> int:
        return self.direito + self.transverso + self.esquerdo

    @property
    def adequado(self) -> bool:
        menor = min(self.direito, self.transverso, self.esquerdo)
        return self.total >= BOSTON_TOTAL_ADEQUADO and menor >= BOSTON_SEGMENTO_ADEQUADO


class Exame(ModeloDeDominio):
    """`observacao` e os textos de "outra" são só consulta e nunca entram em cálculo."""

    data_exame: Data
    indicacao: Indicacao
    indicacao_outra: TextoOpcional = Field(default=None, repr=False)
    examinador: Examinador
    preparo: Boston | None = None
    intubacao_cecal: bool
    motivo_nao_intubacao: MotivoNaoIntubacao | None = None
    motivo_outro: TextoOpcional = Field(default=None, repr=False)
    tempo_retirada_min: MinutosOpcionais = None
    sintomas: ItensDeCatalogo = ()
    lesoes: tuple[Lesao, ...] = ()
    observacao: TextoOpcional = Field(default=None, repr=False)

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        conferir_condicional(
            "indicacao_outra",
            self.indicacao_outra,
            exigido=self.indicacao is Indicacao.OUTRA,
            falta="Descreva a indicação quando for 'outra'",
            sobra="Descrição da indicação só quando ela for 'outra'",
        )
        conferir_condicional(
            "motivo_nao_intubacao",
            self.motivo_nao_intubacao,
            exigido=not self.intubacao_cecal,
            falta="Informe por que o ceco não foi alcançado",
            sobra="Motivo só quando o ceco não foi alcançado",
        )
        conferir_condicional(
            "motivo_outro",
            self.motivo_outro,
            exigido=self.motivo_nao_intubacao is MotivoNaoIntubacao.OUTRO,
            falta="Descreva o motivo quando for 'outro'",
            sobra="Descrição do motivo só quando ele for 'outro'",
        )
        return self

    @property
    def n_polipos(self) -> int:
        return len(self.lesoes)

    @property
    def aguardando_histologia(self) -> bool:
        return any(lesao.aguardando_histologia for lesao in self.lesoes)

    @property
    def preparo_adequado(self) -> bool | None:
        """`None` quando o Boston não foi registrado."""
        return None if self.preparo is None else self.preparo.adequado


def idade_no_exame(paciente: Paciente, exame: Exame) -> int:
    """Anos completos na data do exame. Exame antes do nascimento levanta `DataInvalida`."""
    return idade_em(paciente.data_nascimento, exame.data_exame)
