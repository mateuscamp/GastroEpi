use crate::db::Paciente;
use crate::math::wilson::wilson_ci;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoIndicadorQualidade {
    pub endoscopista: String,
    pub n_exames: usize,
    pub n_polipos: usize,
    pub pdr: f64,
    pub pdr_ic: (f64, f64),
    pub n_adenomas: usize,
    pub adr: f64,
    pub adr_ic: (f64, f64),
}

pub fn indicadores_por_endoscopista(
    pacientes: &[Paciente],
) -> Vec<ResultadoIndicadorQualidade> {
    if pacientes.is_empty() {
        return Vec::new();
    }

    let mut agrupados: HashMap<String, Vec<&Paciente>> = HashMap::new();
    for p in pacientes {
        let medico = p
            .endoscopista
            .clone()
            .unwrap_or_else(|| "Sem endoscopista".to_string());
        agrupados.entry(medico).or_default().push(p);
    }

    let mut resultados: Vec<ResultadoIndicadorQualidade> = Vec::new();

    for (medico, lista) in agrupados {
        let n_exames = lista.len();
        let n_polipos = lista.iter().filter(|p| p.polipo > 0).count();
        let n_adenomas = lista
            .iter()
            .filter(|p| {
                p.resultado_histopatologico
                    .as_ref()
                    .map(|h| h.to_lowercase().contains("adenoma"))
                    .unwrap_or(false)
            })
            .count();

        let pdr = if n_exames > 0 { n_polipos as f64 / n_exames as f64 } else { 0.0 };
        let pdr_ic = wilson_ci(n_polipos, n_exames, 0.05);

        let adr = if n_exames > 0 { n_adenomas as f64 / n_exames as f64 } else { 0.0 };
        let adr_ic = wilson_ci(n_adenomas, n_exames, 0.05);

        resultados.push(ResultadoIndicadorQualidade {
            endoscopista: medico,
            n_exames,
            n_polipos,
            pdr,
            pdr_ic,
            n_adenomas,
            adr,
            adr_ic,
        });
    }

    // Ordena pelo nome do endoscopista (case insensitive / lowercase)
    resultados.sort_by(|a, b| a.endoscopista.to_lowercase().cmp(&b.endoscopista.to_lowercase()));

    resultados
}
