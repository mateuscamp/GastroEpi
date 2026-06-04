use crate::db::{
    BancoDados, Paciente, EntradaAuditoria, InconsistenciaAuditoria,
    InconsistenciaDados, DiagnosticoIntegridadeFisica, ResultadoBackup
};
use crate::math::cochran_armitage::{tendencia_cochran_armitage, ResultadoTendencia};
use crate::math::contingency::{
    tabela_2x2, analise_teste_diagnostico, mantel_haenszel, analisar_contingencia_geral,
    ResultadoTabela2x2, ResultadoTesteDiagnostico, ResultadoMantelHaenszel, ResultadoQuiQuadradoGeral
};
use crate::math::fleiss::{amostra_survey, amostra_comparativa, AmostraSurvey, AmostraEstudoComparativo};
use crate::math::descriptive::{
    frequencias, estratificar, prevalencia_polipo, ItemFrequencia, EstatDescritiva, Prevalencia
};
use crate::math::quality::{indicadores_por_examinador, ResultadoIndicadorQualidade};

use tauri::State;
use std::sync::Mutex;
use std::collections::HashMap;

pub struct DbState(pub Mutex<BancoDados>);

// ────────────── Auth Commands ──────────────

#[tauri::command]
pub fn tem_senha_configurada(state: State<'_, DbState>) -> Result<bool, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.tem_senha_configurada()
}

#[tauri::command]
pub fn configurar_senha(state: State<'_, DbState>, senha: String) -> Result<String, String> {
    let mut db = state.0.lock().map_err(|e| e.to_string())?;
    db.configurar_senha(&senha)
}

#[tauri::command]
pub fn desbloquear(state: State<'_, DbState>, senha: String) -> Result<bool, String> {
    let mut db = state.0.lock().map_err(|e| e.to_string())?;
    db.desbloquear(&senha)
}

#[tauri::command]
pub fn desbloquear_com_chave(state: State<'_, DbState>, chave: String) -> Result<bool, String> {
    let mut db = state.0.lock().map_err(|e| e.to_string())?;
    db.desbloquear_com_chave(&chave)
}

#[tauri::command]
pub fn esta_desbloqueado(state: State<'_, DbState>) -> Result<bool, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    Ok(db.esta_desbloqueado())
}

#[tauri::command]
pub fn obter_nome_usuario(state: State<'_, DbState>) -> Result<Option<String>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.obter_nome_usuario()
}

#[tauri::command]
pub fn definir_nome_usuario(state: State<'_, DbState>, nome: String) -> Result<(), String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.definir_nome_usuario(&nome)
}

// ────────────── CRUD Commands ──────────────

#[tauri::command]
pub fn listar_pacientes(state: State<'_, DbState>) -> Result<Vec<Paciente>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.listar()
}

#[tauri::command]
pub fn buscar_paciente(state: State<'_, DbState>, id: i64) -> Result<Option<Paciente>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.buscar(id)
}

#[tauri::command]
pub fn buscar_paciente_por_prontuario(state: State<'_, DbState>, prontuario: String) -> Result<Option<Paciente>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.buscar_por_prontuario(&prontuario)
}

#[tauri::command]
pub fn buscar_paciente_por_termo(state: State<'_, DbState>, termo: String) -> Result<Vec<Paciente>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.buscar_por_termo(&termo)
}

#[tauri::command]
pub fn cadastrar_paciente(
    state: State<'_, DbState>,
    usuario: String,
    paciente: Paciente,
) -> Result<i64, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.cadastrar(&usuario, &paciente)
}

#[tauri::command]
pub fn editar_paciente(
    state: State<'_, DbState>,
    usuario: String,
    paciente: Paciente,
) -> Result<(), String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.editar(&usuario, &paciente)
}

#[tauri::command]
pub fn excluir_paciente(
    state: State<'_, DbState>,
    usuario: String,
    id: i64,
) -> Result<(), String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.excluir(&usuario, id)
}

// ────────────── Catalog Commands ──────────────

#[tauri::command]
pub fn listar_comorbidades_catalogo(state: State<'_, DbState>) -> Result<Vec<String>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.listar_comorbidades_catalogo()
}

#[tauri::command]
pub fn adicionar_comorbidade_catalogo(
    state: State<'_, DbState>,
    usuario: String,
    nome: String,
) -> Result<(), String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.adicionar_comorbidade_catalogo(&usuario, &nome)
}

#[tauri::command]
pub fn listar_sintomas_catalogo(state: State<'_, DbState>) -> Result<Vec<String>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.listar_sintomas_catalogo()
}

#[tauri::command]
pub fn adicionar_sintoma_catalogo(
    state: State<'_, DbState>,
    usuario: String,
    nome: String,
) -> Result<(), String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.adicionar_sintoma_catalogo(&usuario, &nome)
}

// ────────────── Audit and Integrity Commands ──────────────

#[tauri::command]
pub fn listar_auditoria(state: State<'_, DbState>, limite: usize) -> Result<Vec<EntradaAuditoria>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.listar_auditoria(limite)
}

#[tauri::command]
pub fn verificar_integridade(state: State<'_, DbState>) -> Result<Vec<InconsistenciaAuditoria>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.verificar_integridade()
}

#[tauri::command]
pub fn verificar_integridade_dados(state: State<'_, DbState>) -> Result<Vec<InconsistenciaDados>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.verificar_integridade_dados()
}

