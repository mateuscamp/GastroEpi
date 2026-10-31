"""Repositório: a porta de `servicos` para o banco.

Cada mutação de paciente ou catálogo roda num `BEGIN IMMEDIATE` que também grava o
evento de auditoria (AGENTS.md): ou entram os dois, ou nenhum. O retrato gravado no
evento é a ficha já com a grafia dos catálogos, que é o que `buscar` devolve depois.
"""

from pathlib import Path
from types import TracebackType
from typing import Self

import sqlcipher3

from gastroepi.auditoria.cadeia import Acao, Entidade, EntradaDeAuditoria, Evento, verificar_cadeia
from gastroepi.auditoria.conferencia import RelatorioDeIntegridade, conferir_dados
from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.paciente import Paciente
from gastroepi.persistencia.catalogos import (
    ItemNovo,
    Resolucao,
    TabelaDeItens,
    buscar_item,
    garantir_examinador,
    inserir_item,
    listar_examinadores,
    listar_itens,
    resolver,
)
from gastroepi.persistencia.conexao import (
    abrir_conexao,
    copiar_banco,
    paginas_corrompidas,
    traduzir_corrupcao,
    transacao,
    trocar_chave,
)
from gastroepi.persistencia.estado_atual import estados_atuais
from gastroepi.persistencia.eventos import ler_chave_de_auditoria, ler_entradas, registrar_evento
from gastroepi.persistencia.fichas import (
    apagar_ficha,
    atualizar_ficha,
    inserir_ficha,
    ler_fichas_ou_ilegiveis,
)
from gastroepi.persistencia.relogio import Relogio, RelogioDoSistema
from gastroepi.persistencia.schema import migrar


class PacienteInexistente(LookupError):
    def __init__(self, paciente_id: int) -> None:
        super().__init__(f"Paciente {paciente_id} não existe")
        self.paciente_id = paciente_id


class FichaIlegivel(ValueError):
    def __init__(self, paciente_id: int) -> None:
        super().__init__(f"Paciente {paciente_id} ilegível")
        self.paciente_id = paciente_id


class ProntuarioJaCadastrado(ValueError):
    """A mensagem não repete o prontuário (AGENTS.md, Segurança)."""

    def __init__(self) -> None:
        super().__init__("Prontuário já cadastrado em outro paciente")


class CpfJaCadastrado(ValueError):
    def __init__(self) -> None:
        super().__init__("CPF já cadastrado em outro paciente")


