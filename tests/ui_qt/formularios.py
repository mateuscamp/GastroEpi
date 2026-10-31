"""Preencher os diálogos como o usuário faria (só fictícios)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QTableWidget, QWidget
from pytestqt.qtbot import QtBot

from gastroepi.dominio.exame import Examinador
from gastroepi.dominio.listas import UF, Displasia, Histologia, Indicacao, Paris, Segmento, Sexo
from gastroepi.ui_qt.dialogo_exame import Catalogos, DialogoExame
from gastroepi.ui_qt.dialogo_ficha import AbaPaciente
from gastroepi.ui_qt.dialogo_lesao import DialogoLesao

EXAMINADOR = Examinador(nome="Dra. Teste Fictícia", crm="777", uf=UF.PE)
CATALOGOS = Catalogos(("Hipertensão arterial", "Asma"), ("Dor abdominal",), (EXAMINADOR,))


# O pytest-qt não publica tipos para os métodos de teclado e mouse do QtBot.
def clicar(qtbot: QtBot, botao: QAbstractButton) -> None:
    qtbot.mouseClick(botao, Qt.MouseButton.LeftButton)  # type: ignore[no-untyped-call]  # pytest-qt


def digitar(qtbot: QtBot, campo: QWidget, texto: str) -> None:
    """Só ASCII: o QTest aborta o processo com acento (qasciikey.cpp)."""
    qtbot.keyClicks(campo, texto)  # type: ignore[no-untyped-call]  # pytest-qt


def tecla(qtbot: QtBot, campo: QWidget, qual: Qt.Key) -> None:
    qtbot.keyClick(campo, qual)  # type: ignore[no-untyped-call]  # pytest-qt


def celula(tabela: QTableWidget, linha: int, coluna: int) -> str:
    item = tabela.item(linha, coluna)
    assert item is not None, f"célula vazia em ({linha}, {coluna})"
    return item.text()


def preencher_lesao(qtbot: QtBot, dialogo: DialogoLesao, histologia: Histologia) -> None:
    dialogo.segmento.definir(Segmento.SIGMOIDE)
    dialogo.tamanho.setValue(12)
    dialogo.paris.definir(Paris.IS)
    dialogo.histologia.definir(histologia)
    dialogo.displasia.definir(Displasia.BAIXO)


def preencher_exame(qtbot: QtBot, dialogo: DialogoExame) -> None:
    digitar(qtbot, dialogo.data, "10/02/2024")
    dialogo.indicacao.definir(Indicacao.RASTREIO_RISCO_MEDIO)
    dialogo.examinador.setCurrentIndex(0)
    dialogo.intubacao.definir(True)


def preencher_paciente(qtbot: QtBot, aba: AbaPaciente, prontuario: str = "T00001") -> None:
    digitar(qtbot, aba.prontuario, prontuario)
    digitar(qtbot, aba.cpf, "529.982.247-25")
    aba.nome.setText("Paciente Fictícia de Teste")  # keyClicks só digita ASCII
    aba.sexo.definir(Sexo.FEMININO)
    digitar(qtbot, aba.nascimento, "05/03/1960")
