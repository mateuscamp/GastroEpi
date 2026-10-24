# 0001 — Manter um único executável e extrair o núcleo Rust para um crate sem Tauri

**Status:** Proposto
**Data:** 2026-10-24
**Driver ★:** Integridade e confidencialidade do dado clínico (Princípios I–III da CONSTITUTION)

## Contexto

GastroEpi é um app desktop offline, monousuário, com um único arquivo SQLite cifrado
por campo e cadeia de auditoria HMAC. O código é escrito majoritariamente por agente.
Hoje `db.rs` (1.966 linhas) concentra schema, cofre, CRUD, catálogos, auditoria,
integridade e backup; `App.tsx` (2.787 linhas) concentra todos os painéis e redeclara
à mão os tipos do Rust. O CI só compila — nenhum `cargo test` nem `tsc` roda — e os
testes de `db`/`math` não rodam sem as bibliotecas do WebKitGTK, porque vivem no
mesmo crate que o Tauri. `math/` importa `db::Paciente`, ou seja, a estatística
depende da camada de persistência.

Quantum atual: 1 — o executável Tauri (webview React + core Rust), dono exclusivo de
`gastroepi.db` e dos backups rotacionados.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| A. Manter como está | Zero custo agora | Testes presos ao WebKit; fronteiras só por convenção; arquivos > 1.500 linhas estouram o contexto do agente | Erosão já visível (`math → db`) |
| B. Só módulos dentro de `src-tauri` | Barato; melhora legibilidade | Fronteira não é verificada pelo compilador; testes continuam exigindo GTK | Não resolve testabilidade |
| C. Workspace: `crates/gastroepi-core` (sem Tauri) + `src-tauri` como casca IPC | Fronteira imposta pelo compilador; `cargo test -p gastroepi-core` roda headless em segundos; núcleo de segurança auditável isolado | Movimentação de arquivos (histórico do `git blame`), API `pub` explícita, um `Cargo.toml` a mais | — |
| D. Processos separados / sidecar / serviço local | Isolamento de processo | Superfície de rede local contra o Princípio I; IPC extra; sem driver de escala (1 usuário) | Inviável: viola a soberania local sem ganho |

## Decisão

Manter **um único quantum** (um executável, um banco). Dentro dele, extrair
`crypto`, `db` (dividido) e `math` para `crates/gastroepi-core`, que não depende de
`tauri`. `src-tauri` passa a conter apenas `commands.rs`/`lib.rs`: desserializa,
valida, chama o core, mapeia erro. Os tipos de domínio (`Paciente`, `HistoricoFamiliar`)
saem de `db` para `core::dominio`; `estatistica` passa a depender de `dominio`, nunca
de `persistencia`. A validação de CPF/prontuário/datas é duplicada no core (a IPC é
a fronteira de confiança real; o Zod continua como UX).

## Consequências

**Ganha:** testes do núcleo de segurança e da estatística rodam no CI sem WebKit;
o compilador impede o núcleo de importar Tauri; arquivos menores cabem no contexto
do agente; regras de validação deixam de depender só do frontend.

**Perde:** uma tarde a um dia de movimentação mecânica; `git blame` precisa de
`--follow`; a regra de validação passa a existir em dois lugares (Zod e Rust) e
precisa de vetores de teste compartilhados para não divergir.

**Aceito conscientemente:** continua existindo um único `Mutex<BancoDados>` global e
as estatísticas decifram todos os registros a cada chamada. Revisitar se a base
passar de ~50 mil exames ou se qualquer tela de estatística passar de 1 s.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| Núcleo sem Tauri | `cargo tree -p gastroepi-core -i tauri` | CI | O comando encontra `tauri` |
| Estatística não importa persistência | `grep -rn "crate::persistencia\|crate::db" crates/gastroepi-core/src/estatistica` | CI | Qualquer hit |
| Núcleo testado headless | `cargo test -p gastroepi-core` em `ubuntu-latest` sem libs GTK | CI | Qualquer teste falha |
| Tipos IPC sincronizados | Tipos TS gerados (ts-rs ou tauri-specta) + `git diff --exit-code src/bindings` | CI | Diff não vazio |
| Tamanho de arquivo | Script falha se `*.rs`/`*.tsx` > 600 linhas (lista de exceção temporária) | CI | Arquivo novo ou crescido acima do limite |
| Frontend tipa | `npm run build` (`tsc`) | CI | Erro de tipo |

Regra derivada no `AGENTS.md`: seção "Fronteiras (ADR-0001)".

## Notas

Autor: Mateus Campelo · Criado em: 2026-10-24
