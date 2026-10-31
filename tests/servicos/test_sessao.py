"""Sessão: somente leitura, pasta de backups e detecção de pasta sincronizada."""

from pathlib import Path

import pytest

from gastroepi.servicos.acesso import SenhaIncorreta, criar_cofre
from gastroepi.servicos.sessao import (
    PASTA_DE_BACKUPS,
    chave_pela_senha,
    servico_que_sincroniza,
)

SENHA = "frase longa de teste"


def test_sessao_nova_escreve_e_guarda_os_backups_na_pasta_do_cofre(tmp_path: Path) -> None:
    sessao, _ = criar_cofre(tmp_path, SENHA, SENHA)
    with sessao:
        assert not sessao.somente_leitura
        assert sessao.backup_oferecido is None
        assert sessao.pasta_de_backups == tmp_path / PASTA_DE_BACKUPS


def test_chave_pela_senha_confere_a_senha(tmp_path: Path) -> None:
    criar_cofre(tmp_path, SENHA, SENHA)[0].fechar()

    assert len(chave_pela_senha(tmp_path, SENHA)) == 32
    with pytest.raises(SenhaIncorreta):
        chave_pela_senha(tmp_path, "outra frase qualquer")


def test_servico_que_sincroniza_olha_o_caminho_resolvido(tmp_path: Path) -> None:
    (tmp_path / "Dropbox").mkdir()
    (tmp_path / "local").mkdir()

    assert servico_que_sincroniza(tmp_path / "Dropbox" / ".." / "local") is None
    assert servico_que_sincroniza(tmp_path / "local" / ".." / "Dropbox") == "Dropbox"
