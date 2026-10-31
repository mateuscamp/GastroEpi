"""StatCalc: as calculadoras da v0.1.16 numa aba cada.

Qualidade e estratificação leem o banco; as outras fazem a conta com os números
digitados e não leem nem gravam nada.
"""

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from gastroepi.servicos.acesso import Sessao
from gastroepi.ui_qt.aparencia import rotulo
from gastroepi.ui_qt.calc_amostra import CalcAmostra
from gastroepi.ui_qt.calc_estratificacao import CalcEstratificacao
from gastroepi.ui_qt.calc_mantel_haenszel import CalcMantelHaenszel
from gastroepi.ui_qt.calc_qualidade import CalcQualidade
from gastroepi.ui_qt.calc_tabelas import CalcDiagnostico, CalcTabela2x2
from gastroepi.ui_qt.calc_tendencia import CalcTendencia


class TelaStatCalc(QWidget):
    def __init__(self, sessao: Sessao) -> None:
        super().__init__()
        self.qualidade = CalcQualidade(sessao)
        self.tabela_2x2 = CalcTabela2x2()
        self.diagnostico = CalcDiagnostico()
        self.amostra = CalcAmostra()
        self.tendencia = CalcTendencia()
        self.mantel_haenszel = CalcMantelHaenszel()
        self.estratificacao = CalcEstratificacao(sessao)
        self.abas = QTabWidget(self)
        for aba, nome in (
            (self.qualidade, "Qualidade"),
            (self.tabela_2x2, "Tabela 2x2"),
            (self.diagnostico, "Teste diagnóstico"),
            (self.amostra, "Tamanho de amostra"),
            (self.tendencia, "Tendência"),
            (self.mantel_haenszel, "Mantel-Haenszel"),
            (self.estratificacao, "Estratificação"),
        ):
            self.abas.addTab(aba, nome)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("StatCalc", "titulo", self))
        disposicao.addWidget(self.abas)

    def atualizar(self) -> None:
        self.qualidade.atualizar()
        self.estratificacao.atualizar()
