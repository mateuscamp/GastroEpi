"""Exportar o CSV para análise: uma linha por exame, sem identificar o paciente.

O arquivo sai sem cifra (é a única saída assim, Princípio II), e a tela diz isso antes
do botão. Escolha do dono (2026-10-31): só a exportação anônima.
"""

from pathlib import Path

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gastroepi.servicos import exportar
from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.aparencia import Aviso, com_papel, rotulo
from gastroepi.ui_qt.perguntas import Perguntas
from gastroepi.ui_qt.textos import mensagem_de_erro

AVISO_SEM_CIFRA = (
    "Atenção: o arquivo exportado NÃO é cifrado. Qualquer pessoa com o arquivo consegue"
    " ler. Ele não tem nome, CPF, prontuário, data de nascimento nem textos livres, mas"
    " guarde-o só onde for preciso e apague quando terminar a análise."
)
_O_QUE_SAI = (
    "Sai uma planilha (CSV, abre no Excel) com uma linha por exame: sexo, idade, ano do"
    " exame, indicação, qualidade, lesões e uma coluna sim/não para cada comorbidade e"
    " sintoma. Junto sai um segundo arquivo explicando cada coluna."
)


class TelaExportar(QWidget):
    def __init__(self, sessao: Sessao, perguntas: Perguntas, sugestao: Path | None = None) -> None:
        super().__init__()
        self._sessao, self._perguntas = sessao, perguntas
        self._sugestao = sugestao or Path.home() / "gastroepi-exames.csv"
        self.exportar = com_papel(QPushButton("Exportar CSV…", self), "principal")
        self.aviso = Aviso(self)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Exportar para análise", "titulo", self))
        disposicao.addWidget(rotulo(_O_QUE_SAI, "", self))
        disposicao.addWidget(rotulo(AVISO_SEM_CIFRA, "alerta", self))
        disposicao.addWidget(self.exportar)
        disposicao.addWidget(self.aviso)
        disposicao.addStretch()
        self.exportar.clicked.connect(self._exportar)
        self.exportar.setEnabled(not sessao.somente_leitura)

    def atualizar(self) -> None:
        """Nada a recarregar: a tela só lê o banco ao exportar."""

    def _exportar(self) -> None:
        arquivo = self._perguntas.arquivo_para_salvar(self, "Salvar o CSV", self._sugestao)
        if arquivo is None:
            return
        try:
            feito = exportar.exportar_csv(self._sessao, arquivo)
        except (OSError, PermissionError) as erro:
            self.aviso.erro(mensagem_de_erro(erro))
            return
        self.aviso.sucesso(
            f"{feito.exames} exames exportados em {feito.arquivo}.\n"
            f"Explicação das colunas: {feito.dicionario}.\nLembre: o arquivo não é cifrado."
        )
