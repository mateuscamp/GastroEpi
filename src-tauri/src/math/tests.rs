#[cfg(test)]
mod tests {
    use crate::math::wilson::wilson_ci;
    use crate::math::cochran_armitage::tendencia_cochran_armitage;
    use crate::math::fleiss::{amostra_survey, amostra_comparativa};
    use crate::math::contingency::{tabela_2x2, analise_teste_diagnostico, mantel_haenszel};
    use crate::math::descriptive::descritivas;
    use proptest::prelude::*;

    #[test]
    fn test_wilson_ci_limites() {
        // Casos extremos
        let (low, up) = wilson_ci(0, 10, 0.05);
        assert_eq!(low, 0.0);
        assert!(up > 0.0 && up < 1.0);

        let (low, up) = wilson_ci(10, 10, 0.05);
        assert!(low > 0.0 && low < 1.0);
        assert_eq!(up, 1.0);

        let (low, up) = wilson_ci(5, 10, 0.05);
        assert!(low > 0.0 && low < 0.5);
        assert!(up > 0.5 && up < 1.0);
        assert!(low < up);
    }

    #[test]
    fn test_cochran_armitage_tendencia() {
        let casos = vec![0, 2, 4, 8];
        let totais = vec![10, 10, 10, 10];
        let res = tendencia_cochran_armitage(&casos, &totais, None).unwrap();
        assert!(res.qui_quadrado > 0.0);
        assert!(res.p_valor < 0.05); // Deve ser estatisticamente significante
        assert_eq!(res.direcao, "crescente");
    }

    #[test]
    fn test_fleiss_sample_size() {
        let survey_res = amostra_survey(Some(10000), 0.5, 0.05, 0.95).unwrap();
        assert!(survey_res.tamanho_amostra > 0);
        assert!(survey_res.tamanho_amostra < 10000);

        let comparative_res = amostra_comparativa(0.80, 0.95, 1.0, 0.10, 0.25).unwrap();
        assert!(comparative_res.amostra_grupo1 > 0);
        assert!(comparative_res.amostra_grupo2 > 0);
        assert_eq!(comparative_res.amostra_total, comparative_res.amostra_grupo1 + comparative_res.amostra_grupo2);
    }

    #[test]
    fn test_contingency_2x2() {
        let res = tabela_2x2(10, 5, 2, 8).unwrap();
        assert!(res.odds_ratio > 1.0);
        assert!(res.p_valor_pearson > 0.0);
        assert!(res.p_valor_fisher > 0.0);
    }

    #[test]
    fn test_diagnostic_test() {
        let res = analise_teste_diagnostico(80, 10, 20, 90, 0.05).unwrap();
        assert!((res.sensibilidade - 0.80).abs() < 1e-9);
        assert!((res.especificidade - 0.90).abs() < 1e-9);
        assert!(res.sensibilidade_ic.0 < res.sensibilidade);
        assert!(res.sensibilidade_ic.1 > res.sensibilidade);
    }

    #[test]
    fn test_mantel_haenszel() {
        let estratos = vec![
            (10, 5, 2, 8),
            (12, 4, 3, 9),
        ];
        let res = mantel_haenszel(&estratos).unwrap();
        assert!(res.odds_ratio_mh > 1.0);
        assert!(res.p_valor_mh < 0.05);
    }

    #[test]
    fn test_descritivas() {
        let valores = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let res = descritivas(&valores).unwrap();
        assert_eq!(res.n, 5);
        assert_eq!(res.media, 3.0);
        assert_eq!(res.mediana, 3.0);
        assert_eq!(res.minimo, 1.0);
        assert_eq!(res.maximo, 5.0);
        assert!(res.desvio_padrao > 0.0);
    }

    // Property-based testing com proptest
    proptest! {
        #[test]
        fn prop_wilson_ci_valid(n_casos in 0..1000usize, extra_total in 0..1000usize) {
            let n_total = n_casos + extra_total;
            if n_total > 0 {
                let (low, up) = wilson_ci(n_casos, n_total, 0.05);
                prop_assert!(low >= 0.0 && low <= 1.0);
                prop_assert!(up >= 0.0 && up <= 1.0);
                prop_assert!(low <= up);
            }
        }

        #[test]
        fn prop_cochran_armitage_no_panic(
            casos in prop::collection::vec(0..100usize, 2..10),
            totais_offset in prop::collection::vec(0..100usize, 2..10)
        ) {
            let len = casos.len().min(totais_offset.len());
            let mut casos_trunc = casos;
            casos_trunc.truncate(len);
            let mut totais = Vec::new();
            for i in 0..len {
                totais.push(casos_trunc[i] + totais_offset[i]);
            }
            // Garante que a soma total seja maior que 0
            if totais.iter().sum::<usize>() > 0 {
                let _ = tendencia_cochran_armitage(&casos_trunc, &totais, None);
            }
        }

        #[test]
        fn prop_amostra_survey_no_panic(
            pop in prop::option::of(1..1000000usize),
            p in 0.01..0.99f64,
            d in 0.01..0.99f64,
            conf in 0.90..0.99f64
        ) {
            let _ = amostra_survey(pop, p, d, conf);
        }

        #[test]
        fn prop_amostra_comparativa_no_panic(
            poder in 0.50..0.99f64,
            confianca in 0.90..0.99f64,
            razao in 0.1..10.0f64,
            p0 in 0.01..0.99f64,
            p1 in 0.01..0.99f64
        ) {
            if (p0 - p1).abs() > 1e-4 {
                let _ = amostra_comparativa(poder, confianca, razao, p0, p1);
            }
        }
    }
}
