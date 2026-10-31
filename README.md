# GastroEpi

App desktop **offline** para registro de colonoscopia e epidemiologia de câncer colorretal.
O médico cadastra pacientes e exames lesão por lesão, acompanha os indicadores de qualidade
(taxa de detecção de adenoma, de pólipo) e roda as calculadoras de epidemiologia sobre o
próprio banco, sem nada sair da máquina.

Escrito em **Python 3.13** com **PySide6 (Qt)**, **SQLCipher 4**, **pydantic estrito** e
**numpy/scipy**. A v0.1.16 era um app Tauri (Rust + React); a reescrita está descrita no
[ADR-0002](docs/adr/0002-reescrever-em-python-com-nucleo-puro-e-casca-qt.md) e no
[plano de fases](docs/PLANO-REESCRITA-PYTHON.md). O código antigo está na tag `v0.1.16`.

> Todo dado do repositório, dos testes e do modo demo vem de um gerador de pacientes
> fictícios com semente. Nenhum dado real.

## O que ele faz

- **Cadastro clínico estruturado:** paciente, histórico familiar, exame e cada lesão em
  listas fechadas (ADR-0004). Texto livre (`observacao`, `laudo_texto`) nunca entra em cálculo.
- **Indicadores de qualidade** por examinador, prevalência de pólipo, frequências e
  estratificação do próprio banco.
- **Calculadoras:** tabela 2×2 (OR, RR, qui-quadrado de Pearson e Yates, exato de Fisher),
  teste diagnóstico com intervalos de Wilson, tamanho de amostra (inquérito e comparativo de
  Fleiss), tendência de Cochran-Armitage, Mantel-Haenszel e qui-quadrado R×C.
- **Integridade verificável:** cada mutação grava um elo de auditoria na mesma transação;
  a verificação acusa a primeira entrada adulterada.
- **Durabilidade:** checagem na abertura, backup conferido antes de ganhar o nome, rotação
  por data, cópia externa e recusa de pasta sincronizada (ADR-0005).
- **Exportação:** CSV pt-BR anônimo para análise, com proteção contra injeção de fórmula.

## Arquitetura

Monólito modular: **1 executável, 1 banco**. Um núcleo puro e duas cascas finas.

```
         ui_qt (PySide6)        cli (demo · verificar · backup · exportar)
                 \                 /
                  └──── servicos ──┘        casos de uso: a única porta das cascas
                         │
   dominio · cofre · auditoria · persistencia · estatistica · exportacao
```

| Módulo | Papel |
|---|---|
| `dominio` | Paciente, exame, lesão, CPF, datas, validação (pydantic estrito). Não faz I/O nem importa outro módulo. |
| `cofre` | Argon2id (t=3, m=64 MiB, p=4), chave de dados embrulhada, recovery key. |
| `auditoria` | Calcula e confere a cadeia HMAC-SHA256. Pura: quem grava é a persistência. |
| `persistencia` | SQLCipher: schema, migrações idempotentes, repositório, backup conferido, rotação, trava. |
| `estatistica` | Contingência, Wilson, Fleiss, Cochran-Armitage, Mantel-Haenszel, qualidade, descritiva. |
| `exportacao` | CSV pt-BR com proteção contra injeção. |
| `servicos` | Casos de uso; a casca não vê banco, cofre nem SQL. |

As fronteiras não são convenção: o **import-linter** as quebra no CI. O núcleo nunca importa
Qt; as cascas só importam `servicos` e os tipos de `dominio`; só `persistencia` importa o
`sqlcipher3`; nenhum módulo importa `socket`, `http` ou `urllib`, e a suíte roda com
`pytest --disable-socket`. As regras completas estão no [`AGENTS.md`](AGENTS.md) e os
princípios na [`CONSTITUTION.md`](CONSTITUTION.md).

### Segurança do dado

- **O arquivo inteiro é cifrado** com SQLCipher 4: campos, catálogos, auditoria, WAL e
  backups ([ADR-0003](docs/adr/0003-cifrar-o-banco-inteiro-com-sqlcipher.md)). O `sqlite3`
  da stdlib não abre o banco, e um byte trocado é acusado pelo HMAC de página.
- A chave do banco é aleatória (256 bits), **nunca derivada da senha**. Em disco ela só
  existe embrulhada (AES-256-GCM) por uma chave Argon2id da senha. A recovery key aparece uma
  vez e nunca é gravada.
