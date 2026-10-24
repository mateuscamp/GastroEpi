# GastroEpi

App desktop offline para registro de colonoscopia e epidemiologia de CRC (Tauri v2: React + Rust + SQLite).
Arquitetura: monólito modular · Quantum: 1 executável, 1 banco. ADRs em `docs/adr/`. Princípios em `CONSTITUTION.md` (prevalecem).

## Comandos

- Testes do núcleo (headless, sem GTK): `cargo test -p gastroepi-core`
- Tipos do frontend: `npm run build`
- Rodar local: `npm run tauri dev`

Rodar os dois primeiros antes de declarar qualquer tarefa concluída.

## Fronteiras (ADR-0001)

- `crates/gastroepi-core` nunca depende de `tauri`.
- `estatistica/` importa só `dominio/`. Nunca `persistencia/` nem `cofre/`.
- Só `persistencia/` escreve SQL. Toda mutação de paciente passa por `auditoria` na mesma transação.
- `src-tauri/src/commands.rs` só desserializa, valida, chama o core e mapeia erro. Sem regra de negócio, sem SQL.
- Validação de CPF, prontuário e datas existe no core E no Zod; vetores de teste em comum.
- Tipos do IPC são gerados do Rust (`src/bindings/`). Proibido redeclarar interface à mão no `.tsx`.
- Frontend: um painel por arquivo em `src/features/<painel>/`; `invoke` só em `src/api/`.
- Fronteira nova exige ADR antes do código.

## Segurança (inegociável)

- Nunca logar, imprimir em erro ou exportar sem pedido explícito: nome, CPF, laudo, chave, senha.
- Nunca afrouxar triggers da tabela `auditoria` nem os parâmetros do Argon2id.
- Migração de schema: nova função de migração idempotente + teste com banco da versão anterior.
- Sem rede: nenhuma dependência nova que faça chamada externa.

## Ciclo de mudança (TDD)

1. Vermelho: um teste por comportamento, visto falhar NA ASSERÇÃO.
2. Verde: o mínimo de código; não editar o teste nesta fase.
3. Refatorar com suíte verde; commit `refactor:` não altera asserção.

- Bug: teste de regressão que reproduz primeiro, depois o fix.
- Estatística: valor de referência citado (R, Epi Info ou artigo) no comentário do teste.
- Proibido para ficar verde: mudar asserção, `#[ignore]`, apagar teste, mockar o sujeito.

## Estilo

- Arquivo < 600 linhas; função < 40 linhas.
- Erros com tipo (`thiserror`) no core; conversão para `String` só em `commands.rs`.
- Não apagar comentários de proveniência em refactor.

## Estrutura (alvo)

```
crates/gastroepi-core/src/
  dominio/        Paciente, HistoricoFamiliar, validação
  cofre/          Argon2id, AES-256-GCM, recovery key
  persistencia/   schema, migrações, repositório de pacientes e catálogos
  auditoria/      cadeia HMAC, verificação de integridade
  estatistica/    contingência, Wilson, Fleiss, Cochran-Armitage, qualidade
  exportacao/     CSV pt-BR com proteção contra injeção
src-tauri/src/    lib.rs, commands.rs (casca IPC)
src/api/          wrappers tipados de invoke
src/bindings/     tipos gerados do Rust
src/features/     um diretório por painel
```
