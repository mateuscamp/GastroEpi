"""Repositório: cada mutação e o seu evento de auditoria na mesma transação."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlcipher3

from gastroepi.auditoria.cadeia import QuebraDaCadeia
from gastroepi.auditoria.conferencia import Divergencia, Motivo
from gastroepi.dominio.catalogo import ItemDeCatalogo
from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.ficha import Ficha
from gastroepi.dominio.ficticios import gerar_fichas
from gastroepi.dominio.listas import UF, Histologia
from gastroepi.persistencia.catalogos import ExaminadorDivergente
from gastroepi.persistencia.conexao import BancoCorrompido, ChaveIncorreta
from gastroepi.persistencia.relogio import Relogio
from gastroepi.persistencia.repositorio import (
    CpfJaCadastrado,
    FichaIlegivel,
    PacienteInexistente,
    ProntuarioJaCadastrado,
    Repositorio,
)


@pytest.fixture
def caminho(tmp_path: Path) -> Path:
    return tmp_path / "gastroepi.db"


@pytest.fixture
def repositorio(caminho: Path, chave_de_dados: bytes, relogio: Relogio) -> Iterator[Repositorio]:
    repositorio = Repositorio.abrir(caminho, chave_de_dados, relogio)
    yield repositorio
    repositorio.fechar()


def ficha(numero: int = 1, semente: int = 11) -> Ficha:
    return gerar_fichas(semente=semente, quantidade=numero)[-1]


def alterar_por_fora(caminho: Path, chave: bytes, sql: str, *parametros: object) -> list[object]:
    """Uma ferramenta externa com a chave (DB Browser for SQLCipher), sem passar pelo app."""
    conexao = sqlcipher3.connect(str(caminho))
    conexao.execute(f"PRAGMA key = \"x'{chave.hex()}'\"")
    linhas: list[object] = conexao.execute(sql, parametros).fetchall()
    conexao.commit()
    conexao.close()
    return linhas


def test_cenario_3_linha_de_paciente_alterada_por_fora_acusa_id_e_momento_da_entrada(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    paciente_id = repositorio.cadastrar(ficha(), usuario="teste")
    entrada = repositorio.listar_auditoria()[-1]
    repositorio.fechar()

    alterar_por_fora(
        caminho, chave_de_dados, "UPDATE paciente SET nome = 'Outro Nome' WHERE id = ?", paciente_id
    )

    with Repositorio.abrir(caminho, chave_de_dados) as reaberto:
        relatorio = reaberto.verificar()
    assert relatorio.dados == (
        Divergencia(
            entidade="paciente",
            entidade_id=paciente_id,
            motivo=Motivo.ALTERADO,
            entrada_id=entrada.id,
            momento=entrada.evento.momento,
        ),
    )


def ficha_completa() -> Ficha:
    """A primeira ficha da semente com exames, lesões, sintomas, comorbidades e histórico."""
    return next(
        f
        for f in gerar_fichas(semente=3, quantidade=200)
        if f.paciente.comorbidades
        and f.paciente.historico_familiar
        and len(f.exames) > 1
        and any(e.sintomas for e in f.exames)
        and any(len(e.lesoes) > 1 for e in f.exames)
    )


def test_buscar_devolve_a_ficha_cadastrada_com_exames_lesoes_e_historico(
    repositorio: Repositorio,
) -> None:
    original = ficha_completa()

    paciente_id = repositorio.cadastrar(original, usuario="teste")

    assert repositorio.buscar(paciente_id) == original


def test_buscar_paciente_inexistente_devolve_none(repositorio: Repositorio) -> None:
    assert repositorio.buscar(99) is None


def test_banco_sem_alteracao_por_fora_nao_acusa_nada(repositorio: Repositorio) -> None:
    for original in gerar_fichas(semente=5, quantidade=30):
        repositorio.cadastrar(original, usuario="teste")

    assert repositorio.verificar().dados == ()


def com_paciente(original: Ficha, **mudancas: object) -> Ficha:
    paciente = original.paciente.model_copy(update=mudancas)
    return original.model_copy(update={"paciente": paciente})


def test_editar_grava_a_ficha_nova_e_um_evento_com_antes_e_depois(repositorio: Repositorio) -> None:
    original = ficha_completa()
    nova = com_paciente(ficha(numero=2), prontuario=original.paciente.prontuario)
    paciente_id = repositorio.cadastrar(original, usuario="teste")

    repositorio.editar(paciente_id, nova, usuario="outra")

    assert repositorio.buscar(paciente_id) == nova
    ultima = repositorio.listar_auditoria()[-1].evento
    assert (ultima.acao, ultima.entidade, ultima.entidade_id) == ("editar", "paciente", paciente_id)
    assert (ultima.usuario, ultima.antes, ultima.depois) == (
        "outra", original.model_dump_json(), nova.model_dump_json(),
    )  # fmt: skip
    assert repositorio.verificar().ok


def test_excluir_apaga_a_ficha_em_cascata_e_grava_o_antes(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    original = ficha_completa()
    paciente_id = repositorio.cadastrar(original, usuario="teste")

    repositorio.excluir(paciente_id, usuario="teste")

    assert repositorio.buscar(paciente_id) is None
    ultima = repositorio.listar_auditoria()[-1].evento
    assert (ultima.acao, ultima.entidade_id, ultima.antes, ultima.depois) == (
        "excluir", paciente_id, original.model_dump_json(), None,
    )  # fmt: skip
    assert repositorio.verificar().ok
    repositorio.fechar()
    sobras = "SELECT (SELECT count(*) FROM exame) + (SELECT count(*) FROM lesao)"
    assert alterar_por_fora(caminho, chave_de_dados, sobras) == [(0,)]


@pytest.mark.parametrize("operacao", ["editar", "excluir"])
def test_mutar_paciente_inexistente_levanta_sem_gravar_evento(
    repositorio: Repositorio, operacao: str
) -> None:
    with pytest.raises(PacienteInexistente, match="42"):
        if operacao == "editar":
            repositorio.editar(42, ficha(), usuario="teste")
        else:
            repositorio.excluir(42, usuario="teste")
    assert repositorio.listar_auditoria() == ()


def test_prontuario_repetido_levanta_sem_gravar_nada(repositorio: Repositorio) -> None:
    primeira = ficha(numero=1)
    repositorio.cadastrar(primeira, usuario="teste")
    antes = repositorio.listar_auditoria()
    repetida = com_paciente(ficha_completa(), prontuario=primeira.paciente.prontuario)

    with pytest.raises(ProntuarioJaCadastrado) as erro:
        repositorio.cadastrar(repetida, usuario="teste")

    assert primeira.paciente.prontuario not in str(erro.value)
    assert repositorio.listar_auditoria() == antes
    assert len(repositorio.listar()) == 1


def test_cpf_repetido_levanta_sem_mostrar_o_cpf(repositorio: Repositorio) -> None:
    primeira = ficha(numero=1)
    repositorio.cadastrar(primeira, usuario="teste")
    repetida = com_paciente(ficha(numero=2), cpf=primeira.paciente.cpf)

    with pytest.raises(CpfJaCadastrado) as erro:
        repositorio.cadastrar(repetida, usuario="teste")

    assert str(primeira.paciente.cpf) not in str(erro.value)


def test_editar_para_o_prontuario_de_outro_paciente_levanta(repositorio: Repositorio) -> None:
    primeira, segunda = ficha(numero=1), ficha(numero=2)
    repositorio.cadastrar(primeira, usuario="teste")
    segunda_id = repositorio.cadastrar(segunda, usuario="teste")

    with pytest.raises(ProntuarioJaCadastrado):
        repositorio.editar(
            segunda_id, com_paciente(segunda, prontuario=primeira.paciente.prontuario), "teste"
        )


def test_pacientes_sem_cpf_nao_colidem(repositorio: Repositorio) -> None:
    repositorio.cadastrar(com_paciente(ficha(numero=1), cpf=None), usuario="teste")
    repositorio.cadastrar(com_paciente(ficha(numero=2), cpf=None), usuario="teste")

    assert len(repositorio.listar()) == 2


def test_listar_devolve_as_fichas_por_id(repositorio: Repositorio) -> None:
    fichas = gerar_fichas(semente=8, quantidade=5)
    ids = [repositorio.cadastrar(f, usuario="teste") for f in fichas]

    assert repositorio.listar() == dict(zip(ids, fichas, strict=True))


def test_item_de_catalogo_reaproveita_a_grafia_existente_sem_distinguir_caixa(
    repositorio: Repositorio,
) -> None:
    repositorio.adicionar_comorbidade(ItemDeCatalogo(nome="Hipertensão Arterial"), usuario="teste")
    original = com_paciente(ficha(), comorbidades=("HIPERTENSÃO ARTERIAL",))

    paciente_id = repositorio.cadastrar(original, usuario="teste")

    assert repositorio.buscar(paciente_id) == com_paciente(
        original, comorbidades=("Hipertensão Arterial",)
    )
    assert repositorio.listar_comorbidades() == ("Hipertensão Arterial",)


def test_adicionar_item_de_catalogo_audita_uma_vez(repositorio: Repositorio) -> None:
    assert (
        repositorio.adicionar_sintoma(ItemDeCatalogo(nome="Tenesmo"), usuario="teste") == "Tenesmo"
    )
    assert (
        repositorio.adicionar_sintoma(ItemDeCatalogo(nome="tenesmo"), usuario="teste") == "Tenesmo"
    )

    eventos = [e.evento for e in repositorio.listar_auditoria()]
    assert [(e.acao, e.entidade, e.depois) for e in eventos] == [
        ("cadastrar", "sintoma", '{"nome": "Tenesmo"}'),
    ]
    assert repositorio.listar_sintomas() == ("Tenesmo",)


def test_examinador_com_mesmo_crm_e_outro_nome_levanta_sem_gravar_nada(
    repositorio: Repositorio,
) -> None:
    original = ficha()
    repositorio.cadastrar(original, usuario="teste")
    antes = repositorio.listar_auditoria()
    exame = original.exames[0]
    outro_nome = exame.examinador.model_copy(update={"nome": "Dr. Outro Nome"})
    exames = (exame.model_copy(update={"examinador": outro_nome}),)
    divergente = com_paciente(ficha(numero=2)).model_copy(update={"exames": exames})

    with pytest.raises(ExaminadorDivergente, match=exame.examinador.crm):
        repositorio.cadastrar(divergente, usuario="teste")
    assert repositorio.listar_auditoria() == antes


def test_adicionar_examinador_audita_e_lista(repositorio: Repositorio) -> None:
    examinador = Examinador(nome="Dra. Teste Fictícia", crm="123", uf=UF.BA)

    repositorio.adicionar_examinador(examinador, usuario="teste")
    repositorio.adicionar_examinador(examinador, usuario="teste")

    assert repositorio.listar_examinadores() == (examinador,)
    assert len(repositorio.listar_auditoria()) == 1


def test_verificar_aponta_entrada_de_auditoria_alterada_por_fora(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    for original in gerar_fichas(semente=4, quantidade=3):
        repositorio.cadastrar(original, usuario="teste")
    alvo = repositorio.listar_auditoria()[2]
    repositorio.fechar()

    alterar_por_fora(caminho, chave_de_dados, "DROP TRIGGER IF EXISTS auditoria_sem_update")
    alterar_por_fora(
        caminho, chave_de_dados, "UPDATE auditoria SET usuario = 'x' WHERE id = ?", alvo.id
    )

    with Repositorio.abrir(caminho, chave_de_dados) as reaberto:
        assert reaberto.verificar().cadeia == QuebraDaCadeia(alvo.id, alvo.evento.momento)


def test_edicao_depois_de_alteracao_por_fora_deixa_o_rastro(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    """Editar pelo app não lava a alteração externa: o 'antes' da edição não confere com
    o 'depois' da entrada anterior, e a verificação aponta essa edição."""
    original = ficha()
    paciente_id = repositorio.cadastrar(original, usuario="teste")
    repositorio.fechar()
    alterar_por_fora(
        caminho, chave_de_dados, "UPDATE paciente SET nome = 'Outro' WHERE id = ?", paciente_id
    )

    with Repositorio.abrir(caminho, chave_de_dados) as reaberto:
        reaberto.editar(paciente_id, original, usuario="teste")
        edicao = reaberto.listar_auditoria()[-1]
        assert reaberto.verificar().dados == (
            Divergencia("paciente", paciente_id, Motivo.HISTORICO_INTERROMPIDO, edicao.id,
                        edicao.evento.momento),
        )  # fmt: skip


def ficha_com_adenoma_tubular() -> Ficha:
    return next(
        f
        for f in gerar_fichas(semente=6, quantidade=100)
        if any(lesao.histologia is Histologia.TUBULAR for e in f.exames for lesao in e.lesoes)
    )


@pytest.fixture
def banco_com_ficha_ilegivel(repositorio: Repositorio, caminho: Path, chave_de_dados: bytes) -> int:
    """Displasia incoerente gravada por fora: passa no CHECK, o domínio recusa."""
    repositorio.cadastrar(ficha(numero=1), usuario="teste")
    adenoma = com_paciente(ficha_com_adenoma_tubular(), prontuario="A00001", cpf=None)
    paciente_id = repositorio.cadastrar(adenoma, usuario="teste")
    repositorio.fechar()
    alterar_por_fora(
        caminho, chave_de_dados,
        "UPDATE lesao SET displasia = 'nao_se_aplica' WHERE histologia = 'adenoma_tubular'"
        " AND exame_id IN (SELECT id FROM exame WHERE paciente_id = ?)",
        paciente_id,
    )  # fmt: skip
    return paciente_id


def test_registro_que_o_dominio_recusa_e_acusado_sem_derrubar_a_verificacao(
    banco_com_ficha_ilegivel: int, caminho: Path, chave_de_dados: bytes
) -> None:
    with Repositorio.abrir(caminho, chave_de_dados) as reaberto:
        relatorio = reaberto.verificar()
        entrada = reaberto.listar_auditoria()[-1]

    assert relatorio.dados == (
        Divergencia("paciente", banco_com_ficha_ilegivel, Motivo.ALTERADO, entrada.id,
                    entrada.evento.momento),
    )  # fmt: skip


def test_listar_com_registro_ilegivel_levanta_apontando_o_paciente(
    banco_com_ficha_ilegivel: int, caminho: Path, chave_de_dados: bytes
) -> None:
    with Repositorio.abrir(caminho, chave_de_dados) as reaberto:
        with pytest.raises(FichaIlegivel) as erro:
            reaberto.listar()
        with pytest.raises(FichaIlegivel):
            reaberto.buscar(banco_com_ficha_ilegivel)

    assert erro.value.paciente_id == banco_com_ficha_ilegivel


OUTRA_CHAVE = bytes(range(32, 64))


def test_trocar_chave_preserva_cadeia_e_dados(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    for original in gerar_fichas(semente=12, quantidade=10):
        repositorio.cadastrar(original, usuario="teste")
    antes = repositorio.listar()

    repositorio.trocar_chave(OUTRA_CHAVE)

    assert repositorio.verificar_paginas() == ()
    assert repositorio.verificar().ok
    repositorio.fechar()
    with pytest.raises(ChaveIncorreta):
        Repositorio.abrir(caminho, chave_de_dados)
    with Repositorio.abrir(caminho, OUTRA_CHAVE) as reaberto:
        assert reaberto.listar() == antes
        assert reaberto.verificar().ok


def test_backup_sai_cifrado_e_abre_com_a_mesma_chave(
    repositorio: Repositorio, tmp_path: Path, chave_de_dados: bytes
) -> None:
    original = ficha_completa()
    repositorio.cadastrar(original, usuario="teste")
    destino = tmp_path / "copia.db"

    repositorio.fazer_backup(destino)

    assert original.paciente.nome.encode() not in destino.read_bytes()
    with Repositorio.abrir(destino, chave_de_dados) as copia:
        assert list(copia.listar().values()) == [original]
        assert copia.verificar().ok


def test_banco_integro_nao_tem_pagina_corrompida(repositorio: Repositorio) -> None:
    repositorio.cadastrar(ficha(), usuario="teste")

    assert repositorio.verificar_paginas() == ()


def test_byte_trocado_numa_pagina_e_acusado_nas_paginas_e_na_leitura(
    repositorio: Repositorio, caminho: Path, chave_de_dados: bytes
) -> None:
    for original in gerar_fichas(semente=13, quantidade=40):
        repositorio.cadastrar(original, usuario="teste")
    repositorio.fechar()  # o último fechamento leva o WAL para o .db
    bruto = bytearray(caminho.read_bytes())
    ultima = len(bruto) // 4096
    bruto[(ultima - 1) * 4096 + 2000] ^= 0x01
    caminho.write_bytes(bytes(bruto))

    with Repositorio.abrir(caminho, chave_de_dados) as corrompido:
        assert corrompido.verificar_paginas() == (f"HMAC verification failed for page {ultima}",)
        with pytest.raises(BancoCorrompido):
            corrompido.listar_auditoria()
