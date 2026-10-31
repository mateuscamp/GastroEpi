# Valores de referência do R para a estatística do GastroEpi (Fase 3, Princípio IV).
#
# Uso: Rscript ferramentas/referencias_r/gerar.R <saida.json> tests/fixtures/oraculo_rust_v0_1_16.json5
# Roda no CI (job "referencias-r" do python.yml), com a versão do R fixa. O CI falha se
# a saída divergir do JSON versionado. Não editar o JSON à mão: mudar este script.
#
# Cada função do R abaixo é a implementação de referência citada nos testes. Onde o R
# base não tem a medida, usa-se o pacote indicado; onde nenhum pacote a tem, a fórmula
# publicada é recalculada aqui e a fonte vem no comentário. Sem epiR: ele depende do sf,
# que exige bibliotecas de sistema (udunits, GDAL).

suppressPackageStartupMessages({
  library(jsonlite)
  library(epitools)
  library(DescTools)
})

z_de <- function(alfa) qnorm(1 - alfa / 2)

wilson <- function(x, n, alfa) {
  # Wilson (1927) sem correção de continuidade = prop.test(correct = FALSE).
  ic <- prop.test(x, n, conf.level = 1 - alfa, correct = FALSE)$conf.int
  list(casos = x, total = n, alfa = alfa, ic = as.numeric(ic))
}

razoes_de_verossimilhanca <- function(vp, fp, fn, vn, alfa) {
  # Simel DL, Samsa GP, Matchar DB. J Clin Epidemiol 1991;44:763-770 (método log).
  z <- z_de(alfa)
  sens <- vp / (vp + fn)
  espe <- vn / (fp + vn)
  lrp <- sens / (1 - espe)
  lrn <- (1 - sens) / espe
  ep_p <- sqrt(1 / vp - 1 / (vp + fn) + 1 / fp - 1 / (fp + vn))
  ep_n <- sqrt(1 / fn - 1 / (vp + fn) + 1 / vn - 1 / (fp + vn))
  list(
    lr_positivo = lrp, lr_positivo_ic = lrp * exp(c(-z, z) * ep_p),
    lr_negativo = lrn, lr_negativo_ic = lrn * exp(c(-z, z) * ep_n)
  )
}

diagnostico <- function(vp, fp, fn, vn, alfa) {
  c(
    list(
      entrada = c(vp, fp, fn, vn), alfa = alfa,
      sensibilidade_ic = wilson(vp, vp + fn, alfa)$ic,
      especificidade_ic = wilson(vn, fp + vn, alfa)$ic,
      vpp_ic = wilson(vp, vp + fp, alfa)$ic,
      vpn_ic = wilson(vn, fn + vn, alfa)$ic
    ),
    razoes_de_verossimilhanca(vp, fp, fn, vn, alfa)
  )
}

tabela_2x2 <- function(a, b, c, d) {
  m <- matrix(c(a, c, b, d), nrow = 2)  # linhas: expostos, não expostos
  # epitools: linha 1 = não expostos (referência), coluna 2 = com o desfecho.
  epi <- rbind(c(d, c), c(b, a))
  or <- oddsratio.wald(epi)$measure[2, ]
  rr <- riskratio.wald(epi)$measure[2, ]
  pearson <- suppressWarnings(chisq.test(m, correct = FALSE))
  yates <- suppressWarnings(chisq.test(m, correct = TRUE))
  list(
    entrada = c(a, b, c, d),
    odds_ratio = unname(or[1]), odds_ratio_ic = unname(or[2:3]),
    risco_relativo = unname(rr[1]), risco_relativo_ic = unname(rr[2:3]),
    chi2_pearson = unname(pearson$statistic), p_valor_pearson = pearson$p.value,
    chi2_yates = unname(yates$statistic), p_valor_yates = yates$p.value,
    p_valor_fisher = fisher.test(m)$p.value
  )
}

fisher <- function(a, b, c, d) {
  list(entrada = c(a, b, c, d), p_valor = fisher.test(matrix(c(a, c, b, d), nrow = 2))$p.value)
}

