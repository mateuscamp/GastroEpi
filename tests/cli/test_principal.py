"""CLI `gastroepi`: demo, verificar, backup e exportar contra cofres reais em tmp_path."""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from gastroepi.cli.principal import SENHA_DA_DEMO, USUARIO_DA_DEMO, Terminal, _problemas, main
from gastroepi.servicos import acesso, destino_externo, durabilidade, pacientes
from gastroepi.servicos.acesso import Sessao, desbloquear
from gastroepi.servicos.integridade import QuebraDaCadeia, RelatorioDeIntegridade, Verificacao
from tests.cofres_de_teste import SENHA, adulterar_um_nome, cofre_com_fichas, corromper_o_meio


@dataclass
class TerminalFalso:
    senha: str = SENHA
    saida: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    aberturas: list[tuple[Path | None, Sessao | None]] = field(default_factory=list)
    codigo_da_janela: int = 0

    def terminal(self) -> Terminal:
        return Terminal(
            self.saida.append,
            self.erros.append,
            self._ler_senha,
            self._abrir_app,
            self._abrir_e_fechar,
        )

    def _ler_senha(self, pergunta: str) -> str:
        return self.senha

    def _abrir_app(self, pasta: Path | None, sessao: Sessao | None) -> int:
        self.aberturas.append((pasta, sessao))
        if sessao is not None:
            sessao.fechar()
        return 0

    def _abrir_e_fechar(self, pasta: Path, sessao: Sessao) -> int:
        self.aberturas.append((pasta, sessao))
        assert len(pacientes.listar(sessao)) == 1
        sessao.fechar()
        return self.codigo_da_janela


@pytest.fixture
def falso() -> TerminalFalso:
    return TerminalFalso()


def test_sem_comando_abre_o_app(falso: TerminalFalso, tmp_path: Path) -> None:
    assert main(["--pasta", str(tmp_path)], falso.terminal()) == 0
    assert falso.aberturas == [(tmp_path, None)]


def test_demo_cria_fichas_com_semente_e_abre_desbloqueado(
    falso: TerminalFalso, tmp_path: Path
) -> None:
    pasta = tmp_path / "demo"

    codigo = main(["--pasta", str(pasta), "demo", "--pacientes", "12"], falso.terminal())

    assert codigo == 0
    ((aberta, sessao),) = falso.aberturas
    assert aberta == pasta and sessao is not None
    assert SENHA_DA_DEMO in falso.saida[1]
    with desbloquear(pasta, SENHA_DA_DEMO) as demo:
        assert len(pacientes.listar(demo)) == 12
        assert acesso.nome_do_usuario(demo) == USUARIO_DA_DEMO
        assert len(durabilidade.backups_do_cofre(demo)) == 1


def test_demo_sem_janela_e_em_pasta_temporaria(falso: TerminalFalso) -> None:
    codigo = main(["demo", "--pacientes", "2", "--sem-janela"], falso.terminal())

    assert codigo == 0 and falso.aberturas == []
    pasta = Path(falso.saida[0].rsplit(" em ", 1)[1])
    assert pasta.name.startswith("gastroepi-demo-") and acesso.cofre_existe(pasta)


