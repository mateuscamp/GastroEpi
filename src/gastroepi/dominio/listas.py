"""Listas fechadas do ADR-0004, com as escolhas do dono em 2026-10-31.

O valor de cada item é o código guardado no banco e não muda; o rótulo é o que a tela
mostra. Item novo, removido ou renomeado exige subir VERSAO_DAS_LISTAS e uma migração.
"""

from enum import StrEnum

VERSAO_DAS_LISTAS = 1


class ListaFechada(StrEnum):
    """Item de lista fechada com rótulo em pt-BR."""

    @property
    def rotulo(self) -> str:
        return _ROTULOS[self]


class Sexo(ListaFechada):
    MASCULINO = "M"
    FEMININO = "F"


class Parentesco(ListaFechada):
    PAI = "pai"
    MAE = "mae"
    IRMAO_IRMA = "irmao_irma"
    FILHO_FILHA = "filho_filha"
    AVO = "avo"
    TIO_TIA = "tio_tia"
    SOBRINHO_SOBRINHA = "sobrinho_sobrinha"
    NETO_NETA = "neto_neta"
    MEIO_IRMAO_IRMA = "meio_irmao_irma"
    PRIMO_PRIMA = "primo_prima"
    BISAVO = "bisavo"
    TIO_AVO = "tio_avo"

    @property
    def grau(self) -> int:
        """Grau da genética médica (NCI Dictionary of Genetics Terms), não o do Código
        Civil: 1º compartilha ~50% do DNA, 2º ~25%, 3º ~12,5%. Primo é 3º grau."""
        return _GRAU_DO_PARENTESCO[self]


class Segmento(ListaFechada):
    CECO = "ceco"
    ASCENDENTE = "ascendente"
    FLEXURA_HEPATICA = "flexura_hepatica"
    TRANSVERSO = "transverso"
    FLEXURA_ESPLENICA = "flexura_esplenica"
    DESCENDENTE = "descendente"
    SIGMOIDE = "sigmoide"
    RETO = "reto"


class Paris(ListaFechada):
    IP = "0-Ip"
    ISP = "0-Isp"
    IS = "0-Is"
    IIA = "0-IIa"
    IIB = "0-IIb"
    IIC = "0-IIc"
    III = "0-III"
    NAO_CLASSIFICADA = "nao_classificada"


class Histologia(ListaFechada):
    TUBULAR = "adenoma_tubular"
    TUBULOVILOSO = "adenoma_tubuloviloso"
    VILOSO = "adenoma_viloso"
    SERRILHADA_SESSIL = "lesao_serrilhada_sessil"
    SERRILHADO_TRADICIONAL = "adenoma_serrilhado_tradicional"
    HIPERPLASICO = "hiperplasico"
    ADENOCARCINOMA = "adenocarcinoma"
    OUTRO = "outro"
    AGUARDANDO = "aguardando"
    SEM_HISTOLOGIA = "sem_histologia"


class Displasia(ListaFechada):
    BAIXO = "baixo"
    ALTO = "alto"
    NAO_SE_APLICA = "nao_se_aplica"


class Indicacao(ListaFechada):
    RASTREIO_RISCO_MEDIO = "rastreio_risco_medio"
    RASTREIO_RISCO_AUMENTADO = "rastreio_risco_aumentado"
    VIGILANCIA_POS_POLIPECTOMIA = "vigilancia_pos_polipectomia"
    SANGUE_OCULTO_POSITIVO = "sangue_oculto_positivo"
    DIAGNOSTICA_POR_SINTOMAS = "diagnostica_por_sintomas"
    SEGUIMENTO_DII = "seguimento_dii"
    OUTRA = "outra"


class MotivoNaoIntubacao(ListaFechada):
    PREPARO_INADEQUADO = "preparo_inadequado"
    OBSTRUCAO_OU_ESTENOSE = "obstrucao_ou_estenose"
    DIFICULDADE_TECNICA = "dificuldade_tecnica"
    INTOLERANCIA_OU_SEDACAO = "intolerancia_ou_sedacao"
    COLITE_GRAVE = "colite_grave"
    INTERCORRENCIA_CLINICA = "intercorrencia_clinica"
    OUTRO = "outro"


_GRAU_DO_PARENTESCO: dict[Parentesco, int] = {
    Parentesco.PAI: 1,
    Parentesco.MAE: 1,
    Parentesco.IRMAO_IRMA: 1,
    Parentesco.FILHO_FILHA: 1,
    Parentesco.AVO: 2,
    Parentesco.TIO_TIA: 2,
    Parentesco.SOBRINHO_SOBRINHA: 2,
    Parentesco.NETO_NETA: 2,
    Parentesco.MEIO_IRMAO_IRMA: 2,
    Parentesco.PRIMO_PRIMA: 3,
    Parentesco.BISAVO: 3,
    Parentesco.TIO_AVO: 3,
}