amostra_survey <- function(populacao, p, d, confianca) {
  # Epi Info StatCalc / OpenEpi SSPropor: n = N z² p q / (d² (N − 1) + z² p q).
  z <- z_de(1 - confianca)
  n0 <- z^2 * p * (1 - p) / d^2
  n <- if (is.na(populacao)) n0 else populacao * n0 / (n0 + populacao - 1)
  list(populacao = populacao, p = p, d = d, confianca = confianca, n = n)
}

amostra_comparativa <- function(poder, confianca, razao, p0, p1) {
  # Fleiss JL, Levin B, Paik MC. Statistical Methods for Rates and Proportions, 3ª ed.,
  # 2003, eq. 4.14, sem correção de continuidade (OpenEpi SSCohort/SSCC, "Fleiss").
  za <- z_de(1 - confianca)
  zb <- qnorm(poder)
  pb <- (p1 + razao * p0) / (1 + razao)
  n1 <- (za * sqrt((razao + 1) * pb * (1 - pb)) +
    zb * sqrt(razao * p1 * (1 - p1) + p0 * (1 - p0)))^2 / (razao * (p1 - p0)^2)
  list(poder = poder, confianca = confianca, razao = razao, p0 = p0, p1 = p1,
       n1 = n1, n0 = razao * n1)
}

tendencia <- function(casos, totais, escores) {
  r <- prop.trend.test(casos, totais, score = escores)
  ca <- CochranArmitageTest(rbind(casos, totais - casos))
  list(casos = casos, totais = totais, escores = escores,
       qui_quadrado = unname(r$statistic), p_valor = r$p.value,
       desctools_z = unname(ca$statistic), desctools_p_valor = ca$p.value)
}

mantel_haenszel <- function(estratos) {
  x <- array(unlist(lapply(estratos, function(e) c(e[1], e[3], e[2], e[4]))),
             dim = c(2, 2, length(estratos)))
  mh <- mantelhaen.test(x, correct = FALSE)
  bd <- BreslowDayTest(x, correct = FALSE)
  list(estratos = estratos,
       odds_ratio = unname(mh$estimate), odds_ratio_ic = as.numeric(mh$conf.int),
       chi2 = unname(mh$statistic), p_valor = mh$p.value,
       chi2_homogeneidade = unname(bd$statistic), p_valor_homogeneidade = bd$p.value)
}

qui_quadrado_rxc <- function(linhas) {
  m <- do.call(rbind, linhas)
  r <- suppressWarnings(chisq.test(m, correct = FALSE))
  list(matriz = linhas, chi2 = unname(r$statistic), graus_liberdade = unname(r$parameter),
       p_valor = r$p.value)
}

descritivas <- function(v) {
  q <- quantile(v, c(0.25, 0.5, 0.75), type = 7, names = FALSE)
  list(valores = I(v), n = length(v), media = mean(v), mediana = q[2],
       desvio_padrao = if (length(v) > 1) sd(v) else 0, q1 = q[1], q3 = q[3],
       minimo = min(v), maximo = max(v))
}

base_do_oraculo <- function(caminho) {
  # Os 24 pacientes fictícios do oráculo v0.1.16 (um exame cada). O JSON5 tem Infinity,
  # que o jsonlite não lê; esses campos não são usados aqui.
  texto <- gsub("-?Infinity", "null", paste(readLines(caminho, encoding = "UTF-8"), collapse = "\n"))
  fromJSON(texto)$pacientes_ficticios
}

descritivas_da_base <- function(base) {
  contar <- function(v) as.list(table(v))
  por_grupo <- function(grupo, valor) lapply(split(valor, grupo), descritivas)
  com_polipo <- sum(base$polipo > 0)
  list(
    n_exames = nrow(base),
    frequencia_sexo = contar(base$sexo),
    frequencia_polipos = contar(base$polipo),
    frequencia_indicacao = contar(base$indicacao_exame),
    frequencia_comorbidades = contar(unlist(base$comorbidades)),
    frequencia_sintomas = contar(unlist(base$sintomas)),
    idade_por_sexo = por_grupo(base$sexo, base$idade),
    polipos_por_indicacao = por_grupo(base$indicacao_exame, base$polipo),
    sexo_por_indicacao = lapply(split(base$indicacao_exame, base$sexo), contar),
    prevalencia_polipo = wilson(com_polipo, nrow(base), 0.05)
  )
}

