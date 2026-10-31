# 0002 — Reescrever o GastroEpi em Python: um executável, núcleo puro e casca desktop Qt

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** Integridade e confidencialidade do dado clínico (Princípios I–III da CONSTITUTION)

## Contexto

O GastroEpi v0.1.16 é um app Tauri v2: a interface tem ~4.000 linhas de React/TS
em dois arquivos (`App.tsx` com 2.787 linhas, `DashboardPanel.tsx` com 1.102), e o
núcleo tem ~3.900 linhas de Rust (`db.rs` com 1.966). O dono decidiu transformá-lo
em peça de portfólio Python (vitrine: dados/saúde, backend, engenharia de software,
desktop) e continuar entregando o app a um usuário leigo no Windows, offline e sem
suporte. Só existem dados fictícios, então o formato em disco pode ser redesenhado
sem migração.

O projeto já foi Python uma vez (`~/GastroEpidemio`, NiceGUI) e saiu dele para
"eliminar o interpretador Python e o servidor WebSocket local" (`PLAN.md`). O
ADR-0001 (Proposto, 2026-10-24) recomendou ficar no Tauri e citou "Python reabre
empacotamento" como custo. O fato novo é a mudança de objetivo: a linguagem está
decidida. Este ADR registra a decisão e escolhe a estrutura.

Quantum atual: **1**. É o executável Tauri (webview + núcleo Rust), dono exclusivo
de `gastroepi.db` e de `backups/`. Quantum alvo: **1**, um executável Python
congelado, dono exclusivo do arquivo de banco e dos backups.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| A. Traduzir arquivo por arquivo (`db.py`, `crypto.py`, `math/`, telas) | Começa rápido | Herda os arquivos de 2.000 linhas e a dependência estatística → persistência | Repete a erosão que o ADR-0001 já mediu |
| B. Núcleo puro + casca web local (NiceGUI em janela pywebview) | UI moderna rápida; vitrine web; teste de UI sem navegador | Servidor HTTP/WebSocket em 127.0.0.1 enquanto o cofre está aberto, exigindo token por sessão; reabre o motivo de ter saído do NiceGUI | Paga no ★ sem ganhar no ★ |
| C. Núcleo puro + API FastAPI + tela HTMX em janela | Maior vitrine de backend | Duas camadas de interface para um usuário; a mesma porta aberta de B; mais código | Dobra superfície e código para atender um item da vitrine |
| D. Processos separados (serviço local + cliente) | Isolamento de processo | Rede local contra o Princípio I; IPC extra | Inviável: 1 usuário e 1 máquina não geram driver de escala |
| E. Manter Tauri (ADR-0001) | Instalador de 2 MB, abertura < 1 s | Não atende o objetivo do projeto | O objetivo mudou |
| **F. Núcleo puro + casca desktop PySide6 + CLI** | Nenhuma porta aberta; processo único; teste de UI headless (`offscreen`) e captura de tela de widget; vitrine desktop + dados + engenharia | Instalador ~50x maior; código de tela mais verboso; visual pede trabalho de estilo; vitrine backend só parcial | — |

## Decisão

Reescrever o app inteiro em Python 3.13, num único executável que é dono de um único
banco SQLite. O pacote `src/gastroepi/` separa um **núcleo** que não conhece interface
(`dominio`, `cofre`, `auditoria`, `persistencia`, `estatistica`, `exportacao`,
`servicos`) de duas **cascas** (`ui_qt` em PySide6 e `cli`). As cascas só entram no
núcleo por `servicos`.

A validação existe uma vez só, em `dominio` (pydantic v2 estrito), e as duas cascas
a consomem. Isso elimina a regra duplicada entre Zod e Rust. Só `persistencia` fala
SQL, e toda mutação grava o evento de auditoria na mesma transação. `estatistica`
recebe tipos de `dominio` e nunca lê o banco.

Escolhemos Qt em vez de casca web porque o driver ★ não ganha nada com um servidor
local, e a casca Qt não abre nenhuma porta enquanto a chave está em memória.

