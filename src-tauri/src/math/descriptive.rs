use crate::db::Paciente;
use crate::math::wilson::wilson_ci;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EstatDescritiva {
    pub n: usize,
    pub media: f64,
    pub mediana: f64,
    pub desvio_padrao: f64,
    pub q1: f64,
    pub q3: f64,
    pub minimo: f64,
    pub maximo: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ItemFrequencia {
    pub valor: String,
    pub contagem: usize,
    pub percentual: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Prevalencia {
    pub n_casos: usize,
    pub n_total: usize,
    pub taxa: f64,
    pub ic_inferior: f64,
    pub ic_superior: f64,
}

fn percentile_inclusive(sorted_vals: &[f64], p: f64) -> f64 {
    let n = sorted_vals.len();
    if n == 0 {
        return 0.0;
    }
    if n == 1 {
        return sorted_vals[0];
    }
    let idx = p * (n - 1) as f64;
    let idx_floor = idx.floor() as usize;
    let idx_ceil = (idx_floor + 1).min(n - 1);
    let g = idx - idx_floor as f64;
    (1.0 - g) * sorted_vals[idx_floor] + g * sorted_vals[idx_ceil]
}

pub fn descritivas(valores: &[f64]) -> Result<EstatDescritiva, String> {
    let n = valores.len();
    if n == 0 {
        return Err("sequência vazia: impossível calcular descritivas".to_string());
    }

    let mut ordenados = valores.to_vec();
    ordenados.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let min_val = ordenados[0];
    let max_val = ordenados[n - 1];
    let media = valores.iter().sum::<f64>() / n as f64;

    if n == 1 {
        return Ok(EstatDescritiva {
            n: 1,
            media,
            mediana: min_val,
            desvio_padrao: 0.0,
            q1: min_val,
            q3: min_val,
            minimo: min_val,
            maximo: min_val,
        });
    }

    let mediana = percentile_inclusive(&ordenados, 0.50);
    let q1 = percentile_inclusive(&ordenados, 0.25);
    let q3 = percentile_inclusive(&ordenados, 0.75);

    let variance = valores.iter().map(|&x| (x - media).powi(2)).sum::<f64>() / (n - 1) as f64;
    let desvio_padrao = variance.sqrt();

    Ok(EstatDescritiva {
        n,
        media,
        mediana,
        desvio_padrao,
        q1,
        q3,
        minimo: min_val,
        maximo: max_val,
    })
}

pub fn prevalencia_polipo(pacientes: &[Paciente]) -> Result<Prevalencia, String> {
    if pacientes.is_empty() {
        return Err("lista de pacientes vazia".to_string());
    }
    let n_total = pacientes.len();
    let n_casos = pacientes.iter().filter(|p| p.polipo > 0).count();
    let taxa = n_casos as f64 / n_total as f64;
    let (ic_inferior, ic_superior) = wilson_ci(n_casos, n_total, 0.05);

    Ok(Prevalencia {
        n_casos,
        n_total,
        taxa,
        ic_inferior,
        ic_superior,
    })
}

pub fn obter_campo_paciente_valores(p: &Paciente, campo: &str) -> Vec<String> {
    match campo {
        "sexo" => vec![p.sexo.clone()],
        "polipo" => vec![p.polipo.to_string()],
        "indicacao_exame" => vec![p.indicacao_exame.clone()],
        "examinador" => vec![p.examinador.clone().unwrap_or_else(|| "Sem examinador".to_string())],
        "comorbidades" => p.comorbidades.clone(),
        "sintomas" => p.sintomas.clone(),
        _ => vec![],
    }
}

pub fn frequencias(pacientes: &[Paciente], campo: &str) -> Vec<ItemFrequencia> {
    if pacientes.is_empty() {
        return Vec::new();
    }

    let mut contagem: HashMap<String, usize> = HashMap::new();
    for p in pacientes {
        let valores = obter_campo_paciente_valores(p, campo);
        for val in valores {
            *contagem.entry(val).or_default() += 1;
        }
    }

    let total: usize = contagem.values().sum();
    let mut items: Vec<ItemFrequencia> = contagem
        .into_iter()
        .map(|(valor, contagem)| ItemFrequencia {
            valor,
            contagem,
            percentual: if total > 0 { (contagem as f64 / total as f64) * 100.0 } else { 0.0 },
        })
        .collect();

    // Ordena decrescente por contagem, e secundariamente alfabético
    items.sort_by(|a, b| {
        let count_cmp = b.contagem.cmp(&a.contagem);
        if count_cmp == std::cmp::Ordering::Equal {
            a.valor.cmp(&b.valor)
        } else {
            count_cmp
        }
    });

    items
}

pub fn tabular_cruzado(
    pacientes: &[Paciente],
    campo_linha: &str,
    campo_coluna: &str,
) -> HashMap<String, HashMap<String, usize>> {
    let mut resultado: HashMap<String, HashMap<String, usize>> = HashMap::new();

    for p in pacientes {
        let linhas = obter_campo_paciente_valores(p, campo_linha);
        let colunas = obter_campo_paciente_valores(p, campo_coluna);
        for lin in &linhas {
            for col in &colunas {
                *resultado.entry(lin.clone()).or_default().entry(col.clone()).or_default() += 1;
            }
        }
    }

    resultado
}

pub fn estratificar(
    pacientes: &[Paciente],
    campo_grupo: &str,
    campo_valor: &str,
) -> HashMap<String, EstatDescritiva> {
    let mut grupos: HashMap<String, Vec<f64>> = HashMap::new();

    for p in pacientes {
        let chaves = obter_campo_paciente_valores(p, campo_grupo);
        if chaves.is_empty() {
            continue;
        }
        let chave = chaves[0].clone(); // usa o primeiro valor como chave de grupo

        let val_opt = match campo_valor {
            "idade" => Some(p.idade as f64),
            "polipo" => Some(p.polipo as f64),
            _ => None,
        };

        if let Some(val) = val_opt {
            grupos.entry(chave).or_default().push(val);
        }
    }

    let mut resultado = HashMap::new();
    for (chave, vals) in grupos {
        if !vals.is_empty() {
            if let Ok(est) = descritivas(&vals) {
                resultado.insert(chave, est);
            }
        }
    }

    resultado
}
