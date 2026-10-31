"""Gerador de pacientes fictícios com semente, para a demo e os testes (AGENTS.md).

Nenhum dado real: nomes de listas fixas, CPF com DV calculado sobre base sorteada,
prontuário com prefixo F. Usa só o `random.Random` da semente, então a mesma semente
dá os mesmos pacientes em qualquer máquina. As proporções são plausíveis para a demo,
não estimativas epidemiológicas.
"""

import random
from datetime import date, timedelta
from typing import NamedTuple

from gastroepi.dominio.cpf import digitos_verificadores
from gastroepi.dominio.exame import Boston, Exame, Examinador
from gastroepi.dominio.lesao import ADENOMAS_CONVENCIONAIS, SERRILHADAS, Lesao
from gastroepi.dominio.listas import (
    UF,
    Displasia,
    Histologia,
    Indicacao,
    MotivoNaoIntubacao,
    Parentesco,
    Paris,
    Segmento,
    Sexo,
)
from gastroepi.dominio.paciente import HistoricoFamiliar, Paciente


class FichaFicticia(NamedTuple):
    paciente: Paciente
    exames: tuple[Exame, ...]


NOMES = {
    Sexo.FEMININO: ("Ana", "Beatriz", "Carla", "Daniela", "Elisa", "Fernanda", "Gabriela",
                    "Helena", "Irene", "Joana", "Lúcia", "Marta", "Natália", "Olga", "Paula"),
    Sexo.MASCULINO: ("André", "Bruno", "Carlos", "Diego", "Eduardo", "Fábio", "Gustavo",
                     "Henrique", "Igor", "João", "Luís", "Marcos", "Nelson", "Otávio", "Paulo"),
}  # fmt: skip
SOBRENOMES = (
    "Almeida", "Barros", "Cardoso", "Dias", "Esteves", "Freitas", "Gomes", "Lima",
    "Moura", "Nunes", "Pereira", "Queiroz", "Rocha", "Teixeira", "Vieira",
)  # fmt: skip
EXAMINADORES = (
    Examinador(nome="Dra. Helena Fictícia Prado", crm="100001", uf=UF.SP),
    Examinador(nome="Dr. Rui Fictício Mendes", crm="100002", uf=UF.SP),
    Examinador(nome="Dra. Sônia Fictícia Lopes", crm="200003", uf=UF.MG),
    Examinador(nome="Dr. Caio Fictício Brandão", crm="300004", uf=UF.RJ),
)
COMORBIDADES = ("Hipertensão arterial", "Diabetes mellitus tipo 2", "Dislipidemia",
                "Obesidade", "Tabagismo", "Doença renal crônica")  # fmt: skip
SINTOMAS = ("Hematoquezia", "Alteração do hábito intestinal", "Dor abdominal",
            "Anemia ferropriva", "Perda de peso")  # fmt: skip
PRIMEIRO_EXAME = date(2018, 1, 1)
DIAS_DE_PRIMEIRO_EXAME = 4 * 365

PESO_INDICACAO = {
    Indicacao.RASTREIO_RISCO_MEDIO: 45, Indicacao.RASTREIO_RISCO_AUMENTADO: 12,
    Indicacao.SANGUE_OCULTO_POSITIVO: 10, Indicacao.DIAGNOSTICA_POR_SINTOMAS: 22,
    Indicacao.VIGILANCIA_POS_POLIPECTOMIA: 5, Indicacao.SEGUIMENTO_DII: 3, Indicacao.OUTRA: 3,
}  # fmt: skip
PESO_HISTOLOGIA = {
    Histologia.TUBULAR: 45, Histologia.TUBULOVILOSO: 7, Histologia.VILOSO: 2,
    Histologia.SERRILHADA_SESSIL: 9, Histologia.SERRILHADO_TRADICIONAL: 1,
    Histologia.HIPERPLASICO: 25, Histologia.ADENOCARCINOMA: 2, Histologia.OUTRO: 2,
    Histologia.AGUARDANDO: 5, Histologia.SEM_HISTOLOGIA: 3,
}  # fmt: skip
PESO_PARIS = {
    Paris.IS: 40, Paris.IIA: 25, Paris.ISP: 12, Paris.IP: 10, Paris.IIB: 4, Paris.IIC: 2,
    Paris.III: 1, Paris.NAO_CLASSIFICADA: 6,
}  # fmt: skip
PESO_NOTA_BOSTON = {0: 3, 1: 10, 2: 40, 3: 47}
PESO_N_LESOES = {0: 45, 1: 25, 2: 13, 3: 8, 4: 5, 5: 4}
PESO_N_EXAMES = {1: 75, 2: 20, 3: 5}


def _sortear[T](sorteio: random.Random, pesos: dict[T, int]) -> T:
    return sorteio.choices(list(pesos), weights=list(pesos.values()))[0]


def _cpf(sorteio: random.Random) -> str:
    """O 9º dígito difere do 1º: a base nunca sai toda igual (o CPF seria recusado)."""
    base = "".join(sorteio.choices("0123456789", k=8))
    base += sorteio.choice([d for d in "0123456789" if d != base[0]])
    return base + digitos_verificadores(base)


def _historico(sorteio: random.Random) -> tuple[HistoricoFamiliar, ...]:
    if sorteio.random() >= 0.25:
        return ()
    parentes = sorteio.sample(list(Parentesco), k=sorteio.randint(1, 2))
    return tuple(
        HistoricoFamiliar(
            parentesco=parente,
            idade_diagnostico=sorteio.randint(40, 85) if sorteio.random() < 0.7 else None,
        )
        for parente in parentes
    )


