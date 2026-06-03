use serde::{Deserialize, Serialize};
use statrs::distribution::{ChiSquared, ContinuousCDF};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoTendencia {
    pub qui_quadrado: f64,
    pub p_valor: f64,
    pub graus_liberdade: i32,
    pub escores: Vec<f64>,
    pub proporcoes: Vec<f64>,
    pub direcao: String,
}

pub fn tendencia_cochran_armitage(
    casos: &[usize],
    totais: &[usize],
    escores: Option<&[f64]>,
) -> Result<ResultadoTendencia, String> {
    let k = casos.len();
    if k != totais.len() {
        return Err("casos e totais devem ter o mesmo comprimento".to_string());
    }
    if k < 2 {
        return Err("É necessário pelo menos 2 categorias para o teste de tendência.".to_string());
    }

    for i in 0..k {
        if casos[i] > totais[i] {
            return Err(format!(
                "casos ({}) não pode exceder total ({}) no índice {}",
                casos[i], totais[i], i
            ));
        }
    }

    let escores_calc: Vec<f64> = match escores {
        Some(esc) => {
            if esc.len() != k {
                return Err("escores deve ter o mesmo comprimento que os casos e totais".to_string());
            }
            esc.to_vec()
        }
        None => (0..k).map(|idx| idx as f64).collect(),
    };

    let n_total: usize = totais.iter().sum();
    let r_total: usize = casos.iter().sum();

    if n_total == 0 {
        return Err("tabela vazia (N == 0)".to_string());
    }

    let n_f64 = n_total as f64;
    let p_barra = r_total as f64 / n_f64;

    let proporcoes: Vec<f64> = (0..k)
        .map(|i| {
            if totais[i] > 0 {
                casos[i] as f64 / totais[i] as f64
            } else {
                0.0
            }
        })
        .collect();

    if p_barra == 0.0 || p_barra == 1.0 {
        return Ok(ResultadoTendencia {
            qui_quadrado: 0.0,
            p_valor: 1.0,
            graus_liberdade: 1,
            escores: escores_calc,
            proporcoes,
            direcao: "neutra".to_string(),
        });
    }

    let u: f64 = (0..k)
        .map(|i| escores_calc[i] * (casos[i] as f64 - totais[i] as f64 * p_barra))
        .sum();

    let sum_nt: f64 = (0..k).map(|i| totais[i] as f64 * escores_calc[i]).sum();
    let sum_nt2: f64 = (0..k).map(|i| totais[i] as f64 * escores_calc[i] * escores_calc[i]).sum();

    let var_u = p_barra * (1.0 - p_barra) * (sum_nt2 - (sum_nt * sum_nt) / n_f64);

    if var_u <= 0.0 {
        return Ok(ResultadoTendencia {
            qui_quadrado: 0.0,
            p_valor: 1.0,
            graus_liberdade: 1,
            escores: escores_calc,
            proporcoes,
            direcao: "neutra".to_string(),
        });
    }

    let z = u / var_u.sqrt();
    let chi2_val = z * z;

    let chi2_dist = ChiSquared::new(1.0).map_err(|e| e.to_string())?;
    let p_val = 1.0 - chi2_dist.cdf(chi2_val);

    let direcao = if u > 0.0 {
        "crescente"
    } else if u < 0.0 {
        "decrescente"
    } else {
        "neutra"
    };

    Ok(ResultadoTendencia {
        qui_quadrado: chi2_val,
        p_valor: p_val,
        graus_liberdade: 1,
        escores: escores_calc,
        proporcoes,
        direcao: direcao.to_string(),
    })
}
