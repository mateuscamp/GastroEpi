import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Lock,
  Unlock,
  Key,
  Users,
  TrendingUp,
  ShieldCheck,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Database,
  Plus,
  Trash2,
  Edit3,
  Search,
  RefreshCw,
  LogOut,
  Sliders,
  Play,
  Copy
} from "lucide-react";
import {
  pacienteSchema,
  converterParaBR,
  converterParaISO,
  formatarCPF
} from "./validation";
import "./App.css";

// ──────────────────────────── TIPOS ────────────────────────────

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
  data_exame: string; // YYYY-MM-DD in DB
  idade: number;
  sexo: string;
  polipo: number;
  resultado_histopatologico?: string | null;
  indicacao_exame: string;
  comorbidades: string[];
  sintomas: string[];
  historico_familiar: HistoricoFamiliar[];
  endoscopista?: string | null;
}

interface EntradaAuditoria {
  id?: number | null;
  timestamp: string;
  usuario: string;
  acao: string;
  entidade: string;
  entidade_id?: number | null;
  snapshot_antes?: string | null;
  snapshot_depois?: string | null;
  hash_atual: string;
}

interface InconsistenciaAuditoria {
  id_entrada: number;
  motivo: string;
  hash_esperado: string;
  hash_encontrado: string;
}

interface InconsistenciaDados {
  entidade: string;
  entidade_id?: number | null;
  motivo: string;
  campos: string[];
}

interface ResultadoIndicadorQualidade {
  endoscopista: string;
  n_exames: number;
  n_polipos: number;
  pdr: number;
  pdr_ic: [number, number];
  n_adenomas: number;
  adr: number;
  adr_ic: [number, number];
}

interface Prevalencia {
  n_casos: number;
  n_total: number;
  taxa: number;
  ic_inferior: number;
  ic_superior: number;
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

interface ResultadoTesteDiagnostico {
  sensibilidade: number;
  sensibilidade_ic: [number, number];
  especificidade: number;
  especificidade_ic: [number, number];
  vpp: number;
  vpp_ic: [number, number];
  vpn: number;
  vpn_ic: [number, number];
  lr_positivo: number;
  lr_positivo_ic: [number, number];
  lr_negativo: number;
  lr_negativo_ic: [number, number];
  vp: number;
  fp: number;
  fn_val: number;
  vn: number;
}

interface AmostraSurvey {
  tamanho_amostra: number;
  populacao: number | null;
  frequencia_esperada: number;
  margem_erro: number;
  nivel_confianca: number;
}

interface AmostraEstudoComparativo {
  amostra_grupo1: number;
  amostra_grupo2: number;
  amostra_total: number;
  poder: number;
  nivel_confianca: number;
  razao: number;
  p0: number;
  p1: number;
}

interface ResultadoTendencia {
  qui_quadrado: number;
  p_valor: number;
  graus_liberdade: number;
  escores: number[];
  proporcoes: number[];
  direcao: string;
}

interface ResultadoMantelHaenszel {
  odds_ratio_mh: number;
  odds_ratio_mh_ic: [number, number];
  p_valor_mh: number;
  chi2_homogeneidade: number;
  p_valor_homogeneidade: number;
  graus_liberdade: number;
}

// ──────────────────────────── APP PRINCIPAL ────────────────────────────

export default function App() {
  const [unlocked, setUnlocked] = useState(false);
  const [isSetup, setIsSetup] = useState(false); // se precisa cadastrar senha
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState("Dr. Mateus");
  const [activeTab, setActiveTab] = useState<"pacientes" | "calculadores" | "auditoria">("pacientes");

  // Alertas globais
  const [alert, setAlert] = useState<{ type: "success" | "error" | "warning"; msg: string } | null>(null);

  // Efeito inicial para verificar se o banco tem senha
  useEffect(() => {
    checkSetupStatus();
  }, []);

  const checkSetupStatus = async () => {
    try {
      const config = await invoke<boolean>("tem_senha_configurada");
      setIsSetup(!config);
      const isUnl = await invoke<boolean>("esta_desbloqueado");
      setUnlocked(isUnl);
    } catch (e) {
      showMsg("error", "Erro ao conectar com o banco de dados: " + String(e));
    } finally {
      setLoading(false);
    }
  };

  const showMsg = (type: "success" | "error" | "warning", msg: string) => {
    setAlert({ type, msg });
    setTimeout(() => setAlert(null), 5000);
  };

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="h-10 w-10 animate-spin text-indigo-500" />
          <span className="text-sm font-medium tracking-wide">Iniciando GastroEpi...</span>
        </div>
      </div>
    );
  }

  if (!unlocked) {
    return (
      <LockScreen
        isSetup={isSetup}
        onUnlock={() => {
          setUnlocked(true);
          showMsg("success", "Cofre desbloqueado com sucesso!");
        }}
        onSetupComplete={(_recKey) => {
          setIsSetup(false);
          setUnlocked(true);
          showMsg("success", "Senha configurada! Chave de recuperação gerada.");
        }}
        showMsg={showMsg}
      />
    );
  }

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0">
        <div>
          {/* Logo / Header */}
          <div className="p-6 border-b border-slate-800 flex items-center gap-3">
            <Database className="h-6 w-6 text-indigo-500" />
            <div>
              <h1 className="font-bold text-lg leading-tight">GastroEpi</h1>
              <span className="text-xs text-slate-400">v1.0.0 • Offline</span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="p-4 space-y-1">
            <button
              onClick={() => setActiveTab("pacientes")}
              className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                activeTab === "pacientes"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/10"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              }`}
            >
              <Users className="h-4 w-4" />
              <span>Pacientes</span>
            </button>

            <button
              onClick={() => setActiveTab("calculadores")}
              className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                activeTab === "calculadores"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/10"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              }`}
            >
              <TrendingUp className="h-4 w-4" />
              <span>StatCalc & Qualidade</span>
            </button>

            <button
              onClick={() => setActiveTab("auditoria")}
              className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                activeTab === "auditoria"
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/10"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              }`}
            >
              <ShieldCheck className="h-4 w-4" />
              <span>Auditoria & Cofre</span>
            </button>
          </nav>
        </div>

        {/* User / Session Info */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <span className="text-xs text-slate-500 block">Usuário Ativo</span>
              <select
                value={currentUser}
                onChange={(e) => setCurrentUser(e.target.value)}
                className="text-sm font-semibold text-slate-200 bg-transparent border-none focus:ring-0 p-0 cursor-pointer w-full truncate"
              >
                <option value="Dr. Mateus" className="bg-slate-900 text-slate-100">Dr. Mateus</option>
                <option value="Dra. Ana Costa" className="bg-slate-900 text-slate-100">Dra. Ana Costa</option>
                <option value="Dr. Carlos Silva" className="bg-slate-900 text-slate-100">Dr. Carlos Silva</option>
              </select>
            </div>
            <button
              onClick={async () => {
                window.location.reload();
              }}
              title="Bloquear Banco"
              className="p-2 hover:bg-red-950/40 hover:text-red-400 text-slate-500 rounded-lg transition-colors cursor-pointer"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Floating Alertas */}
        {alert && (
          <div
            className={`absolute top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl animate-slide-up border ${
              alert.type === "success"
                ? "bg-emerald-950/90 text-emerald-300 border-emerald-800"
                : alert.type === "error"
                ? "bg-red-950/90 text-red-300 border-red-800"
                : "bg-amber-950/90 text-amber-300 border-amber-800"
            }`}
          >
            {alert.type === "success" && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
            {alert.type === "error" && <XCircle className="h-5 w-5 text-red-400" />}
            {alert.type === "warning" && <AlertTriangle className="h-5 w-5 text-amber-400" />}
            <span className="text-sm font-medium">{alert.msg}</span>
          </div>
        )}

        {/* Content Wrapper */}
        <div className="flex-1 overflow-y-auto p-8 no-scrollbar bg-slate-950/50">
          {activeTab === "pacientes" && <PacientePanel currentUser={currentUser} showMsg={showMsg} />}
          {activeTab === "calculadores" && <StatCalcPanel showMsg={showMsg} />}
          {activeTab === "auditoria" && <AuditPanel showMsg={showMsg} />}
        </div>
      </main>
    </div>
  );
}

// ──────────────────────────── TELA DE BLOQUEIO / SETUP ────────────────────────────

interface LockScreenProps {
  isSetup: boolean;
  onUnlock: () => void;
  onSetupComplete: (recKey: string) => void;
  showMsg: (type: "success" | "error" | "warning", msg: string) => void;
}

