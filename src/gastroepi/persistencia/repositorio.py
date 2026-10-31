"""Repositório: a porta de `servicos` para o banco."""

from pathlib import Path
from types import TracebackType
from typing import Self

import sqlcipher3

from gastroepi.auditoria.cadeia import Acao, Entidade, EntradaDeAuditoria, Evento
from gastroepi.auditoria.conferencia import RelatorioDeIntegridade, conferir_dados
from gastroepi.dominio.ficha import Ficha
from gastroepi.persistencia.catalogos import resolver
from gastroepi.persistencia.conexao import abrir_conexao, transacao
from gastroepi.persistencia.estado_atual import estados_atuais
from gastroepi.persistencia.eventos import ler_chave_de_auditoria, ler_entradas, registrar_evento
from gastroepi.persistencia.fichas import inserir_ficha, ler_ficha
from gastroepi.persistencia.relogio import Relogio, RelogioDoSistema
from gastroepi.persistencia.schema import migrar


class Repositorio:
    def __init__(self, conexao: sqlcipher3.Connection, relogio: Relogio) -> None:
        self._conexao = conexao
        self._relogio = relogio
        self._chave_de_auditoria = ler_chave_de_auditoria(conexao)

    @classmethod
    def abrir(cls, caminho: Path, chave: bytes, relogio: Relogio | None = None) -> Self:
        conexao = abrir_conexao(caminho, chave)
        migrar(conexao)
        return cls(conexao, relogio or RelogioDoSistema())

    def fechar(self) -> None:
        self._conexao.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.fechar()

    def cadastrar(self, ficha: Ficha, usuario: str) -> int:
        with transacao(self._conexao):
            resolucao = resolver(self._conexao, ficha)
            for novo in resolucao.novos:
                self._auditar(usuario, Acao.CADASTRAR, novo.entidade, novo.id, depois=novo.retrato)
            paciente_id = inserir_ficha(self._conexao, resolucao)
            retrato = resolucao.ficha.model_dump_json()
            self._auditar(usuario, Acao.CADASTRAR, Entidade.PACIENTE, paciente_id, depois=retrato)
        return paciente_id

    def buscar(self, paciente_id: int) -> Ficha | None:
        return ler_ficha(self._conexao, paciente_id)

    def listar_auditoria(self) -> tuple[EntradaDeAuditoria, ...]:
        return ler_entradas(self._conexao)

    def verificar(self) -> RelatorioDeIntegridade:
        entradas = ler_entradas(self._conexao)
        return RelatorioDeIntegridade(dados=conferir_dados(entradas, estados_atuais(self._conexao)))

    def _auditar(
        self, usuario: str, acao: Acao, entidade: Entidade, entidade_id: int, depois: str
    ) -> None:
        momento = self._relogio.agora().isoformat(timespec="milliseconds")
        evento = Evento(momento, usuario, acao, entidade, entidade_id, None, depois)
        registrar_evento(self._conexao, self._chave_de_auditoria, evento)