def test_demo_em_cofre_que_ja_existe_e_recusada(falso: TerminalFalso, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()

    assert main(["--pasta", str(tmp_path), "demo", "--sem-janela"], falso.terminal()) == 1
    assert falso.erros == ["Erro: Já existe um cofre nesta pasta"]


def test_verificar_cofre_integro_e_uso_de_outro(falso: TerminalFalso, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=60)[0].fechar()

    assert main(["--pasta", str(tmp_path), "verificar"], falso.terminal()) == 0
    assert falso.saida[0].startswith("Integridade: ok")
    assert any(linha.startswith("  indicação:") for linha in falso.saida)
    assert any("acima de 5%" in linha for linha in falso.saida)  # a semente 9 passa de 5%


def test_verificar_acusa_a_adulteracao(falso: TerminalFalso, tmp_path: Path) -> None:
    sessao, recovery_key = cofre_com_fichas(tmp_path, quantidade=5)
    sessao.fechar()
    adulterar_um_nome(tmp_path, recovery_key)

    assert main(["--pasta", str(tmp_path), "verificar"], falso.terminal()) == 1
    assert falso.erros[0] == "Integridade: REPROVADA"
    assert "paciente 2: alterado" in falso.erros[1]


def test_verificar_com_pagina_estragada(falso: TerminalFalso, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=40)[0].fechar()
    corromper_o_meio(tmp_path)

    assert main(["--pasta", str(tmp_path), "verificar"], falso.terminal()) == 1
    assert falso.erros[1].startswith("  página com defeito")


def test_backup_e_exportar(falso: TerminalFalso, tmp_path: Path) -> None:
    cofre, saida = tmp_path / "cofre", tmp_path / "exames.csv"
    sessao, _ = cofre_com_fichas(cofre, quantidade=3)
    pendrive = tmp_path / "pendrive"
    pendrive.mkdir()
    with sessao:
        destino_externo.configurar(sessao, pendrive, SENHA)

    assert main(["--pasta", str(cofre), "backup"], falso.terminal()) == 0
    assert main(["--pasta", str(cofre), "exportar", str(saida)], falso.terminal()) == 0
    assert falso.saida[0].startswith("Backup conferido em")
    assert falso.saida[1].startswith("Cópia externa conferida em")
    assert "NÃO é cifrado" in falso.saida[-1]
    assert saida.exists()


def test_senha_errada_e_cofre_ausente(falso: TerminalFalso, tmp_path: Path) -> None:
    assert main(["--pasta", str(tmp_path / "nada"), "backup"], falso.terminal()) == 1
    assert not (tmp_path / "nada").exists()  # não cria a pasta à toa
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()
    falso.senha = "errada"

    assert main(["--pasta", str(tmp_path), "backup"], falso.terminal()) == 1
    assert falso.erros[-1] == "Erro: Senha incorreta"


def test_outra_instancia_aberta(falso: TerminalFalso, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()

    with durabilidade.travar_instancia(tmp_path):
        assert main(["--pasta", str(tmp_path), "verificar"], falso.terminal()) == 1

    assert falso.erros == ["Erro: O GastroEpi já está aberto com este cofre"]


def test_terminal_padrao_escreve_no_stdout_e_no_stderr(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    terminal = Terminal()
    terminal.escrever("saída")
    terminal.escrever_erro("erro")

    capturado = capsys.readouterr()
    assert (capturado.out, capturado.err) == ("saída\n", "erro\n")


def test_cadeia_quebrada_aparece_nos_problemas() -> None:
    relatorio = RelatorioDeIntegridade(QuebraDaCadeia(7, "2026-10-31T12:00:00+00:00"), ())

    assert _problemas(Verificacao((), relatorio)) == ["cadeia quebrada na entrada 7"]


def test_backup_sem_destino_externo(falso: TerminalFalso, tmp_path: Path) -> None:
    cofre_com_fichas(tmp_path, quantidade=1)[0].fechar()

    assert main(["--pasta", str(tmp_path), "backup"], falso.terminal()) == 0
    assert len(falso.saida) == 1


def test_smoke_cadastra_abre_a_janela_reabre_e_sai_com_zero(falso: TerminalFalso) -> None:
    assert main(["--smoke"], falso.terminal()) == 0

    ((pasta, _),) = falso.aberturas
    assert pasta is not None and not pasta.exists()  # a pasta temporária some no fim
    assert falso.saida == ["smoke ok: cofre criado, 1 paciente fictício, janela, integridade ok"]


def test_smoke_falha_se_a_janela_falha(falso: TerminalFalso) -> None:
    falso.codigo_da_janela = 1

    assert main(["--smoke"], falso.terminal()) == 1
    assert falso.erros == ["smoke FALHOU: janela 1, integridade ok, pacientes 1"]


def test_smoke_de_verdade_com_a_janela_qt(capsys: pytest.CaptureFixture[str]) -> None:
    """O mesmo caminho do `GastroEpi.exe --smoke` no CI (ADR-0006), com o Qt de verdade."""
    assert main(["--smoke"]) == 0
    assert capsys.readouterr().out.startswith("smoke ok")