function LockScreen({ isSetup, onUnlock, onSetupComplete, showMsg }: LockScreenProps) {
  const [senha, setSenha] = useState("");
  const [confirmaSenha, setConfirmaSenha] = useState("");
  const [chaveRecuperacao, setChaveRecuperacao] = useState("");
  const [modoChave, setModoChave] = useState(false);
  const [unlLoading, setUnlLoading] = useState(false);

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!senha) return;
    setUnlLoading(true);
    try {
      let success = false;
      if (modoChave) {
        success = await invoke<boolean>("desbloquear_com_chave", { chave: senha });
      } else {
        success = await invoke<boolean>("desbloquear", { senha });
      }

      if (success) {
        onUnlock();
      } else {
        showMsg("error", modoChave ? "Chave de recuperação inválida!" : "Senha incorreta!");
      }
    } catch (err) {
      showMsg("error", "Erro ao tentar desbloquear: " + String(err));
    } finally {
      setUnlLoading(false);
    }
  };

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (senha.length < 8) {
      showMsg("error", "A senha deve conter pelo menos 8 caracteres.");
      return;
    }
    if (senha !== confirmaSenha) {
      showMsg("error", "As senhas não coincidem.");
      return;
    }
    setUnlLoading(true);
    try {
      const recKey = await invoke<string>("configurar_senha", { senha });
      setChaveRecuperacao(recKey);
    } catch (err) {
      showMsg("error", "Falha ao configurar a senha: " + String(err));
    } finally {
      setUnlLoading(false);
    }
  };

  const copiarChave = () => {
    navigator.clipboard.writeText(chaveRecuperacao);
    showMsg("success", "Chave copiada para a área de transferência!");
  };

  return (
    <div className="h-screen w-screen bg-slate-950 flex items-center justify-center text-slate-100 p-6">
      <div className="w-full max-w-md p-8 rounded-2xl border border-slate-800/80 bg-slate-900/60 shadow-2xl backdrop-blur-md animate-fade-in">
        <div className="flex flex-col items-center mb-8">
          <div className="h-16 w-16 bg-indigo-600/10 border border-indigo-500/20 text-indigo-500 flex items-center justify-center rounded-2xl mb-4">
            {isSetup ? <Key className="h-8 w-8" /> : <Lock className="h-8 w-8" />}
          </div>
          <h2 className="text-2xl font-extrabold tracking-tight">
            {isSetup ? "Configurar Acesso" : "Banco de Dados Bloqueado"}
          </h2>
          <p className="text-sm text-slate-400 mt-2 text-center">
            {isSetup
              ? "Defina uma senha mestre para criptografar os dados em repouso."
              : modoChave
              ? "Insira sua chave de recuperação para desbloquear."
              : "Insira a senha mestre para carregar os laudos e dados de pacientes."}
          </p>
        </div>

        {chaveRecuperacao ? (
          <div className="space-y-6">
            <div className="p-4 bg-emerald-950/30 border border-emerald-800/40 rounded-xl">
              <span className="text-xs text-emerald-400 font-semibold uppercase tracking-wider block mb-1">Chave de Recuperação Gerada</span>
              <p className="text-xs text-slate-300 leading-relaxed mb-4">
                Guarde esta chave em local seguro. Ela permite recuperar o acesso caso você esqueça a senha mestre.
              </p>
              <div className="bg-slate-950 border border-slate-800 p-3 rounded-lg font-mono text-center text-sm font-bold tracking-widest flex items-center justify-between gap-2 text-indigo-400 select-all">
                <span className="truncate">{chaveRecuperacao}</span>
                <button
                  onClick={copiarChave}
                  className="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-100 transition-colors cursor-pointer"
                  title="Copiar Chave"
                >
                  <Copy className="h-4 w-4" />
                </button>
              </div>
            </div>

            <button
              onClick={() => onSetupComplete(chaveRecuperacao)}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all duration-200 cursor-pointer hover:shadow-lg hover:shadow-indigo-500/10 active:scale-98"
            >
              Concluir Setup e Desbloquear
            </button>
          </div>
        ) : isSetup ? (
          <form onSubmit={handleSetup} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1">Senha Mestre (Mínimo 8 caracteres)</label>
              <input
                type="password"
                required
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-400 block mb-1">Confirmar Senha</label>
              <input
                type="password"
                required
                value={confirmaSenha}
                onChange={(e) => setConfirmaSenha(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={unlLoading}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
            >
              {unlLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Unlock className="h-4 w-4" />}
              <span>Configurar e Criptografar</span>
            </button>
          </form>
        ) : (
          <form onSubmit={handleUnlock} className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-semibold text-slate-400">
                  {modoChave ? "Chave de Recuperação" : "Senha Mestre"}
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setModoChave(!modoChave);
                    setSenha("");
                  }}
                  className="text-xs text-indigo-400 hover:underline cursor-pointer"
                >
                  {modoChave ? "Usar senha mestre" : "Esqueceu a senha?"}
                </button>
              </div>
              <input
                type={modoChave ? "text" : "password"}
                required
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                placeholder={modoChave ? "XXXX-XXXX-XXXX-XXXX" : "••••••••"}
                className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm focus:ring-1 focus:ring-indigo-500 transition-all outline-none font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={unlLoading}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
            >
              {unlLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Unlock className="h-4 w-4" />}
              <span>Desbloquear Banco</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────── PAINEL DE PACIENTES ────────────────────────────

interface PacientePanelProps {
  currentUser: string;
  showMsg: (type: "success" | "error" | "warning", msg: string) => void;
}

function PacientePanel({ currentUser, showMsg }: PacientePanelProps) {
  const [pacientes, setPacientes] = useState<Paciente[]>([]);
  const [termoBusca, setTermoBusca] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [modalAberto, setModalAberto] = useState(false);
  const [editandoId, setEditandoId] = useState<number | null>(null);

  // Catálogos
  const [comorbidadesCatalogo, setComorbidadesCatalogo] = useState<string[]>([]);
  const [sintomasCatalogo, setSintomasCatalogo] = useState<string[]>([]);

  // Estado do formulário
  const [formProntuario, setFormProntuario] = useState("");
  const [formCpf, setFormCpf] = useState("");
  const [formNome, setFormNome] = useState("");
  const [formDataExame, setFormDataExame] = useState("");
  const [formIdade, setFormIdade] = useState("");
  const [formSexo, setFormSexo] = useState<"M" | "F">("F");
  const [formPolipo, setFormPolipo] = useState("0");
  const [formIndicacao, setFormIndicacao] = useState("Rastreio");
  const [formHistopatologico, setFormHistopatologico] = useState("");
  const [formComorbidades, setFormComorbidades] = useState<string[]>([]);
  const [formSintomas, setFormSintomas] = useState<string[]>([]);
  const [formHistorico, setFormHistorico] = useState<HistoricoFamiliar[]>([]);

  // Modais de catálogo customizados
  const [addComorbidadeNome, setAddComorbidadeNome] = useState("");
  const [addSintomaNome, setAddSintomaNome] = useState("");

  // Zod Erros
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    carregarPacientes();
    carregarCatalogos();
  }, []);

  const carregarPacientes = async () => {
    setCarregando(true);
    try {
      const list = await invoke<Paciente[]>("listar_pacientes");
      setPacientes(list);
    } catch (e) {
      showMsg("error", "Erro ao carregar lista de pacientes: " + String(e));
    } finally {
      setCarregando(false);
    }
  };

  const carregarCatalogos = async () => {
    try {
      const c = await invoke<string[]>("listar_comorbidades_catalogo");
      const s = await invoke<string[]>("listar_sintomas_catalogo");
      setComorbidadesCatalogo(c);
      setSintomasCatalogo(s);
    } catch (_) {}
  };

  const lidarComBusca = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!termoBusca.trim()) {
      carregarPacientes();
      return;
    }
    setCarregando(true);
    try {
      const list = await invoke<Paciente[]>("buscar_paciente_por_termo", { termo: termoBusca });
      setPacientes(list);
    } catch (e) {
      showMsg("error", "Erro ao realizar busca: " + String(e));
    } finally {
      setCarregando(false);
    }
  };

  const abrirModalCriar = () => {
    setEditandoId(null);
    setFormProntuario("");
    setFormCpf("");
    setFormNome("");
    setFormDataExame("");
    setFormIdade("");
    setFormSexo("F");
    setFormPolipo("0");
    setFormIndicacao("Rastreio");
    setFormHistopatologico("");
    setFormComorbidades([]);
    setFormSintomas([]);
    setFormHistorico([]);
    setFormErrors({});
    setModalAberto(true);
  };

  const abrirModalEditar = async (p: Paciente) => {
    if (!p.id) return;
    setEditandoId(p.id);
    setFormProntuario(p.numero_prontuario);
    setFormCpf(p.cpf ? formatarCPF(p.cpf) : "");
    setFormNome(p.nome);
    setFormDataExame(converterParaBR(p.data_exame));
    setFormIdade(p.idade.toString());
    setFormSexo(p.sexo as "M" | "F");
    setFormPolipo(p.polipo.toString());
    setFormIndicacao(p.indicacao_exame);
    setFormHistopatologico(p.resultado_histopatologico || "");
    setFormComorbidades(p.comorbidades);
    setFormSintomas(p.sintomas);
    setFormHistorico(p.historico_familiar);
    setFormErrors({});
    setModalAberto(true);
  };

  const salvarPaciente = async () => {
    // Validação frontend via Zod
    const rawData = {
      numero_prontuario: formProntuario,
      cpf: formCpf || null,
      nome: formNome,
      data_exame: formDataExame,
      idade: formIdade,
      sexo: formSexo,
      polipo: formPolipo,
      indicacao_exame: formIndicacao,
      resultado_histopatologico: formHistopatologico || null,
      comorbidades: formComorbidades,
      sintomas: formSintomas,
      historico_familiar: formHistorico,
    };

    const valid = pacienteSchema.safeParse(rawData);
    if (!valid.success) {
      const errMap: Record<string, string> = {};
      valid.error.issues.forEach((err: any) => {
        if (err.path.length > 0) {
          errMap[err.path[0]] = err.message;
        }
      });
      setFormErrors(errMap);
      showMsg("error", "Há erros no formulário de pacientes.");
      return;
    }

    const payload: Paciente = {
      id: editandoId,
      numero_prontuario: formProntuario,
      cpf: formCpf ? formCpf.replace(/\D/g, "") : null,
      nome: formNome,
      data_exame: converterParaISO(formDataExame),
      idade: parseInt(formIdade) || 0,
      sexo: formSexo,
      polipo: parseInt(formPolipo) || 0,
      resultado_histopatologico: formHistopatologico || null,
      indicacao_exame: formIndicacao,
      comorbidades: formComorbidades,
      sintomas: formSintomas,
      historico_familiar: formHistorico,
      endoscopista: editandoId ? null : currentUser,
    };

    try {
      if (editandoId) {
        await invoke("editar_paciente", { usuario: currentUser, paciente: payload });
        showMsg("success", "Paciente editado com sucesso!");
      } else {
        await invoke("cadastrar_paciente", { usuario: currentUser, paciente: payload });
        showMsg("success", "Paciente cadastrado com sucesso!");
      }
      setModalAberto(false);
      carregarPacientes();
    } catch (e) {
      showMsg("error", "Erro ao persistir paciente: " + String(e));
    }
  };

  const excluirPaciente = async (id: number) => {
    if (!confirm("Tem certeza que deseja excluir permanentemente este paciente e todos os seus laudos?")) {
      return;
    }
    try {
      await invoke("excluir_paciente", { usuario: currentUser, id });
      showMsg("success", "Paciente removido com sucesso!");
      carregarPacientes();
    } catch (e) {
      showMsg("error", "Falha ao excluir paciente: " + String(e));
    }
  };

  // Funções dinâmicas para histórico familiar
  const addHistoricoItem = () => {
    setFormHistorico([...formHistorico, { parentesco: "", grau: 1, idade_diagnostico: null }]);
  };

  const removeHistoricoItem = (index: number) => {
    setFormHistorico(formHistorico.filter((_, i) => i !== index));
  };

  const updateHistoricoItem = (index: number, field: keyof HistoricoFamiliar, val: any) => {
    const updated = [...formHistorico];
    updated[index] = { ...updated[index], [field]: val };
    setFormHistorico(updated);
  };

  // Funções para adicionar itens ao catálogo no banco de dados
  const criarComorbidadeNoBanco = async () => {
    if (!addComorbidadeNome.trim()) return;
    try {
      await invoke("adicionar_comorbidade_catalogo", { usuario: currentUser, nome: addComorbidadeNome.trim() });
      await carregarCatalogos();
      setFormComorbidades([...formComorbidades, addComorbidadeNome.trim()]);
      setAddComorbidadeNome("");
    } catch (e) {
      showMsg("error", "Erro ao adicionar comorbidade: " + String(e));
    }
  };

  const criarSintomaNoBanco = async () => {
    if (!addSintomaNome.trim()) return;
    try {
      await invoke("adicionar_sintoma_catalogo", { usuario: currentUser, nome: addSintomaNome.trim() });
      await carregarCatalogos();
      setFormSintomas([...formSintomas, addSintomaNome.trim()]);
      setAddSintomaNome("");
    } catch (e) {
      showMsg("error", "Erro ao adicionar sintoma: " + String(e));
    }
  };

  const exportarCSV = async () => {
    try {
      const csvContent = await invoke<string>("exportar_pacientes_csv");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", `GastroEpi_Pacientes_${new Date().toISOString().split("T")[0]}.csv`);
      link.style.visibility = "hidden";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      showMsg("success", "CSV gerado com sucesso para Excel (pt-BR)!");
    } catch (e) {
      showMsg("error", "Erro ao exportar CSV: " + String(e));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Panel */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight">Cadastro Clínico</h2>
          <p className="text-sm text-slate-400 mt-1">Gerencie a base de pacientes sob custódia criptográfica.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={exportarCSV}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-800 bg-slate-900/50 text-slate-300 hover:text-slate-100 hover:bg-slate-800/80 transition-all font-medium text-sm cursor-pointer"
          >
            <FileSpreadsheet className="h-4 w-4 text-emerald-500" />
            <span>Exportar Excel (CSV)</span>
          </button>
          <button
            onClick={abrirModalCriar}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition-all font-medium text-sm hover:shadow-lg hover:shadow-indigo-600/10 cursor-pointer active:scale-98"
          >
            <Plus className="h-4 w-4" />
            <span>Novo Paciente</span>
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <form onSubmit={lidarComBusca} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-3.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            value={termoBusca}
            onChange={(e) => setTermoBusca(e.target.value)}
            placeholder="Pesquisar por nome ou prontuário médico..."
            className="w-full bg-slate-900 border border-slate-800 focus:border-indigo-500 rounded-xl pl-12 pr-4 py-3 text-sm focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
          />
        </div>
        <button
          type="submit"
          className="px-5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-slate-100 rounded-xl transition-all border border-slate-700/50 cursor-pointer"
        >
          Filtrar
        </button>
        {termoBusca && (
          <button
            type="button"
            onClick={() => {
              setTermoBusca("");
              carregarPacientes();
            }}
            className="px-4 hover:bg-slate-800/40 text-slate-400 hover:text-slate-200 rounded-xl transition-all border border-transparent cursor-pointer"
          >
            Limpar
          </button>
        )}
      </form>

      {/* Patients Grid / Table */}
      {carregando ? (
        <div className="flex h-64 items-center justify-center bg-slate-900/20 border border-slate-900 rounded-2xl">
          <RefreshCw className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      ) : pacientes.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 bg-slate-900/20 border border-slate-900 rounded-2xl text-slate-500">
          <Users className="h-12 w-12 text-slate-700 mb-3" />
          <span>Nenhum paciente cadastrado ou encontrado.</span>
        </div>
      ) : (
        <div className="border border-slate-800/80 bg-slate-900/30 rounded-2xl overflow-hidden shadow-xl backdrop-blur-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-xs font-semibold text-slate-400 bg-slate-950/40">
                  <th className="p-4">Prontuário</th>
                  <th className="p-4">Nome</th>
                  <th className="p-4">Idade / Sexo</th>
                  <th className="p-4">Data do Exame</th>
                  <th className="p-4">Indicação</th>
                  <th className="p-4 text-center">Pólipos</th>
                  <th className="p-4">Endoscopista</th>
                  <th className="p-4 text-center">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm text-slate-200">
                {pacientes.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-900/40 transition-colors">
                    <td className="p-4 font-mono text-xs font-semibold text-slate-400">{p.numero_prontuario}</td>
                    <td className="p-4 font-semibold text-slate-100">{p.nome}</td>
                    <td className="p-4">
                      {p.idade} anos • <span className="font-semibold text-slate-400">{p.sexo}</span>
                    </td>
                    <td className="p-4 text-slate-300">{converterParaBR(p.data_exame)}</td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        p.indicacao_exame === "Diagnóstico" ? "bg-cyan-950/50 text-cyan-400 border border-cyan-800/30" : "bg-slate-950/60 text-slate-400 border border-slate-800/50"
                      }`}>
                        {p.indicacao_exame}
                      </span>
                    </td>
                    <td className="p-4 text-center font-bold font-mono">
                      <span className={p.polipo > 0 ? "text-amber-500" : "text-slate-500"}>
                        {p.polipo}
                      </span>
                    </td>
                    <td className="p-4 text-slate-400 text-xs">{p.endoscopista || "Desconhecido"}</td>
                    <td className="p-4">
                      <div className="flex justify-center gap-2">
                        <button
                          onClick={() => abrirModalEditar(p)}
                          className="p-1.5 hover:bg-indigo-950/40 hover:text-indigo-400 text-slate-400 rounded transition-all cursor-pointer"
                          title="Editar Ficha"
                        >
                          <Edit3 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => p.id && excluirPaciente(p.id)}
                          className="p-1.5 hover:bg-red-950/40 hover:text-red-400 text-slate-400 rounded transition-all cursor-pointer"
                          title="Remover Ficha"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* FORM MODAL DE PACIENTE */}
      {modalAberto && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col animate-fade-in">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-slate-100">{editandoId ? "Editar Paciente" : "Novo Paciente"}</h3>
                <p className="text-xs text-slate-400 mt-1">Todos os dados de laudo e CPFs serão cifrados fisicamente.</p>
              </div>
              <button
                onClick={() => setModalAberto(false)}
                className="text-slate-400 hover:text-slate-100 p-1.5 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancelar
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm text-slate-300">
              {/* Seção 1: Dados Pessoais */}
              <div className="space-y-4">
                <span className="text-xs font-semibold text-indigo-400 uppercase tracking-widest block border-b border-slate-800 pb-2">1. Informações Básicas</span>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Registro Prontuário *</label>
                    <input
                      type="text"
                      value={formProntuario}
                      onChange={(e) => setFormProntuario(e.target.value)}
                      placeholder="Ex: 874312"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                    {formErrors.numero_prontuario && <span className="text-xs text-red-400 mt-1 block">{formErrors.numero_prontuario}</span>}
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">CPF (Opcional)</label>
                    <input
                      type="text"
                      value={formCpf}
                      onChange={(e) => setFormCpf(e.target.value)}
                      placeholder="000.000.000-00"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                    {formErrors.cpf && <span className="text-xs text-red-400 mt-1 block">{formErrors.cpf}</span>}
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Nome Completo *</label>
                    <input
                      type="text"
                      value={formNome}
                      onChange={(e) => setFormNome(e.target.value)}
                      placeholder="Ex: Maria das Dores"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                    {formErrors.nome && <span className="text-xs text-red-400 mt-1 block">{formErrors.nome}</span>}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Idade *</label>
                    <input
                      type="number"
                      value={formIdade}
                      onChange={(e) => setFormIdade(e.target.value)}
                      placeholder="Ex: 50"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                    {formErrors.idade && <span className="text-xs text-red-400 mt-1 block">{formErrors.idade}</span>}
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Sexo *</label>
                    <select
                      value={formSexo}
                      onChange={(e) => setFormSexo(e.target.value as "M" | "F")}
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    >
                      <option value="F">Feminino</option>
                      <option value="M">Masculino</option>
                    </select>
                    {formErrors.sexo && <span className="text-xs text-red-400 mt-1 block">{formErrors.sexo}</span>}
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Data do Exame (dd/mm/aaaa) *</label>
                    <input
                      type="text"
                      value={formDataExame}
                      onChange={(e) => setFormDataExame(e.target.value)}
                      placeholder="03/06/2026"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                    {formErrors.data_exame && <span className="text-xs text-red-400 mt-1 block">{formErrors.data_exame}</span>}
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Indicação *</label>
                    <select
                      value={formIndicacao}
                      onChange={(e) => setFormIndicacao(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    >
                      <option value="Rastreio">Rastreio</option>
                      <option value="Diagnóstico">Diagnóstico (Sintomático)</option>
                    </select>
                    {formErrors.indicacao_exame && <span className="text-xs text-red-400 mt-1 block">{formErrors.indicacao_exame}</span>}
                  </div>
                </div>
              </div>

              {/* Seção 2: Histórico Clínico e Sintomas */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Comorbidades */}
                <div className="space-y-3">
                  <span className="text-xs font-semibold text-indigo-400 uppercase tracking-widest block border-b border-slate-800 pb-2">Comorbidades</span>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={addComorbidadeNome}
                      onChange={(e) => setAddComorbidadeNome(e.target.value)}
                      placeholder="Criar nova comorbidade..."
                      className="flex-1 bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs outline-none"
                    />
                    <button
                      type="button"
                      onClick={criarComorbidadeNoBanco}
                      className="px-3 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-xl border border-slate-700 cursor-pointer"
                    >
                      Criar
                    </button>
                  </div>
                  <div className="h-32 border border-slate-800 rounded-xl p-3 bg-slate-950/60 overflow-y-auto space-y-1">
                    {comorbidadesCatalogo.map((c) => {
                      const isChecked = formComorbidades.includes(c);
                      return (
                        <label key={c} className="flex items-center gap-2 text-xs py-0.5 cursor-pointer text-slate-300 hover:text-slate-100">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              if (isChecked) {
                                setFormComorbidades(formComorbidades.filter((item) => item !== c));
                              } else {
                                setFormComorbidades([...formComorbidades, c]);
                              }
                            }}
                            className="rounded border-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                          />
                          <span>{c}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Sintomas */}
                <div className="space-y-3">
                  <span className="text-xs font-semibold text-indigo-400 uppercase tracking-widest block border-b border-slate-800 pb-2">Sintomas</span>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={addSintomaNome}
                      onChange={(e) => setAddSintomaNome(e.target.value)}
                      placeholder="Criar novo sintoma..."
                      className="flex-1 bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs outline-none"
                    />
                    <button
                      type="button"
                      onClick={criarSintomaNoBanco}
                      className="px-3 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-xl border border-slate-700 cursor-pointer"
                    >
                      Criar
                    </button>
                  </div>
                  <div className="h-32 border border-slate-800 rounded-xl p-3 bg-slate-950/60 overflow-y-auto space-y-1">
                    {sintomasCatalogo.map((s) => {
                      const isChecked = formSintomas.includes(s);
                      return (
                        <label key={s} className="flex items-center gap-2 text-xs py-0.5 cursor-pointer text-slate-300 hover:text-slate-100">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              if (isChecked) {
                                setFormSintomas(formSintomas.filter((item) => item !== s));
                              } else {
                                setFormSintomas([...formSintomas, s]);
                              }
                            }}
                            className="rounded border-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                          />
                          <span>{s}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Seção 3: Histórico Familiar */}
              <div className="space-y-3">
                <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                  <span className="text-xs font-semibold text-indigo-400 uppercase tracking-widest block">3. Histórico Familiar (Câncer Colorretal)</span>
                  <button
                    type="button"
                    onClick={addHistoricoItem}
                    className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer"
                  >
                    <Plus className="h-3 w-3" />
                    <span>Adicionar Familiar</span>
                  </button>
                </div>
                {formHistorico.length === 0 ? (
                  <p className="text-xs text-slate-500 py-2">Sem histórico familiar de câncer reportado.</p>
                ) : (
                  <div className="space-y-2">
                    {formHistorico.map((h, index) => (
                      <div key={index} className="flex items-center gap-3 p-3 bg-slate-950/50 border border-slate-800/80 rounded-xl animate-fade-in">
                        <div className="flex-1 grid grid-cols-3 gap-3">
                          <div>
                            <input
                              type="text"
                              required
                              value={h.parentesco}
                              onChange={(e) => updateHistoricoItem(index, "parentesco", e.target.value)}
                              placeholder="Familiar (ex: Pai, Irmã)"
                              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg px-2.5 py-1.5 text-xs outline-none"
                            />
                          </div>
                          <div>
                            <select
                              value={h.grau}
                              onChange={(e) => updateHistoricoItem(index, "grau", parseInt(e.target.value))}
                              className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg px-2.5 py-1.5 text-xs outline-none"
                            >
                              <option value={1}>1º Grau (Pais, Filhos, Irmãos)</option>
                              <option value={2}>2º Grau (Avós, Tios, Sobrinhos)</option>
                              <option value={3}>3º Grau (Primos)</option>
                            </select>
                          </div>
                          <div>
                            <input
                              type="number"
                              value={h.idade_diagnostico === null ? "" : String(h.idade_diagnostico)}
                              onChange={(e) => updateHistoricoItem(index, "idade_diagnostico", e.target.value ? parseInt(e.target.value) : null)}
                              placeholder="Idade do diagnóstico (Opcional)"
                              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs outline-none"
                            />
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeHistoricoItem(index)}
                          className="p-1 text-slate-500 hover:text-red-400 hover:bg-red-950/20 rounded transition-colors cursor-pointer"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Seção 4: Dados Endoscópicos e Achados */}
              <div className="space-y-4">
                <span className="text-xs font-semibold text-indigo-400 uppercase tracking-widest block border-b border-slate-800 pb-2">4. Achados da Colonoscopia</span>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Quantidade de Pólipos *</label>
                    <input
                      type="number"
                      value={formPolipo}
                      onChange={(e) => setFormPolipo(e.target.value)}
                      placeholder="0"
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                    {formErrors.polipo && <span className="text-xs text-red-400 mt-1 block">{formErrors.polipo}</span>}
                  </div>
                  <div className="md:col-span-3">
                    <label className="text-xs text-slate-400 font-semibold block mb-1">Resultado Histopatológico (Laudo Cifrado)</label>
                    <input
                      type="text"
                      value={formHistopatologico}
                      onChange={(e) => setFormHistopatologico(e.target.value)}
                      placeholder="Ex: Adenoma tubular com displasia de baixo grau..."
                      className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-slate-800 bg-slate-950/40 flex items-center justify-end gap-3">
              <button
                onClick={() => setModalAberto(false)}
                className="px-4 py-2 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-slate-200 text-sm font-medium rounded-xl transition-all cursor-pointer"
              >
                Voltar
              </button>
              <button
                onClick={salvarPaciente}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl transition-all hover:shadow-lg hover:shadow-indigo-600/10 cursor-pointer active:scale-98"
              >
                Salvar Cadastro
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────── PAINEL DE ESTATÍSTICA (STATCALC) ────────────────────────────

interface StatCalcPanelProps {
  showMsg: (type: "success" | "error" | "warning", msg: string) => void;
}

function StatCalcPanel({ showMsg }: StatCalcPanelProps) {
  const [subTab, setSubTab] = useState<"qualidade" | "tabela2x2" | "diagnostico" | "amostra" | "trend" | "strat">("qualidade");

  return (
    <div className="space-y-6">
      {/* Tab Header */}
      <div>
        <h2 className="text-3xl font-extrabold tracking-tight">StatCalc Epidemiológico</h2>
        <p className="text-sm text-slate-400 mt-1">Calculadoras epidemiológicas de alta fidelidade baseadas no Epi Info.</p>
      </div>

      {/* Selector Tabs */}
      <div className="flex border-b border-slate-800 overflow-x-auto no-scrollbar gap-2 pb-px text-sm">
        <button
          onClick={() => setSubTab("qualidade")}
          className={`py-2.5 px-4 font-medium border-b-2 cursor-pointer transition-colors ${
            subTab === "qualidade" ? "border-indigo-500 text-indigo-400" : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Indicadores de Qualidade (BD)
        </button>
        <button
          onClick={() => setSubTab("tabela2x2")}
          className={`py-2.5 px-4 font-medium border-b-2 cursor-pointer transition-colors ${
            subTab === "tabela2x2" ? "border-indigo-500 text-indigo-400" : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Tabela 2x2
        </button>
        <button
          onClick={() => setSubTab("diagnostico")}
          className={`py-2.5 px-4 font-medium border-b-2 cursor-pointer transition-colors ${
            subTab === "diagnostico" ? "border-indigo-500 text-indigo-400" : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Teste Diagnóstico
        </button>
        <button
          onClick={() => setSubTab("amostra")}
          className={`py-2.5 px-4 font-medium border-b-2 cursor-pointer transition-colors ${
            subTab === "amostra" ? "border-indigo-500 text-indigo-400" : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Tamanho Amostral
        </button>
        <button
          onClick={() => setSubTab("trend")}
          className={`py-2.5 px-4 font-medium border-b-2 cursor-pointer transition-colors ${
            subTab === "trend" ? "border-indigo-500 text-indigo-400" : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Tendência Linear
        </button>
        <button
          onClick={() => setSubTab("strat")}
          className={`py-2.5 px-4 font-medium border-b-2 cursor-pointer transition-colors ${
            subTab === "strat" ? "border-indigo-500 text-indigo-400" : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Mantel-Haenszel
        </button>
      </div>

      <div className="bg-slate-900/10 rounded-2xl border border-slate-900 p-6">
        {subTab === "qualidade" && <QualidadeIndicators showMsg={showMsg} />}
        {subTab === "tabela2x2" && <Tabela2x2Calculator showMsg={showMsg} />}
        {subTab === "diagnostico" && <TesteDiagnosticoCalculator showMsg={showMsg} />}
        {subTab === "amostra" && <TamanhoAmostraCalculator showMsg={showMsg} />}
        {subTab === "trend" && <CochranTrendCalculator showMsg={showMsg} />}
        {subTab === "strat" && <MantelHaenszelCalculator showMsg={showMsg} />}
      </div>
    </div>
  );
}

// ───────────────── Sub-Painel: Indicadores de Qualidade ─────────────────

function QualidadeIndicators({ showMsg }: { showMsg: (type: "success" | "error" | "warning", msg: string) => void }) {
  const [qualidadeList, setQualidadeList] = useState<ResultadoIndicadorQualidade[]>([]);
  const [prevalencia, setPrevalencia] = useState<Prevalencia | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    carregarDados();
  }, []);

  const carregarDados = async () => {
    setLoading(true);
    try {
      const q = await invoke<ResultadoIndicadorQualidade[]>("obter_indicadores_qualidade");
      setQualidadeList(q);
      const prev = await invoke<Prevalencia>("obter_prevalencia_polipo");
      setPrevalencia(prev);
    } catch (e) {
      showMsg("warning", "Banco sem pacientes suficientes para calcular indicadores de qualidade.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <RefreshCw className="h-6 w-6 animate-spin text-indigo-500 mx-auto" />;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Prevalência Global Card */}
      {prevalencia && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide block">Prevalência de Pólipos</span>
              <h3 className="text-3xl font-extrabold text-indigo-400 mt-2">
                {(prevalencia.taxa * 100).toFixed(1)}%
              </h3>
              <span className="text-xs text-slate-400 mt-1 block">
                IC 95%: [{(prevalencia.ic_inferior * 100).toFixed(1)}% - {(prevalencia.ic_superior * 100).toFixed(1)}%]
              </span>
            </div>
            <div className="text-slate-600 text-xs text-right">
              <span className="font-bold text-slate-300 block">{prevalencia.n_casos} casos</span>
              <span>de {prevalencia.n_total} exames</span>
            </div>
          </div>
        </div>
      )}

      {/* Tabela de Qualidade por Endoscopista */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold">Indicadores de Qualidade por Endoscopista</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Métricas de ADR (Adenoma Detection Rate) e PDR (Polyp Detection Rate) recomendadas pela ASGE/ACG.
          </p>
        </div>

        {qualidadeList.length === 0 ? (
          <div className="p-6 border border-dashed border-slate-800 text-center text-slate-500 rounded-xl">
            Sem dados de exames válidos.
          </div>
        ) : (
          <div className="border border-slate-800/80 rounded-xl overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-800 text-xs font-semibold text-slate-400 bg-slate-950/40">
                  <th className="p-4">Endoscopista</th>
                  <th className="p-4 text-center">Nº Exames</th>
                  <th className="p-4 text-center">PDR (Pólipos)</th>
                  <th className="p-4 text-center">ADR (Adenomas) *</th>
                  <th className="p-4">Status ADR (ASGE Target &ge; 25%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-sm text-slate-200">
                {qualidadeList.map((q) => {
                  const adrPercent = q.adr * 100;
                  const belowTarget = adrPercent < 25.0;
                  return (
                    <tr key={q.endoscopista} className="hover:bg-slate-900/20 transition-colors">
                      <td className="p-4 font-semibold text-slate-100">{q.endoscopista}</td>
                      <td className="p-4 text-center font-mono text-slate-400">{q.n_exames}</td>
                      <td className="p-4 text-center">
                        <span className="font-bold">{(q.pdr * 100).toFixed(1)}%</span>
                        <span className="text-[10px] text-slate-500 block">
                          [{(q.pdr_ic[0] * 100).toFixed(0)}% - {(q.pdr_ic[1] * 100).toFixed(0)}%]
                        </span>
                      </td>
                      <td className="p-4 text-center">
                        <span className={`font-bold ${belowTarget ? "text-amber-500" : "text-emerald-400"}`}>
                          {adrPercent.toFixed(1)}%
                        </span>
                        <span className="text-[10px] text-slate-500 block">
                          [{(q.adr_ic[0] * 100).toFixed(0)}% - {(q.adr_ic[1] * 100).toFixed(0)}%]
                        </span>
                      </td>
                      <td className="p-4">
                        {belowTarget ? (
                          <div className="flex items-center gap-2 text-amber-500 text-xs font-semibold px-2.5 py-1 bg-amber-950/20 border border-amber-800/30 rounded-lg w-fit">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            <span>Alerta: ADR abaixo de 25%</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold px-2.5 py-1 bg-emerald-950/20 border border-emerald-800/30 rounded-lg w-fit">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>Alvo Atingido</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <span className="text-[10px] text-slate-500 block">
          * A ADR é calculada com base em pacientes com resultado histopatológico contendo o termo "adenoma".
        </span>
      </div>
    </div>
  );
}

// ───────────────── Sub-Painel: Calculadora Tabela 2x2 ─────────────────

function Tabela2x2Calculator({ showMsg }: { showMsg: (type: "success" | "error" | "warning", msg: string) => void }) {
  const [a, setA] = useState("10");
  const [b, setB] = useState("20");
  const [c, setC] = useState("5");
  const [d, setD] = useState("30");
  const [resultado, setResultado] = useState<ResultadoTabela2x2 | null>(null);

  const calcular = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await invoke<ResultadoTabela2x2>("calcular_tabela_2x2", {
        a: parseInt(a) || 0,
        b: parseInt(b) || 0,
        c: parseInt(c) || 0,
        d: parseInt(d) || 0,
      });
      setResultado(res);
      showMsg("success", "Tabela 2x2 calculada com precisão f64.");
    } catch (err) {
      showMsg("error", "Erro nos parâmetros de cálculo: " + String(err));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-bold">Tabela 2x2 Contingência</h3>
          <p className="text-xs text-slate-500 mt-0.5">Entre com os dados de contagem de exposição e desfecho.</p>
        </div>

        <form onSubmit={calcular} className="space-y-6">
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl">
            <div className="grid grid-cols-3 gap-2 text-center text-xs font-semibold text-slate-400 mb-2">
              <div></div>
              <div>Desfecho+</div>
              <div>Desfecho-</div>
            </div>
            <div className="grid grid-cols-3 gap-2 items-center mb-2">
              <div className="text-xs font-semibold text-slate-400 text-right pr-2">Exposto+</div>
              <input
                type="number"
                value={a}
                onChange={(e) => setA(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
              <input
                type="number"
                value={b}
                onChange={(e) => setB(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
            </div>
            <div className="grid grid-cols-3 gap-2 items-center">
              <div className="text-xs font-semibold text-slate-400 text-right pr-2">Exposto-</div>
              <input
                type="number"
                value={c}
                onChange={(e) => setC(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
              <input
                type="number"
                value={d}
                onChange={(e) => setD(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer active:scale-98 transition-all hover:shadow-lg hover:shadow-indigo-600/10"
          >
            <Play className="h-4 w-4 fill-white" />
            <span>Processar Estatísticas</span>
          </button>
        </form>
      </div>

      {/* Resultados */}
      <div className="space-y-6 bg-slate-900/30 border border-slate-850 p-6 rounded-2xl">
        <h4 className="font-bold text-sm text-indigo-400 uppercase tracking-widest block border-b border-slate-850 pb-2">Resultados Analíticos</h4>

        {resultado ? (
          <div className="space-y-4 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Total Amostral (N)</span>
              <span className="font-mono font-bold">{resultado.n_total}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Odds Ratio (OR)</span>
              <div className="text-right">
                <span className="font-mono font-bold block text-slate-100">{resultado.odds_ratio.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono">IC 95%: [{resultado.odds_ratio_ic[0].toFixed(3)} - {resultado.odds_ratio_ic[1].toFixed(3)}]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Risco Relativo (RR)</span>
              <div className="text-right">
                <span className="font-mono font-bold block text-slate-100">{resultado.risco_relativo.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono">IC 95%: [{resultado.risco_relativo_ic[0].toFixed(3)} - {resultado.risco_relativo_ic[1].toFixed(3)}]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Qui-Quadrado Pearson</span>
              <div className="text-right">
                <span className="font-mono font-bold block text-slate-100">{resultado.chi2_pearson.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono">p-valor: {resultado.p_valor_pearson.toExponential(4)}</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Qui-Quadrado Yates (Correção)</span>
              <div className="text-right">
                <span className="font-mono font-bold block text-slate-100">{resultado.chi2_yates.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono">p-valor: {resultado.p_valor_yates.toExponential(4)}</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Teste Exato de Fisher (Bicaudal)</span>
              <span className="font-mono font-bold text-indigo-400">p-valor: {resultado.p_valor_fisher.toExponential(4)}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500 py-12 text-center">Forneça as contagens e execute para ver a modelagem estatística.</p>
        )}
      </div>
    </div>
  );
}

// ───────────────── Sub-Painel: Teste Diagnóstico Calculator ─────────────────

function TesteDiagnosticoCalculator({ showMsg }: { showMsg: (type: "success" | "error" | "warning", msg: string) => void }) {
  const [vp, setVp] = useState("80");
  const [fp, setFp] = useState("10");
  const [fnVal, setFnVal] = useState("20");
  const [vn, setVn] = useState("90");
  const [alfa, setAlfa] = useState("0.05");
  const [resultado, setResultado] = useState<ResultadoTesteDiagnostico | null>(null);

  const calcular = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await invoke<ResultadoTesteDiagnostico>("calcular_teste_diagnostico", {
        vp: parseInt(vp) || 0,
        fp: parseInt(fp) || 0,
        fnVal: parseInt(fnVal) || 0,
        vn: parseInt(vn) || 0,
        alfa: parseFloat(alfa) || 0.05,
      });
      setResultado(res);
      showMsg("success", "Métricas diagnósticas e LRs processados.");
    } catch (err) {
      showMsg("error", "Erro ao executar cálculo diagnóstico: " + String(err));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-bold">Fidelidade de Teste Diagnóstico</h3>
          <p className="text-xs text-slate-500 mt-0.5">Compare um teste sob avaliação contra a referência padrão-ouro.</p>
        </div>

        <form onSubmit={calcular} className="space-y-6">
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl">
            <div className="grid grid-cols-3 gap-2 text-center text-xs font-semibold text-slate-400 mb-2">
              <div></div>
              <div>Padrão-Ouro+</div>
              <div>Padrão-Ouro-</div>
            </div>
            <div className="grid grid-cols-3 gap-2 items-center mb-2">
              <div className="text-xs font-semibold text-slate-400 text-right pr-2">Teste+</div>
              <input
                type="number"
                value={vp}
                onChange={(e) => setVp(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
              <input
                type="number"
                value={fp}
                onChange={(e) => setFp(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
            </div>
            <div className="grid grid-cols-3 gap-2 items-center mb-4">
              <div className="text-xs font-semibold text-slate-400 text-right pr-2">Teste-</div>
              <input
                type="number"
                value={fnVal}
                onChange={(e) => setFnVal(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
              <input
                type="number"
                value={vn}
                onChange={(e) => setVn(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-center text-sm focus:border-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 font-semibold block mb-1">Nível de Significância (alfa)</label>
              <input
                type="text"
                value={alfa}
                onChange={(e) => setAlfa(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-2 w-24 text-center text-xs outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer transition-all active:scale-98"
          >
            <Play className="h-4 w-4 fill-white" />
            <span>Processar Ficha Diagnóstica</span>
          </button>
        </form>
      </div>

      {/* Resultados */}
      <div className="space-y-6 bg-slate-900/30 border border-slate-850 p-6 rounded-2xl">
        <h4 className="font-bold text-sm text-indigo-400 uppercase tracking-widest block border-b border-slate-850 pb-2">Resultados Diagnósticos</h4>

        {resultado ? (
          <div className="space-y-3.5 text-sm">
            <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
              <span className="text-slate-400">Sensibilidade</span>
              <div className="text-right">
                <span className="font-mono font-bold">{(resultado.sensibilidade * 100).toFixed(2)}%</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{(resultado.sensibilidade_ic[0] * 100).toFixed(1)}% - {(resultado.sensibilidade_ic[1] * 100).toFixed(1)}%]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
              <span className="text-slate-400">Especificidade</span>
              <div className="text-right">
                <span className="font-mono font-bold">{(resultado.especificidade * 100).toFixed(2)}%</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{(resultado.especificidade_ic[0] * 100).toFixed(1)}% - {(resultado.especificidade_ic[1] * 100).toFixed(1)}%]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
              <span className="text-slate-400">Valor Preditivo Positivo (VPP)</span>
              <div className="text-right">
                <span className="font-mono font-bold">{(resultado.vpp * 100).toFixed(2)}%</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{(resultado.vpp_ic[0] * 100).toFixed(1)}% - {(resultado.vpp_ic[1] * 100).toFixed(1)}%]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
              <span className="text-slate-400">Valor Preditivo Negativo (VPN)</span>
              <div className="text-right">
                <span className="font-mono font-bold">{(resultado.vpn * 100).toFixed(2)}%</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{(resultado.vpn_ic[0] * 100).toFixed(1)}% - {(resultado.vpn_ic[1] * 100).toFixed(1)}%]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
              <span className="text-slate-400">Razão Verossimilhança Positiva (LR+)</span>
              <div className="text-right">
                <span className="font-mono font-bold">{resultado.lr_positivo.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{resultado.lr_positivo_ic[0].toFixed(2)} - {resultado.lr_positivo_ic[1].toFixed(2)}]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
              <span className="text-slate-400">Razão Verossimilhança Negativa (LR-)</span>
              <div className="text-right">
                <span className="font-mono font-bold">{resultado.lr_negativo.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{resultado.lr_negativo_ic[0].toFixed(2)} - {resultado.lr_negativo_ic[1].toFixed(2)}]</span>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500 py-12 text-center">Execute para ver o laudo de sensibilidade e LRs.</p>
        )}
      </div>
    </div>
  );
}

// ───────────────── Sub-Painel: Tamanho de Amostra ─────────────────

function TamanhoAmostraCalculator({ showMsg }: { showMsg: (type: "success" | "error" | "warning", msg: string) => void }) {
  const [tipo, setTipo] = useState<"survey" | "comparative">("survey");

  // Survey inputs
  const [popSurvey, setPopSurvey] = useState("10000");
  const [pSurvey, setPSurvey] = useState("0.5");
  const [dSurvey, setDSurvey] = useState("0.05");
  const [confSurvey, setConfSurvey] = useState("0.95");
  const [surveyRes, setSurveyRes] = useState<AmostraSurvey | null>(null);

  // Comparative inputs
  const [poderComp, setPoderComp] = useState("0.80");
  const [confComp, setConfComp] = useState("0.95");
  const [ratioComp, setRatioComp] = useState("1.0");
  const [p0Comp, setP0Comp] = useState("0.10");
  const [p1Comp, setP1Comp] = useState("0.25");
  const [comparativeRes, setComparativeRes] = useState<AmostraEstudoComparativo | null>(null);

  const calcularSurvey = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const pop = popSurvey.trim() ? parseInt(popSurvey) : null;
      const res = await invoke<AmostraSurvey>("calcular_amostra_survey", {
        populacao: pop,
        p: parseFloat(pSurvey),
        d: parseFloat(dSurvey),
        confianca: parseFloat(confSurvey),
      });
      setSurveyRes(res);
      showMsg("success", "Cálculo de amostragem transversal concluído.");
    } catch (err) {
      showMsg("error", "Erro nos parâmetros do cálculo: " + String(err));
    }
  };

  const calcularComparative = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await invoke<AmostraEstudoComparativo>("calcular_amostra_comparativa", {
        poder: parseFloat(poderComp),
        confianca: parseFloat(confComp),
        razao: parseFloat(ratioComp),
        p0: parseFloat(p0Comp),
        p1: parseFloat(p1Comp),
      });
      setComparativeRes(res);
      showMsg("success", "Fórmula de Fleiss processada com sucesso.");
    } catch (err) {
      showMsg("error", "Erro ao executar Fleiss: " + String(err));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-lg font-bold">Cálculo de Poder & Tamanho Amostral</h3>
            <p className="text-xs text-slate-500 mt-0.5">Determine o tamanho amostral necessário para seu estudo.</p>
          </div>
          <div className="flex bg-slate-950 p-1 border border-slate-800 rounded-lg text-xs">
            <button
              onClick={() => setTipo("survey")}
              className={`px-3 py-1 rounded font-medium cursor-pointer transition-colors ${
                tipo === "survey" ? "bg-indigo-600 text-white" : "text-slate-400"
              }`}
            >
              Levantamento
            </button>
            <button
              onClick={() => setTipo("comparative")}
              className={`px-3 py-1 rounded font-medium cursor-pointer transition-colors ${
                tipo === "comparative" ? "bg-indigo-600 text-white" : "text-slate-400"
              }`}
            >
              Estudo Comparativo
            </button>
          </div>
        </div>

        {tipo === "survey" ? (
          <form onSubmit={calcularSurvey} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">População (N - Opcional)</label>
                <input
                  type="number"
                  value={popSurvey}
                  onChange={(e) => setPopSurvey(e.target.value)}
                  placeholder="Infinita"
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Frequência Esperada (0.01 - 0.99)</label>
                <input
                  type="text"
                  value={pSurvey}
                  onChange={(e) => setPSurvey(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Margem de Erro (d)</label>
                <input
                  type="text"
                  value={dSurvey}
                  onChange={(e) => setDSurvey(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Confiança (1-alfa)</label>
                <input
                  type="text"
                  value={confSurvey}
                  onChange={(e) => setConfSurvey(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all cursor-pointer active:scale-98"
            >
              Calcular Amostragem
            </button>
          </form>
        ) : (
          <form onSubmit={calcularComparative} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Poder Desejado (0.50 - 0.99)</label>
                <input
                  type="text"
                  value={poderComp}
                  onChange={(e) => setPoderComp(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Nível de Confiança</label>
                <input
                  type="text"
                  value={confComp}
                  onChange={(e) => setConfComp(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Razão Controles/Casos</label>
                <input
                  type="text"
                  value={ratioComp}
                  onChange={(e) => setRatioComp(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2 py-2.5 text-xs text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Taxa Controle (p0)</label>
                <input
                  type="text"
                  value={p0Comp}
                  onChange={(e) => setP0Comp(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2 py-2.5 text-xs text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 font-semibold block mb-1">Taxa Exposto (p1)</label>
                <input
                  type="text"
                  value={p1Comp}
                  onChange={(e) => setP1Comp(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2 py-2.5 text-xs text-slate-200 outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all cursor-pointer active:scale-98"
            >
              Calcular Coorte (Fleiss)
            </button>
          </form>
        )}
      </div>

      {/* Resultados */}
      <div className="bg-slate-900/30 border border-slate-850 p-6 rounded-2xl flex flex-col justify-between">
        <div>
          <h4 className="font-bold text-sm text-indigo-400 uppercase tracking-widest block border-b border-slate-850 pb-2">Resultado do Poder</h4>
          
          {tipo === "survey" && surveyRes ? (
            <div className="space-y-4 text-sm mt-6 animate-fade-in">
              <div className="flex items-center justify-between py-2 border-b border-slate-900">
                <span className="text-slate-400">Tamanho de Amostra Recomendado</span>
                <span className="font-mono font-bold text-indigo-400 text-2xl">{surveyRes.tamanho_amostra}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-slate-900">
                <span className="text-slate-400">População de Referência (N)</span>
                <span className="font-mono font-bold text-slate-200">{surveyRes.populacao ? surveyRes.populacao : "Infinita"}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-slate-900">
                <span className="text-slate-400">Frequência Estimada</span>
                <span className="font-mono font-bold text-slate-200">{(surveyRes.frequencia_esperada * 100).toFixed(1)}%</span>
              </div>
            </div>
          ) : tipo === "comparative" && comparativeRes ? (
            <div className="space-y-3.5 text-sm mt-6 animate-fade-in">
              <div className="flex items-center justify-between py-2 border-b border-slate-900">
                <span className="text-slate-400">Amostra Recomendada (Total)</span>
                <span className="font-mono font-bold text-indigo-400 text-2xl">{comparativeRes.amostra_total}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
                <span className="text-slate-400">Amostra Grupo 1 (Expostos)</span>
                <span className="font-mono font-bold text-slate-200">{comparativeRes.amostra_grupo1}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
                <span className="text-slate-400">Amostra Grupo 2 (Não Expostos)</span>
                <span className="font-mono font-bold text-slate-200">{comparativeRes.amostra_grupo2}</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-900">
                <span className="text-slate-400">Poder Estatístico</span>
                <span className="font-mono font-bold text-slate-200">{(comparativeRes.poder * 100).toFixed(0)}%</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500 py-12 text-center mt-6">Execute as especificações para receber o reporte do poder estatístico.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ───────────────── Sub-Painel: Cochran-Armitage Trend Calculator ─────────────────

function CochranTrendCalculator({ showMsg }: { showMsg: (type: "success" | "error" | "warning", msg: string) => void }) {
  const [categorias, setCategorias] = useState<Array<{ nome: string; casos: string; totais: string }>>([
    { nome: "< 50 anos", casos: "5", totais: "50" },
    { nome: "50-60 anos", casos: "15", totais: "60" },
    { nome: "60-70 anos", casos: "25", totais: "55" },
    { nome: "> 70 anos", casos: "30", totais: "45" },
  ]);
  const [resultado, setResultado] = useState<ResultadoTendencia | null>(null);

  const addCategoria = () => {
    setCategorias([...categorias, { nome: `Grupo ${categorias.length + 1}`, casos: "0", totais: "0" }]);
  };

  const removeCategoria = (index: number) => {
    setCategorias(categorias.filter((_, i) => i !== index));
  };

  const updateCategoria = (index: number, field: "nome" | "casos" | "totais", val: string) => {
    const updated = [...categorias];
    updated[index][field] = val;
    setCategorias(updated);
  };

  const calcular = async (e: React.FormEvent) => {
    e.preventDefault();
    const casos = categorias.map((c) => parseInt(c.casos) || 0);
    const totais = categorias.map((c) => parseInt(c.totais) || 0);

    try {
      const res = await invoke<ResultadoTendencia>("calcular_tendencia_cochran_armitage", {
        casos,
        totais,
        escores: null,
      });
      setResultado(res);
      showMsg("success", "Teste de tendência linear Cochran-Armitage concluído.");
    } catch (err) {
      showMsg("error", "Erro ao executar CA: " + String(err));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-lg font-bold">Tendência Linear de Cochran-Armitage</h3>
            <p className="text-xs text-slate-500 mt-0.5">Analise o crescimento ou decrescimento de proporções ordinais.</p>
          </div>
          <button
            type="button"
            onClick={addCategoria}
            className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer"
          >
            <Plus className="h-3 w-3" />
            <span>Adicionar Grupo</span>
          </button>
        </div>

        <form onSubmit={calcular} className="space-y-6">
          <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1 no-scrollbar">
            {categorias.map((c, index) => (
              <div key={index} className="flex items-center gap-3 p-3 bg-slate-950/60 border border-slate-800 rounded-xl animate-fade-in">
                <input
                  type="text"
                  value={c.nome}
                  onChange={(e) => updateCategoria(index, "nome", e.target.value)}
                  placeholder="Nome do grupo"
                  className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 outline-none"
                />
                <div className="w-24">
                  <input
                    type="number"
                    value={c.casos}
                    onChange={(e) => updateCategoria(index, "casos", e.target.value)}
                    placeholder="Casos+"
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-center outline-none"
                  />
                </div>
                <div className="w-24">
                  <input
                    type="number"
                    value={c.totais}
                    onChange={(e) => updateCategoria(index, "totais", e.target.value)}
                    placeholder="Total"
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-center outline-none"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removeCategoria(index)}
                  className="p-1 text-slate-500 hover:text-red-400 hover:bg-red-950/20 rounded transition-colors cursor-pointer"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all cursor-pointer active:scale-98"
          >
            <span>Executar Cochran-Armitage</span>
          </button>
        </form>
      </div>

      {/* Resultados */}
      <div className="bg-slate-900/30 border border-slate-850 p-6 rounded-2xl">
        <h4 className="font-bold text-sm text-indigo-400 uppercase tracking-widest block border-b border-slate-850 pb-2">Resultado da Tendência</h4>

        {resultado ? (
          <div className="space-y-4 text-sm mt-6 animate-fade-in">
            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Qui-Quadrado de Tendência</span>
              <span className="font-mono font-bold text-slate-100">{resultado.qui_quadrado.toFixed(4)}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">p-valor</span>
              <span className="font-mono font-bold text-indigo-400">{resultado.p_valor.toExponential(4)}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Direção da Tendência</span>
              <span className={`px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wider ${
                resultado.direcao === "crescente" ? "bg-emerald-950 text-emerald-400 border border-emerald-800/30" : resultado.direcao === "decrescente" ? "bg-red-950 text-red-400 border border-red-800/30" : "bg-slate-950 text-slate-400 border border-slate-800/50"
              }`}>
                {resultado.direcao}
              </span>
            </div>

            <div className="py-2 border-b border-slate-900">
              <span className="text-slate-400 block mb-2">Proporções por Categoria</span>
              <div className="space-y-1 bg-slate-950 border border-slate-800 p-3 rounded-lg font-mono text-xs text-slate-300">
                {resultado.proporcoes.map((p: number, idx: number) => (
                  <div key={idx} className="flex justify-between">
                    <span>{categorias[idx]?.nome || `Grupo ${idx + 1}`}:</span>
                    <span className="font-bold">{(p * 100).toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500 py-12 text-center">Insira pelo menos 2 categorias e execute para receber os coeficientes estatísticos.</p>
        )}
      </div>
    </div>
  );
}

// ───────────────── Sub-Painel: Mantel-Haenszel Calculator ─────────────────

function MantelHaenszelCalculator({ showMsg }: { showMsg: (type: "success" | "error" | "warning", msg: string) => void }) {
  const [estratos, setEstratos] = useState<Array<{ a: string; b: string; c: string; d: string }>>([
    { a: "10", b: "5", c: "2", d: "8" },
    { a: "12", b: "4", c: "3", d: "9" },
  ]);
  const [resultado, setResultado] = useState<ResultadoMantelHaenszel | null>(null);

  const addEstrato = () => {
    setEstratos([...estratos, { a: "0", b: "0", c: "0", d: "0" }]);
  };

  const removeEstrato = (index: number) => {
    setEstratos(estratos.filter((_, i) => i !== index));
  };

  const updateEstrato = (index: number, field: "a" | "b" | "c" | "d", val: string) => {
    const updated = [...estratos];
    updated[index][field] = val;
    setEstratos(updated);
  };

  const calcular = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = estratos.map((e) => [
      parseInt(e.a) || 0,
      parseInt(e.b) || 0,
      parseInt(e.c) || 0,
      parseInt(e.d) || 0,
    ]);

    try {
      const res = await invoke<ResultadoMantelHaenszel>("calcular_mantel_haenszel", { estratos: payload });
      setResultado(res);
      showMsg("success", "Homogeneidade de Mantel-Haenszel e Breslow-Day calculadas.");
    } catch (err) {
      showMsg("error", "Erro ao executar Mantel-Haenszel: " + String(err));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-lg font-bold">Estratificação de Mantel-Haenszel</h3>
            <p className="text-xs text-slate-500 mt-0.5">Analise tabelas 2x2 pareadas ajustando por fatores de confusão.</p>
          </div>
          <button
            type="button"
            onClick={addEstrato}
            className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-semibold cursor-pointer"
          >
            <Plus className="h-3 w-3" />
            <span>Adicionar Estrato</span>
          </button>
        </div>

        <form onSubmit={calcular} className="space-y-6">
          <div className="space-y-4 max-h-[40vh] overflow-y-auto pr-1 no-scrollbar">
            {estratos.map((est, index) => (
              <div key={index} className="p-4 bg-slate-950/65 border border-slate-800 rounded-xl space-y-2 animate-fade-in">
                <div className="flex justify-between items-center border-b border-slate-900 pb-1.5 mb-2">
                  <span className="text-xs font-bold text-indigo-400">Estrato {index + 1}</span>
                  <button
                    type="button"
                    onClick={() => removeEstrato(index)}
                    className="text-xs text-red-500 hover:text-red-400 font-semibold cursor-pointer"
                  >
                    Excluir
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-[10px] font-semibold text-slate-400">
                  <div>Exposta+/Doença+ (a)</div>
                  <div>Exposta+/Doença- (b)</div>
                  <div>Exposta-/Doença+ (c)</div>
                  <div>Exposta-/Doença- (d)</div>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <input
                    type="number"
                    value={est.a}
                    onChange={(e) => updateEstrato(index, "a", e.target.value)}
                    className="bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-center text-xs outline-none"
                  />
                  <input
                    type="number"
                    value={est.b}
                    onChange={(e) => updateEstrato(index, "b", e.target.value)}
                    className="bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-center text-xs outline-none"
                  />
                  <input
                    type="number"
                    value={est.c}
                    onChange={(e) => updateEstrato(index, "c", e.target.value)}
                    className="bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-center text-xs outline-none"
                  />
                  <input
                    type="number"
                    value={est.d}
                    onChange={(e) => updateEstrato(index, "d", e.target.value)}
                    className="bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-center text-xs outline-none"
                  />
                </div>
              </div>
            ))}
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition-all cursor-pointer active:scale-98"
          >
            <span>Executar Mantel-Haenszel</span>
          </button>
        </form>
      </div>

      {/* Resultados */}
      <div className="bg-slate-900/30 border border-slate-850 p-6 rounded-2xl">
        <h4 className="font-bold text-sm text-indigo-400 uppercase tracking-widest block border-b border-slate-850 pb-2">Resultado da Análise Ajustada</h4>

        {resultado ? (
          <div className="space-y-4 text-sm mt-6 animate-fade-in">
            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Odds Ratio MH Ajustado</span>
              <div className="text-right">
                <span className="font-mono font-bold text-slate-100">{resultado.odds_ratio_mh.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono block">IC 95%: [{resultado.odds_ratio_mh_ic[0].toFixed(3)} - {resultado.odds_ratio_mh_ic[1].toFixed(3)}]</span>
              </div>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">p-valor de Associação (MH)</span>
              <span className="font-mono font-bold text-slate-200">{resultado.p_valor_mh.toExponential(4)}</span>
            </div>

            <div className="flex items-center justify-between py-2 border-b border-slate-900">
              <span className="text-slate-400">Teste de Breslow-Day (Homogeneidade)</span>
              <div className="text-right">
                <span className="font-mono font-bold block text-slate-100">Qui² = {resultado.chi2_homogeneidade.toFixed(4)}</span>
                <span className="text-xs text-slate-500 font-mono block">p-valor: {resultado.p_valor_homogeneidade.toFixed(5)}</span>
              </div>
            </div>
            
            <p className="text-[10px] text-slate-500 leading-relaxed">
              O teste de Breslow-Day avalia se a associação OR é homogênea entre os estratos. Um p-valor &lt; 0.05 sugere que a OR varia significativamente entre os estratos.
            </p>
          </div>
        ) : (
          <p className="text-xs text-slate-500 py-12 text-center">Preencha os estratos e execute para obter o laudo estatístico.</p>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────── PAINEL DE AUDITORIA ────────────────────────────

interface AuditPanelProps {
  showMsg: (type: "success" | "error" | "warning", msg: string) => void;
}

function AuditPanel({ showMsg }: AuditPanelProps) {
  const [logs, setLogs] = useState<EntradaAuditoria[]>([]);
  const [loading, setLoading] = useState(true);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [executingCheck, setExecutingCheck] = useState(false);

  useEffect(() => {
    carregarAuditoria();
  }, []);

  const carregarAuditoria = async () => {
    setLoading(true);
    try {
      const list = await invoke<EntradaAuditoria[]>("listar_auditoria", { limite: 50 });
      setLogs(list);
    } catch (e) {
      showMsg("error", "Erro ao carregar auditoria: " + String(e));
    } finally {
      setLoading(false);
    }
  };

  const addConsoleLog = (line: string) => {
    setConsoleOutput((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${line}`]);
  };

  const executarIntegridadeCadeia = async () => {
    setExecutingCheck(true);
    setConsoleOutput([]);
    addConsoleLog("Iniciando verificação de integridade criptográfica da cadeia...");
    try {
      const failures = await invoke<InconsistenciaAuditoria[]>("verificar_integridade");
      if (failures.length === 0) {
        addConsoleLog("SUCESSO: A cadeia hash SHA-256 está perfeitamente consistente.");
        addConsoleLog("Nenhuma alteração direta ou deleção física foi detectada.");
        showMsg("success", "Cadeia de auditoria verificada com sucesso.");
      } else {
        failures.forEach((f) => {
          addConsoleLog(`FALHA: Quebra de integridade na entrada #${f.id_entrada}`);
          addConsoleLog(`Motivo: ${f.motivo}`);
          addConsoleLog(`Hash esperado: ${f.hash_esperado}`);
          addConsoleLog(`Hash encontrado: ${f.hash_encontrado}`);
        });
        showMsg("error", "A integridade da cadeia de auditoria foi violada!");
      }
    } catch (e) {
      addConsoleLog("ERRO: Falha ao rodar verificação: " + String(e));
    } finally {
      setExecutingCheck(false);
    }
  };

  const executarIntegridadeDados = async () => {
    setExecutingCheck(true);
    setConsoleOutput([]);
    addConsoleLog("Iniciando auditoria semântica cruzada (Estado vs Snapshots)...");
    try {
      const failures = await invoke<InconsistenciaDados[]>("verificar_integridade_dados");
      if (failures.length === 0) {
        addConsoleLog("SUCESSO: A integridade semântica dos pacientes coincide 100% com os hashes auditados.");
        showMsg("success", "Semântica dos dados validada com sucesso.");
      } else {
        failures.forEach((f) => {
          addConsoleLog(`INCONSISTÊNCIA DETECTADA: Paciente id=${f.entidade_id}`);
          addConsoleLog(`Problema: ${f.motivo}`);
        });
        showMsg("error", "Foram encontradas inconsistências na integridade dos dados!");
      }
    } catch (e) {
      addConsoleLog("ERRO: Falha ao rodar verificação: " + String(e));
    } finally {
      setExecutingCheck(false);
    }
  };

  const executarDiagnosticoFisico = async () => {
    setExecutingCheck(true);
    setConsoleOutput([]);
    addConsoleLog("Iniciando diagnóstico físico do banco SQLite (PRAGMA integrity_check)...");
    try {
      const res = await invoke<{ status: string; mensagem: string }>("diagnosticar_integridade_fisica");
      addConsoleLog(`Status físico: ${res.status.toUpperCase()}`);
      addConsoleLog(`Detalhes: ${res.mensagem}`);
      if (res.status === "ok") {
        showMsg("success", "Estrutura do banco de dados OK.");
      } else {
        showMsg("error", "O banco de dados apresenta corrupção física!");
      }
    } catch (e) {
      addConsoleLog("ERRO: Falha ao diagnosticar: " + String(e));
    } finally {
      setExecutingCheck(false);
    }
  };

  const criarBackupManual = async () => {
    setExecutingCheck(true);
    setConsoleOutput([]);
    addConsoleLog("Iniciando procedimento de backup online...");
    try {
      const res = await invoke<{ caminho: string; timestamp: string; removidos: string[] }>("realizar_backup", { maxBackups: 5 });
      addConsoleLog(`Backup criado em: ${res.caminho}`);
      if (res.removidos.length > 0) {
        addConsoleLog("Rotacionando backups antigos. Removidos:");
        res.removidos.forEach((path) => addConsoleLog(` - ${path}`));
      }
      showMsg("success", "Backup gerado com sucesso.");
    } catch (e) {
      addConsoleLog("ERRO: Falha ao realizar backup: " + String(e));
    } finally {
      setExecutingCheck(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Panel */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight">Segurança e Auditoria</h2>
          <p className="text-sm text-slate-400 mt-1">Cadeia de custódia verificável para transações médicas.</p>
        </div>
      </div>

      {/* Ações de Segurança */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <button
          onClick={executarIntegridadeCadeia}
          disabled={executingCheck}
          className="flex flex-col items-center justify-center p-4 bg-slate-900 border border-slate-800 rounded-xl hover:bg-slate-850 hover:border-slate-700 transition-all gap-2 text-center text-xs font-semibold hover:shadow-lg disabled:opacity-50 cursor-pointer"
        >
          <ShieldCheck className="h-6 w-6 text-indigo-400" />
          <span>Verificar Cadeia Hash</span>
        </button>

        <button
          onClick={executarIntegridadeDados}
          disabled={executingCheck}
          className="flex flex-col items-center justify-center p-4 bg-slate-900 border border-slate-800 rounded-xl hover:bg-slate-850 hover:border-slate-700 transition-all gap-2 text-center text-xs font-semibold hover:shadow-lg disabled:opacity-50 cursor-pointer"
        >
          <Sliders className="h-6 w-6 text-indigo-400" />
          <span>Audit Semântico</span>
        </button>

        <button
          onClick={executarDiagnosticoFisico}
          disabled={executingCheck}
          className="flex flex-col items-center justify-center p-4 bg-slate-900 border border-slate-800 rounded-xl hover:bg-slate-850 hover:border-slate-700 transition-all gap-2 text-center text-xs font-semibold hover:shadow-lg disabled:opacity-50 cursor-pointer"
        >
          <Database className="h-6 w-6 text-indigo-400" />
          <span>Diagnóstico Físico</span>
        </button>

        <button
          onClick={criarBackupManual}
          disabled={executingCheck}
          className="flex flex-col items-center justify-center p-4 bg-slate-900 border border-slate-800 rounded-xl hover:bg-slate-850 hover:border-slate-700 transition-all gap-2 text-center text-xs font-semibold hover:shadow-lg disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className="h-6 w-6 text-indigo-400" />
          <span>Backup Online</span>
        </button>
      </div>

      {/* Console Output */}
      {consoleOutput.length > 0 && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-1 text-slate-300 max-h-48 overflow-y-auto no-scrollbar shadow-inner">
          <span className="text-[10px] text-slate-500 font-bold block uppercase tracking-wider mb-2">Painel de Diagnóstico</span>
          {consoleOutput.map((line, idx) => (
            <div key={idx} className={line.includes("ERRO") || line.includes("FALHA") ? "text-red-400" : line.includes("SUCESSO") ? "text-emerald-400" : ""}>
              {line}
            </div>
          ))}
        </div>
      )}

      {/* Logs Table */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold">Últimos 50 Logs de Auditoria</h3>
        {loading ? (
          <RefreshCw className="h-8 w-8 animate-spin text-indigo-500 mx-auto" />
        ) : logs.length === 0 ? (
          <div className="p-6 border border-dashed border-slate-800 text-center text-slate-500 rounded-xl">
            Nenhuma operação auditada até o momento.
          </div>
        ) : (
          <div className="border border-slate-800/80 rounded-xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto max-h-[50vh] no-scrollbar">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-slate-800 text-xs font-semibold text-slate-400 bg-slate-950/40">
                    <th className="p-3">ID</th>
                    <th className="p-3">Data/Hora (UTC)</th>
                    <th className="p-3">Usuário</th>
                    <th className="p-3">Ação</th>
                    <th className="p-3">Entidade</th>
                    <th className="p-3">Ref ID</th>
                    <th className="p-3">Assinatura SHA-256 (Hash)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-xs text-slate-200 font-mono">
                  {logs.map((log) => {
                    return (
                      <tr key={log.id} className="hover:bg-slate-900/20 transition-colors">
                        <td className="p-3 font-bold text-slate-500">{log.id}</td>
                        <td className="p-3 text-slate-400">{log.timestamp}</td>
                        <td className="p-3 font-bold">{log.usuario}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            log.acao === "cadastrar"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800/20"
                              : log.acao === "editar"
                              ? "bg-indigo-950 text-indigo-400 border border-indigo-800/20"
                              : "bg-red-950 text-red-400 border border-red-800/20"
                          }`}>
                            {log.acao}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400">{log.entidade}</td>
                        <td className="p-3 text-slate-400">{log.entidade_id || "-"}</td>
                        <td className="p-3 text-slate-500 truncate max-w-xs" title={log.hash_atual}>
                          {log.hash_atual.substring(0, 16)}...
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
