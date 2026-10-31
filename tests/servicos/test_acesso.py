"""Acesso ao cofre: criar, desbloquear por senha ou recovery key, trocar senha e chave."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.senha import SenhaCurta, SenhasDiferentes
from gastroepi.dominio.usuario import USUARIO_PADRAO
from gastroepi.servicos import pacientes
from gastroepi.servicos.acesso import (
    NOME_DA_CHAVE,
    NOME_DO_BANCO,
    ArquivoDeChaveAusente,
    CofreJaExiste,
    RecoveryKeyInvalida,
    SenhaIncorreta,
    cofre_existe,
    criar_cofre,
    definir_nome_do_usuario,
    desbloquear,
    gerar_nova_recovery_key,
    nome_do_usuario,
    pasta_padrao,
    recuperar_acesso,
    trocar_senha,
)

SENHA = "frase longa de teste"
BLOCOS_DE_8 = re.compile(r"([0-9A-HJKMNP-TV-Z]{8} ){7}[0-9A-HJKMNP-TV-Z]{8}")


@pytest.fixture
def recovery(tmp_path: Path) -> str:
    """Cofre criado com uma ficha fictícia; devolve a recovery key mostrada na criação."""
    sessao, recovery_key = criar_cofre(tmp_path, SENHA, SENHA)
    with sessao:
        pacientes.cadastrar(sessao, gerar_fichas(semente=1, quantidade=1)[0], usuario="teste")
    return recovery_key


def test_cenario_1_senha_duas_vezes_mostra_a_recovery_key_em_blocos_de_8(tmp_path: Path) -> None:
    assert not cofre_existe(tmp_path)

    sessao, recovery_key = criar_cofre(tmp_path, SENHA, SENHA)
    sessao.fechar()

    assert BLOCOS_DE_8.fullmatch(recovery_key)
    assert cofre_existe(tmp_path)
    assert {p.name for p in tmp_path.iterdir()} >= {NOME_DO_BANCO, NOME_DA_CHAVE}


def test_cenario_1_confirmacao_diferente_nao_cria_nada(tmp_path: Path) -> None:
    with pytest.raises(SenhasDiferentes):
        criar_cofre(tmp_path, SENHA, SENHA + "x")

    assert list(tmp_path.iterdir()) == []


def test_senha_curta_nao_cria_nada(tmp_path: Path) -> None:
    with pytest.raises(SenhaCurta):
        criar_cofre(tmp_path, "curta", "curta")

    assert list(tmp_path.iterdir()) == []


def test_criar_por_cima_de_um_cofre_existente_e_recusado(tmp_path: Path, recovery: str) -> None:
    antes = (tmp_path / NOME_DA_CHAVE).read_bytes()

    with pytest.raises(CofreJaExiste):
        criar_cofre(tmp_path, SENHA, SENHA)
    assert (tmp_path / NOME_DA_CHAVE).read_bytes() == antes


def test_senha_certa_desbloqueia_e_ve_os_dados(tmp_path: Path, recovery: str) -> None:
    with desbloquear(tmp_path, SENHA) as sessao:
        assert len(pacientes.listar(sessao)) == 1


def test_senha_errada_nao_desbloqueia(tmp_path: Path, recovery: str) -> None:
    with pytest.raises(SenhaIncorreta):
        desbloquear(tmp_path, SENHA + "x")


def test_sem_arquivo_de_chave_a_senha_nao_basta(tmp_path: Path, recovery: str) -> None:
    (tmp_path / NOME_DA_CHAVE).unlink()

    with pytest.raises(ArquivoDeChaveAusente):
        desbloquear(tmp_path, SENHA)


def test_recovery_key_com_erro_de_digitacao_aponta_o_bloco(tmp_path: Path, recovery: str) -> None:
    blocos = recovery.split()
    blocos[4] = blocos[4][:3] + ("0" if blocos[4][3] != "0" else "1") + blocos[4][4:]

    with pytest.raises(RecoveryKeyInvalida) as erro:
        recuperar_acesso(tmp_path, " ".join(blocos), "senha nova longa", "senha nova longa")
    assert erro.value.bloco == 5


def test_recuperar_acesso_confere_a_senha_nova_antes_de_tudo(tmp_path: Path, recovery: str) -> None:
    antes = (tmp_path / NOME_DA_CHAVE).read_bytes()

    with pytest.raises(SenhasDiferentes):
        recuperar_acesso(tmp_path, recovery, "senha nova longa", "outra senha longa")
    assert (tmp_path / NOME_DA_CHAVE).read_bytes() == antes


def test_trocar_senha_com_a_senha_atual_errada_nao_muda_nada(tmp_path: Path, recovery: str) -> None:
    antes = (tmp_path / NOME_DA_CHAVE).read_bytes()

    with pytest.raises(SenhaIncorreta):
        trocar_senha(tmp_path, SENHA + "x", "senha nova longa", "senha nova longa")
    assert (tmp_path / NOME_DA_CHAVE).read_bytes() == antes


def test_nova_recovery_key_exige_a_senha(tmp_path: Path, recovery: str) -> None:
    with desbloquear(tmp_path, SENHA) as sessao, pytest.raises(SenhaIncorreta):
        gerar_nova_recovery_key(sessao, SENHA + "x")

    with recuperar_acesso(tmp_path, recovery, SENHA, SENHA) as sessao:
        assert len(pacientes.listar(sessao)) == 1


def test_pasta_padrao_fica_fora_de_documentos() -> None:
    windows = pasta_padrao({"LOCALAPPDATA": r"C:\Users\x\AppData\Local"}, "win32")
    linux = pasta_padrao({"XDG_DATA_HOME": "/home/x/.dados"}, "linux")

    assert windows == Path(r"C:\Users\x\AppData\Local") / "GastroEpi"
    assert linux == Path("/home/x/.dados/GastroEpi")
    assert pasta_padrao({}, "linux") == Path.home() / ".local" / "share" / "GastroEpi"
    assert pasta_padrao({}, "win32") == Path.home() / ".local" / "share" / "GastroEpi"


def test_nome_do_usuario_tem_padrao_e_e_validado_no_dominio(tmp_path: Path) -> None:
    sessao, _ = criar_cofre(tmp_path, SENHA, SENHA)
    with sessao:
        assert nome_do_usuario(sessao) == USUARIO_PADRAO
        assert definir_nome_do_usuario(sessao, "  Ana Fictícia ") == "Ana Fictícia"
        with pytest.raises(ValidationError):
            definir_nome_do_usuario(sessao, "   ")
        assert nome_do_usuario(sessao) == "Ana Fictícia"
