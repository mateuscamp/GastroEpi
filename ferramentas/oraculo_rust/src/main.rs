//! Gera tests/fixtures/oraculo_rust_v0_1_16.json5.
//!
//! Uso (da raiz do repositório):
//!   cargo run --release --manifest-path ferramentas/oraculo_rust/Cargo.toml > tests/fixtures/oraculo_rust_v0_1_16.json5
//!
//! Saída em JSON5 porque o serde_json grava infinito e NaN como `null`, e a v0.1.16
//! devolve infinito de propósito (OR com b·c = 0, LR+ com especificidade 100%).
//! O `json.loads` do Python lê os literais `Infinity` e `NaN`.

#[path = "../../../src-tauri/src/math/mod.rs"]
mod math;
mod db;

use db::Paciente;
use math::cochran_armitage::tendencia_cochran_armitage;
use math::contingency::{
    analisar_contingencia_geral, analise_teste_diagnostico, fisher_exact_2x2, mantel_haenszel,
    tabela_2x2,
};
use math::descriptive::{descritivas, estratificar, frequencias, prevalencia_polipo, tabular_cruzado};
use math::fleiss::{amostra_comparativa, amostra_survey};
use math::quality::indicadores_por_examinador;
use math::wilson::wilson_ci;
use serde::Serialize;

#[derive(Serialize)]
struct Caso<E: Serialize, S: Serialize> {
    entrada: E,
    saida: S,
}

fn grupo<E: Serialize, S: Serialize>(nome: &str, casos: Vec<Caso<E, S>>) -> String {
    let itens: Vec<String> = casos
        .iter()
        .map(|c| json5::to_string(c).expect("caso serializável"))
        .collect();
    format!("  \"{}\": [\n    {}\n  ]", nome, itens.join(",\n    "))
}

const TABELAS_2X2: [(usize, usize, usize, usize); 8] = [
    (0, 0, 0, 0),
    (3, 1, 1, 3),
    (10, 2, 3, 15),
    (0, 5, 5, 0),
    (1, 9, 11, 3),
    (12, 5, 7, 20),
    (0, 0, 5, 5),
    (231, 32, 27, 54),
];

fn casos_contingencia() -> Vec<String> {
    let wilson = [(0, 0, 0.05), (0, 10, 0.05), (10, 10, 0.05), (5, 10, 0.05), (1, 100, 0.05),
        (37, 120, 0.05), (3, 7, 0.01), (50, 1000, 0.10)];
    let diagnostico = [(80, 10, 20, 90, 0.05), (0, 0, 0, 0, 0.05), (10, 0, 0, 10, 0.05),
        (5, 5, 5, 5, 0.05), (231, 32, 27, 54, 0.05), (0, 10, 10, 0, 0.05), (45, 15, 5, 135, 0.01)];
    vec![
        grupo("wilson_ci", wilson.iter().map(|&(k, n, a)| Caso { entrada: (k, n, a), saida: wilson_ci(k, n, a) }).collect()),
        grupo("fisher_exact_2x2", TABELAS_2X2.iter().map(|&(a, b, c, d)| Caso { entrada: (a, b, c, d), saida: fisher_exact_2x2(a, b, c, d) }).collect()),
        grupo("tabela_2x2", TABELAS_2X2.iter().map(|&(a, b, c, d)| Caso { entrada: (a, b, c, d), saida: tabela_2x2(a, b, c, d) }).collect()),
        grupo("analise_teste_diagnostico", diagnostico.iter().map(|&(vp, fp, fneg, vn, a)| Caso { entrada: (vp, fp, fneg, vn, a), saida: analise_teste_diagnostico(vp, fp, fneg, vn, a) }).collect()),
    ]
}

