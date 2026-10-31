"""Bloqueio automático: sem teclado nem mouse por 15 min, o cofre fecha (PLANO, Fase 5).

O vigia filtra os eventos da aplicação inteira e reinicia o cronômetro a cada tecla,
clique ou rolagem. Mexer o mouse sem clicar não conta: um cursor parado em cima da
janela geraria movimento sem ninguém usando.
"""

from datetime import timedelta

from PySide6.QtCore import QEvent, QObject, QTimer, Signal

INATIVIDADE_PADRAO = timedelta(minutes=15)
_DE_USO = frozenset(
    {
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.Wheel,
        QEvent.Type.TouchBegin,
    }
)


class VigiaDeInatividade(QObject):
    inativo = Signal()

    def __init__(self, limite: timedelta = INATIVIDADE_PADRAO, pai: QObject | None = None) -> None:
        super().__init__(pai)
        self._cronometro = QTimer(self)
        self._cronometro.setSingleShot(True)
        self._cronometro.setInterval(int(limite.total_seconds() * 1000))
        self._cronometro.timeout.connect(self.inativo.emit)

    @property
    def ativo(self) -> bool:
        return self._cronometro.isActive()

    def iniciar(self) -> None:
        self._cronometro.start()

    def parar(self) -> None:
        self._cronometro.stop()

    def eventFilter(self, observado: QObject, evento: QEvent) -> bool:
        if evento.type() in _DE_USO and self._cronometro.isActive():
            self._cronometro.start()
        return False
