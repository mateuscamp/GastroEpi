use serde::{Deserialize, Serialize};
use statrs::distribution::{ContinuousCDF, Normal};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AmostraSurvey {
    pub tamanho_amostra: usize,
    pub populacao: Option<usize>,
    pub frequencia_esperada: f64,
    pub margem_erro: f64,
    pub nivel_confianca: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AmostraEstudoComparativo {
    pub amostra_grupo1: usize,
    pub amostra_grupo2: usize,
    pub amostra_total: usize,
    pub poder: f64,
    pub nivel_confianca: f64,
    pub razao: f64,
    pub p0: f64,
    pub p1: f64,
}

pub fn amostra_survey(
    populacao: Option<usize>,
    p: f64,
    d: f64,
    confianca: f64,
) -> Result<AmostraSurvey, String> {
    if let Some(n) = populacao {
        if n == 0 {
            return Err("população N deve ser > 0".to_string());
        }
    }
    if !(0.0 < p && p < 1.0) {
        return Err(format!("frequência p deve estar entre 0 e 1 (exclusivo): {}", p));
    }
    if !(0.0 < d && d < 1.0) {
        return Err(format!("margem de erro d deve estar entre 0 e 1 (exclusivo): {}", d));
    }
    if !(0.0 < confianca && confianca < 1.0) {
        return Err(format!("confiança deve estar entre 0 e 1 (exclusivo): {}", confianca));
    }

    let alfa = 1.0 - confianca;
    let n_dist = Normal::new(0.0, 1.0).map_err(|e| e.to_string())?;
    let z = n_dist.inverse_cdf(1.0 - alfa / 2.0);

    // n0 para população infinita
    let n0 = (z * z * p * (1.0 - p)) / (d * d);

    let tamanho = match populacao {
        None => n0.ceil() as usize,
        Some(n_val) => {
            let n = n0 / (1.0 + (n0 - 1.0) / n_val as f64);
            let mut t = n.ceil() as usize;
            if t > n_val {
                t = n_val;
            }
            t
        }
    };

    Ok(AmostraSurvey {
        tamanho_amostra: tamanho,
        populacao,
        frequencia_esperada: p,
        margem_erro: d,
        nivel_confianca: confianca,
    })
}

pub fn amostra_comparativa(
    poder: f64,
    confianca: f64,
    razao: f64,
    p0: f64,
    p1: f64,
) -> Result<AmostraEstudoComparativo, String> {
    if !(0.0 < poder && poder < 1.0) {
        return Err(format!("poder deve estar entre 0 e 1 (exclusivo): {}", poder));
    }
    if !(0.0 < confianca && confianca < 1.0) {
        return Err(format!("confiança deve estar entre 0 e 1 (exclusivo): {}", confianca));
    }
    if razao <= 0.0 {
        return Err(format!("razão r deve ser > 0: {}", razao));
    }
    if !(0.0 < p0 && p0 < 1.0) {
        return Err(format!("p0 deve estar entre 0 e 1 (exclusivo): {}", p0));
    }
    if !(0.0 < p1 && p1 < 1.0) {
        return Err(format!("p1 deve estar entre 0 e 1 (exclusivo): {}", p1));
    }
    if (p0 - p1).abs() < 1e-9 {
        return Err("proporções p0 e p1 não podem ser iguais (associação nula)".to_string());
    }

    let alfa = 1.0 - confianca;
    let n_dist = Normal::new(0.0, 1.0).map_err(|e| e.to_string())?;
    let z_alfa = n_dist.inverse_cdf(1.0 - alfa / 2.0);
    let z_beta = n_dist.inverse_cdf(poder); // Cauda única para o poder

    let p_barra = (p1 + razao * p0) / (1.0 + razao);
    let q_barra = 1.0 - p_barra;
    let q0 = 1.0 - p0;
    let q1 = 1.0 - p1;

    let numerador = (
        z_alfa * ((razao + 1.0) * p_barra * q_barra).sqrt()
        + z_beta * (razao * p1 * q1 + p0 * q0).sqrt()
    ).powi(2);
    let denominador = razao * (p1 - p0).powi(2);

    let n1 = numerador / denominador;
    let n0 = razao * n1;

    let n1_ceil = n1.ceil() as usize;
    let n0_ceil = n0.ceil() as usize;

    Ok(AmostraEstudoComparativo {
        amostra_grupo1: n1_ceil,
        amostra_grupo2: n0_ceil,
        amostra_total: n1_ceil + n0_ceil,
        poder,
        nivel_confianca: confianca,
        razao,
        p0,
        p1,
    })
}
