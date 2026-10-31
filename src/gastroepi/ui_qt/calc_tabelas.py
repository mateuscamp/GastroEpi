"""Tabela 2x2 (OR, RR, qui-quadrado, Fisher) e teste diagnóstico (sensibilidade,
especificidade, valores preditivos e razões de verossimilhança)."""

from PySide6.QtWidgets import QGridLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from gastroepi.servicos import calculadoras
from gastroepi.servicos.calculadoras import (
    EntradaInvalida,
    ResultadoDiagnostico,
    ResultadoTabela2x2,
)
from gastroepi.ui_qt.aparencia import rotulo
from gastroepi.ui_qt.calc_comum import Resultado, botao_calcular, caixa_de_contagem
from gastroepi.ui_qt.textos import com_ic, p_valor, proporcao, qui_quadrado


class Grade2x2(QWidget):
    """Quatro caixas com os nomes das linhas e colunas escritos ao lado."""

    def __init__(self, linhas: tuple[str, str], colunas: tuple[str, str], pai: QWidget) -> None:
        super().__init__(pai)
        grade = QGridLayout(self)
        self.caixas: list[QSpinBox] = []
        for coluna, nome in enumerate(colunas, start=1):
            grade.addWidget(QLabel(f"<b>{nome}</b>", self), 0, coluna)
        for linha, nome in enumerate(linhas, start=1):
            grade.addWidget(QLabel(f"<b>{nome}</b>", self), linha, 0)
            for coluna in (1, 2):
                caixa = caixa_de_contagem(pai=self)
                grade.addWidget(caixa, linha, coluna)
                self.caixas.append(caixa)

    def valores(self) -> tuple[int, int, int, int]:
        a, b, c, d = (caixa.value() for caixa in self.caixas)
        return a, b, c, d

    def definir(self, a: int, b: int, c: int, d: int) -> None:
        for caixa, valor in zip(self.caixas, (a, b, c, d), strict=True):
            caixa.setValue(valor)


def linhas_da_tabela_2x2(r: ResultadoTabela2x2) -> list[tuple[str, str]]:
    return [
        ("Odds ratio (Woolf)", com_ic(r.odds_ratio, r.odds_ratio_ic)),
        (
            "Risco relativo",
            com_ic(r.risco_relativo, r.risco_relativo_ic),
        ),
        ("Qui-quadrado de Pearson", qui_quadrado(r.chi2_pearson, r.p_valor_pearson)),
        (
            "Qui-quadrado com correção de Yates",
            qui_quadrado(r.chi2_yates, r.p_valor_yates),
        ),
        ("Exato de Fisher (bicaudal)", p_valor(r.p_valor_fisher)),
        ("Total", str(r.n_total)),
    ]


def linhas_do_diagnostico(r: ResultadoDiagnostico) -> list[tuple[str, str]]:
    return [
        ("Sensibilidade", proporcao(r.sensibilidade)),
        ("Especificidade", proporcao(r.especificidade)),
        ("Valor preditivo positivo", proporcao(r.vpp)),
        ("Valor preditivo negativo", proporcao(r.vpn)),
        ("Razão de verossimilhança positiva", com_ic(r.lr_positivo, r.lr_positivo_ic)),
        ("Razão de verossimilhança negativa", com_ic(r.lr_negativo, r.lr_negativo_ic)),
    ]


class CalcTabela2x2(QWidget):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.grade = Grade2x2(("Expostos", "Não expostos"), ("Com o desfecho", "Sem"), self)
        self.calcular = botao_calcular(self)
        self.resultado = Resultado(self)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Tabela 2x2", "subtitulo", self))
        disposicao.addWidget(self.grade)
        disposicao.addWidget(self.calcular)
        disposicao.addWidget(self.resultado)
        disposicao.addStretch()
        self.calcular.clicked.connect(self._calcular)

    def _calcular(self) -> None:
        try:
            resultado = calculadoras.calcular_tabela_2x2(*self.grade.valores())
        except EntradaInvalida as erro:
            self.resultado.falhar(str(erro))
            return
        self.resultado.mostrar(linhas_da_tabela_2x2(resultado), "Célula zerada: IC de 0 a ∞.")


class CalcDiagnostico(QWidget):
    def __init__(self, pai: QWidget | None = None) -> None:
        super().__init__(pai)
        self.grade = Grade2x2(
            ("Teste positivo", "Teste negativo"), ("Doentes", "Não doentes"), self
        )
        self.calcular = botao_calcular(self)
        self.resultado = Resultado(self)
        disposicao = QVBoxLayout(self)
        disposicao.addWidget(rotulo("Teste diagnóstico", "subtitulo", self))
        disposicao.addWidget(self.grade)
        disposicao.addWidget(self.calcular)
        disposicao.addWidget(self.resultado)
        disposicao.addStretch()
        self.calcular.clicked.connect(self._calcular)

    def _calcular(self) -> None:
        vp, fp, fn, vn = self.grade.valores()  # a grade é (positivo, negativo) x (doente, não)
        try:
            resultado = calculadoras.calcular_teste_diagnostico(vp, fp, fn, vn)
        except EntradaInvalida as erro:
            self.resultado.falhar(str(erro))
            return
        self.resultado.mostrar(linhas_do_diagnostico(resultado))
