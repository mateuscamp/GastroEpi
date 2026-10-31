"""CSV para análise: uma linha por exame, sem identificação e sem texto livre."""

import csv
import io

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import Histologia, Indicacao
from gastroepi.exportacao.csv_analise import (
    BOM,
    COLUNAS,
    csv_de_analise,
    dicionario_de_dados,
    proteger_celula,
)

FICHAS = gerar_fichas(semente=5, quantidade=20)  # tem histologia e indicação 'outra'


def _ler(texto: str) -> list[dict[str, str]]:
    assert texto.startswith(BOM)
    return list(csv.DictReader(io.StringIO(texto[1:], newline=""), delimiter=";"))


def test_uma_linha_por_exame_com_o_paciente_sequencial() -> None:
    linhas = _ler(csv_de_analise(FICHAS))

    assert len(linhas) == sum(len(f.exames) for f in FICHAS)
    assert {linha["paciente"] for linha in linhas} == {str(n) for n in range(1, 21)}
    primeira = FICHAS[0]
    assert linhas[0]["n_polipos"] == str(primeira.exames[0].n_polipos)
    assert linhas[0]["sexo"] == primeira.paciente.sexo.value


def test_nenhum_identificador_nem_texto_livre_sai_no_arquivo() -> None:
    texto = csv_de_analise(FICHAS)
    exames = [e for f in FICHAS for e in f.exames]
    assert any(x.histologia is Histologia.OUTRO for e in exames for x in e.lesoes)
    assert any(e.indicacao is Indicacao.OUTRA for e in exames)

    for ficha in FICHAS:
        paciente = ficha.paciente
        assert paciente.nome not in texto
        assert paciente.prontuario not in texto
        assert paciente.cpf is not None and paciente.cpf not in texto
        assert paciente.data_nascimento.isoformat() not in texto
    assert "Pólipo inflamatório" not in texto  # histologia_outra, texto livre
    assert "Avaliação pré-operatória" not in texto  # indicacao_outra


def test_comorbidades_e_sintomas_viram_colunas_sim_nao() -> None:
    linhas = _ler(csv_de_analise(FICHAS))
    cabecalho = list(linhas[0])
    comorbidade = next(c for c in cabecalho if c.startswith("comorbidade: "))
    nome = comorbidade.removeprefix("comorbidade: ")

    for linha, (ficha, exame) in zip(
        linhas, [(f, e) for f in FICHAS for e in f.exames], strict=True
    ):
        assert linha[comorbidade] == ("sim" if nome in ficha.paciente.comorbidades else "não")
        assert linha["serrilhada"] == ("sim" if any(x.serrilhada for x in exame.lesoes) else "não")


def test_decimal_com_virgula_e_campos_vazios_quando_faltam() -> None:
    linhas = _ler(csv_de_analise(FICHAS))
    exames = [e for f in FICHAS for e in f.exames]
    com_tempo = next(i for i, e in enumerate(exames) if e.tempo_retirada_min)
    sem_boston = next(i for i, e in enumerate(exames) if e.preparo is None)

    tempo = exames[com_tempo].tempo_retirada_min
    assert linhas[com_tempo]["tempo_retirada_min"] == f"{tempo:g}".replace(".", ",")
    assert linhas[sem_boston]["boston_direito"] == linhas[sem_boston]["preparo_adequado"] == ""


def test_lista_vazia_tem_so_o_cabecalho() -> None:
    assert csv_de_analise([]).count("\r\n") == 1


def test_formula_e_separador_sao_neutralizados() -> None:
    assert proteger_celula("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert proteger_celula("-3+2") == "'-3+2"
    assert proteger_celula("@soma") == "'@soma"
    assert proteger_celula('a;b "c"') == '"a;b ""c"""'
    assert proteger_celula("linha\nquebrada") == '"linha\nquebrada"'
    assert proteger_celula("Hipertensão") == "Hipertensão"


def test_dicionario_descreve_cada_coluna() -> None:
    linhas = list(csv.reader(io.StringIO(dicionario_de_dados()[1:], newline=""), delimiter=";"))

    nomes = {linha[0] for linha in linhas[1:]}
    assert {c[0] for c in COLUNAS} <= nomes
    assert {"paciente", "exame"} <= nomes
