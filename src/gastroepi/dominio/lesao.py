"""Lesão (pólipo) do exame e as classificações derivadas dela (ADR-0004).

Classificações, nunca digitadas:
- adenoma convencional: tubular, tubuloviloso ou viloso (WHO Classification of Tumours,
  Digestive System Tumours, 5ª ed., 2019);
- adenoma avançado: adenoma convencional ≥ 10 mm, com componente viloso ou com displasia
  de alto grau (Gupta S et al., US Multi-Society Task Force, Gastroenterology
  2020;158:1131-1153);
- serrilhada: lesão serrilhada séssil ou adenoma serrilhado tradicional (ADR-0004; o
  hiperplásico fica de fora).

O `laudo_texto` é só para consulta e não entra em nenhuma delas.
"""

from typing import Annotated, Self

from pydantic import Field, model_validator

from gastroepi.dominio.campos import ModeloDeDominio, TextoOpcional, conferir_condicional
from gastroepi.dominio.erros import DisplasiaIncoerente
from gastroepi.dominio.listas import Displasia, Histologia, Paris, Segmento

ADENOMAS_CONVENCIONAIS = frozenset({Histologia.TUBULAR, Histologia.TUBULOVILOSO, Histologia.VILOSO})
COMPONENTE_VILOSO = frozenset({Histologia.TUBULOVILOSO, Histologia.VILOSO})
SERRILHADAS = frozenset({Histologia.SERRILHADA_SESSIL, Histologia.SERRILHADO_TRADICIONAL})
# Escolha do dono (2026-10-31): estas exigem "não se aplica"; serrilhadas, adenocarcinoma
# e "outra" aceitam qualquer grau.
SEM_DISPLASIA = frozenset(
    {Histologia.HIPERPLASICO, Histologia.AGUARDANDO, Histologia.SEM_HISTOLOGIA}
)
TAMANHO_AVANCADO_MM = 10  # USMSTF 2020


class Lesao(ModeloDeDominio):
    segmento: Segmento
    tamanho_mm: Annotated[int, Field(ge=1)]
    paris: Paris
    histologia: Histologia
    displasia: Displasia
    histologia_outra: TextoOpcional = Field(default=None, repr=False)
    laudo_texto: TextoOpcional = Field(default=None, repr=False)

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        conferir_condicional(
            "histologia_outra",
            self.histologia_outra,
            exigido=self.histologia is Histologia.OUTRO,
            falta="Descreva a histologia quando for 'outra'",
            sobra="Descrição da histologia só quando ela for 'outra'",
        )
        self._conferir_displasia()
        return self

    def _conferir_displasia(self) -> None:
        sem_grau = self.displasia is Displasia.NAO_SE_APLICA
        if self.adenoma_convencional and sem_grau:
            mensagem = "Displasia: adenoma convencional exige baixo ou alto grau"
            raise DisplasiaIncoerente(mensagem, campo="displasia")
        if self.histologia in SEM_DISPLASIA and not sem_grau:
            mensagem = f"Displasia: {self.histologia.rotulo.lower()} exige 'não se aplica'"
            raise DisplasiaIncoerente(mensagem, campo="displasia")

    @property
    def adenoma_convencional(self) -> bool:
        return self.histologia in ADENOMAS_CONVENCIONAIS

    @property
    def adenoma_avancado(self) -> bool:
        return self.adenoma_convencional and (
            self.tamanho_mm >= TAMANHO_AVANCADO_MM
            or self.histologia in COMPONENTE_VILOSO
            or self.displasia is Displasia.ALTO
        )

    @property
    def serrilhada(self) -> bool:
        return self.histologia in SERRILHADAS

    @property
    def aguardando_histologia(self) -> bool:
        """Só "aguardando" deixa pendente; "sem histologia" já é a resposta final."""
        return self.histologia is Histologia.AGUARDANDO