fn casos_amostra() -> Vec<String> {
    let survey = [(None, 0.5, 0.05, 0.95), (Some(1000), 0.5, 0.05, 0.95), (Some(100), 0.2, 0.05, 0.95),
        (None, 0.1, 0.02, 0.99), (Some(0), 0.5, 0.05, 0.95), (None, 0.5, 0.0, 0.95), (None, 1.5, 0.05, 0.95)];
    let comparativa = [(0.8, 0.95, 1.0, 0.2, 0.3), (0.9, 0.95, 2.0, 0.1, 0.2), (0.8, 0.99, 1.0, 0.05, 0.15),
        (0.8, 0.95, 1.0, 0.3, 0.3), (0.8, 0.95, 0.5, 0.4, 0.2), (1.2, 0.95, 1.0, 0.2, 0.3)];
    vec![
        grupo("amostra_survey", survey.iter().map(|&(pop, p, d, c)| Caso { entrada: (pop, p, d, c), saida: amostra_survey(pop, p, d, c) }).collect()),
        grupo("amostra_comparativa", comparativa.iter().map(|&(pw, c, r, p0, p1)| Caso { entrada: (pw, c, r, p0, p1), saida: amostra_comparativa(pw, c, r, p0, p1) }).collect()),
    ]
}

fn casos_tendencia_e_estratos() -> Vec<String> {
    let tendencia: Vec<(Vec<usize>, Vec<usize>, Option<Vec<f64>>)> = vec![
        (vec![5, 10, 15], vec![50, 50, 50], None),
        (vec![2, 4, 6, 8], vec![20, 20, 20, 20], Some(vec![1.0, 2.0, 3.0, 4.0])),
        (vec![10, 10, 10], vec![50, 50, 50], None),
        (vec![1, 2], vec![10, 10], None),
        (vec![0, 0, 0], vec![10, 10, 10], None),
        (vec![1, 2], vec![10], None),
        (vec![15, 10, 5], vec![40, 40, 40], Some(vec![0.0, 1.0, 2.0])),
    ];
    let estratos: Vec<Vec<(usize, usize, usize, usize)>> = vec![
        vec![(10, 20, 5, 30), (8, 15, 6, 25)],
        vec![],
        vec![(0, 0, 0, 0)],
        vec![(5, 5, 5, 5), (10, 2, 3, 15), (1, 9, 11, 3)],
    ];
    let matrizes: Vec<Vec<Vec<usize>>> = vec![
        vec![vec![10, 20], vec![30, 40]],
        vec![vec![5, 10, 15], vec![20, 25, 30], vec![10, 5, 1]],
        vec![vec![1]],
        vec![vec![0, 0], vec![0, 0]],
    ];
    let rotulos = |n: usize, prefixo: &str| (0..n).map(|i| format!("{prefixo}{i}")).collect::<Vec<_>>();
    vec![
        grupo("tendencia_cochran_armitage", tendencia.iter().map(|(c, t, e)| Caso { entrada: (c, t, e), saida: tendencia_cochran_armitage(c, t, e.as_deref()) }).collect()),
        grupo("mantel_haenszel", estratos.iter().map(|e| Caso { entrada: e, saida: mantel_haenszel(e) }).collect()),
        grupo("analisar_contingencia_geral", matrizes.iter().map(|m| {
            let (l, c) = (rotulos(m.len(), "L"), rotulos(m[0].len(), "C"));
            let saida = analisar_contingencia_geral(m, &l, &c);
            Caso { entrada: (m, l, c), saida }
        }).collect()),
    ]
}

