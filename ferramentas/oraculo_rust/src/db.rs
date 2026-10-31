//! Cópia fiel de `Paciente` e `HistoricoFamiliar` de src-tauri/src/db.rs (v0.1.16, linhas 35-63).
//! Existe porque `math/descriptive.rs` e `math/quality.rs` importam `crate::db::Paciente`,
//! e incluir o db.rs inteiro traria rusqlite e a cripto sem necessidade.
#![allow(dead_code)]

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoricoFamiliar {
    pub id: Option<i64>,
    pub parentesco: String,
    pub grau: i32,
    pub idade_diagnostico: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Paciente {
    pub id: Option<i64>,
    pub numero_prontuario: String,
    pub cpf: Option<String>,
    pub nome: String,
    pub data_exame: String,
    pub idade: i32,
    pub sexo: String,
    pub polipo: i32,
    pub resultado_histopatologico: Option<String>,
    pub indicacao_exame: String,
    pub comorbidades: Vec<String>,
    pub sintomas: Vec<String>,
    pub historico_familiar: Vec<HistoricoFamiliar>,
    pub examinador: Option<String>,
}
