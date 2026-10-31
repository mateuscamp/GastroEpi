# GastroEpi

App desktop offline para registro de colonoscopia e epidemiologia de câncer colorretal.
Em reescrita de Tauri (Rust + TS) para Python: ADR-0002 (Aceito) e `docs/PLANO-REESCRITA-PYTHON.md`.
Arquitetura: monólito modular · Quantum: 1 executável, 1 banco. ADRs em `docs/adr/`. Princípios em `CONSTITUTION.md` (prevalecem).

## Comandos

- Setup: `uv sync`
- Testes: `uv run pytest`. Roda headless (`QT_QPA_PLATFORM=offscreen`), sem rede e sem senha real.
- Checagem completa: `uv run poe check` (ruff, mypy --strict, lint-imports, pytest com cobertura ≥ 90%).
- Rodar: `uv run gastroepi` (cofre em `%LOCALAPPDATA%\GastroEpi`) e `uv run gastroepi demo` (fictícios
  com semente numa pasta temporária, já desbloqueado; a senha aparece no terminal).
- Capturas das telas: `GASTROEPI_CAPTURAS=<pasta> uv run pytest tests/ui_qt`.
- Congelar (ADR-0006): `uv run --group empacotamento pyinstaller --noconfirm empacotamento/gastroepi.spec`,
  depois `dist/GastroEpi/GastroEpi --smoke`. Import que o congelado não acha entra em `hiddenimports`
  no `.spec`, com o motivo; o `--smoke` do instalador no CI é o portão.

Rodar `uv run poe check` antes de declarar qualquer tarefa concluída.

## Transição

- Oráculo congelado da v0.1.16, não editar: `src-tauri/`, `src/*.ts*`, `src/*.css`, `src/assets/`, `package*.json`.
- Fixtures em `tests/fixtures/`: `oraculo_rust_v0_1_16.json5` (gerado por `ferramentas/oraculo_rust/`) e
  `vetores_validacao_v0_1_16.json` (gerado do `src/validation.ts` no Node). Nunca editar à mão.
- Se Python e oráculo divergirem, decide o valor de referência citado (R, Epi Info, artigo). Registrar a divergência no commit.

## Fronteiras (ADR-0002)

- Núcleo: `dominio`, `cofre`, `auditoria`, `persistencia`, `estatistica`, `exportacao`, `servicos`. Cascas: `ui_qt`, `cli`.
- O núcleo nunca importa `PySide6`, `ui_qt` ou `cli`.
- Cascas importam só `servicos` e os tipos de `dominio`. Nunca `persistencia`, `cofre`, `auditoria` ou `sqlite3`.
- `dominio` não importa outro módulo do projeto e não faz I/O.
- `estatistica` e `exportacao` importam só `dominio`. Nunca leem o banco.
- `auditoria` é pura: calcula e verifica elos. Quem grava é `persistencia`.
- Só `persistencia` importa `sqlcipher3` (ADR-0003). O banco nunca é aberto pelo `sqlite3` da stdlib.
- Toda mutação de paciente ou catálogo grava o evento de auditoria na mesma transação.
- Validação só em `dominio` (pydantic estrito). A casca não revalida nem reimplementa regra.
- Texto livre (`observacao`, `laudo_texto`) nunca entra em cálculo. Dado que vai para estatística é campo de lista fechada (ADR-0004).
- Nenhum módulo importa `socket`, `http`, `urllib`, `requests` ou `httpx`.
- Fronteira nova, dependência nova ou mudança de formato em disco exige ADR antes do código.

## Segurança (inegociável)

- Nunca logar, pôr em mensagem de exceção ou exportar sem pedido explícito: nome, CPF, prontuário, laudo, chave, senha, recovery key.
- Nunca afrouxar as triggers de `auditoria` nem os parâmetros do Argon2id (t=3, m=64 MiB, p=4).
- Toda conexão começa por `PRAGMA key`; nenhum comando antes dele. Sem cifra por campo: o arquivo inteiro já é cifrado.
- Nunca gravar em disco a chave de dados, a senha ou a recovery key. O `gastroepi.chave` só guarda a chave embrulhada.
- Testes e fixtures usam só pacientes do gerador de fictícios com semente. Nunca dado real.
- Migração de schema: função idempotente + teste com banco da versão anterior.
- Nenhum backup ganha o nome final sem passar na conferência. Nenhum código apaga o banco estragado (ADR-0005).
- Sessão somente leitura nunca escreve nem copia. O banco em uso nunca fica em pasta sincronizada.

## Ciclo de mudança (TDD)

1. Vermelho: um teste por comportamento, nomeado pelo comportamento. Precisa falhar NA ASSERÇÃO; `ImportError` não conta.
2. Verde: o mínimo de código que passa, sem editar o teste. Rodar a suíte inteira.
3. Refatorar com a suíte verde. Commit `refactor:` não altera asserção.

- Bug: primeiro o teste de regressão visto falhando, depois o fix.
- Estatística: teste com `@pytest.mark.referencia` e o valor de referência citado na docstring.
- O relatório da tarefa mostra a linha de falha do vermelho e o resumo do verde.
- Proibido para ficar verde: mudar asserção, `skip`/`xfail`, apagar teste, enfraquecer asserção, mockar o sujeito, `try/except` no teste.

## Testes

- Casca: `pytest-qt` contra serviços reais em `tmp_path`; caixa modal entra por `Perguntas`
  injetada. `connect` nunca recebe lambda ou closure (segfault do PySide; `test_casca.py`).
  Digitar acento no teste é `setText`: o `keyClicks` aborta fora do ASCII.

- I/O com fake nomeado e injetado (relógio, sistema de arquivos). Banco: SQLite real em `tmp_path`, nunca mock.
- Para `src/gastroepi/<modulo>/<arquivo>.py` existe `tests/<modulo>/test_<arquivo>.py`.
- A suíte inteira roda em ≤ 60 s. Passou disso, é bug de teste.

## Estilo

- Arquivo ≤ 400 linhas; função ≤ 40 (alvo 20); no máximo 2 níveis de indentação.
- `mypy --strict`: sem `Any`; `# type: ignore` só com o motivo na mesma linha.
- Nomes em português, como no domínio. Proibidos nomes genéricos (`dados`, `util`, `helper`, `manager`).
- Exceções tipadas do núcleo, com o valor recebido e o formato esperado, mas sem dado sensível. A casca traduz para pt-BR.
- Não apagar comentários de proveniência em refactor.

## Estrutura (alvo)

```
src/gastroepi/
  dominio/       Paciente, HistoricoFamiliar, CPF, datas, validação, gerador de fictícios
  cofre/         Argon2id, chave de dados, gastroepi.chave, recovery key
  auditoria/     elo HMAC, verificação da cadeia e dos dados
  persistencia/  SQLCipher: schema, migrações, repositório, backup conferido, rotação, trava
  estatistica/   contingência, Wilson, Fleiss, Cochran-Armitage, Mantel-Haenszel, qualidade, descritiva
  exportacao/    CSV pt-BR com proteção contra injeção
  servicos/      casos de uso: a única porta das cascas para o núcleo
  ui_qt/         casca PySide6, uma tela por módulo
  cli/           demo, verificar, backup, exportar
tests/<modulo>/ · tests/arquitetura/ · tests/fixtures/
```
