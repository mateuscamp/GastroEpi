"""Governança do ADR-0002, "★ Mutação sempre auditada": teste de estado do hypothesis.

Sequências aleatórias de cadastrar, editar, excluir, recusas (prontuário repetido,
paciente inexistente) e acréscimos ao catálogo. Depois de cada passo:
- a verificação não acusa nada na cadeia nem nos dados;
- o banco devolve exatamente o modelo em memória (com a grafia dos catálogos);
- uma mutação recusada não deixou rastro (nenhuma entrada nova de auditoria).
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    invariant,
    rule,
    run_state_machine_as_test,
)

from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.cpf import digitos_verificadores
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.persistencia.relogio import Relogio
from gastroepi.persistencia.repositorio import (
    PacienteInexistente,
    ProntuarioJaCadastrado,
    Repositorio,
)

CHAVE = bytes(range(32))
SEMENTES = st.integers(min_value=0, max_value=2**32 - 1)
# Variações de caixa de itens que as fichas fictícias também usam.
NOMES_DE_CATALOGO = st.sampled_from(
    ["Obesidade", "OBESIDADE", "obesidade", "Asma", "ASMA", "Tabagismo", "tabagismo"]
)
NOMES_DE_SINTOMA = st.sampled_from(["Dor abdominal", "DOR ABDOMINAL", "Tenesmo", "tenesmo"])


class MutacoesAleatorias(RuleBasedStateMachine):
    pacientes = Bundle("pacientes")

    def __init__(self, relogio: Relogio) -> None:
        super().__init__()
        self.pasta = Path(tempfile.mkdtemp(prefix="gastroepi-hypothesis-"))
        self.repositorio = Repositorio.abrir(self.pasta / "gastroepi.db", CHAVE, relogio)
        self.esperado: dict[int, Ficha] = {}
        self.grafias: dict[str, dict[str, str]] = {"comorbidade": {}, "sintoma": {}}
        self.numero = 0

    def teardown(self) -> None:
        self.repositorio.fechar()
        shutil.rmtree(self.pasta, ignore_errors=True)

    def _ficha(self, semente: int) -> Ficha:
        """Ficha fictícia válida com prontuário e CPF únicos nesta sequência."""
        self.numero += 1
        base = f"{100_000_000 + self.numero:09d}"
        ficha = gerar_fichas(semente=semente, quantidade=1)[0]
        paciente = ficha.paciente.model_copy(
            update={"prontuario": f"H{self.numero:05d}", "cpf": base + digitos_verificadores(base)}
        )
        return ficha.model_copy(update={"paciente": paciente})

    def _grafia(self, catalogo: str, nome: str) -> str:
        return self.grafias[catalogo].setdefault(nome.casefold(), nome)

    def _como_gravada(self, ficha: Ficha) -> Ficha:
        comorbidades = tuple(self._grafia("comorbidade", c) for c in ficha.paciente.comorbidades)
        exames = tuple(
            e.model_copy(update={"sintomas": tuple(self._grafia("sintoma", s) for s in e.sintomas)})
            for e in ficha.exames
        )
        paciente = ficha.paciente.model_copy(update={"comorbidades": comorbidades})
        return ficha.model_copy(update={"paciente": paciente, "exames": exames})

    @rule(target=pacientes, semente=SEMENTES)
    def cadastrar(self, semente: int) -> int:
        ficha = self._ficha(semente)
        paciente_id = self.repositorio.cadastrar(ficha, usuario="hypothesis")
        self.esperado[paciente_id] = self._como_gravada(ficha)
        return paciente_id

    @rule(paciente_id=pacientes, semente=SEMENTES)
    def editar(self, paciente_id: int, semente: int) -> None:
        ficha = self._ficha(semente)
        if paciente_id not in self.esperado:
            self._recusada(PacienteInexistente, self.repositorio.editar, paciente_id, ficha)
            return
        self.repositorio.editar(paciente_id, ficha, usuario="hypothesis")
        self.esperado[paciente_id] = self._como_gravada(ficha)

    @rule(paciente_id=pacientes)
    def excluir(self, paciente_id: int) -> None:
        if paciente_id not in self.esperado:
            self._recusada(PacienteInexistente, self.repositorio.excluir, paciente_id)
            return
        self.repositorio.excluir(paciente_id, usuario="hypothesis")
        del self.esperado[paciente_id]

    @rule(paciente_id=pacientes, semente=SEMENTES)
    def cadastrar_prontuario_repetido(self, paciente_id: int, semente: int) -> None:
        if paciente_id not in self.esperado:
            return
        ficha = self._ficha(semente)
        prontuario = self.esperado[paciente_id].paciente.prontuario
        repetida = ficha.model_copy(
            update={"paciente": ficha.paciente.model_copy(update={"prontuario": prontuario})}
        )
        self._recusada(ProntuarioJaCadastrado, self.repositorio.cadastrar, repetida)

    @rule(nome=NOMES_DE_CATALOGO)
    def adicionar_comorbidade(self, nome: str) -> None:
        gravado = self.repositorio.adicionar_comorbidade(
            ItemDeCatalogo(nome=nome), usuario="hypothesis"
        )
        assert gravado == self._grafia("comorbidade", nome)

    @rule(nome=NOMES_DE_SINTOMA)
    def adicionar_sintoma(self, nome: str) -> None:
        gravado = self.repositorio.adicionar_sintoma(
            ItemDeCatalogo(nome=nome), usuario="hypothesis"
        )
        assert gravado == self._grafia("sintoma", nome)

    def _recusada(self, erro: type[Exception], mutacao: object, *argumentos: object) -> None:
        antes = len(self.repositorio.listar_auditoria())
        assert callable(mutacao)
        with pytest.raises(erro):
            mutacao(*argumentos, usuario="hypothesis")
        assert len(self.repositorio.listar_auditoria()) == antes

    @invariant()
    def cadeia_e_dados_sem_inconsistencia(self) -> None:
        relatorio = self.repositorio.verificar()
        assert relatorio.cadeia is None
        assert relatorio.dados == ()

    @invariant()
    def banco_igual_ao_modelo(self) -> None:
        assert self.repositorio.listar() == self.esperado
        assert self.repositorio.listar_comorbidades() == tuple(
            sorted(self.grafias["comorbidade"].values(), key=str.casefold)
        )


def test_mutacoes_aleatorias_nao_deixam_inconsistencia(relogio: Relogio) -> None:
    class ComRelogioFalso(MutacoesAleatorias):
        def __init__(self) -> None:
            super().__init__(relogio)

    run_state_machine_as_test(
        ComRelogioFalso, settings=settings(max_examples=40, stateful_step_count=15, deadline=None)
    )
