use statrs::distribution::{ContinuousCDF, Normal};

/// Intervalo de confiança de Wilson para uma proporção (95% por padrão se alfa = 0.05).
/// Implementa a fórmula clássica de Wilson (1927).
pub fn wilson_ci(n_casos: usize, n_total: usize, alfa: f64) -> (f64, f64) {
    if n_total == 0 {
        return (0.0, 0.0);
    }
    let p = n_casos as f64 / n_total as f64;
    let n = n_total as f64;
    
    let n_dist = Normal::new(0.0, 1.0).unwrap();
    let z = n_dist.inverse_cdf(1.0 - alfa / 2.0);
    
    let denom = 1.0 + z * z / n;
    let centro = (p + z * z / (2.0 * n)) / denom;
    let margem = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)).sqrt()) / denom;
    
    let mut lower = (centro - margem).max(0.0);
    let mut upper = (centro + margem).min(1.0);
    
    if n_casos == 0 {
        lower = 0.0;
    }
    if n_casos == n_total {
        upper = 1.0;
    }
    
    (lower, upper)
}

/// Intervalo de confiança para Razão de Verossimilhança Positiva (LR+) via método log-linear (Simel et al., 1991).
pub fn lr_positivo_ci(
    vp: usize,
    fp: usize,
    fn_val: usize,
    vn: usize,
    lr_pos: f64,
    alfa: f64,
) -> (f64, f64) {
    let total_doentes = vp + fn_val;
    let total_saudaveis = fp + vn;
    let espe = if total_saudaveis > 0 { vn as f64 / total_saudaveis as f64 } else { 0.0 };
    let um_menos_espe = 1.0 - espe;

    if vp > 0 && fp > 0 && total_doentes > 0 && total_saudaveis > 0 && um_menos_espe > 0.0 {
        let n_dist = Normal::new(0.0, 1.0).unwrap();
        let z = n_dist.inverse_cdf(1.0 - alfa / 2.0);
        let se_log_lr_pos = (1.0 / vp as f64 - 1.0 / total_doentes as f64 + 1.0 / fp as f64 - 1.0 / total_saudaveis as f64).sqrt();
        (
            lr_pos * (-z * se_log_lr_pos).exp(),
            lr_pos * (z * se_log_lr_pos).exp(),
        )
    } else {
        (0.0, f64::INFINITY)
    }
}

/// Intervalo de confiança para Razão de Verossimilhança Negativa (LR-) via método log-linear (Simel et al., 1991).
pub fn lr_negativo_ci(
    vp: usize,
    fp: usize,
    fn_val: usize,
    vn: usize,
    lr_neg: f64,
    alfa: f64,
) -> (f64, f64) {
    let total_doentes = vp + fn_val;
    let total_saudaveis = fp + vn;
    let espe = if total_saudaveis > 0 { vn as f64 / total_saudaveis as f64 } else { 0.0 };

    if fn_val > 0 && vn > 0 && total_doentes > 0 && total_saudaveis > 0 && espe > 0.0 {
        let n_dist = Normal::new(0.0, 1.0).unwrap();
        let z = n_dist.inverse_cdf(1.0 - alfa / 2.0);
        let se_log_lr_neg = (1.0 / fn_val as f64 - 1.0 / total_doentes as f64 + 1.0 / vn as f64 - 1.0 / total_saudaveis as f64).sqrt();
        (
            lr_neg * (-z * se_log_lr_neg).exp(),
            lr_neg * (z * se_log_lr_neg).exp(),
        )
    } else {
        (0.0, f64::INFINITY)
    }
}
