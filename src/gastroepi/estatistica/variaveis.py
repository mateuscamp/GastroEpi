"""As variáveis que a estatística lê do domínio, por exame (ADR-0004: uma linha por exame).

Só campos de lista fechada e números entram aqui. Texto livre (`observacao`,
`laudo_texto`, os "outra/outro") nunca é lido (AGENTS.md; fitness em tests/arquitetura).
"""

from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import NamedTuple

from gastroepi.dominio.exame import Exame, idade_no_exame
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.paciente import Paciente

NENHUMA = "Nenhuma"  # exame sem item numa variável de vários valores (comorbidade, sintoma)


class Variavel(StrEnum):
    """Variáveis de categoria. Comorbidade e sintoma têm vários valores por exame."""

    SEXO = "sexo"
    FAIXA_ETARIA = "faixa_etaria"
    INDICACAO = "indicacao"
    EXAMINADOR = "examinador"
    COMORBIDADE = "comorbidade"
    SINTOMA = "sintoma"
    N_POLIPOS = "n_polipos"


class VariavelNumerica(StrEnum):
    IDADE = "idade"
    N_POLIPOS = "n_polipos"
    TEMPO_RETIRADA = "tempo_retirada"


class ExameDoPaciente(NamedTuple):
    paciente: Paciente
    exame: Exame

    @property
    def idade(self) -> int:
        return idade_no_exame(self.paciente, self.exame)


def exames_de(fichas: Iterable[Ficha]) -> list[ExameDoPaciente]:
    return [ExameDoPaciente(f.paciente, exame) for f in fichas for exame in f.exames]


def faixa_etaria(idade: int) -> str:
    """Década da idade no exame: 40-49, 50-59…"""
    inicio = idade // 10 * 10
    return f"{inicio}-{inicio + 9}"


def rotulo_do_examinador(registro: ExameDoPaciente) -> str:
    """O CRM entra no rótulo: dois médicos com o mesmo nome continuam separados."""
    examinador = registro.exame.examinador
    return f"{examinador.nome} (CRM-{examinador.uf} {examinador.crm})"


_CATEGORIAS: dict[Variavel, Callable[[ExameDoPaciente], tuple[str, ...]]] = {
    Variavel.SEXO: lambda r: (r.paciente.sexo.rotulo,),
    Variavel.FAIXA_ETARIA: lambda r: (faixa_etaria(r.idade),),
    Variavel.INDICACAO: lambda r: (r.exame.indicacao.rotulo,),
    Variavel.EXAMINADOR: lambda r: (rotulo_do_examinador(r),),
    Variavel.COMORBIDADE: lambda r: r.paciente.comorbidades or (NENHUMA,),
    Variavel.SINTOMA: lambda r: r.exame.sintomas or (NENHUMA,),
    Variavel.N_POLIPOS: lambda r: (str(r.exame.n_polipos),),
}
_MEDIDAS: dict[VariavelNumerica, Callable[[ExameDoPaciente], float | None]] = {
    VariavelNumerica.IDADE: lambda r: float(r.idade),
    VariavelNumerica.N_POLIPOS: lambda r: float(r.exame.n_polipos),
    VariavelNumerica.TEMPO_RETIRADA: lambda r: r.exame.tempo_retirada_min,
}


def categorias(registro: ExameDoPaciente, variavel: Variavel) -> tuple[str, ...]:
    return _CATEGORIAS[variavel](registro)


def medida(registro: ExameDoPaciente, variavel: VariavelNumerica) -> float | None:
    """`None` quando o exame não tem a medida (tempo de retirada é opcional)."""
    return _MEDIDAS[variavel](registro)
