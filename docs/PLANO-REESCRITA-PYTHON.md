# GastroEpi — decisão 0002: como reescrever o app inteiro em Python

**Status:** Aceito · **Data:** 2026-10-31 · ADRs: [0002](adr/0002-reescrever-em-python-com-nucleo-puro-e-casca-qt.md),
[0003](adr/0003-cifrar-o-banco-inteiro-com-sqlcipher.md), [0004](adr/0004-registrar-o-exame-em-dados-estruturados.md)

Origem das ideias de durabilidade, relatório e exportação: a conversa de 2026-10-24
(sessão `claude.ai/code/session_01EzZwqyjZDjVB2241MnSp7N`), registrada em
`docs/PLANO-REESTRUTURACAO.md` na branch `docs/adr-0001-arquitetura`.

**Bottom line**: reescrever como **um executável Python** com **núcleo puro** (domínio,
cofre, auditoria, persistência, estatística, exportação, serviços) e **casca desktop
PySide6** + CLI, com fronteiras verificadas no CI. O app não abre nenhuma porta e o
cofre nunca fica alcançável por outro processo. A decisão se inverte se o instalador
passar de 250 MB ou a abertura a frio passar de 8 s no Windows de teste; nesse caso,
troca-se só a casca.

## Drivers

| ★ | Característica | Origem (frase do problema) | Como se mede |
|---|---|---|---|
| ★ | Integridade e confidencialidade do dado clínico | CONSTITUTION I–III; "não corromper os dados" (prioridade nº 1); o usuário leigo vai digitar pacientes reais depois da entrega | (1) hypothesis com sequências aleatórias de mutação → 0 inconsistências na cadeia e nos dados; (2) 1 linha adulterada por fora → acusa a 1ª entrada afetada; (3) 0 ocorrências de nome/CPF/prontuário/laudo conhecidos nos bytes do `.db` e dos backups (ADR-0003) |
| | Implantabilidade e operação sem suporte | "usuário leigo no Windows"; "algo que eu pudesse largar na mão dele" sem ser chamado (conversa de 2026-10-24) | Instalador gerado no CI (`windows-latest`) a cada tag; `GastroEpi.exe --smoke` sai com 0; funciona sem Python instalado; ≤ 250 MB; abertura a frio ≤ 8 s (Tauri hoje: 2 MB, < 1 s) |
| | Fidelidade estatística | Princípio IV; os testes Rust atuais só checam sinal (`p_valor > 0.0`) | 100% das funções públicas de `estatistica/` com teste de valor de referência citado (R/Epi Info, tolerância 1e-6) e paridade com o oráculo v0.1.16 |
| | Soberania local | Princípio I | Suíte inteira com `--disable-socket`; 0 imports de rede no pacote |
| | Testabilidade headless | ADR-0001: "testes presos ao WebKit; o CI só compila" | `uv run pytest` sem display em ≤ 60 s, em Ubuntu e Windows; cobertura de ramos ≥ 90% no núcleo |
| | Legibilidade para agente | `App.tsx` com 2.787 linhas, `db.rs` com 1.966 | 0 arquivos > 400 linhas; 0 funções > 40; `mypy --strict` com 0 erros; contratos do import-linter verdes |
| | Demonstrabilidade (portfólio) | "criar um portfólio Python": dados/saúde, backend, engenharia, desktop | Clone limpo → `uv sync && uv run gastroepi demo` abre com pacientes fictícios; README com arquitetura e ADRs; CI verde visível |

## Quantum

- **Hoje:** 1. É o executável Tauri (webview React + núcleo Rust), dono de `gastroepi.db` e `backups/`.
- **Alvo:** 1. Um executável Python congelado, dono do mesmo tipo de arquivo. Não há
  driver de modularidade com evidência para distribuir (1 usuário, 1 máquina, ~10 mil
  registros), então a conversa é sobre módulos dentro do monólito.

## Dimensões emaranhadas

- **Linguagem × empacotamento**: Python no Windows de um leigo exige executável
  congelado. Cada dependência nativa (Qt, scipy) entra no instalador e no tempo de abertura.
- **Casca × superfície de rede**: uma casca web exige servidor em 127.0.0.1 enquanto
  o cofre está aberto. A casca Qt não abre porta.