args <- commandArgs(trailingOnly = TRUE)

grades <- list(
  versao_r = R.version.string,
  pacotes = lapply(c(jsonlite = "jsonlite", epitools = "epitools", DescTools = "DescTools"),
                  function(p) as.character(packageVersion(p))),
  wilson = mapply(wilson,
    c(0, 10, 5, 1, 37, 3, 50, 0, 1),
    c(10, 10, 10, 100, 120, 7, 1000, 1, 1),
    c(0.05, 0.05, 0.05, 0.05, 0.05, 0.01, 0.1, 0.05, 0.05), SIMPLIFY = FALSE),
  fisher = lapply(list(c(3, 1, 1, 3), c(10, 2, 3, 15), c(0, 5, 5, 0), c(1, 9, 11, 3),
                       c(12, 5, 7, 20), c(0, 0, 5, 5), c(231, 32, 27, 54)),
                  function(e) do.call(fisher, as.list(e))),
  tabela_2x2 = lapply(list(c(3, 1, 1, 3), c(10, 2, 3, 15), c(1, 9, 11, 3), c(12, 5, 7, 20),
                           c(231, 32, 27, 54)),
                      function(e) do.call(tabela_2x2, as.list(e))),
  diagnostico = list(diagnostico(80, 10, 20, 90, 0.05), diagnostico(5, 5, 5, 5, 0.05),
                     diagnostico(231, 32, 27, 54, 0.05), diagnostico(45, 15, 5, 135, 0.01)),
  amostra_survey = list(amostra_survey(NA, 0.5, 0.05, 0.95), amostra_survey(1000, 0.5, 0.05, 0.95),
                        amostra_survey(100, 0.2, 0.05, 0.95), amostra_survey(NA, 0.1, 0.02, 0.99)),
  amostra_comparativa = list(amostra_comparativa(0.8, 0.95, 1, 0.2, 0.3),
                             amostra_comparativa(0.9, 0.95, 2, 0.1, 0.2),
                             amostra_comparativa(0.8, 0.99, 1, 0.05, 0.15),
                             amostra_comparativa(0.8, 0.95, 0.5, 0.4, 0.2)),
  tendencia = list(tendencia(c(5, 10, 15), c(50, 50, 50), c(0, 1, 2)),
                   tendencia(c(2, 4, 6, 8), c(20, 20, 20, 20), c(1, 2, 3, 4)),
                   tendencia(c(1, 2), c(10, 10), c(0, 1)),
                   tendencia(c(15, 10, 5), c(40, 40, 40), c(0, 1, 2)),
                   tendencia(c(3, 8, 11, 20), c(40, 45, 38, 41), c(40, 50, 60, 70))),
  mantel_haenszel = list(mantel_haenszel(list(c(10, 20, 5, 30), c(8, 15, 6, 25))),
                         mantel_haenszel(list(c(5, 5, 5, 5), c(10, 2, 3, 15), c(1, 9, 11, 3)))),
  qui_quadrado_rxc = list(qui_quadrado_rxc(list(c(10, 20), c(30, 40))),
                          qui_quadrado_rxc(list(c(5, 10, 15), c(20, 25, 30), c(10, 5, 1)))),
  descritivas = list(descritivas(c(1, 2, 3, 4, 5)), descritivas(c(7.5)),
                     descritivas(c(2, 2, 2, 2)), descritivas(c(1, 100, 3, 8, 2, 9.5, 40))),
  base_do_oraculo = descritivas_da_base(base_do_oraculo(args[2]))
)

write_json(grades, args[1], auto_unbox = TRUE, digits = NA, pretty = TRUE, na = "null")