O código Rust/TS fica congelado como oráculo até a paridade e sai num commit único
no corte; a tag `v0.1.16` o preserva. Ainda não decidido: como cifrar em repouso
(ADR-0003), como garantir a durabilidade (ADR-0005) e qual empacotador usar
(ADR-0006). O modelo de dados estruturado é o ADR-0004. Cada um é decidido antes do código da sua fase.

## Consequências

**Ganha:** núcleo de segurança e estatística testável headless em segundos, no Linux
e no Windows; fronteiras verificadas por máquina (import-linter + `tests/arquitetura`),
não por convenção; uma só regra de validação; estatística conferida contra R/Epi Info
(hoje os testes Rust só checam sinal, como `p_valor > 0.0`); a casca pode ser
trocada sem mexer no núcleo.

**Perde:**
- Instalador Windows de 2 MB → estimados 80–150 MB (Qt + numpy/scipy/statsmodels).
- Abertura de < 1 s → estimados 2–5 s.
- Risco de falso positivo de antivírus com executável congelado.
- ~7.900 linhas reescritas sem funcionalidade nova para o usuário até a Fase 6.
- A garantia do compilador Rust vira verificação do `mypy --strict`, que é mais fraca.

**Aceito conscientemente:**
- O usuário fica na v0.1.16 até o instalador Python passar no roteiro em Windows.
- A vitrine backend/web não é atendida por esta casca. Se o portfólio passar a mirar
  backend, cria-se uma casca FastAPI sobre `servicos` sem tocar o núcleo.
- Revisitar a casca Qt se o instalador passar de **250 MB** ou a abertura a frio
  passar de **8 s** na máquina Windows de teste.
- Discordância registrada: a análise de 2026-10-24 preferia o Tauri pelo tamanho e
  pela abertura. Esta decisão paga esse custo em troca do objetivo de portfólio.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| Núcleo não conhece interface | import-linter `forbidden`: núcleo ↛ `PySide6`, `gastroepi.ui_qt`, `gastroepi.cli` | CI + pre-commit | Contrato quebrado |
| Cascas só entram por `servicos` | import-linter `forbidden`: `ui_qt`, `cli` ↛ `persistencia`, `cofre`, `auditoria`, `sqlite3` | CI | Contrato quebrado |
| Estatística não lê banco | import-linter `forbidden`: `estatistica`, `exportacao` ↛ tudo do projeto exceto `dominio` | CI | Contrato quebrado |
| Só `persistencia` fala SQL | import-linter `forbidden`: pacote exceto `persistencia` ↛ `sqlite3` | CI | Contrato quebrado |
| Sem rede (Princípio I) | import-linter `forbidden`: pacote ↛ `socket`, `http`, `urllib`, `requests`, `httpx`; `pytest --disable-socket` | CI | Contrato quebrado ou teste abre socket |
| ★ Mutação sempre auditada | Teste de estado do hypothesis: sequência aleatória de cadastrar/editar/excluir/catálogo → verificação da cadeia e dos dados | CI | Qualquer inconsistência |
| ★ Adulteração detectada (Cenário 3) | Teste: altera 1 linha por `sqlite3` externo → verificação | CI | Não acusa a primeira entrada afetada |
| Legibilidade | `tests/arquitetura`: arquivo ≤ 400 linhas, função ≤ 40 | CI + pre-commit | Qualquer arquivo ou função acima |
| Tipos | `mypy --strict src/` | CI | Qualquer erro |
| Oráculo congelado | Retirada no corte (Fase 7, 2026-10-31): o código Rust/TS saiu e a tag `v0.1.16` o preserva; ficam os fixtures em `tests/fixtures/`, gerados dessa tag | — | — |
| Roda no Windows | Job `windows-latest`: `uv run pytest`; job `instalador`: build + `--smoke` do instalado (ADR-0006) | CI | Teste falha; instalador > 250 MB ou `--smoke` > 8 s |

Regra derivada no `AGENTS.md`: seção "Fronteiras (ADR-0002)".

## Notas

Autor: Mateus Campelo · Criado em: 2026-10-31 · Aprovado em: 2026-10-31
Substitui: 0001
