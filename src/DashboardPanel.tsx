import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  BarChart3,
  PieChart as PieIcon,
  Activity,
  Calendar,
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Sliders
} from "lucide-react";

// Types matching Rust backend
interface HistoricoFamiliar {
  id?: number | null;
  parentesco: string;
  grau: number;
  idade_diagnostico?: number | null;
}

interface Paciente {
  id?: number | null;
  numero_prontuario: string;
  cpf?: string | null;
  nome: string;
  data_exame: string;
  idade: number;
  sexo: string;
  polipo: number;
  resultado_histopatologico?: string | null;
  indicacao_exame: string;
  comorbidades: string[];
  sintomas: string[];
  historico_familiar: HistoricoFamiliar[];
  examinador?: string | null;
}

interface ResultadoTabela2x2 {
  tabela: [[number, number], [number, number]];
  odds_ratio: number;
  odds_ratio_ic: [number, number];
  risco_relativo: number;
  risco_relativo_ic: [number, number];
  chi2_pearson: number;
  chi2_yates: number;
  p_valor_pearson: number;
  p_valor_yates: number;
  p_valor_fisher: number;
  n_total: number;
}

interface DashboardPanelProps {
  showMsg: (type: "success" | "error" | "warning", msg: string) => void;
}

// Age helper
const FAIXAS = [
  { label: "0-19", min: 0, max: 19 },
  { label: "20-29", min: 20, max: 29 },
  { label: "30-39", min: 30, max: 39 },
  { label: "40-49", min: 40, max: 49 },
  { label: "50-59", min: 50, max: 59 },
  { label: "60-69", min: 60, max: 69 },
  { label: "70+", min: 70, max: 200 }
];

function getFaixaEtaria(idade: number): string {
  for (const f of FAIXAS) {
    if (idade >= f.min && idade <= f.max) {
      return f.label;
    }
  }
  return "Outro";
}

const formatVal = (val: number | null | undefined, decimals: number): string => {
  if (val === null || val === undefined || isNaN(val) || !isFinite(val)) return "—";
  return val.toFixed(decimals);
};

const formatarDataExame = (dataStr: string | null | undefined): string => {
  if (!dataStr) return "—";
  try {
    const dateObj = new Date(dataStr.includes("T") ? dataStr : dataStr + "T12:00:00");
    if (!isNaN(dateObj.getTime())) {
      return dateObj.toLocaleDateString("pt-BR");
    }
  } catch (e) {
    console.error("Erro ao formatar data:", e);
  }
  
  if (dataStr.includes("-")) {
    const parts = dataStr.split("-");
    if (parts.length === 3) {
      if (parts[0].length === 4) {
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
      }
    }
  }
  return dataStr;
};

