"""Bloqueio por inatividade: tecla e clique reiniciam o cronômetro; o tempo esgotado avisa."""

from datetime import timedelta

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLineEdit
from pytestqt.qtbot import QtBot

from gastroepi.ui_qt.vigia_inatividade import INATIVIDADE_PADRAO, VigiaDeInatividade


def test_padrao_e_15_minutos() -> None:
    assert timedelta(minutes=15) == INATIVIDADE_PADRAO


def test_sem_uso_avisa_e_para(qtbot: QtBot, qapp: QApplication) -> None:
    vigia = VigiaDeInatividade(timedelta(milliseconds=50))
    qapp.installEventFilter(vigia)
    vigia.iniciar()

    with qtbot.waitSignal(vigia.inativo, timeout=1000):
        pass

    assert not vigia.ativo
    qapp.removeEventFilter(vigia)


def test_tecla_reinicia_o_cronometro(qtbot: QtBot, qapp: QApplication) -> None:
    vigia = VigiaDeInatividade(timedelta(milliseconds=300))
    campo = QLineEdit()
    qtbot.addWidget(campo)
    vigia.iniciar()
    qtbot.wait(200)

    tecla = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a")
    assert vigia.eventFilter(campo, tecla) is False  # o evento segue para o campo
    qtbot.wait(200)

    assert vigia.ativo  # 400 ms desde o início, mas só 200 desde a tecla
    vigia.parar()
    assert not vigia.ativo


def test_movimento_sem_clique_nao_conta(qtbot: QtBot) -> None:
    vigia = VigiaDeInatividade(timedelta(seconds=10))
    campo = QLineEdit()
    qtbot.addWidget(campo)
    movimento = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(1, 1),
        QPointF(1, 1),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    vigia.iniciar()
    restante = vigia._cronometro.remainingTime()
    qtbot.wait(30)

    vigia.eventFilter(campo, movimento)

    assert vigia._cronometro.remainingTime() < restante
