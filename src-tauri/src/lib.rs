pub mod crypto;
pub mod db;
pub mod math;
pub mod commands;

use db::BancoDados;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let app_data_dir = app.path().app_data_dir().expect("failed to get app data dir");
            std::fs::create_dir_all(&app_data_dir).expect("failed to create app data dir");
            let db_path = app_data_dir.join("gastroepi.db");
            let db_path_str = db_path.to_str().expect("invalid db path");
            
            let db = BancoDados::new(db_path_str);
            db.criar().expect("failed to initialize database");
            
            // Realizar backup preventivo no boot
            let _ = db.realizar_backup(5); // Mantém no máximo 5 backups rotacionados
            
            app.manage(commands::DbState(std::sync::Mutex::new(db)));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::tem_senha_configurada,
            commands::configurar_senha,
            commands::desbloquear,
            commands::desbloquear_com_chave,
            commands::esta_desbloqueado,
            commands::obter_nome_usuario,
            commands::definir_nome_usuario,
            commands::listar_pacientes,
            commands::buscar_paciente,
            commands::buscar_paciente_por_prontuario,
            commands::buscar_paciente_por_termo,
            commands::cadastrar_paciente,
            commands::editar_paciente,
            commands::excluir_paciente,
            commands::listar_comorbidades_catalogo,
            commands::adicionar_comorbidade_catalogo,
            commands::listar_sintomas_catalogo,
            commands::adicionar_sintoma_catalogo,
            commands::listar_auditoria,
            commands::verificar_integridade,
            commands::verificar_integridade_dados,
            commands::diagnosticar_integridade_fisica,
            commands::realizar_backup,
            commands::calcular_tabela_2x2,
            commands::calcular_teste_diagnostico,
            commands::calcular_amostra_survey,
            commands::calcular_amostra_comparativa,
            commands::calcular_tendencia_cochran_armitage,
            commands::calcular_mantel_haenszel,
            commands::calcular_qui_quadrado_geral,
            commands::obter_indicadores_qualidade,
            commands::obter_frequencias,
            commands::obter_estratificacao,
            commands::obter_prevalencia_polipo,
            commands::exportar_pacientes_csv
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
