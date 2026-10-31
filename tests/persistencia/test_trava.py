"""Instância única por trava de arquivo, sem socket (ADR-0005, item 7)."""

from pathlib import Path

import pytest

from gastroepi.persistencia.trava import NOME_DA_TRAVA, OutraInstanciaAberta, Trava


def test_segunda_trava_na_mesma_pasta_e_recusada(tmp_path: Path) -> None:
    with Trava(tmp_path / NOME_DA_TRAVA), pytest.raises(OutraInstanciaAberta):
        Trava(tmp_path / NOME_DA_TRAVA)


def test_soltar_deixa_travar_de_novo(tmp_path: Path) -> None:
    primeira = Trava(tmp_path / NOME_DA_TRAVA)
    primeira.soltar()
    primeira.soltar()  # soltar duas vezes não é erro

    with Trava(tmp_path / NOME_DA_TRAVA):
        pass


def test_pastas_diferentes_nao_se_travam(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    with Trava(tmp_path / "a" / NOME_DA_TRAVA), Trava(tmp_path / "b" / NOME_DA_TRAVA):
        pass