/// 24 pacientes fictícios fixos. O laudo 6 diz "ausência de adenoma" de propósito:
/// a v0.1.16 conta esse exame como adenoma (busca de substring em quality.rs).
fn pacientes_ficticios() -> Vec<Paciente> {
    let laudos = [None, Some("Adenoma tubular com displasia de baixo grau"), Some("Pólipo hiperplásico"),
        Some("Adenoma tubuloviloso"), Some("Lesão serrilhada séssil"), Some("Adenocarcinoma invasivo"),
        Some("Mucosa colônica sem alterações; ausência de adenoma"), Some("adenoma viloso")];
    let examinadores = [Some("Dra. Ana"), Some("Dr. Bruno"), Some("Dra. Ana"), None, Some(""), Some("Dr. Bruno")];
    let comorbidades = [vec![], vec!["Obesidade"], vec!["Tabagismo", "Etilismo"], vec!["Diabetes Mellitus tipo 2"]];
    let sintomas = [vec![], vec!["Dor abdominal"], vec!["Hematoquezia / Sangramento retal", "Anemia ferropriva"]];
    (0..24)
        .map(|i| Paciente {
            id: Some(i as i64 + 1),
            numero_prontuario: format!("FICT-{:04}", i + 1),
            cpf: None,
            nome: format!("Paciente Ficticio {}", i + 1),
            data_exame: format!("2026-{:02}-{:02}", i % 12 + 1, i % 28 + 1),
            idade: 40 + (i as i32 * 7) % 45,
            sexo: if i % 3 == 0 { "M" } else { "F" }.to_string(),
            polipo: [0, 1, 0, 2, 0, 3, 0, 1][i % 8],
            resultado_histopatologico: laudos[i % laudos.len()].map(str::to_string),
            indicacao_exame: if i % 4 == 0 { "Diagnóstico" } else { "Rastreio" }.to_string(),
            comorbidades: comorbidades[i % comorbidades.len()].iter().map(|s| s.to_string()).collect(),
            sintomas: sintomas[i % sintomas.len()].iter().map(|s| s.to_string()).collect(),
            historico_familiar: vec![],
            examinador: examinadores[i % examinadores.len()].map(str::to_string),
        })
        .collect()
}

fn casos_do_banco() -> Vec<String> {
    let pacientes = pacientes_ficticios();
    let vazio: Vec<Paciente> = vec![];
    let campos = ["sexo", "polipo", "indicacao_exame", "examinador", "comorbidades", "sintomas", "inexistente"];
    let valores: Vec<Vec<f64>> = vec![vec![1.0, 2.0, 3.0, 4.0, 5.0], vec![], vec![7.5], vec![2.0; 4],
        vec![1.0, 100.0, 3.0, 8.0, 2.0, 9.5, 40.0]];
    let estratos = [("sexo", "idade"), ("indicacao_exame", "polipo"), ("examinador", "idade"), ("sexo", "inexistente")];
    vec![
        format!("  \"pacientes_ficticios\": {}", json5::to_string(&pacientes).expect("serializável")),
        grupo("descritivas", valores.iter().map(|v| Caso { entrada: v, saida: descritivas(v) }).collect()),
        grupo("prevalencia_polipo", vec![Caso { entrada: "pacientes_ficticios", saida: prevalencia_polipo(&pacientes) },
            Caso { entrada: "vazio", saida: prevalencia_polipo(&vazio) }]),
        grupo("frequencias", campos.iter().map(|c| Caso { entrada: c, saida: frequencias(&pacientes, c) }).collect()),
        grupo("estratificar", estratos.iter().map(|&(g, v)| Caso { entrada: (g, v), saida: estratificar(&pacientes, g, v) }).collect()),
        grupo("tabular_cruzado", vec![Caso { entrada: ("sexo", "indicacao_exame"), saida: tabular_cruzado(&pacientes, "sexo", "indicacao_exame") }]),
        grupo("indicadores_por_examinador", vec![Caso { entrada: "pacientes_ficticios", saida: indicadores_por_examinador(&pacientes) }]),
    ]
}

fn main() {
    let mut blocos = vec!["  \"versao\": \"v0.1.16\"".to_string()];
    blocos.extend(casos_contingencia());
    blocos.extend(casos_amostra());
    blocos.extend(casos_tendencia_e_estratos());
    blocos.extend(casos_do_banco());
    println!("{{\n{}\n}}", blocos.join(",\n"));
}