- **Auditoria append-only:** triggers do banco bloqueiam `UPDATE` e `DELETE` na tabela de
  auditoria, e os elos formam uma cadeia HMAC-SHA256 com chave própria, que sobrevive à
  rotação da chave de dados. Um teste de estado do hypothesis faz mutações aleatórias e
  confere cadeia e dados no fim.

### Estatística com referência

Toda função pública de `estatistica` tem teste marcado `@pytest.mark.referencia`, com o valor
de referência citado na docstring (Princípio IV). Os valores vêm do **R 4.5.1** (`epitools`,
`DescTools`), gerados por [`ferramentas/referencias_r/gerar.R`](ferramentas/referencias_r/gerar.R);
o CI reroda o script e falha se a saída divergir do fixture versionado. A paridade com a
v0.1.16 está congelada em `tests/fixtures/`, com as divergências de propósito documentadas
no plano (ex.: p < 1e-16, que a v0.1.16 arredondava para 0).

## Como rodar

Requer [uv](https://docs.astral.sh/uv/). O Python certo vem da `.python-version`.

```bash
uv sync
```

```bash
uv run gastroepi demo
```

O modo demo cria um cofre de pacientes fictícios numa pasta temporária, já desbloqueado; a
senha aparece no terminal. `uv run gastroepi` abre o cofre de verdade (no Windows, em
`%LOCALAPPDATA%\GastroEpi`). Os outros comandos: `verificar`, `backup` e `exportar`.

```bash
uv run poe check
```

A checagem completa: `ruff format` e `ruff check`, `mypy --strict`, os contratos do
import-linter e o pytest com cobertura ≥ 90% (100% dos ramos no `dominio`). A suíte roda em
menos de 60 s, headless (`QT_QPA_PLATFORM=offscreen`), sem rede e sem senha real. Os testes da
casca usam `pytest-qt` contra serviços reais em `tmp_path`, e o banco é sempre SQLite real,
nunca mock.

## Instalador Windows

Gerado no CI a cada PR e a cada tag `v*`
([ADR-0006](docs/adr/0006-empacotar-com-pyinstaller-onedir-e-inno-setup.md)): PyInstaller
*onedir* em modo janela e instalador Inno Setup **por usuário**, sem pedir administrador. O
CI instala em silêncio no `windows-latest` e roda o `GastroEpi.exe --smoke` instalado, um
autoteste que cria, fecha e reabre um cofre cifrado. É o portão do PR, com os tetos do ADR-0002:

| Medido no CI (Fase 6) | Valor | Limite |
|---|---|---|
| Instalador | 62,5 MB | 250 MB |
| `--smoke` do instalado | 6,2 s | 8 s |

O instalador não é assinado: o SmartScreen pede **Mais informações → Executar assim mesmo**.
O roteiro de aceitação manual está em [`docs/ROTEIRO-WINDOWS.md`](docs/ROTEIRO-WINDOWS.md).

Para congelar localmente:

```bash
uv run --group empacotamento pyinstaller --noconfirm empacotamento/gastroepi.spec
```

## Decisões (ADRs)

| ADR | Decisão |
|---|---|
| [0001](docs/adr/0001-monolito-modular-com-nucleo-sem-tauri.md) | Núcleo Rust sem Tauri (substituído pelo 0002) |
| [0002](docs/adr/0002-reescrever-em-python-com-nucleo-puro-e-casca-qt.md) | Reescrever em Python: um executável, núcleo puro e casca Qt |
| [0003](docs/adr/0003-cifrar-o-banco-inteiro-com-sqlcipher.md) | Cifrar o banco inteiro com SQLCipher, chave de dados separada da senha |
| [0004](docs/adr/0004-registrar-o-exame-em-dados-estruturados.md) | Exame em dados estruturados: lesão por lesão, qualidade e listas fechadas |
| [0005](docs/adr/0005-durabilidade-do-cofre.md) | Durabilidade: checagem na abertura, backup conferido, rotação e cópia externa |
| [0006](docs/adr/0006-empacotar-com-pyinstaller-onedir-e-inno-setup.md) | PyInstaller onedir e Inno Setup por usuário |

Cada ADR termina numa tabela de Governança: a checagem executável que o CI roda para que a
decisão não se perca.

## Licença

[GPL-3.0](LICENSE).
