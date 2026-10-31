"""CLI `gastroepi`: abre o app, ou roda `demo`, `verificar`, `backup` e `exportar`.

A senha é lida sem eco (`getpass`) e nunca vem por argumento, que fica no histórico do
shell. Todo comando que abre o cofre segura a trava de instância (ADR-0005, item 7).
Saída: 0 deu certo; 1 erro ou integridade reprovada.
"""

import argparse
import getpass
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.servicos import (
    acesso,
    destino_externo,
    durabilidade,
    exportar,
    integridade,
    pacientes,
)
from gastroepi.servicos.acesso import Sessao

if TYPE_CHECKING:
    from gastroepi.ui_qt.janela_principal import JanelaPrincipal

SENHA_DA_DEMO = "demonstração do gastroepi"
USUARIO_DA_DEMO = "Demonstração"
SENHA_DO_SMOKE = "autoteste do gastroepi congelado"


def _abrir_app(pasta: Path | None, sessao: Sessao | None) -> int:
    from gastroepi.ui_qt.aplicacao import rodar  # só aqui: o resto da CLI não carrega o Qt

    return rodar(pasta, sessao)


def _abrir_e_fechar(pasta: Path, sessao: Sessao) -> int:
    """Abre a janela desbloqueada, desenha uma vez e fecha (o `--smoke`, ADR-0006)."""
    from gastroepi.ui_qt.aplicacao import processar_eventos, rodar

    janelas: list[JanelaPrincipal] = []
    codigo = rodar(pasta, sessao, ao_abrir=janelas.append, laco_de_eventos=processar_eventos)
    for janela in janelas:
        janela.close()  # fechar a janela fecha a sessão
    return codigo


def _escrever_erro(texto: str) -> None:
    print(texto, file=sys.stderr)


@dataclass
class Terminal:
    """O que a CLI usa do mundo de fora; os testes injetam o seu."""

    escrever: Callable[[str], None] = print
    escrever_erro: Callable[[str], None] = _escrever_erro
    ler_senha: Callable[[str], str] = getpass.getpass
    abrir_app: Callable[[Path | None, Sessao | None], int] = field(default=_abrir_app)
    abrir_e_fechar: Callable[[Path, Sessao], int] = field(default=_abrir_e_fechar)


def _argumentos() -> argparse.ArgumentParser:
    raiz = argparse.ArgumentParser(prog="gastroepi", description="Registro de colonoscopia")
    raiz.add_argument("--pasta", type=Path, help="pasta do cofre (padrão: a do app)")
    raiz.add_argument("--smoke", action="store_true", help="autoteste do executável (ADR-0006)")
    comandos = raiz.add_subparsers(dest="comando")
    demo = comandos.add_parser("demo", help="cofre de pacientes fictícios, e abre o app")
    demo.add_argument("--semente", type=int, default=42)
    demo.add_argument("--pacientes", type=int, default=300)
    demo.add_argument("--sem-janela", action="store_true", help="só cria o cofre")
    comandos.add_parser("verificar", help="integridade e o uso de 'outro' (ADR-0004)")
    comandos.add_parser("backup", help="backup conferido agora")
    saida = comandos.add_parser("exportar", help="CSV anônimo para análise (sem cifra)")
    saida.add_argument("arquivo", type=Path)
    return raiz


def main(argv: Sequence[str] | None = None, terminal: Terminal | None = None) -> int:
    terminal = terminal or Terminal()
    args = _argumentos().parse_args(argv)
    if args.smoke:
        return _smoke(terminal)
    if args.comando is None:
        return terminal.abrir_app(args.pasta, None)
    if args.comando == "demo":
        return _demo(args, terminal)
    pasta: Path = args.pasta or acesso.pasta_padrao()
    acao = {"verificar": _verificar, "backup": _backup, "exportar": _exportar}[args.comando]
    if not acesso.cofre_existe(pasta):
        terminal.escrever_erro(f"Erro: nenhum cofre em {pasta}")
        return 1
    try:
        with durabilidade.travar_instancia(pasta), _desbloquear(pasta, terminal) as sessao:
            return acao(sessao, args, terminal)
    except (OSError, ValueError, RuntimeError) as erro:
        terminal.escrever_erro(f"Erro: {erro}")
        return 1


def _desbloquear(pasta: Path, terminal: Terminal) -> Sessao:
    return acesso.desbloquear(pasta, terminal.ler_senha("Senha do GastroEpi: "))