class Repositorio:
    def __init__(self, conexao: sqlcipher3.Connection, chave: bytes, relogio: Relogio) -> None:
        self._conexao = conexao
        self._chave = chave
        self._relogio = relogio
        with traduzir_corrupcao():
            self._chave_de_auditoria = ler_chave_de_auditoria(conexao)

    @classmethod
    def abrir(cls, caminho: Path, chave: bytes, relogio: Relogio | None = None) -> Self:
        conexao = abrir_conexao(caminho, chave)
        try:
            with traduzir_corrupcao():
                migrar(conexao)
            return cls(conexao, chave, relogio or RelogioDoSistema())
        except BaseException:
            conexao.close()
            raise

    def fechar(self) -> None:
        self._conexao.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.fechar()

    # ── Pacientes ─────────────────────────────────────────────────────

    def cadastrar(self, ficha: Ficha, usuario: str) -> int:
        with transacao(self._conexao):
            self._conferir_unicos(ficha.paciente, paciente_id=None)
            resolucao = self._resolver(ficha, usuario)
            paciente_id = inserir_ficha(self._conexao, resolucao)
            retrato = resolucao.ficha.model_dump_json()
            self._auditar(usuario, Acao.CADASTRAR, Entidade.PACIENTE, paciente_id, None, retrato)
        return paciente_id

    def editar(self, paciente_id: int, ficha: Ficha, usuario: str) -> None:
        """O 'antes' é o que está gravado, não o último retrato: se alguém alterou o banco
        por fora, a verificação acusa a quebra do histórico nesta entrada."""
        with transacao(self._conexao):
            antes = self._ficha_existente(paciente_id).model_dump_json()
            self._conferir_unicos(ficha.paciente, paciente_id)
            resolucao = self._resolver(ficha, usuario)
            atualizar_ficha(self._conexao, paciente_id, resolucao)
            depois = resolucao.ficha.model_dump_json()
            self._auditar(usuario, Acao.EDITAR, Entidade.PACIENTE, paciente_id, antes, depois)

    def excluir(self, paciente_id: int, usuario: str) -> None:
        with transacao(self._conexao):
            antes = self._ficha_existente(paciente_id).model_dump_json()
            apagar_ficha(self._conexao, paciente_id)
            self._auditar(usuario, Acao.EXCLUIR, Entidade.PACIENTE, paciente_id, antes, None)

    def buscar(self, paciente_id: int) -> Ficha | None:
        with transacao(self._conexao, "DEFERRED"):
            fichas = ler_fichas_ou_ilegiveis(self._conexao, paciente_id)
        return self._legiveis(fichas).get(paciente_id)

    def listar(self) -> dict[int, Ficha]:
        """Levanta `FichaIlegivel` no primeiro paciente que o domínio recusa: a tela não
        mostra um registro inválido, e a verificação aponta a entrada contrariada."""
        with transacao(self._conexao, "DEFERRED"):
            fichas = ler_fichas_ou_ilegiveis(self._conexao)
        return self._legiveis(fichas)

    # ── Catálogos ─────────────────────────────────────────────────────

    def adicionar_comorbidade(self, item: ItemDeCatalogo, usuario: str) -> str:
        """Devolve a grafia do catálogo: a já existente, se o nome repete sem a caixa."""
        return self._adicionar_item("comorbidade", item, usuario)

    def adicionar_sintoma(self, item: ItemDeCatalogo, usuario: str) -> str:
        return self._adicionar_item("sintoma", item, usuario)

    def listar_comorbidades(self) -> tuple[str, ...]:
        with traduzir_corrupcao():
            return tuple(nome for _, nome in listar_itens(self._conexao, "comorbidade"))

    def listar_sintomas(self) -> tuple[str, ...]:
        with traduzir_corrupcao():
            return tuple(nome for _, nome in listar_itens(self._conexao, "sintoma"))

    def adicionar_examinador(self, examinador: Examinador, usuario: str) -> None:
        with transacao(self._conexao):
            _, novo = garantir_examinador(self._conexao, examinador)
            if novo is not None:
                self._auditar_item(usuario, novo)

    def listar_examinadores(self) -> tuple[Examinador, ...]:
        with traduzir_corrupcao():
            return tuple(examinador for _, examinador in listar_examinadores(self._conexao))

    # ── Auditoria ─────────────────────────────────────────────────────

    def listar_auditoria(self) -> tuple[EntradaDeAuditoria, ...]:
        with traduzir_corrupcao():
            return ler_entradas(self._conexao)

    def verificar(self) -> RelatorioDeIntegridade:
        """Cadeia e dados lidos na mesma transação de leitura: um retrato coerente."""
        with transacao(self._conexao, "DEFERRED"):
            entradas = ler_entradas(self._conexao)
            atuais = estados_atuais(self._conexao)
        return RelatorioDeIntegridade(
            cadeia=verificar_cadeia(self._chave_de_auditoria, entradas),
            dados=conferir_dados(entradas, atuais),
        )

    def verificar_paginas(self) -> tuple[str, ...]:
        """Integridade física: o HMAC de cada página do SQLCipher (ADR-0003)."""
        return paginas_corrompidas(self._conexao)

    # ── Chave e cópia ─────────────────────────────────────────────────

    def trocar_chave(self, nova: bytes) -> None:
        """`PRAGMA rekey`. A chave da auditoria mora dentro do banco e não muda: a cadeia
        continua valendo (ADR-0003, item 5)."""
        trocar_chave(self._conexao, nova)
        self._chave = nova

    def fazer_backup(self, destino: Path) -> None:
        with traduzir_corrupcao():
            copiar_banco(self._conexao, destino, self._chave)

    # ── Internos ──────────────────────────────────────────────────────

    @staticmethod
    def _legiveis(fichas: dict[int, Ficha | None]) -> dict[int, Ficha]:
        legiveis = {}
        for paciente_id, ficha in fichas.items():
            if ficha is None:
                raise FichaIlegivel(paciente_id)
            legiveis[paciente_id] = ficha
        return legiveis

    def _ficha_existente(self, paciente_id: int) -> Ficha:
        """Lê dentro da transação de escrita que já está aberta."""
        ficha = self._legiveis(ler_fichas_ou_ilegiveis(self._conexao, paciente_id)).get(paciente_id)
        if ficha is None:
            raise PacienteInexistente(paciente_id)
        return ficha

    def _conferir_unicos(self, paciente: Paciente, paciente_id: int | None) -> None:
        sql = "SELECT 1 FROM paciente WHERE {} = ? AND id IS NOT ?"
        repetido = self._conexao.execute(
            sql.format("prontuario"), (paciente.prontuario, paciente_id)
        )
        if repetido.fetchone() is not None:
            raise ProntuarioJaCadastrado
        if paciente.cpf is None:
            return
        if self._conexao.execute(sql.format("cpf"), (paciente.cpf, paciente_id)).fetchone():
            raise CpfJaCadastrado

    def _resolver(self, ficha: Ficha, usuario: str) -> Resolucao:
        resolucao = resolver(self._conexao, ficha)
        for novo in resolucao.novos:
            self._auditar_item(usuario, novo)
        return resolucao

    def _adicionar_item(self, tabela: TabelaDeItens, item: ItemDeCatalogo, usuario: str) -> str:
        with transacao(self._conexao):
            existente = buscar_item(self._conexao, tabela, item.nome)
            if existente is not None:
                return existente[1]
            self._auditar_item(usuario, inserir_item(self._conexao, tabela, item.nome))
        return item.nome

    def _auditar_item(self, usuario: str, novo: ItemNovo) -> None:
        self._auditar(usuario, Acao.CADASTRAR, novo.entidade, novo.id, None, novo.retrato)

    def _auditar(
        self,
        usuario: str,
        acao: Acao,
        entidade: Entidade,
        entidade_id: int,
        antes: str | None,
        depois: str | None,
    ) -> None:
        momento = self._relogio.agora().isoformat(timespec="milliseconds")
        evento = Evento(momento, usuario, acao, entidade, entidade_id, antes, depois)
        registrar_evento(self._conexao, self._chave_de_auditoria, evento)
