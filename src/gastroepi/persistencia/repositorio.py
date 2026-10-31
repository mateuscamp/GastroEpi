"""Repositório: a porta de `servicos` para o banco.

Cada mutação de paciente ou catálogo roda num `BEGIN IMMEDIATE` que também grava o
evento de auditoria (AGENTS.md): ou entram os dois, ou nenhum. O retrato gravado no
evento é a ficha já com a grafia dos catálogos, que é o que `buscar` devolve depois.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
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
from gastroepi.persistencia.backups import (
    NOME_DA_CHAVE,
    Backup,
    copiar_com_fsync,
    gravar_backup,
)
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
    BancoCorrompido,
    BancoSomenteLeitura,
    abrir_conexao,
    copiar_banco,
    paginas_corrompidas,
    passa_no_quick_check,
    proibir_escrita,
    traduzir_corrupcao,
    transacao,
    trocar_chave,
)
from gastroepi.persistencia.estado_atual import estados_atuais
from gastroepi.persistencia.eventos import (
    gravar_metadado,
    ler_chave_de_auditoria,
    ler_entradas,
    ler_metadado,
    registrar_evento,
)
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
    """`somente_leitura`: o banco não passou no `quick_check` da abertura (ADR-0005). Ele
    não é migrado, toda escrita levanta `BancoSomenteLeitura`, e a leitura vai até onde
    as páginas deixarem."""

    def __init__(
        self,
        conexao: sqlcipher3.Connection,
        chave: bytes,
        relogio: Relogio,
        somente_leitura: bool = False,
    ) -> None:
        self._conexao = conexao
        self._chave = chave
        self._relogio = relogio
        self.somente_leitura = somente_leitura
        self._chave_de_auditoria: bytes | None = None
        try:
            with traduzir_corrupcao():
                self._chave_de_auditoria = ler_chave_de_auditoria(conexao)
        except BancoCorrompido:
            if not somente_leitura:
                raise

    @classmethod
    def abrir(cls, caminho: Path, chave: bytes, relogio: Relogio | None = None) -> Self:
        conexao = abrir_conexao(caminho, chave)
        try:
            integro = passa_no_quick_check(conexao)
            with traduzir_corrupcao():
                (migrar if integro else proibir_escrita)(conexao)
            return cls(conexao, chave, relogio or RelogioDoSistema(), not integro)
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
        with self._escrita():
            self._conferir_unicos(ficha.paciente, paciente_id=None)
            resolucao = self._resolver(ficha, usuario)
            paciente_id = inserir_ficha(self._conexao, resolucao)
            retrato = resolucao.ficha.model_dump_json()
            self._auditar(usuario, Acao.CADASTRAR, Entidade.PACIENTE, paciente_id, None, retrato)
        return paciente_id

    def editar(self, paciente_id: int, ficha: Ficha, usuario: str) -> None:
        """O 'antes' é o que está gravado, não o último retrato: se alguém alterou o banco
        por fora, a verificação acusa a quebra do histórico nesta entrada."""
        with self._escrita():
            antes = self._ficha_existente(paciente_id).model_dump_json()
            self._conferir_unicos(ficha.paciente, paciente_id)
            resolucao = self._resolver(ficha, usuario)
            atualizar_ficha(self._conexao, paciente_id, resolucao)
            depois = resolucao.ficha.model_dump_json()
            self._auditar(usuario, Acao.EDITAR, Entidade.PACIENTE, paciente_id, antes, depois)

    def excluir(self, paciente_id: int, usuario: str) -> None:
        with self._escrita():
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
        with self._escrita():
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
        if self._chave_de_auditoria is None:
            raise BancoCorrompido
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
        if self.somente_leitura:
            raise BancoSomenteLeitura
        trocar_chave(self._conexao, nova)
        self._chave = nova

    def fazer_backup(
        self, pasta_de_backups: Path, arquivo_de_chave: Path, momento: datetime
    ) -> Backup:
        """Cópia conferida antes de ganhar o nome final (ADR-0005, item 4). Somente leitura
        não copia: uma cópia do banco estragado não pode empurrar as boas na rotação."""
        if self.somente_leitura:
            raise BancoSomenteLeitura

        def pela_api_de_backup(destino: Path) -> None:
            with traduzir_corrupcao():
                copiar_banco(self._conexao, destino, self._chave)

        return gravar_backup(
            pela_api_de_backup, arquivo_de_chave, self._chave, pasta_de_backups, momento
        )

    def copiar_backup(self, origem: Backup, pasta_de_destino: Path) -> Backup:
        """Leva um backup pronto para outra pasta, com a mesma conferência (destino externo).
        Se ele já está lá, não copia de novo."""
        ja_copiado = pasta_de_destino / origem.pasta.name
        if ja_copiado.is_dir():  # só ganha o nome final depois de conferido
            return Backup(ja_copiado, origem.momento)
        return gravar_backup(
            lambda destino: copiar_com_fsync(origem.banco, destino),
            origem.pasta / NOME_DA_CHAVE,
            self._chave,
            pasta_de_destino,
            origem.momento,
        )

    def marca_de_alteracao(self) -> int:
        """O maior id da auditoria: toda mutação grava um evento (ADR-0005, item 6)."""
        with traduzir_corrupcao():
            linha = self._conexao.execute("SELECT coalesce(max(id), 0) FROM auditoria")
            marca: int = linha.fetchone()[0]
        return marca

    # ── Preferências (metadados, fora da auditoria) ───────────────────

    def ler_preferencia(self, nome: str) -> str | None:
        with traduzir_corrupcao():
            return ler_metadado(self._conexao, nome)

    def gravar_preferencia(self, nome: str, valor: str | None) -> None:
        with self._escrita():
            gravar_metadado(self._conexao, nome, valor)

    # ── Internos ──────────────────────────────────────────────────────

    @contextmanager
    def _escrita(self) -> Iterator[None]:
        if self.somente_leitura:
            raise BancoSomenteLeitura
        with transacao(self._conexao):
            yield

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
        with self._escrita():
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
        assert self._chave_de_auditoria is not None  # só None em somente leitura, sem escrita
        registrar_evento(self._conexao, self._chave_de_auditoria, evento)