def _nascimento(sorteio: random.Random, primeiro_exame: date, idade: int) -> date:
    """Último aniversário nos 365 dias antes do exame: a idade no exame é a sorteada."""
    aniversario = primeiro_exame - timedelta(days=sorteio.randint(0, 364))
    if (aniversario.month, aniversario.day) == (2, 29):
        aniversario -= timedelta(days=1)
    return aniversario.replace(year=aniversario.year - idade)


def _paciente(sorteio: random.Random, numero: int, primeiro_exame: date) -> Paciente:
    sexo = sorteio.choice(list(Sexo))
    sobrenomes = " ".join(sorteio.sample(SOBRENOMES, k=2))
    return Paciente(
        prontuario=f"F{numero:05d}",
        cpf=_cpf(sorteio),
        nome=f"{sorteio.choice(NOMES[sexo])} {sobrenomes}",
        sexo=sexo,
        data_nascimento=_nascimento(sorteio, primeiro_exame, sorteio.randint(40, 80)),
        comorbidades=tuple(sorteio.sample(COMORBIDADES, k=sorteio.randint(0, 3))),
        historico_familiar=_historico(sorteio),
    )


def _histologia_e_displasia(sorteio: random.Random) -> tuple[Histologia, Displasia]:
    histologia = _sortear(sorteio, PESO_HISTOLOGIA)
    if histologia in ADENOMAS_CONVENCIONAIS:
        displasia = Displasia.ALTO if sorteio.random() < 0.08 else Displasia.BAIXO
    elif histologia in SERRILHADAS and sorteio.random() < 0.3:
        displasia = Displasia.BAIXO
    else:
        displasia = Displasia.NAO_SE_APLICA
    return histologia, displasia


def _tamanho_mm(sorteio: random.Random, histologia: Histologia) -> int:
    if histologia is Histologia.ADENOCARCINOMA:
        return sorteio.randint(15, 40)
    faixa = sorteio.random()
    if faixa < 0.7:
        return sorteio.randint(2, 6)
    return sorteio.randint(7, 9) if faixa < 0.9 else sorteio.randint(10, 30)


def _lesao(sorteio: random.Random) -> Lesao:
    histologia, displasia = _histologia_e_displasia(sorteio)
    return Lesao(
        segmento=sorteio.choice(list(Segmento)),
        tamanho_mm=_tamanho_mm(sorteio, histologia),
        paris=_sortear(sorteio, PESO_PARIS),
        histologia=histologia,
        displasia=displasia,
        histologia_outra="Pólipo inflamatório" if histologia is Histologia.OUTRO else None,
    )


def _boston(sorteio: random.Random) -> Boston | None:
    if sorteio.random() < 0.2:
        return None  # laudo sem Boston: a escolha do dono permite
    direito, transverso, esquerdo = (_sortear(sorteio, PESO_NOTA_BOSTON) for _ in range(3))
    return Boston(direito=direito, transverso=transverso, esquerdo=esquerdo)


def _sintomas(sorteio: random.Random, indicacao: Indicacao) -> tuple[str, ...]:
    if indicacao is not Indicacao.DIAGNOSTICA_POR_SINTOMAS:
        return ()
    return tuple(sorteio.sample(SINTOMAS, k=sorteio.randint(1, 2)))


def _exame(sorteio: random.Random, data_exame: date, indicacao: Indicacao) -> Exame:
    intubou = sorteio.random() < 0.95
    motivo = None if intubou else sorteio.choice(list(MotivoNaoIntubacao))
    retirada = round(sorteio.uniform(4, 14), 1) if sorteio.random() < 0.7 else None
    return Exame(
        data_exame=data_exame,
        indicacao=indicacao,
        indicacao_outra="Avaliação pré-operatória" if indicacao is Indicacao.OUTRA else None,
        examinador=sorteio.choice(EXAMINADORES),
        preparo=_boston(sorteio),
        intubacao_cecal=intubou,
        motivo_nao_intubacao=motivo,
        motivo_outro="Recusa em prosseguir" if motivo is MotivoNaoIntubacao.OUTRO else None,
        tempo_retirada_min=retirada,
        sintomas=_sintomas(sorteio, indicacao),
        lesoes=tuple(_lesao(sorteio) for _ in range(_sortear(sorteio, PESO_N_LESOES))),
    )


def _datas_dos_exames(sorteio: random.Random) -> list[date]:
    """1 a 3 exames; cada retorno de 1 a 2 anos depois, todos antes de 2026."""
    datas = [PRIMEIRO_EXAME + timedelta(days=sorteio.randint(0, DIAS_DE_PRIMEIRO_EXAME))]
    for _ in range(_sortear(sorteio, PESO_N_EXAMES) - 1):
        datas.append(datas[-1] + timedelta(days=sorteio.randint(365, 730)))
    return datas


def _ficha(sorteio: random.Random, numero: int) -> FichaFicticia:
    datas = _datas_dos_exames(sorteio)
    paciente = _paciente(sorteio, numero, datas[0])
    primeiro = _exame(sorteio, datas[0], _sortear(sorteio, PESO_INDICACAO))
    retornos = (_exame(sorteio, d, Indicacao.VIGILANCIA_POS_POLIPECTOMIA) for d in datas[1:])
    return FichaFicticia(paciente, (primeiro, *retornos))


def gerar_fichas(semente: int, quantidade: int) -> tuple[FichaFicticia, ...]:
    """`quantidade` pacientes fictícios, cada um com 1 a 3 exames, sempre iguais por semente."""
    sorteio = random.Random(semente)
    return tuple(_ficha(sorteio, numero) for numero in range(1, quantidade + 1))