- **Formato em disco × confidencialidade × consulta**: o que fica cifrado decide se o
  SQL consegue filtrar e indexar. Hoje idade, sexo, prontuário e data ficam legíveis
  no arquivo. O ADR-0003 resolve com SQLCipher: o arquivo inteiro cifrado e o SQL
  funcionando sobre todos os campos.
- **Persistência × auditoria**: se o evento de auditoria for gravado fora da transação
  da mutação, um crash deixa estado e cadeia divergentes.
- **Estatística × persistência**: no Rust, `math` importa `db::Paciente`. Toda mudança
  de schema quebra cálculo.
- **Validação × casca**: hoje a regra mora no Zod e não no Rust. Com uma linguagem só,
  a duplicação some, desde que a casca seja proibida de validar.
- **Senha × chave dos dados**: hoje a recovery key é a própria chave derivada da senha.
  Trocar a senha obriga a recifrar tudo. O ADR-0003 resolve com uma chave de dados
  aleatória, embrulhada pela senha.

## Opções

| Opção | Ganha | Perde | Driver afetado | Viável? |
|---|---|---|---|---|
| Tradução arquivo por arquivo | Velocidade inicial | Arquivos gigantes e `estatística → banco` | Legibilidade, testabilidade | Não |
| Núcleo + casca web local (NiceGUI) | UI moderna, vitrine web | Porta aberta com cofre aberto; repete a saída do NiceGUI | ★, soberania | Sim, com token; não escolhida |
| Núcleo + FastAPI + HTMX | Vitrine backend | Duas interfaces, porta aberta, mais código | ★, legibilidade | Sim; não escolhida |
| Serviço local + cliente | Isolamento | Rede contra o Princípio I | Soberania | Não |
| Manter Tauri | 2 MB, < 1 s | Não é portfólio Python | Demonstrabilidade | Não (objetivo mudou) |
| **Núcleo + PySide6 + CLI** | Sem porta; UI testável headless | Instalador ~50x maior; UI verbosa | Implantabilidade (custo) | **Escolhida** |

## Trade-off da escolhida

- **Escala:** são ~10 mil pacientes fictícios, 1 usuário e 1 máquina. O desempenho do
  Python não pesa: o SQLCipher decifra por página dentro do C, e a listagem dos 10 mil
  pacientes vai ser medida na Fase 2.
- **Custo real:** o instalador vai de 2 MB para algo entre 80 e 150 MB, e a abertura,
  de < 1 s para 2–5 s, num usuário que abre o app algumas vezes por dia.
- **Ganho:** a vitrine vem do núcleo (estatística validada, cofre, cadeia de auditoria),
  não da casca. Para chegar lá, reescrevem-se ~7.900 linhas (≈4.000 de UI, ≈3.900 de
  Rust), numa ordem que entrega o núcleo testado antes da primeira tela.

## Pilha (nível de design: barato de trocar, sem ADR próprio)

- Python 3.13 via `uv` (o sistema tem 3.14; a 3.13 tem wheels estáveis de PySide6,
  scipy e statsmodels).
- Projeto: `pyproject.toml`, `uv.lock`, layout `src/`.
- Qualidade: `ruff` (lint + formatação), `mypy --strict` com plugin do pydantic,
  `import-linter`, `pip-audit` (substitui o `cargo audit`).
- Testes: `pytest`, `hypothesis` (herdeiro do `proptest`), `pytest-qt` com
  `QT_QPA_PLATFORM=offscreen`, `pytest-socket`, `coverage`.
- Núcleo: `pydantic` v2, `sqlcipher3` (SQLCipher 4, ADR-0003), `cryptography`
  (embrulho da chave em AES-256-GCM, HMAC), `argon2-cffi` (Argon2id),
  `numpy`/`scipy`/`statsmodels`/`pandas` em `estatistica/`.
- Casca: `PySide6-Essentials`.

Durante a transição, o pacote Python mora em `src/gastroepi/`, ao lado dos arquivos
TS congelados em `src/*.tsx`. No corte, `src/` fica só com `gastroepi/`.

## Fases

Toda fase começa pelo teste vermelho citado, visto falhando **na asserção**, e só
termina com a checagem completa verde no CI em Ubuntu e Windows.

### Fase 0 — Esqueleto e portões (nenhuma funcionalidade)

