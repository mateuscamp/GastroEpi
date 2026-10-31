"""Exportar o CSV para análise: o arquivo, o dicionário ao lado e a recusa em RO."""

from pathlib import Path

import pytest

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.exportacao.csv_analise import BOM
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import criar_cofre, desbloquear
from gastroepi.servicos.exportar import BancoSomenteLeitura, exportar_csv
from tests.cofres_de_teste import SENHA, cofre_com_fichas, corromper_o_meio


def test_exporta_o_csv_e_o_dicionario(tmp_path: Path) -> None:
    cofre, saida = tmp_path / "cofre", tmp_path / "saida"
    saida.mkdir()
    fichas = gerar_fichas(semente=3, quantidade=4)
    sessao, _ = criar_cofre(cofre, SENHA, SENHA)
    with sessao:
        for ficha in fichas:
            pacientes.cadastrar(sessao, ficha, usuario="teste")
        exportacao = exportar_csv(sessao, saida / "exames.csv")

    assert exportacao.exames == sum(len(f.exames) for f in fichas)
    assert exportacao.dicionario == saida / "exames-dicionario.csv"
    texto = exportacao.arquivo.read_bytes().decode("utf-8")
    assert texto.startswith(BOM)
    assert texto.count("\r\n") == exportacao.exames + 1
    assert exportacao.dicionario.read_text(encoding="utf-8").startswith(BOM)


def test_sessao_somente_leitura_nao_exporta(tmp_path: Path) -> None:
    sessao, _ = cofre_com_fichas(tmp_path, quantidade=40)
    sessao.fechar()
    corromper_o_meio(tmp_path)

    with desbloquear(tmp_path, SENHA) as sessao:
        assert sessao.somente_leitura
        with pytest.raises(BancoSomenteLeitura):
            exportar_csv(sessao, tmp_path / "x.csv")
    assert not (tmp_path / "x.csv").exists()