_ROTULOS: dict[ListaFechada, str] = {
    Sexo.MASCULINO: "Masculino",
    Sexo.FEMININO: "Feminino",
    Parentesco.PAI: "Pai",
    Parentesco.MAE: "Mãe",
    Parentesco.IRMAO_IRMA: "Irmão/irmã",
    Parentesco.FILHO_FILHA: "Filho/filha",
    Parentesco.AVO: "Avô/avó",
    Parentesco.TIO_TIA: "Tio/tia",
    Parentesco.SOBRINHO_SOBRINHA: "Sobrinho/sobrinha",
    Parentesco.NETO_NETA: "Neto/neta",
    Parentesco.MEIO_IRMAO_IRMA: "Meio-irmão/meia-irmã",
    Parentesco.PRIMO_PRIMA: "Primo/prima",
    Parentesco.BISAVO: "Bisavô/bisavó",
    Parentesco.TIO_AVO: "Tio-avô/tia-avó",
    Segmento.CECO: "Ceco",
    Segmento.ASCENDENTE: "Cólon ascendente",
    Segmento.FLEXURA_HEPATICA: "Flexura hepática",
    Segmento.TRANSVERSO: "Cólon transverso",
    Segmento.FLEXURA_ESPLENICA: "Flexura esplênica",
    Segmento.DESCENDENTE: "Cólon descendente",
    Segmento.SIGMOIDE: "Sigmoide",
    Segmento.RETO: "Reto",
    # Classificação de Paris (Gastrointest Endosc 2003;58(6 Suppl):S3-43)
    Paris.IP: "0-Ip (pediculada)",
    Paris.ISP: "0-Isp (subpediculada)",
    Paris.IS: "0-Is (séssil)",
    Paris.IIA: "0-IIa (plana elevada)",
    Paris.IIB: "0-IIb (plana)",
    Paris.IIC: "0-IIc (plana deprimida)",
    Paris.III: "0-III (escavada)",
    Paris.NAO_CLASSIFICADA: "Não classificada",
    Histologia.TUBULAR: "Adenoma tubular",
    Histologia.TUBULOVILOSO: "Adenoma tubuloviloso",
    Histologia.VILOSO: "Adenoma viloso",
    Histologia.SERRILHADA_SESSIL: "Lesão serrilhada séssil",
    Histologia.SERRILHADO_TRADICIONAL: "Adenoma serrilhado tradicional",
    Histologia.HIPERPLASICO: "Pólipo hiperplásico",
    Histologia.ADENOCARCINOMA: "Adenocarcinoma",
    Histologia.OUTRO: "Outra",
    Histologia.AGUARDANDO: "Aguardando histologia",
    Histologia.SEM_HISTOLOGIA: "Sem histologia (não recuperada ou não enviada)",
    Displasia.BAIXO: "Baixo grau",
    Displasia.ALTO: "Alto grau",
    Displasia.NAO_SE_APLICA: "Não se aplica",
    Indicacao.RASTREIO_RISCO_MEDIO: "Rastreio de risco médio",
    Indicacao.RASTREIO_RISCO_AUMENTADO: "Rastreio de risco aumentado",
    Indicacao.VIGILANCIA_POS_POLIPECTOMIA: "Vigilância pós-polipectomia",
    Indicacao.SANGUE_OCULTO_POSITIVO: "Sangue oculto/FIT positivo",
    Indicacao.DIAGNOSTICA_POR_SINTOMAS: "Diagnóstica por sintomas",
    Indicacao.SEGUIMENTO_DII: "Seguimento de DII",
    Indicacao.OUTRA: "Outra",
    MotivoNaoIntubacao.PREPARO_INADEQUADO: "Preparo inadequado",
    MotivoNaoIntubacao.OBSTRUCAO_OU_ESTENOSE: "Lesão obstrutiva ou estenose",
    MotivoNaoIntubacao.DIFICULDADE_TECNICA: "Dificuldade técnica (angulação, alça)",
    MotivoNaoIntubacao.INTOLERANCIA_OU_SEDACAO: "Intolerância do paciente ou sedação insuficiente",
    MotivoNaoIntubacao.COLITE_GRAVE: "Colite grave",
    MotivoNaoIntubacao.INTERCORRENCIA_CLINICA: "Intercorrência clínica ou complicação",
    MotivoNaoIntubacao.OUTRO: "Outro",
}


class UF(StrEnum):
    """Unidade federativa do CRM: o mesmo número existe em conselhos de estados diferentes."""

    AC = "AC"
    AL = "AL"
    AP = "AP"
    AM = "AM"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MT = "MT"
    MS = "MS"
    MG = "MG"
    PA = "PA"
    PB = "PB"
    PR = "PR"
    PE = "PE"
    PI = "PI"
    RJ = "RJ"
    RN = "RN"
    RS = "RS"
    RO = "RO"
    RR = "RR"
    SC = "SC"
    SP = "SP"
    SE = "SE"
    TO = "TO"