def _demo(args: argparse.Namespace, terminal: Terminal) -> int:
    pasta: Path = args.pasta or Path(tempfile.mkdtemp(prefix="gastroepi-demo-"))
    try:
        sessao, _ = acesso.criar_cofre(pasta, SENHA_DA_DEMO, SENHA_DA_DEMO)
    except (OSError, ValueError) as erro:
        terminal.escrever_erro(f"Erro: {erro}")
        return 1
    acesso.definir_nome_do_usuario(sessao, USUARIO_DA_DEMO)
    for ficha in gerar_fichas(semente=args.semente, quantidade=args.pacientes):
        pacientes.cadastrar(sessao, ficha, USUARIO_DA_DEMO)
    durabilidade.fazer_backup(sessao)
    terminal.escrever(f"Cofre de demonstração com {args.pacientes} pacientes fictícios em {pasta}")
    terminal.escrever(f"Senha da demonstração: {SENHA_DA_DEMO}")
    if args.sem_janela:
        sessao.fechar()
        return 0
    return terminal.abrir_app(pasta, sessao)


def _smoke(terminal: Terminal) -> int:
    """Autoteste do executável congelado: cofre temporário, 1 fictício, janela, reabertura."""
    with tempfile.TemporaryDirectory(prefix="gastroepi-smoke-") as nome:
        pasta = Path(nome)
        sessao, _ = acesso.criar_cofre(pasta, SENHA_DO_SMOKE, SENHA_DO_SMOKE)
        pacientes.cadastrar(sessao, gerar_fichas(semente=1, quantidade=1)[0], "smoke")
        janela = terminal.abrir_e_fechar(pasta, sessao)
        with acesso.desbloquear(pasta, SENHA_DO_SMOKE) as reaberta:
            ok = integridade.verificar(reaberta).ok
            cadastrados = len(pacientes.listar(reaberta))
    if janela == 0 and ok and cadastrados == 1:
        terminal.escrever("smoke ok: cofre criado, 1 paciente fictício, janela, integridade ok")
        return 0
    situacao = "ok" if ok else "REPROVADA"
    terminal.escrever_erro(
        f"smoke FALHOU: janela {janela}, integridade {situacao}, pacientes {cadastrados}"
    )
    return 1


def _verificar(sessao: Sessao, args: argparse.Namespace, terminal: Terminal) -> int:
    verificacao = integridade.verificar(sessao)
    if verificacao.ok:
        terminal.escrever("Integridade: ok (páginas, cadeia de auditoria e dados)")
    else:
        terminal.escrever_erro("Integridade: REPROVADA")
        for linha in _problemas(verificacao):
            terminal.escrever_erro(f"  {linha}")
    terminal.escrever("Uso de 'outro' (revisar a lista acima de 5%, ADR-0004):")
    for uso in integridade.uso_de_outro(sessao):
        fracao = "sem registros" if uso.fracao is None else f"{100 * uso.fracao:.1f}%"
        alerta = "  <- acima de 5%: revisar a lista" if uso.acima_do_limite else ""
        terminal.escrever(f"  {uso.campo}: {uso.outros} de {uso.registros} ({fracao}){alerta}")
    return 0 if verificacao.ok else 1


def _problemas(verificacao: integridade.Verificacao) -> list[str]:
    if verificacao.auditoria is None:
        return [f"página com defeito: {p}" for p in verificacao.paginas_corrompidas]
    linhas = []
    if verificacao.auditoria.cadeia is not None:
        linhas.append(f"cadeia quebrada na entrada {verificacao.auditoria.cadeia.entrada_id}")
    for d in verificacao.auditoria.dados:
        linhas.append(f"{d.entidade} {d.entidade_id}: {d.motivo} (entrada {d.entrada_id})")
    return linhas


def _backup(sessao: Sessao, args: argparse.Namespace, terminal: Terminal) -> int:
    backup = durabilidade.fazer_backup(sessao)
    terminal.escrever(f"Backup conferido em {backup.pasta}")
    copia = destino_externo.copiar_se_presente(sessao)
    if copia is not None:
        terminal.escrever(f"Cópia externa conferida em {copia.pasta}")
    return 0


def _exportar(sessao: Sessao, args: argparse.Namespace, terminal: Terminal) -> int:
    feito = exportar.exportar_csv(sessao, args.arquivo)
    terminal.escrever(f"{feito.exames} exames em {feito.arquivo} (dicionário: {feito.dicionario})")
    terminal.escrever("Atenção: o arquivo NÃO é cifrado. Guarde só onde for preciso.")
    return 0
