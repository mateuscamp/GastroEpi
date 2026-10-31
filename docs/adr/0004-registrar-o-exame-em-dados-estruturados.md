# 0004 — Registrar o exame em dados estruturados: lesão por lesão, qualidade e listas fechadas

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** Fidelidade estatística (Princípio IV): o indicador calculado tem que ser o indicador definido

## Contexto

Na v0.1.16, a taxa de detecção de adenoma por examinador sai de
`laudo.to_lowercase().contains("adenoma")` (`src-tauri/src/math/quality.rs:44`). Isso gera três erros:
- "ausência de adenoma" conta como adenoma, e "adenona" não conta;
- o denominador são todos os exames, inclusive vigilância e sintomáticos, quando o
  indicador é definido sobre rastreio;
- o nº de pólipos é digitado à parte do laudo. O oráculo da v0.1.16 mostra uma
  examinadora com **0 pólipos e 2 adenomas** (`tests/fixtures/oraculo_rust_v0_1_16.json5`,
  `indicadores_por_examinador`).

O grau de parentesco é escolhido separado do parentesco digitado, e os dois podem se
contradizer. O examinador é o nome digitado, então uma grafia diferente vira outro médico.
Prontuário único por registro impede um segundo exame do mesmo paciente, que é
justamente o caso da vigilância pós-polipectomia.

O dono escolheu, em 2026-10-31:
- registro por lesão;
- preparo (Boston), intubação cecal e tempo de retirada;
- indicação em lista fechada;
- examinador e parentesco em listas.

Só há dados fictícios, então não há migração.

Quantum: 1, inalterado. O dono do dado continua sendo `persistencia`; o schema muda.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| A. Texto livre (v0.1.16) | Digitação mínima | Indicadores errados por construção | É o problema |
| B. Texto livre + achado principal fechado | Mudança mínima | Só o achado mais grave entra na estatística; sem tamanho nem localização, não há adenoma avançado | O dono escolheu por lesão |
| C. Caixas por exame (adenoma? serrilhado? avançado?) | Digitação rápida | Perde tamanho e segmento; "avançado" vira julgamento manual | Idem |
| **D. Paciente → exames → lesões, com listas fechadas** | Todos os indicadores por definição, com IC; coerência garantida pelo tipo | Formulário mais longo; fluxo em duas etapas (exame, depois histologia) | — |

## Decisão

**Paciente e exame se separam (1:N).**
- `Paciente`: prontuário (único), CPF, nome, sexo, data de nascimento, comorbidades e
  histórico familiar.
- `Exame`: data, indicação, examinador, preparo, intubação cecal, tempo de retirada,
  sintomas, lesões e observação.
- A idade no exame é calculada da data de nascimento, não digitada.

**Lesão por lesão.** Cada pólipo é uma `Lesao` com:
- segmento: ceco, ascendente, flexura hepática, transverso, flexura esplênica,
  descendente, sigmoide ou reto;
- tamanho em mm (inteiro ≥ 1);
- morfologia de Paris: 0-Ip, 0-Isp, 0-Is, 0-IIa, 0-IIb, 0-IIc, 0-III ou não classificada;
- histologia, com o grau de displasia (baixo, alto, não se aplica): adenoma tubular,
  tubuloviloso ou viloso, lesão serrilhada séssil, adenoma serrilhado tradicional,
  hiperplásico, adenocarcinoma, outro (com texto) ou aguardando/sem histologia.

O nº de pólipos é `len(exame.lesoes)`, nunca digitado. O laudo do patologista pode
chegar depois: o exame fica "aguardando histologia" até cada lesão ter a sua.

**Classificações derivadas, em `dominio`, com referência citada no código e testadas:**
- adenoma convencional: tubular, tubuloviloso ou viloso;
- adenoma avançado: adenoma ≥ 10 mm, componente viloso ou displasia de alto grau;
- serrilhada: lesão serrilhada séssil ou adenoma serrilhado tradicional.

**Qualidade do exame:**
- escala de Boston, 0–3 por segmento (direito, transverso, esquerdo). O preparo é
  adequado com total ≥ 6 e cada segmento ≥ 2;
- intubação cecal (sim/não, com motivo em lista quando não);
- tempo de retirada em minutos.

**Indicação em lista fechada:** rastreio de risco médio, rastreio de risco aumentado,
vigilância pós-polipectomia, sangue oculto/FIT positivo, diagnóstica por sintomas,
seguimento de DII ou outra (com texto). A taxa de detecção de adenoma conta só o rastreio
de risco médio a partir de 45 anos. O limiar de alerta (25% na v0.1.16) fica no código,
com a diretriz citada, e é revisado na Fase 3.

