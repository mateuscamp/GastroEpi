use serde::{Deserialize, Serialize};
use statrs::distribution::{ChiSquared, ContinuousCDF};
use crate::math::wilson::{wilson_ci, lr_positivo_ci, lr_negativo_ci};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoTabela2x2 {
    pub tabela: ((usize, usize), (usize, usize)),
    pub odds_ratio: f64,
    pub odds_ratio_ic: (f64, f64),
    pub risco_relativo: f64,
    pub risco_relativo_ic: (f64, f64),
    pub chi2_pearson: f64,
    pub chi2_yates: f64,
    pub p_valor_pearson: f64,
    pub p_valor_yates: f64,
    pub p_valor_fisher: f64,
    pub n_total: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoTesteDiagnostico {
    pub sensibilidade: f64,
    pub sensibilidade_ic: (f64, f64),
    pub especificidade: f64,
    pub especificidade_ic: (f64, f64),
    pub vpp: f64,
    pub vpp_ic: (f64, f64),
    pub vpn: f64,
    pub vpn_ic: (f64, f64),
    pub lr_positivo: f64,
    pub lr_positivo_ic: (f64, f64),
    pub lr_negativo: f64,
    pub lr_negativo_ic: (f64, f64),
    pub vp: usize,
    pub fp: usize,
    pub fn_val: usize,
    pub vn: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoQuiQuadradoGeral {
    pub chi2: f64,
    pub p_valor: f64,
    pub graus_liberdade: i32,
    pub categorias_linhas: Vec<String>,
    pub categorias_colunas: Vec<String>,
    pub matriz_contingencia: Vec<Vec<usize>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoMantelHaenszel {
    pub odds_ratio_mh: f64,
    pub odds_ratio_mh_ic: (f64, f64),
    pub p_valor_mh: f64,
    pub chi2_homogeneidade: f64,
    pub p_valor_homogeneidade: f64,
    pub graus_liberdade: i32,
}

fn ln_factorial(n: usize) -> f64 {
    statrs::function::gamma::ln_gamma(n as f64 + 1.0)
}

fn ln_combination(n: usize, k: usize) -> f64 {
    if k > n {
        return f64::NEG_INFINITY;
    }
    ln_factorial(n) - ln_factorial(k) - ln_factorial(n - k)
}

pub fn fisher_exact_2x2(a: usize, b: usize, c: usize, d: usize) -> f64 {
    let n = a + b + c + d;
    if n == 0 {
        return 1.0;
    }
    let r1 = a + b;
    let r2 = c + d;
    let c1 = a + c;

    let min_x = if r1 + c1 > n { r1 + c1 - n } else { 0 };
    let max_x = r1.min(c1);

    if min_x == max_x {
        return 1.0;
    }

    let ln_denom = ln_combination(n, c1);

    let get_ln_p = |x: usize| -> f64 {
        ln_combination(r1, x) + ln_combination(r2, c1 - x) - ln_denom
    };

    let observed_ln_p = get_ln_p(a);

    let mut p_val = 0.0;
    for x in min_x..=max_x {
        let ln_p = get_ln_p(x);
        if ln_p <= observed_ln_p + 1e-9 {
            p_val += (ln_p).exp();
        }
    }

    p_val.min(1.0)
}

fn or_ci_woolf(a: usize, b: usize, c: usize, d: usize, alfa: f64) -> (f64, f64) {
    if a == 0 || b == 0 || c == 0 || d == 0 {
        return (0.0, f64::INFINITY);
    }
    let log_or = ((a * d) as f64 / (b * c) as f64).ln();
    let se = (1.0 / a as f64 + 1.0 / b as f64 + 1.0 / c as f64 + 1.0 / d as f64).sqrt();
    let n_dist = statrs::distribution::Normal::new(0.0, 1.0).unwrap();
    let z = n_dist.inverse_cdf(1.0 - alfa / 2.0);
    ((log_or - z * se).exp(), (log_or + z * se).exp())
}

fn rr_ci_log(a: usize, b: usize, c: usize, d: usize, alfa: f64) -> (f64, f64) {
    let n1 = a + b;
    let n0 = c + d;
    if n1 == 0 || n0 == 0 || a == 0 || c == 0 {
        return (0.0, f64::INFINITY);
    }
    let rr = (a as f64 / n1 as f64) / (c as f64 / n0 as f64);
    let se = (1.0 / a as f64 - 1.0 / n1 as f64 + 1.0 / c as f64 - 1.0 / n0 as f64).sqrt();
    let n_dist = statrs::distribution::Normal::new(0.0, 1.0).unwrap();
    let z = n_dist.inverse_cdf(1.0 - alfa / 2.0);
    ((rr.ln() - z * se).exp(), (rr.ln() + z * se).exp())
}

pub fn tabela_2x2(a: usize, b: usize, c: usize, d: usize) -> Result<ResultadoTabela2x2, String> {
    let n_total = a + b + c + d;
    if n_total == 0 {
        return Err("tabela vazia (n_total == 0)".to_string());
    }

    let or_val = if b * c == 0 {
        if a * d > 0 { f64::INFINITY } else { 0.0 }
    } else {
        (a * d) as f64 / (b * c) as f64
    };

    let n1 = a + b;
    let n0 = c + d;
    let rr_val = if n1 > 0 && n0 > 0 && c > 0 {
        (a as f64 / n1 as f64) / (c as f64 / n0 as f64)
    } else if n1 > 0 && (n0 == 0 || c == 0) {
        if a > 0 { f64::INFINITY } else { 0.0 }
    } else {
        0.0
    };

    let or_ic = or_ci_woolf(a, b, c, d, 0.05);
    let rr_ic = rr_ci_log(a, b, c, d, 0.05);

    let (chi2_pearson, p_valor_pearson, chi2_yates, p_valor_yates) = if n1 == 0 || n0 == 0 || (a + c) == 0 || (b + d) == 0 {
        (0.0, 1.0, 0.0, 1.0)
    } else {
        let n = n_total as f64;
        let a_f = a as f64;
        let b_f = b as f64;
        let c_f = c as f64;
        let d_f = d as f64;

        let num_pearson = n * (a_f * d_f - b_f * c_f).powi(2);
        let den = (a_f + b_f) * (c_f + d_f) * (a_f + c_f) * (b_f + d_f);
        let chi2_p = num_pearson / den;

        let num_yates = n * ((a_f * d_f - b_f * c_f).abs() - n / 2.0).powi(2);
        let chi2_y = if (a_f * d_f - b_f * c_f).abs() > n / 2.0 {
            num_yates / den
        } else {
            0.0
        };

        let chi2_dist = ChiSquared::new(1.0).map_err(|e| e.to_string())?;
        let p_p = 1.0 - chi2_dist.cdf(chi2_p);
        let p_y = 1.0 - chi2_dist.cdf(chi2_y);

        (chi2_p, p_p, chi2_y, p_y)
    };

    let p_valor_fisher = fisher_exact_2x2(a, b, c, d);

    Ok(ResultadoTabela2x2 {
        tabela: ((a, b), (c, d)),
        odds_ratio: or_val,
        odds_ratio_ic: or_ic,
        risco_relativo: rr_val,
        risco_relativo_ic: rr_ic,
        chi2_pearson,
        chi2_yates,
        p_valor_pearson,
        p_valor_yates,
        p_valor_fisher,
        n_total,
    })
}

pub fn analise_teste_diagnostico(
    vp: usize,
    fp: usize,
    fn_val: usize,
    vn: usize,
    alfa: f64,
) -> Result<ResultadoTesteDiagnostico, String> {
    let total = vp + fp + fn_val + vn;
    if total == 0 {
        return Err("tabela de contingência vazia (total == 0)".to_string());
    }

    let total_doentes = vp + fn_val;
    let total_saudaveis = fp + vn;
    let total_test_pos = vp + fp;
    let total_test_neg = fn_val + vn;

    let sens = if total_doentes > 0 { vp as f64 / total_doentes as f64 } else { 0.0 };
    let espe = if total_saudaveis > 0 { vn as f64 / total_saudaveis as f64 } else { 0.0 };
    let vpp = if total_test_pos > 0 { vp as f64 / total_test_pos as f64 } else { 0.0 };
    let vpn = if total_test_neg > 0 { vn as f64 / total_test_neg as f64 } else { 0.0 };

    let sens_ic = wilson_ci(vp, total_doentes, alfa);
    let espe_ic = wilson_ci(vn, total_saudaveis, alfa);
    let vpp_ic = wilson_ci(vp, total_test_pos, alfa);
    let vpn_ic = wilson_ci(vn, total_test_neg, alfa);

    let lr_pos = if (1.0 - espe) == 0.0 {
        if sens > 0.0 { f64::INFINITY } else { 0.0 }
    } else {
        sens / (1.0 - espe)
    };

    let lr_neg = if espe == 0.0 {
        if (1.0 - sens) > 0.0 { f64::INFINITY } else { 0.0 }
    } else {
        (1.0 - sens) / espe
    };

    let lr_pos_ic = lr_positivo_ci(vp, fp, fn_val, vn, lr_pos, alfa);
    let lr_neg_ic = lr_negativo_ci(vp, fp, fn_val, vn, lr_neg, alfa);

    Ok(ResultadoTesteDiagnostico {
        sensibilidade: sens,
        sensibilidade_ic: sens_ic,
        especificidade: espe,
        especificidade_ic: espe_ic,
        vpp,
        vpp_ic,
        vpn,
        vpn_ic,
        lr_positivo: lr_pos,
        lr_positivo_ic: lr_pos_ic,
        lr_negativo: lr_neg,
        lr_negativo_ic: lr_neg_ic,
        vp,
        fp,
        fn_val,
        vn,
    })
}

pub fn analisar_contingencia_geral(
    matriz: &[Vec<usize>],
    categorias_linhas: &[String],
    categorias_colunas: &[String],
) -> Option<ResultadoQuiQuadradoGeral> {
    let r = matriz.len();
    if r < 2 {
        return None;
    }
    let c = matriz[0].len();
    if c < 2 {
        return None;
    }

    let mut row_sums = vec![0.0; r];
    let mut col_sums = vec![0.0; c];
    let mut n = 0.0;

    for i in 0..r {
        for j in 0..c {
            let val = matriz[i][j] as f64;
            row_sums[i] += val;
            col_sums[j] += val;
            n += val;
        }
    }

    if n == 0.0 {
        return None;
    }

    for &rs in &row_sums {
        if rs == 0.0 {
            return None;
        }
    }
    for &cs in &col_sums {
        if cs == 0.0 {
            return None;
        }
    }

    let mut chi2 = 0.0;
    for i in 0..r {
        for j in 0..c {
            let o = matriz[i][j] as f64;
            let e = (row_sums[i] * col_sums[j]) / n;
            chi2 += (o - e).powi(2) / e;
        }
    }

    let dof = (r - 1) * (c - 1);
    let chi2_dist = ChiSquared::new(dof as f64).ok()?;
    let p_valor = 1.0 - chi2_dist.cdf(chi2);

    Some(ResultadoQuiQuadradoGeral {
        chi2,
        p_valor,
        graus_liberdade: dof as i32,
        categorias_linhas: categorias_linhas.to_vec(),
        categorias_colunas: categorias_colunas.to_vec(),
        matriz_contingencia: matriz.iter().map(|v| v.to_vec()).collect(),
    })
}

fn resolver_a_esperado(n1: usize, n2: usize, m1: usize, _m2: usize, theta: f64) -> f64 {
    let n = (n1 + n2) as f64;
    if n == 0.0 {
        return 0.0;
    }
    if (theta - 1.0).abs() < 1e-9 {
        return (n1 * m1) as f64 / n;
    }

    let n1_f = n1 as f64;
    let n2_f = n2 as f64;
    let m1_f = m1 as f64;

    let coef_a = 1.0 - theta;
    let coef_b = (n2_f - m1_f) + theta * (n1_f + m1_f);
    let coef_c = -theta * n1_f * m1_f;

    let delta = coef_b * coef_b - 4.0 * coef_a * coef_c;
    if delta < 0.0 {
        return (n1 * m1) as f64 / n;
    }

    let sqrt_delta = delta.sqrt();
    let r1 = (-coef_b + sqrt_delta) / (2.0 * coef_a);
    let r2 = (-coef_b - sqrt_delta) / (2.0 * coef_a);

    let min_val = 0.0f64.max((n1 as isize + m1 as isize - (n1 + n2) as isize) as f64);
    let max_val = (n1.min(m1)) as f64;

    if min_val - 1e-5 <= r1 && r1 <= max_val + 1e-5 {
        r1.max(min_val).min(max_val)
    } else {
        r2.max(min_val).min(max_val)
    }
}

pub fn mantel_haenszel(
    estratos: &[(usize, usize, usize, usize)],
) -> Result<ResultadoMantelHaenszel, String> {
    if estratos.is_empty() {
        return Err("É necessário pelo menos 1 estrato para análise.".to_string());
    }

    let mut r_sum = 0.0;
    let mut s_sum = 0.0;
    let mut sum_a_coef = 0.0;
    let mut sum_b_coef = 0.0;
    let mut sum_c_coef = 0.0;

    let mut sum_a = 0.0;
    let mut sum_e_a = 0.0;
    let mut sum_var_a = 0.0;

    for &(a, b, c, d) in estratos {
        let n = (a + b + c + d) as f64;
        if n == 0.0 {
            continue;
        }

        let a_f = a as f64;
        let b_f = b as f64;
        let c_f = c as f64;
        let d_f = d as f64;

        let r_i = (a_f * d_f) / n;
        let s_i = (b_f * c_f) / n;
        r_sum += r_i;
        s_sum += s_i;

        sum_a_coef += ((a_f + d_f) * a_f * d_f) / (n * n);
        sum_b_coef += ((a_f + d_f) * b_f * c_f + (b_f + c_f) * a_f * d_f) / (n * n);
        sum_c_coef += ((b_f + c_f) * b_f * c_f) / (n * n);

        let n1 = a + b;
        let n2 = c + d;
        let m1 = a + c;
        let m2 = b + d;

        sum_a += a_f;
        sum_e_a += (n1 * m1) as f64 / n;
        if n > 1.0 {
            sum_var_a += (n1 * n2 * m1 * m2) as f64 / (n * n * (n - 1.0));
        }
    }

    let (or_mh, or_mh_ic) = if r_sum == 0.0 && s_sum == 0.0 {
        (1.0, (1.0, 1.0))
    } else if s_sum == 0.0 {
        (f64::INFINITY, (0.0, f64::INFINITY))
    } else if r_sum == 0.0 {
        (0.0, (0.0, f64::INFINITY))
    } else {
        let or_val = r_sum / s_sum;
        let var_ln_or = (sum_a_coef / (2.0 * r_sum * r_sum))
            + (sum_b_coef / (2.0 * r_sum * s_sum))
            + (sum_c_coef / (2.0 * s_sum * s_sum));
        let sd = var_ln_or.sqrt();
        let z_crit = 1.959963984540054;
        (
            or_val,
            (
                (or_val.ln() - z_crit * sd).exp(),
                (or_val.ln() + z_crit * sd).exp(),
            ),
        )
    };

    let p_valor_mh = if sum_var_a > 0.0 {
        let chi2_mh = (sum_a - sum_e_a).powi(2) / sum_var_a;
        let chi2_dist = ChiSquared::new(1.0).map_err(|e| e.to_string())?;
        1.0 - chi2_dist.cdf(chi2_mh)
    } else {
        1.0
    };

    let k = estratos.len();
    if k < 2 {
        return Ok(ResultadoMantelHaenszel {
            odds_ratio_mh: or_mh,
            odds_ratio_mh_ic: or_mh_ic,
            p_valor_mh,
            chi2_homogeneidade: 0.0,
            p_valor_homogeneidade: 1.0,
            graus_liberdade: 0,
        });
    }

    let mut chi2_bd = 0.0;
    for &(a, b, c, d) in estratos {
        let n = a + b + c + d;
        if n == 0 {
            continue;
        }
        let n1 = a + b;
        let n2 = c + d;
        let m1 = a + c;

        let a_esp = resolver_a_esperado(n1, n2, m1, b + d, or_mh);

        let mut inv_var = 0.0;
        for val in &[a_esp, n1 as f64 - a_esp, m1 as f64 - a_esp, (n2 as isize - m1 as isize) as f64 + a_esp] {
            if *val > 1e-9 {
                inv_var += 1.0 / *val;
            } else {
                inv_var += 1e9;
            }
        }
        let var_a = if inv_var > 0.0 { 1.0 / inv_var } else { 0.0 };

        if var_a > 0.0 {
            chi2_bd += (a as f64 - a_esp).powi(2) / var_a;
        }
    }

    let chi2_dist = ChiSquared::new((k - 1) as f64).map_err(|e| e.to_string())?;
    let p_homog = 1.0 - chi2_dist.cdf(chi2_bd);

    Ok(ResultadoMantelHaenszel {
        odds_ratio_mh: or_mh,
        odds_ratio_mh_ic: or_mh_ic,
        p_valor_mh,
        chi2_homogeneidade: chi2_bd,
        p_valor_homogeneidade: p_homog,
        graus_liberdade: (k - 1) as i32,
    })
}