#[tauri::command]
pub fn diagnosticar_integridade_fisica(state: State<'_, DbState>) -> Result<DiagnosticoIntegridadeFisica, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    Ok(db.diagnosticar_integridade_fisica())
}

#[tauri::command]
pub fn realizar_backup(state: State<'_, DbState>, max_backups: usize) -> Result<ResultadoBackup, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    db.realizar_backup(max_backups)
}

// ────────────── Analytics Commands (Calculators) ──────────────

#[tauri::command]
pub fn calcular_tabela_2x2(a: usize, b: usize, c: usize, d: usize) -> Result<ResultadoTabela2x2, String> {
    tabela_2x2(a, b, c, d)
}

#[tauri::command]
pub fn calcular_teste_diagnostico(
    vp: usize,
    fp: usize,
    fn_val: usize,
    vn: usize,
    alfa: f64,
) -> Result<ResultadoTesteDiagnostico, String> {
    analise_teste_diagnostico(vp, fp, fn_val, vn, alfa)
}

#[tauri::command]
pub fn calcular_amostra_survey(
    populacao: Option<usize>,
    p: f64,
    d: f64,
    confianca: f64,
) -> Result<AmostraSurvey, String> {
    amostra_survey(populacao, p, d, confianca)
}

#[tauri::command]
pub fn calcular_amostra_comparativa(
    poder: f64,
    confianca: f64,
    razao: f64,
    p0: f64,
    p1: f64,
) -> Result<AmostraEstudoComparativo, String> {
    amostra_comparativa(poder, confianca, razao, p0, p1)
}

#[tauri::command]
pub fn calcular_tendencia_cochran_armitage(
    casos: Vec<usize>,
    totais: Vec<usize>,
    escores: Option<Vec<f64>>,
) -> Result<ResultadoTendencia, String> {
    tendencia_cochran_armitage(&casos, &totais, escores.as_deref())
}

#[tauri::command]
pub fn calcular_mantel_haenszel(
    estratos: Vec<(usize, usize, usize, usize)>,
) -> Result<ResultadoMantelHaenszel, String> {
    mantel_haenszel(&estratos)
}

#[tauri::command]
pub fn calcular_qui_quadrado_geral(
    matriz: Vec<Vec<usize>>,
    linhas: Vec<String>,
    colunas: Vec<String>,
) -> Result<Option<ResultadoQuiQuadradoGeral>, String> {
    Ok(analisar_contingencia_geral(&matriz, &linhas, &colunas))
}

#[tauri::command]
pub fn obter_indicadores_qualidade(state: State<'_, DbState>) -> Result<Vec<ResultadoIndicadorQualidade>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    let pacientes = db.listar()?;
    Ok(indicadores_por_examinador(&pacientes))
}

#[tauri::command]
pub fn obter_frequencias(state: State<'_, DbState>, campo: String) -> Result<Vec<ItemFrequencia>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    let pacientes = db.listar()?;
    Ok(frequencias(&pacientes, &campo))
}

#[tauri::command]
pub fn obter_estratificacao(
    state: State<'_, DbState>,
    campo_grupo: String,
    campo_valor: String,
) -> Result<HashMap<String, EstatDescritiva>, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    let pacientes = db.listar()?;
    Ok(estratificar(&pacientes, &campo_grupo, &campo_valor))
}

#[tauri::command]
pub fn obter_prevalencia_polipo(state: State<'_, DbState>) -> Result<Prevalencia, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    let pacientes = db.listar()?;
    prevalencia_polipo(&pacientes)
}

// ────────────── Export CSV Command ──────────────

fn sanitizar_csv_cell(val: &str) -> String {
    let cleaned = val.replace(';', " ").replace('\n', " ").replace('\r', " ").trim().to_string();
    if cleaned.starts_with('=') || cleaned.starts_with('+') || cleaned.starts_with('-') || cleaned.starts_with('@') {
        format!("'{}", cleaned)
    } else {
        cleaned
    }
}

#[tauri::command]
pub fn exportar_pacientes_csv(state: State<'_, DbState>) -> Result<String, String> {
    let db = state.0.lock().map_err(|e| e.to_string())?;
    let pacientes = db.listar()?;

    // UTF-8 BOM
    let mut csv = String::from("\u{FEFF}");
    csv.push_str("Prontuário;CPF;Nome;Data do Exame;Idade;Sexo;Pólipos;Examinador;Indicação;Resultado Histopatológico\n");

    for p in pacientes {
        let prontuario = sanitizar_csv_cell(&p.numero_prontuario);
        let cpf = sanitizar_csv_cell(p.cpf.as_deref().unwrap_or(""));
        let nome = sanitizar_csv_cell(&p.nome);
        let data_exame = sanitizar_csv_cell(&p.data_exame);
        let idade = p.idade.to_string();
        let sexo = sanitizar_csv_cell(&p.sexo);
        let polipo = p.polipo.to_string();
        let examinador = sanitizar_csv_cell(p.examinador.as_deref().unwrap_or(""));
        let indicacao = sanitizar_csv_cell(&p.indicacao_exame);
        let resultado = sanitizar_csv_cell(p.resultado_histopatologico.as_deref().unwrap_or(""));

        csv.push_str(&format!(
            "{};{};{};{};{};{};{};{};{};{}\n",
            prontuario, cpf, nome, data_exame, idade, sexo, polipo, examinador, indicacao, resultado
        ));
    }

    Ok(csv)
}