**Cadastros:**
- O examinador é um cadastro (nome + CRM) escolhido numa lista, distinto do usuário que
  opera o app (este continua na auditoria).
- O parentesco é uma lista (pai, mãe, irmão/irmã, filho/filha, avô/avó, tio/tia,
  sobrinho/sobrinha, primo/prima…), e o grau 1–3 sai dela.
- Comorbidades e sintomas continuam como catálogos auditados (já são vocabulário controlado).

**Exportação para análise** (conversa de 2026-10-24): uma linha por exame, uma coluna por
variável, comorbidades e sintomas como colunas sim/não, sem nome, CPF ou prontuário,
acompanhada de dicionário de dados. É a mesma forma tabular que o relatório fechado
(Fase 3b) usa.

**Texto livre só como observação.** Os campos `observacao` (exame) e `laudo_texto`
(lesão) existem para consulta e nunca entram em cálculo.

## Consequências

**Ganha:**
- Indicadores calculados pela definição, por examinador e com IC de Wilson: taxa de
  detecção de adenoma (rastreio), de adenoma avançado e de lesão serrilhada; adenomas
  por exame; taxa de pólipos; intubação cecal; tempo médio de retirada; preparo adequado.
- Incoerência impossível pelo tipo: nº de pólipos = lesões, e grau = parentesco.
- Vigilância com vários exames por paciente.
- Base para o relatório epidemiológico (vitrine dados/saúde).

**Perde:**
- Digitação mais longa: ~4 campos por pólipo, mais preparo e retirada.
- Fluxo em duas etapas quando a histologia chega depois.
- Schema maior (paciente, exame, lesão, examinador, histórico, catálogos).
- Listas fechadas exigem revisão quando a classificação mudar (ex.: OMS). A lista é
  versionada no `dominio` e cada mudança passa por migração.
- O oráculo v0.1.16 deixa de servir para os indicadores de qualidade: divergência
  intencional, documentada no teste.
- A data de nascimento é um dado pessoal a mais (o arquivo inteiro é cifrado, ADR-0003).

**Aceito conscientemente:**
- "Outro" com texto existe em histologia e indicação como válvula de escape. Revisitar
  a lista se "outro" passar de 5% dos registros de qualquer campo (medido pelo
  `gastroepi verificar`).

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| ★ Estatística não lê texto livre | `tests/arquitetura`: nenhum acesso a `observacao*` ou `laudo_texto` dentro de `estatistica/` | CI | Qualquer acesso |
| ★ "Ausência de adenoma" não vira adenoma | Teste de regressão: o mesmo texto da v0.1.16 em `laudo_texto` não altera nenhum indicador | CI | Indicador muda |
| ★ Denominador da taxa de adenoma | Teste: exames de vigilância, sintomáticos e < 45 anos não entram | CI | Entram |
| Nº de pólipos coerente | Tipo: `n_polipos` é propriedade derivada; o schema não tem coluna de contagem | CI (mypy + teste do schema) | Existe campo ou coluna digitável |
| Grau coerente | Propriedade (hypothesis): todo `Parentesco` tem grau 1–3; o schema não tem coluna de grau | CI | Falha |
| Classificações derivadas | Testes de referência: adenoma avançado, serrilhada e preparo adequado, com a definição citada | CI | Valor diverge |
| Uso de "outro" | `gastroepi verificar` informa o percentual de "outro" por campo | Manual, mensal | > 5% em algum campo |

Regra derivada no `AGENTS.md`: "Texto livre (`observacao`, `laudo_texto`) nunca entra em cálculo."

## Notas

Autor: Mateus Campelo · Criado em: 2026-10-31 · Aprovado em: 2026-10-31
Estende: 0002, 0003

**Detalhamento das listas (2026-10-31, Fase 1, escolhas do dono):**
- Parentesco (grau da genética médica, não o do Código Civil): 1º pai, mãe, irmão/irmã,
  filho/filha; 2º avô/avó, tio/tia, sobrinho/sobrinha, neto/neta, meio-irmão/meia-irmã;
  3º primo/prima, bisavô/bisavó, tio-avô/tia-avó.
- Motivo de não intubação cecal: preparo inadequado, lesão obstrutiva ou estenose,
  dificuldade técnica, intolerância ou sedação insuficiente, colite grave, intercorrência
  clínica ou complicação, outro (com texto).
- "Aguardando/sem histologia" vira dois itens: só "aguardando" deixa o exame pendente. A
  displasia é coerente com a histologia: adenoma convencional exige baixo ou alto grau;
  hiperplásico, aguardando e sem histologia exigem "não se aplica".
- Entre os campos de qualidade, só a intubação cecal é obrigatória; Boston (os 3
  segmentos ou nenhum) e tempo de retirada (minutos, com decimal) podem faltar.