**Estado em 2026-10-31:** feita. Verde no CI em Ubuntu e Windows (PR #6). A sonda
congelada passou no `windows-latest`: pasta de 25 MB, SQLCipher 4.19.0.

- `pyproject.toml` com `uv`; pacotes vazios de cada fronteira; `tests/arquitetura/`
  adaptado da skill (arquivo ≤ 400, função ≤ 40, nomes grepáveis, sem ciclo).
- Contratos do import-linter da tabela de Governança do ADR-0002.
- `pytest --disable-socket` por padrão; `.github/workflows/python.yml` com Ubuntu e Windows.
- O `build.yml` do Tauri fica como está até o corte.
- **Oráculo:** `ferramentas/oraculo_rust/` é um crate à parte que inclui os arquivos de
  `src-tauri/src/math/` por `#[path]`, sem compilar o Tauri. Ele grava em
  `tests/fixtures/oraculo_rust_v0_1_16.json5` as saídas de cada função numa grade de
  entradas, inclusive as bordas (zeros, n = 0, células vazias). Os vetores de CPF e
  data (`vetores_validacao_v0_1_16.json`) saem do próprio `src/validation.ts`, rodado no Node.
- **Spike do SQLCipher (ADR-0003):** job `windows-latest` com Python 3.13 instala o
  `sqlcipher3`, congela um script que cria, fecha e reabre um banco cifrado, e roda o
  executável. Se falhar, o ADR-0003 vai para o plano B (`apsw-sqlite3mc`) antes da Fase 2.
- Emendar a CONSTITUTION para v2.0.0:
  - restrições técnicas passam a ser Python/Qt (ADR-0002, aceito);
  - Princípio II passa a exigir o arquivo inteiro cifrado (ADR-0003);
  - Princípio V troca Zod por pydantic no `dominio`;
  - o protocolo de início de sessão (`cargo audit`) sai.
- **Primeiro vermelho:** o contrato "núcleo não conhece interface" falha com um
  `import PySide6` plantado em `dominio/`. Depois a violação é removida.
- **Sai quando:** CI verde nos dois sistemas e oráculo versionado.

### Fase 1 — Domínio e validação (`dominio/`)

**Estado em 2026-10-31:** feita. Verde no CI em Ubuntu e Windows (PR #7): `uv run poe check`
com 227 testes em ~2 s e 100% dos ramos em `dominio`, agora um passo do próprio `poe check`.

- Tipos do ADR-0004: `Paciente`, `HistoricoFamiliar`, `Exame`, `Examinador` (nome + CRM
  + UF), `Boston`, `Lesao` e as listas fechadas em `dominio/listas.py` (`VERSAO_DAS_LISTAS = 1`).
  CPF e prontuário são tipos de campo (`campos.py`), não classes.
- Derivados como propriedades, nunca campos: `n_polipos`, grau do parentesco, idade no
  exame, adenoma convencional, adenoma avançado (USMSTF 2020), serrilhada, preparo
  adequado (Boston, Calderwood 2014) e "aguardando histologia".
- `problemas_de` traduz o `ValidationError` para (campo, código, mensagem pt-BR). O
  `repr` e as mensagens nunca mostram nome, CPF, prontuário, nascimento ou texto livre.
- Escolhas do dono no AskUserQuestion (registradas no ADR-0004, Notas): 12 parentescos
  com grau da genética médica; 6 motivos de não intubação + outro; "aguardando" separado
  de "sem histologia" e displasia coerente com a histologia; só a intubação cecal é
  obrigatória entre os campos de qualidade.
- Divergências da v0.1.16, de propósito: CPF com letra é recusado (a v0.1.16 apagava a
  letra); data fora do ISO é recusada em vez de virar vazio; o eco `formatado`/`iso` das
  entradas inválidas não é reproduzido, porque a entrada inválida é recusada.
- Achado: "um dígito trocado falha" não vale para todo CPF. Em 0,18% das trocas o resto
  passa de 0 para 1 (ou o inverso) e o DV continua 0 (ex.: `704.999.622-06` e
  `804.999.622-06`). A propriedade do hypothesis exclui essa dobra, e um teste a documenta.

Plano original da fase:

- `Paciente`, `HistoricoFamiliar`, `Cpf`, `Prontuario`, datas `dd/mm/aaaa` ↔ ISO,
  `Sexo` e indicação. Pydantic estrito: rejeita `True` em campo inteiro (Princípio V),
  converte vazio ou espaço em `None`, normaliza o CPF para 11 dígitos com DV e recusa
  dígitos repetidos.
- Gerador de pacientes fictícios com semente (usado pela `demo` e pelos testes).
- **Primeiro vermelho:** Cenário 2, `111.111.111-11` recusado com mensagem pt-BR.
- **Sai quando:** todos os vetores do `validation.ts` passam; propriedades do
  hypothesis (CPF válido gerado passa; um dígito trocado falha); cobertura de ramos de 100%.

### Fase 2 — Cofre, persistência e auditoria

- **Cofre ([ADR-0003](adr/0003-cifrar-o-banco-inteiro-com-sqlcipher.md)):** banco
  SQLCipher 4 aberto com uma chave de dados aleatória.
  - O `gastroepi.chave` guarda essa chave embrulhada pela senha (Argon2id t=3, m=64 MiB, p=4).
  - A recovery key é a própria chave, em base32 com dígito de verificação.
  - Trocar a senha só re-embrulha a chave.
  - "Gerar nova recovery key" faz `PRAGMA rekey`.
  - A chave HMAC da auditoria é separada e fica dentro do banco.
- `auditoria/` é pura: calcula o elo HMAC-SHA256 e verifica a sequência. Começa limpa,
  só com `v2`, sem o caminho legado SHA-256.
- `persistencia/` cuida do schema, das triggers append-only, das migrações idempotentes
  e do repositório. Cada mutação e seu evento entram no mesmo `BEGIN IMMEDIATE`.
- **Primeiro vermelho:** Cenário 3. Uma linha alterada por `sqlite3` externo é acusada
  com o id e o timestamp da entrada.
- **Sai quando:** passam o teste de estado do hypothesis, toda a tabela de Governança
  do ADR-0003 (bytes, cabeçalho, adulteração, recovery sem arquivo de chave, troca de
  senha, rekey) e o Cenário 1 (senha duas vezes → recovery key em blocos de 8).

### Fase 3 — Estatística (`estatistica/`)

- Funções a portar:
  - Wilson e IC das razões de verossimilhança;
  - 2x2 (OR de Woolf, RR, Pearson, Yates, Fisher) e teste diagnóstico;
  - amostra survey e Fleiss;
  - Cochran-Armitage, Mantel-Haenszel e qui-quadrado R×C;
  - ADR/PDR por examinador, com alerta abaixo de 25%;
  - frequências, estratificação e prevalência.
- Cada função tem um teste `@pytest.mark.referencia` com o valor do R (`binom`, `epitools`,
  `fisher.test`, `mantelhaen.test`, `prop.trend.test`) ou do Epi Info citado na docstring,
  e um teste de paridade com o oráculo.
- Se o R e o oráculo divergirem, vale o R, e o commit registra a divergência. Exemplo
  esperado: as variantes do Cochran-Armitage diferem por um fator N/(N−1).
- **Primeiro vermelho:** Wilson com 0/10 igual ao valor do R.
- **Sai quando:** a fitness "toda função pública tem teste de referência" passa.

### Fase 3b — Relatório epidemiológico fechado

Pedido da conversa de 2026-10-24: o filho do dono aperta um botão e recebe um documento
pronto, sem escolher análise, variável nem teste; no máximo escolhe o período.

- **Especificação, antes do código:** uma lista de 5 a 10 perguntas combinada com o dono
  (ex.: "histórico familiar aumenta pólipo?", "a partir de que idade aumenta o adenoma?",
  "homem tem mais que mulher?"). Sem a lista, esta fase não começa.
- **Conteúdo fixo:**
  - descrição da base;
  - associação de cada pergunta pré-exame com pólipo e com adenoma, com correção de
    Benjamini-Hochberg;
  - uma regressão logística multivariável (`statsmodels`) com todas as variáveis juntas;
  - tendência por faixa etária.
- **Frases automáticas** em português simples para cada resultado. Exemplo: "pacientes com
  histórico familiar de 1º grau tiveram cerca de duas vezes mais chance de pólipo,
  mesmo considerando idade e sexo".
- **O relatório se protege sozinho:**
  - "poucos casos, resultado não confiável" em vez de um número enganoso;
  - quantos dados faltam por campo;
  - aviso, e nunca travamento, quando a regressão não converge ou há separação perfeita;
  - parágrafo fixo de limitações: são pessoas que procuraram o exame, e associação não é causa.
- **Exportação para análise** (ADR-0004): uma linha por exame, comorbidades e sintomas
  como colunas sim/não, sem nome, CPF ou prontuário, com dicionário de dados. É a saída
  para quem quiser ir além do relatório (R, Jamovi).
- **Primeiro vermelho:** a regressão logística de uma base fictícia fixa bate com o
  `glm(..., family = binomial)` do R até 1e-6.

### Fase 4 — Durabilidade (ADR-0005)

Trata as lacunas levantadas em 2026-10-24 (branch `docs/adr-0001-arquitetura`):

- `quick_check` na abertura; se falhar, o banco abre em somente leitura e oferece
  restaurar o último backup válido.
- O backup é gravado num arquivo temporário, conferido com `integrity_check` e só então
  renomeado para o nome final.
- Rotação por data: 7 diários, 4 semanais e 12 mensais. Hoje, abrir o app 5 vezes num
  dia apaga todo o histórico de backups.
- Backup ao fechar e a cada 15 min se houve alteração.
- Instância única por trava de arquivo (sem socket).
- O app se recusa a abrir banco dentro de pasta sincronizada (OneDrive/Drive/Dropbox).
- Destino externo opcional, com aviso se a última cópia tiver mais de 7 dias. Pode ser
  um pendrive ou uma pasta do Google Drive, com três regras da conversa de 2026-10-24:
  - o banco em uso nunca fica na pasta sincronizada; só as cópias prontas e conferidas
    vão para lá, junto com o `gastroepi.chave`;
  - a recovery key nunca vai para o mesmo Drive: fica no papel;
  - com cópias na nuvem, a senha deve ser uma frase longa (~4 palavras), porque o
    Argon2id só atrasa a adivinhação.
- **Primeiro vermelho:** bytes corrompidos → abrir → modo somente leitura.

### Fase 5 — Casca Qt (`ui_qt/`) e CLI (`cli/`)

- Telas, uma por módulo:
  - desbloqueio (criar senha, senha, recovery key);
  - pacientes (`QTableView` com modelo, ordenação e filtro para 10 mil linhas; formulário; catálogos);
  - painel com gráficos;
  - StatCalc (qualidade, 2x2, diagnóstico, amostra, tendência, Mantel-Haenszel);
  - auditoria (lista, verificações, integridade física, backup manual, nome do usuário);
  - exportação CSV, com aviso de que o arquivo sai sem cifra.
- Bloqueio automático do cofre após um tempo sem uso (padrão 15 min), que fecha a
  conexão e descarta a chave.
- CLI: `gastroepi demo`, `verificar`, `backup` e `exportar`.
- `pytest-qt` em `offscreen`, contra `servicos` reais com banco temporário. O CI salva
  a captura de cada tela como artefato para revisão visual.
- **Primeiro vermelho:** Cenário 1 dirigido pelo `qtbot`.
- **Sai quando:** os 35 comandos da v0.1.16 (tabela abaixo) existem em `servicos` e são
  alcançáveis por uma tela.

### Fase 6 — Empacotamento Windows (ADR-0006: PyInstaller, Nuitka ou Briefcase)

- Instalador gerado no CI em cada tag.
- `GastroEpi.exe --smoke`: abre um banco temporário, cria senha, cadastra um paciente
  fictício, verifica e sai com 0.
- Medir tamanho e abertura a frio contra os limites do ADR-0002.
- Roteiro manual de ~10 min na máquina Windows de teste, só com fictícios, numa pasta
  descartável: abrir e criar senha → cadastrar → editar → excluir → painel → StatCalc →
  exportar → fechar e reabrir.
- **Sai quando:** o roteiro passa e o `--smoke` está verde no CI.

### Fase 7 — Corte

- Um commit remove `src-tauri/`, os arquivos TS/CSS de `src/`, `package*.json`,
  `index.html`, `public/`, `vite.config.ts`, `tsconfig*.json`, o `build.yml` do Tauri
  e o manifesto Flatpak do Tauri.
- README em Python; tag `v0.2.0` com o instalador.
- Os PRs do Dependabot de cargo/npm perdem o objeto e são fechados, com o seu OK.

## Paridade: os 35 comandos da v0.1.16

| Grupo | Comandos Tauri | Destino em Python |
|---|---|---|
| Acesso (7) | `tem_senha_configurada`, `configurar_senha`, `desbloquear`, `desbloquear_com_chave`, `esta_desbloqueado`, `obter_nome_usuario`, `definir_nome_usuario` | `servicos.acesso` |
| Pacientes (7) | `listar_pacientes`, `buscar_paciente`, `buscar_paciente_por_prontuario`, `buscar_paciente_por_termo`, `cadastrar_paciente`, `editar_paciente`, `excluir_paciente` | `servicos.pacientes` |
| Catálogos (4) | `listar_`/`adicionar_comorbidade_catalogo`, `listar_`/`adicionar_sintoma_catalogo` | `servicos.catalogos` |
| Integridade (5) | `listar_auditoria`, `verificar_integridade`, `verificar_integridade_dados`, `diagnosticar_integridade_fisica`, `realizar_backup` | `servicos.integridade` |
| Calculadoras (7) | `calcular_tabela_2x2`, `calcular_teste_diagnostico`, `calcular_amostra_survey`, `calcular_amostra_comparativa`, `calcular_tendencia_cochran_armitage`, `calcular_mantel_haenszel`, `calcular_qui_quadrado_geral` | `servicos.calculadoras` → `estatistica` |
| Estatística do banco (4) | `obter_indicadores_qualidade`, `obter_frequencias`, `obter_estratificacao`, `obter_prevalencia_polipo` | `servicos.indicadores` → `estatistica` |
| Exportação (1) | `exportar_pacientes_csv` | `servicos.exportar` → `exportacao` |

## Fitness functions

| Driver | Checagem | Tipo | Onde roda | Falha quando |
|---|---|---|---|---|
| ★ Integridade | Teste de estado do hypothesis com mutações aleatórias → verificar cadeia e dados | Holística, contínua | CI | Qualquer inconsistência |
| ★ Integridade | Adulteração externa de 1 linha (Cenário 3) | Atômica, contínua | CI | Não acusa a 1ª entrada afetada |
| ★ Integridade | `UPDATE`/`DELETE` em `auditoria` | Atômica, contínua | CI | Não levanta erro |
| ★ Confidencialidade | Busca de nome/CPF/prontuário/laudo/comorbidade conhecidos nos bytes do `.db`, do `-wal`, dos backups e do `gastroepi.chave` (ADR-0003) | Holística, contínua | CI | Qualquer achado |
| ★ Confidencialidade | O `sqlite3` da stdlib não abre o banco; 1 byte trocado é acusado pelo HMAC de página (ADR-0003) | Atômica, contínua | CI | Abre, ou a adulteração passa |
| Implantabilidade | Spike do `sqlcipher3` congelado em `windows-latest` (ADR-0003) | Atômica, acionada na Fase 0 | CI | O executável não cria/reabre o banco |
| ★ Fronteiras | Contratos do import-linter (núcleo ↛ casca; casca ↛ persistência/cofre; só `persistencia` usa `sqlite3`) | Atômica, contínua | CI + pre-commit | Contrato quebrado |
| Soberania local | `pytest --disable-socket` + contrato proibindo módulos de rede | Atômica, contínua | CI | Socket aberto ou import de rede |
| Fidelidade estatística | Todas as funções públicas de `estatistica/` com teste `referencia`; paridade com o oráculo | Atômica, contínua | CI | Função sem teste ou divergência acima da tolerância |
| Implantabilidade | Build do instalador + `--smoke` em `windows-latest`; tamanho | Holística, acionada por tag | CI | `--smoke` ≠ 0 ou > 250 MB |
| Implantabilidade | Roteiro de 10 min na máquina Windows de teste | Manual, antes de cada entrega | Mateus | Qualquer passo estranho anotado sem correção |
| Testabilidade | Tempo da suíte e cobertura de ramos do núcleo | Holística, contínua | CI | > 60 s ou < 90% |
| Legibilidade | `tests/arquitetura` + `mypy --strict` | Atômica, contínua | CI + pre-commit | Arquivo > 400, função > 40, erro de tipo |
| Oráculo congelado | Diff do PR em `src-tauri/`, `src/*.ts*`, `src/*.css`, `src/assets/`, `package*.json` | Atômica, contínua | CI | Qualquer mudança |

## Contrato para o agente

Ver [`AGENTS.md`](../AGENTS.md), seção "Fronteiras (ADR-0002)".

## Próximo passo

Fase 0: esqueleto `uv` com os portões de arquitetura e o CI verde em Ubuntu e Windows.
O primeiro vermelho é o contrato "núcleo não conhece interface" falhando contra um
`import PySide6` plantado.