export default function DashboardPanel({ showMsg }: DashboardPanelProps) {
  const [pacientes, setPacientes] = useState<Paciente[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters state
  const [filtroSexo, setFiltroSexo] = useState<string[]>(["M", "F"]);
  const [filtroFaixa, setFiltroFaixa] = useState<string[]>(FAIXAS.map(f => f.label));

  // 2x2 analysis stats
  const [res2x2, setRes2x2] = useState<ResultadoTabela2x2 | null>(null);
  const [loading2x2, setLoading2x2] = useState(false);

  // Pagination for details table
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Load patients
  const fetchPacientes = async () => {
    setLoading(true);
    try {
      const list = await invoke<Paciente[]>("listar_pacientes");
      setPacientes(list);
    } catch (e) {
      showMsg("error", "Erro ao carregar pacientes para o painel: " + String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPacientes();
  }, []);

  // Filtered patients
  const filtrados = pacientes.filter(p => {
    const matchesSexo = filtroSexo.includes(p.sexo);
    const faixa = getFaixaEtaria(p.idade);
    const matchesFaixa = filtroFaixa.includes(faixa);
    return matchesSexo && matchesFaixa;
  });

  // Recompute 2x2 stats when filtrados change
  useEffect(() => {
    const compute2x2 = async () => {
      // a: Feminino + Polipo Presente (Exposto + Outcome+)
      // b: Feminino + Polipo Ausente (Exposto + Outcome-)
      // c: Masculino + Polipo Presente (Não Exposto + Outcome+)
      // d: Masculino + Polipo Ausente (Não Exposto + Outcome-)
      const a = filtrados.filter(p => p.sexo === "F" && p.polipo > 0).length;
      const b = filtrados.filter(p => p.sexo === "F" && p.polipo === 0).length;
      const c = filtrados.filter(p => p.sexo === "M" && p.polipo > 0).length;
      const d = filtrados.filter(p => p.sexo === "M" && p.polipo === 0).length;

      // Avoid calling with zeros if it might crash or cause no variance
      if (a + b + c + d === 0) {
        setRes2x2(null);
        return;
      }

      setLoading2x2(true);
      try {
        const res = await invoke<ResultadoTabela2x2>("calcular_tabela_2x2", { a, b, c, d });
        setRes2x2(res);
      } catch (e) {
        console.error("Erro ao calcular Tabela 2x2 no dashboard:", e);
        setRes2x2(null);
      } finally {
        setLoading2x2(false);
      }
    };

    compute2x2();
    setCurrentPage(1); // Reset table page when filters change
  }, [filtroSexo, filtroFaixa, pacientes]);

  // Median calculation
  const getMedianaIdade = (list: Paciente[]) => {
    if (list.length === 0) return 0;
    const sortedAges = list.map(p => p.idade).sort((x, y) => x - y);
    const mid = Math.floor(sortedAges.length / 2);
    if (sortedAges.length % 2 !== 0) {
      return sortedAges[mid];
    }
    return Math.round((sortedAges[mid - 1] + sortedAges[mid]) / 2);
  };

  // KPIs
  const totalPacientes = filtrados.length;
  const comPolipos = filtrados.filter(p => p.polipo > 0).length;
  const medianaIdade = getMedianaIdade(filtrados);
  const comHistFamiliar = filtrados.filter(
    p => p.historico_familiar && p.historico_familiar.length > 0
  ).length;

  // Chart data extraction
  // 1. Sex (Pie)
  const sexCounts = filtrados.reduce(
    (acc, p) => {
      if (p.sexo === "M") acc.M += 1;
      else if (p.sexo === "F") acc.F += 1;
      return acc;
    },
    { M: 0, F: 0 }
  );
  const pieDataSexo = [
    {
      name: "Masculino",
      value: sexCounts.M,
      color: "#0ea5e9",
      gradientFrom: "#38bdf8",
      gradientTo: "#0284c7"
    },
    {
      name: "Feminino",
      value: sexCounts.F,
      color: "#d946ef",
      gradientFrom: "#f472b6",
      gradientTo: "#c084fc"
    }
  ];

  // 2. Faixa Etária (Bar)
  const faixaEtariaCounts = FAIXAS.map(f => {
    const count = filtrados.filter(p => getFaixaEtaria(p.idade) === f.label).length;
    return { label: f.label, value: count };
  });

  // 3. Distribuição de Pólipos (Bar)
  const maxPolyp = Math.max(...filtrados.map(p => typeof p.polipo === 'number' && !isNaN(p.polipo) ? p.polipo : 0), 0);
  const polipoRange = Array.from({ length: Math.min(maxPolyp + 1, 6) }, (_, i) => i); // Cap at 5+
  const polipoCounts = polipoRange.map(n => {
    let count = 0;
    if (n === 5) {
      count = filtrados.filter(p => p.polipo >= 5).length;
    } else {
      count = filtrados.filter(p => p.polipo === n).length;
    }
    return {
      label: n === 5 ? "5+" : `${n}`,
      value: count
    };
  });

  // 4. Comorbidades (Horizontal Bar, Top 15)
  const comorbMap: Record<string, number> = {};
  filtrados.forEach(p => {
    if (p.comorbidades) {
      p.comorbidades.forEach(c => {
        const key = c.trim().toLowerCase();
        if (key) {
          comorbMap[c.trim()] = (comorbMap[c.trim()] || 0) + 1;
        }
      });
    }
  });
  const topComorbidades = Object.entries(comorbMap)
    .map(([label, value]) => ({ label, value }))
    .sort((x, y) => y.value - x.value)
    .slice(0, 15);

  // 5. Exames por Mês (Line)
  const examesMesMap: Record<string, number> = {};
  filtrados.forEach(p => {
    if (p.data_exame && p.data_exame.length >= 7) {
      const mes = p.data_exame.substring(0, 7); // YYYY-MM
      examesMesMap[mes] = (examesMesMap[mes] || 0) + 1;
    }
  });
  const lineDataExames = Object.entries(examesMesMap)
    .map(([label, value]) => ({ label, value }))
    .sort((x, y) => x.label.localeCompare(y.label));

  // 6. Histórico Familiar (Bar)
  const familiarCounts = {
    grau1: filtrados.filter(p => p.historico_familiar?.some(h => h && h.grau === 1)).length,
    grau2: filtrados.filter(p => p.historico_familiar?.some(h => h && h.grau === 2) && !p.historico_familiar?.some(x => x && x.grau === 1)).length,
    grau3: filtrados.filter(p => p.historico_familiar?.some(h => h && h.grau === 3) && !p.historico_familiar?.some(x => x && x.grau < 3)).length,
    semHist: filtrados.filter(p => !p.historico_familiar || p.historico_familiar.length === 0).length
  };
  const barDataFamiliar = [
    { label: "1º Grau", value: familiarCounts.grau1 },
    { label: "2º Grau", value: familiarCounts.grau2 },
    { label: "3º Grau", value: familiarCounts.grau3 },
    { label: "Sem Histórico", value: familiarCounts.semHist }
  ];

  // Details Table Pagination
  const totalPages = Math.ceil(filtrados.length / itemsPerPage);
  const paginatedList = filtrados.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const getMenorGrauFamiliar = (p: Paciente): string => {
    if (!p.historico_familiar || p.historico_familiar.length === 0) return "—";
    const minGrau = Math.min(...p.historico_familiar.filter(h => h && typeof h.grau === 'number').map(h => h.grau));
    return `${minGrau}º Grau`;
  };

  const handleSexoFilterToggle = (sexo: string) => {
    if (filtroSexo.includes(sexo)) {
      if (filtroSexo.length > 1) {
        setFiltroSexo(filtroSexo.filter(s => s !== sexo));
      }
    } else {
      setFiltroSexo([...filtroSexo, sexo]);
    }
  };

  const handleFaixaFilterToggle = (faixa: string) => {
    if (filtroFaixa.includes(faixa)) {
      if (filtroFaixa.length > 1) {
        setFiltroFaixa(filtroFaixa.filter(f => f !== faixa));
      }
    } else {
      setFiltroFaixa([...filtroFaixa, faixa]);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400">
        <RefreshCw className="h-8 w-8 animate-spin text-indigo-500 mr-3" />
        Carregando painel de estatísticas...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex justify-between items-center pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-indigo-500" />
            Painel Epidemiológico
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Métricas descritivas e agrupamentos epidemiológicos dinâmicos em tempo real (Sem PII).
          </p>
        </div>
        <button
          onClick={fetchPacientes}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-semibold border border-slate-700 transition cursor-pointer"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Atualizar Dados
        </button>
      </div>

      {pacientes.length === 0 ? (
        <div className="p-8 bg-slate-900 border border-slate-800 rounded-xl text-center text-slate-400">
          <BookOpen className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-lg font-medium">Nenhum paciente cadastrado no banco.</p>
          <p className="text-sm text-slate-500 mt-1">
            Cadastre registros na aba de Pacientes para exibir gráficos e dados descritivos aqui.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          
          {/* Side Filters Panel */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5 lg:col-span-1 shadow-lg backdrop-blur-sm">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2 pb-2 border-b border-slate-800">
              <Filter className="h-4 w-4 text-indigo-400" />
              Filtros Dinâmicos
            </h3>

            {/* Sex Selection */}
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Sexo</span>
              <div className="flex flex-col gap-2">
                <label className="flex items-center gap-2.5 text-sm text-slate-300 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    checked={filtroSexo.includes("M")}
                    onChange={() => handleSexoFilterToggle("M")}
                    className="accent-indigo-500 rounded border-slate-700 bg-slate-850 w-4 h-4 cursor-pointer"
                  />
                  <span>Masculino (M)</span>
                </label>
                <label className="flex items-center gap-2.5 text-sm text-slate-300 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    checked={filtroSexo.includes("F")}
                    onChange={() => handleSexoFilterToggle("F")}
                    className="accent-indigo-500 rounded border-slate-700 bg-slate-850 w-4 h-4 cursor-pointer"
                  />
                  <span>Feminino (F)</span>
                </label>
              </div>
            </div>

            {/* Age range Selection */}
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">Faixa Etária</span>
              <div className="flex flex-col gap-2">
                {FAIXAS.map(f => (
                  <label key={f.label} className="flex items-center gap-2.5 text-sm text-slate-300 cursor-pointer hover:text-white">
                    <input
                      type="checkbox"
                      checked={filtroFaixa.includes(f.label)}
                      onChange={() => handleFaixaFilterToggle(f.label)}
                      className="accent-indigo-500 rounded border-slate-700 bg-slate-850 w-4 h-4 cursor-pointer"
                    />
                    <span>{f.label} anos</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="pt-2 text-[10px] text-slate-500 leading-tight border-t border-slate-800">
              * A alteração nos filtros acima recalcula imediatamente todos os gráficos, KPIs, tabelas de contingência e listagem detalhada.
            </div>
          </div>

          {/* Main Dashboard Content */}
          <div className="lg:col-span-3 space-y-6">
            
            {/* KPI Cards Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow flex flex-col justify-between">
                <span className="text-xs font-semibold text-slate-400 block">Total Pacientes</span>
                <span className="text-3xl font-extrabold text-white mt-2">{totalPacientes}</span>
                <span className="text-[10px] text-slate-500 mt-1 block">no filtro selecionado</span>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow flex flex-col justify-between">
                <span className="text-xs font-semibold text-slate-400 block">Com Pólipos</span>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl font-extrabold text-white">{comPolipos}</span>
                  {totalPacientes > 0 && (
                    <span className="text-xs text-indigo-400 font-bold">
                      {((comPolipos / totalPacientes) * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-slate-500 mt-1 block">taxa de detecção</span>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow flex flex-col justify-between">
                <span className="text-xs font-semibold text-slate-400 block">Mediana de Idade</span>
                <span className="text-3xl font-extrabold text-white mt-2">{medianaIdade} <span className="text-xs font-normal text-slate-400">anos</span></span>
                <span className="text-[10px] text-slate-500 mt-1 block">idade mediana</span>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow flex flex-col justify-between">
                <span className="text-xs font-semibold text-slate-400 block">Histórico Familiar</span>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl font-extrabold text-white">{comHistFamiliar}</span>
                  {totalPacientes > 0 && (
                    <span className="text-xs text-indigo-400 font-bold">
                      {((comHistFamiliar / totalPacientes) * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-slate-500 mt-1 block">relato familiar de CCR</span>
              </div>
            </div>

            {/* Charts Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Chart 1: Sexo (Pie) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
                <h4 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
                  <PieIcon className="h-4 w-4 text-pink-400" />
                  Distribuição por Sexo
                </h4>
                <div className="h-56">
                  <SvgPieChart data={pieDataSexo} />
                </div>
              </div>

              {/* Chart 2: Faixa Etária (Bar) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
                <h4 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-indigo-400" />
                  Distribuição por Faixa Etária (Anos)
                </h4>
                <div className="h-56">
                  {totalPacientes > 0 ? (
                    <SvgBarChart data={faixaEtariaCounts} colorFrom="#4f46e5" colorTo="#818cf8" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-slate-400">Nenhum dado</div>
                  )}
                </div>
              </div>

              {/* Chart 3: Distribuição de Pólipos (Bar) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
                <h4 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-emerald-400" />
                  Distribuição de Pólipos por Paciente
                </h4>
                <div className="h-56">
                  {totalPacientes > 0 ? (
                    <SvgBarChart data={polipoCounts} colorFrom="#10b981" colorTo="#34d399" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-slate-400">Nenhum dado</div>
                  )}
                </div>
              </div>

              {/* Chart 4: Histórico Familiar (Bar) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
                <h4 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-sky-400" />
                  Histórico Familiar (Relação de Maior Risco)
                </h4>
                <div className="h-56">
                  {totalPacientes > 0 ? (
                    <SvgBarChart data={barDataFamiliar} colorFrom="#0ea5e9" colorTo="#38bdf8" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-slate-400">Nenhum dado</div>
                  )}
                </div>
              </div>

              {/* Chart 5: Exames por Mês (Line) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow md:col-span-2">
                <h4 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-rose-400" />
                  Série Temporal: Exames Realizados por Mês
                </h4>
                <div className="h-52">
                  {lineDataExames.length > 0 ? (
                    <SvgLineChart data={lineDataExames} />
                  ) : (
                    <div className="flex h-full items-center justify-center text-slate-500 text-xs py-10">
                      Nenhum dado de série temporal disponível.
                    </div>
                  )}
                </div>
              </div>

              {/* Chart 6: Comorbidades (Horizontal Bar, Top 15) */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow md:col-span-2">
                <h4 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-3 mb-4 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-yellow-400" />
                  Comorbidades mais Frequentes (Top 15)
                </h4>
                <div>
                  {topComorbidades.length > 0 ? (
                    <HorizontalBarChart data={topComorbidades} />
                  ) : (
                    <div className="flex h-44 items-center justify-center text-slate-500 text-xs">
                      Nenhuma comorbidade relatada no filtro atual.
                    </div>
                  )}
                </div>
              </div>

            </div>

            {/* 2x2 Contingence table analysis */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
              <div className="border-b border-slate-800 pb-3">
                <h3 className="text-md font-bold text-slate-200 flex items-center gap-2">
                  <Sliders className="h-5 w-5 text-indigo-400" />
                  Análise de Associação Estocástica (Pólipos × Sexo)
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Matriz de contingência cruzando o Sexo Feminino (exposto) versus Sexo Masculino (não-exposto) contra a presença de pólipo (desfecho).
                </p>
              </div>

              {loading2x2 ? (
                <div className="h-32 flex items-center justify-center text-slate-400">
                  <RefreshCw className="h-6 w-6 animate-spin text-indigo-400 mr-2" />
                  Calculando inferências estatísticas no backend...
                </div>
              ) : res2x2 ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                  
                  {/* Table View */}
                  <div className="lg:col-span-2 overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400">
                          <th className="py-2.5 font-semibold">Grupo</th>
                          <th className="py-2.5 text-right font-semibold">Com Pólipos (+)</th>
                          <th className="py-2.5 text-right font-semibold">Sem Pólipos (-)</th>
                          <th className="py-2.5 text-right font-semibold">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-slate-800 text-slate-300">
                          <td className="py-3 font-medium">Feminino (Exposto+)</td>
                          <td className="py-3 text-right font-mono">{res2x2.tabela[0][0]}</td>
                          <td className="py-3 text-right font-mono">{res2x2.tabela[0][1]}</td>
                          <td className="py-3 text-right font-mono text-slate-400">
                            {res2x2.tabela[0][0] + res2x2.tabela[0][1]}
                          </td>
                        </tr>
                        <tr className="border-b border-slate-800 text-slate-300">
                          <td className="py-3 font-medium">Masculino (Exposto-)</td>
                          <td className="py-3 text-right font-mono">{res2x2.tabela[1][0]}</td>
                          <td className="py-3 text-right font-mono">{res2x2.tabela[1][1]}</td>
                          <td className="py-3 text-right font-mono text-slate-400">
                            {res2x2.tabela[1][0] + res2x2.tabela[1][1]}
                          </td>
                        </tr>
                        <tr className="text-slate-200 font-semibold bg-slate-950/30">
                          <td className="py-3">Total</td>
                          <td className="py-3 text-right font-mono">
                            {res2x2.tabela[0][0] + res2x2.tabela[1][0]}
                          </td>
                          <td className="py-3 text-right font-mono">
                            {res2x2.tabela[0][1] + res2x2.tabela[1][1]}
                          </td>
                          <td className="py-3 text-right font-mono">
                            {res2x2.n_total}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {/* Calculations Box */}
                  <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-800 space-y-4">
                    <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                      Medidas de Associação (f64)
                    </h4>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-[10px] text-slate-500 font-semibold block">Odds Ratio (OR)</span>
                        <span className="text-lg font-extrabold text-slate-100 block">
                          {formatVal(res2x2.odds_ratio, 3)}
                        </span>
                        <span className="text-[9px] text-slate-400 block leading-tight mt-0.5">
                          IC 95%: [{formatVal(res2x2.odds_ratio_ic[0], 2)} — {formatVal(res2x2.odds_ratio_ic[1], 2)}]
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 font-semibold block">Risco Relativo (RR)</span>
                        <span className="text-lg font-extrabold text-slate-100 block">
                          {formatVal(res2x2.risco_relativo, 3)}
                        </span>
                        <span className="text-[9px] text-slate-400 block leading-tight mt-0.5">
                          IC 95%: [{formatVal(res2x2.risco_relativo_ic[0], 2)} — {formatVal(res2x2.risco_relativo_ic[1], 2)}]
                        </span>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-slate-850 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 font-medium">p-Fisher (Bicaudal):</span>
                        <span className={`font-mono font-bold ${res2x2.p_valor_fisher < 0.05 ? "text-emerald-400" : "text-slate-300"}`}>
                          {res2x2.p_valor_fisher < 0.0001 ? "< 0.0001" : formatVal(res2x2.p_valor_fisher, 5)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 font-medium">p-Pearson (Chi2):</span>
                        <span className={`font-mono ${res2x2.p_valor_pearson < 0.05 ? "text-emerald-400" : "text-slate-300"}`}>
                          {res2x2.p_valor_pearson < 0.0001 ? "< 0.0001" : formatVal(res2x2.p_valor_pearson, 5)}
                        </span>
                      </div>
                    </div>
                    
                    {res2x2.p_valor_fisher < 0.05 && (
                      <div className="flex gap-2 items-start bg-emerald-950/20 text-emerald-300 p-2 rounded-lg border border-emerald-900/50 text-[10px]">
                        <span className="font-bold">Efeito Significativo:</span>
                        <span>Há associação estatisticamente relevante (p &lt; 0.05) entre o sexo e a presença de pólipos na amostra filtrada.</span>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-slate-500 text-xs">
                  Insira mais registros de pacientes masculinos e femininos com/sem pólipos para computar testes estatísticos de associação.
                </div>
              )}
            </div>

            {/* Details table without PII */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
              <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">
                    Detalhamento dos Registros (Visão Agregada Sem PII)
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Nome completo, CPF e laudo descritivo completo são omitidos nesta tela para conformidade ética.
                  </p>
                </div>
                <span className="text-[10px] bg-slate-800 px-2.5 py-1 rounded text-slate-400 font-medium">
                  {filtrados.length} registro{filtrados.length !== 1 ? 's' : ''}
                </span>
              </div>

              {filtrados.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-sm">
                  Nenhum registro corresponde aos filtros selecionados.
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                          <th className="py-2.5">Prontuário</th>
                          <th className="py-2.5">Data Exame</th>
                          <th className="py-2.5 text-right">Idade</th>
                          <th className="py-2.5">Faixa Etária</th>
                          <th className="py-2.5 text-center">Sexo</th>
                          <th className="py-2.5 text-right">Pólipos</th>
                          <th className="py-2.5 text-right">Nº Comorb.</th>
                          <th className="py-2.5">Hist. Familiar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedList.map((p, idx) => (
                          <tr key={p.id || idx} className="border-b border-slate-800/60 hover:bg-slate-850/30 text-slate-300">
                            <td className="py-3.5 font-mono font-medium text-slate-100">
                              {p.numero_prontuario}
                            </td>
                            <td className="py-3.5">
                              {formatarDataExame(p.data_exame)}
                            </td>
                            <td className="py-3.5 text-right">{p.idade}</td>
                            <td className="py-3.5 text-slate-400">{getFaixaEtaria(p.idade)}</td>
                            <td className="py-3.5 text-center">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                p.sexo === "M" ? "bg-sky-950/40 text-sky-400 border border-sky-900/30" : "bg-fuchsia-950/40 text-fuchsia-400 border border-fuchsia-900/30"
                              }`}>
                                {p.sexo}
                              </span>
                            </td>
                            <td className="py-3.5 text-right font-mono">{p.polipo}</td>
                            <td className="py-3.5 text-right">{p.comorbidades?.length || 0}</td>
                            <td className="py-3.5 text-slate-400">{getMenorGrauFamiliar(p)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Footer */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-3 border-t border-slate-850">
                      <span className="text-[11px] text-slate-500 font-medium">
                        Página {currentPage} de {totalPages}
                      </span>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                          disabled={currentPage === 1}
                          className="p-1.5 rounded bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-slate-200 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                          disabled={currentPage === totalPages}
                          className="p-1.5 rounded bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-slate-200 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

          </div>

        </div>
      )}
    </div>
  );
}

// Chart subcomponents helper classes
interface SvgPieChartProps {
  data: {
    name: string;
    value: number;
    color: string;
    gradientFrom: string;
    gradientTo: string;
  }[];
}

function SvgPieChart({ data }: SvgPieChartProps) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  if (total === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500 text-xs">
        Sem dados para gerar gráfico de pizza.
      </div>
    );
  }

  let accumulatedAngle = 0;

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="relative w-40 h-40">
        <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90">
          <defs>
            {data.map((item, idx) => (
              <linearGradient key={idx} id={`pie-grad-${idx}`} x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={item.gradientFrom} />
                <stop offset="100%" stopColor={item.gradientTo} />
              </linearGradient>
            ))}
          </defs>
          {data.map((item, idx) => {
            if (item.value === 0) return null;

            const percentage = item.value / total;
            const angle = percentage * 360;

            if (percentage === 1) {
              return (
                <circle
                  key={idx}
                  cx="50"
                  cy="50"
                  r="40"
                  fill={`url(#pie-grad-${idx})`}
                />
              );
            }

            const startAngleRad = (accumulatedAngle * Math.PI) / 180;
            const endAngleRad = ((accumulatedAngle + angle) * Math.PI) / 180;

            const r = 40;
            const cx = 50;
            const cy = 50;

            const x1 = cx + r * Math.cos(startAngleRad);
            const y1 = cy + r * Math.sin(startAngleRad);

            const x2 = cx + r * Math.cos(endAngleRad);
            const y2 = cy + r * Math.sin(endAngleRad);

            const largeArcFlag = angle > 180 ? 1 : 0;

            const pathData = `
              M ${cx} ${cy}
              L ${x1} ${y1}
              A ${r} ${r} 0 ${largeArcFlag} 1 ${x2} ${y2}
              Z
            `;

            accumulatedAngle += angle;

            return (
              <path
                key={idx}
                d={pathData}
                fill={`url(#pie-grad-${idx})`}
                className="transition-all duration-300 hover:opacity-90 hover:scale-[1.03] origin-center cursor-pointer"
                style={{ transformOrigin: "50px 50px" }}
              >
                <title>{`${item.name}: ${item.value} (${(percentage * 100).toFixed(1)}%)`}</title>
              </path>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4 text-[11px] flex-wrap justify-center">
        {data.map((item, idx) => {
          const percentage = total > 0 ? (item.value / total) * 100 : 0;
          return (
            <div key={idx} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: `linear-gradient(135deg, ${item.gradientFrom}, ${item.gradientTo})` }}
              />
              <span className="text-slate-400 font-medium">
                {item.name}: <span className="text-slate-200 font-bold">{item.value}</span> ({percentage.toFixed(1)}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface SvgBarChartProps {
  data: {
    label: string;
    value: number;
  }[];
  colorFrom: string;
  colorTo: string;
}

function SvgBarChart({ data, colorFrom, colorTo }: SvgBarChartProps) {
  const maxVal = Math.max(...data.map(d => d.value), 0);

  if (maxVal === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500 text-xs">
        Nenhum registro para exibir neste gráfico.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full justify-between py-1">
      <div className="flex flex-1 items-end gap-3 h-40 px-2 border-b border-slate-800/80">
        {data.map((item, idx) => {
          const heightPercent = maxVal > 0 ? (item.value / maxVal) * 100 : 0;
          return (
            <div key={idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
              
              {/* Tooltip */}
              <div className="absolute -top-7 bg-slate-950 text-[10px] px-2 py-0.5 rounded text-slate-200 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none whitespace-nowrap z-10 shadow-lg border border-slate-800 font-medium">
                {item.value} Paciente{item.value !== 1 ? 's' : ''}
              </div>

              {/* Bar */}
              <div
                className="w-full rounded-t-md transition-all duration-300 group-hover:opacity-90 relative cursor-pointer"
                style={{
                  height: `${Math.max(heightPercent, 2)}%`,
                  background: `linear-gradient(to top, ${colorFrom}, ${colorTo})`
                }}
              />
            </div>
          );
        })}
      </div>

      {/* Axis Labels */}
      <div className="flex justify-between mt-2.5 px-0.5 text-[9px] text-slate-500 font-semibold uppercase tracking-wider whitespace-nowrap">
        {data.map((item, idx) => (
          <div key={idx} className="flex-1 text-center truncate px-0.5" title={item.label}>
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}

interface SvgLineChartProps {
  data: {
    label: string;
    value: number;
  }[];
}

function SvgLineChart({ data }: SvgLineChartProps) {
  const maxVal = Math.max(...data.map(d => d.value), 0);
  const width = 500;
  const height = 150;
  const padding = 20;

  if (data.length === 0 || maxVal === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500 text-xs">
        Nenhum registro com data válida encontrada.
      </div>
    );
  }

  // Calculate coordinates
  const points = data.map((item, idx) => {
    const x = padding + (idx / Math.max(data.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - (maxVal > 0 ? (item.value / maxVal) : 0) * (height - padding * 2);
    return { x, y, label: item.label, value: item.value };
  });

  const pathD = points.reduce((path, p, idx) => {
    return path + `${idx === 0 ? "M" : "L"} ${p.x} ${p.y} `;
  }, "");

  const areaD = points.length > 0
    ? `${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`
    : "";

  // Helper to format YYYY-MM to pt-BR MM/YY
  const formatMonth = (str: string) => {
    const parts = str.split("-");
    if (parts.length === 2) {
      return `${parts[1]}/${parts[0].substring(2)}`;
    }
    return str;
  };

  return (
    <div className="flex flex-col h-full justify-between py-1">
      <div className="relative w-full h-36">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id="line-area-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="line-stroke-grad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#f43f5e" />
              <stop offset="100%" stopColor="#fda4af" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="#334155" strokeWidth="0.5" strokeDasharray="3,3" />
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="#334155" strokeWidth="0.5" strokeDasharray="3,3" />
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#475569" strokeWidth="0.75" />

          {/* Filled gradient area */}
          {areaD && <path d={areaD} fill="url(#line-area-grad)" />}

          {/* Stroke Line */}
          {pathD && <path d={pathD} fill="none" stroke="url(#line-stroke-grad)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}

          {/* Data Points */}
          {points.map((p, idx) => (
            <g key={idx} className="group cursor-pointer">
              <circle
                cx={p.x}
                cy={p.y}
                r="3.5"
                fill="#f43f5e"
                stroke="#0f172a"
                strokeWidth="1.5"
                className="transition-all duration-150 hover:r-5 hover:fill-rose-300"
              />
              <title>{`${formatMonth(p.label)}: ${p.value} exame(s)`}</title>
            </g>
          ))}
        </svg>
      </div>

      {/* Axis labels */}
      <div className="flex justify-between px-1 text-[9px] text-slate-500 font-semibold">
        {data.length > 0 && <span>{formatMonth(data[0].label)}</span>}
        {data.length > 2 && <span>{formatMonth(data[Math.floor(data.length / 2)].label)}</span>}
        {data.length > 1 && <span>{formatMonth(data[data.length - 1].label)}</span>}
      </div>
    </div>
  );
}

interface HorizontalBarChartProps {
  data: {
    label: string;
    value: number;
  }[];
}

function HorizontalBarChart({ data }: HorizontalBarChartProps) {
  const maxVal = Math.max(...data.map(d => d.value), 0);

  if (maxVal === 0) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500 text-xs">
        Nenhuma comorbidade registrada.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5 py-1 max-h-56 overflow-y-auto pr-1">
      {data.map((item, idx) => {
        const widthPercent = maxVal > 0 ? (item.value / maxVal) * 100 : 0;
        return (
          <div key={idx} className="flex flex-col gap-1 text-[11px] group">
            <div className="flex justify-between text-slate-300 font-medium">
              <span className="truncate max-w-[200px]" title={item.label}>
                {item.label}
              </span>
              <span className="text-slate-100 font-bold bg-slate-800/60 px-1.5 py-0.5 rounded-sm">
                {item.value}
              </span>
            </div>
            <div className="w-full bg-slate-950/80 rounded-full h-1.5 overflow-hidden border border-slate-850">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{
                  width: `${widthPercent}%`,
                  background: "linear-gradient(to right, #fbbf24, #f59e0b)"
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
