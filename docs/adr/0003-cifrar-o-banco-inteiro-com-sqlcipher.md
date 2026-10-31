# 0003 — Cifrar o arquivo inteiro do banco com SQLCipher, com a chave de dados separada da senha

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** Integridade e confidencialidade do dado clínico (Princípios I–III da CONSTITUTION)

## Contexto

Na v0.1.16 a cifra é por campo (AES-256-GCM). Só nome, CPF, laudo e snapshots de
auditoria são cifrados. Ficam legíveis no `.db` e nos backups: prontuário, data do
exame, idade, sexo, pólipos, indicação, examinador, comorbidades, sintomas e histórico
familiar. Prontuário + data + idade + sexo bastam para reidentificar um paciente.

A chave dos dados é derivada direto da senha, e a recovery key é essa mesma chave em
base64. Por isso trocar a senha mudaria a chave de tudo. A mesma chave cifra os campos
e assina a cadeia HMAC.

O dono rejeitou a cifra parcial e escolheu cifrar o arquivo inteiro com SQLCipher. Só
há dados fictícios, então não há migração. O ADR-0002 deixou esta decisão para antes
da Fase 2.

Evidência de empacotamento, o risco que fazia preferir outra opção. Em 2026-10-31 o PyPI tem:
- `sqlcipher3` 0.6.4 (binding oficial, publicado em 2026-10-13), com wheels `win_amd64`
  para cp313 e cp314;
- `apsw-sqlite3mc` 3.54.0.0 (2026-10-13) e `sqlcipher3-wheels` 0.5.7 (comunitário, 2026-01),
  também com wheels para Windows;
- `sqlcipher3-binary`, sem wheel para Windows.

Quantum: 1, inalterado. O dono do dado continua sendo `persistencia`. O arquivo de
chave `gastroepi.chave` passa a fazer parte do dado.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| A. Cifra por campo (como hoje) | SQL sobre os campos em claro; só stdlib | Reidentificação pelos campos em claro; todo campo novo depende de alguém lembrar de cifrar | O dono rejeitou |
| B. Registro inteiro cifrado (AES-GCM) + índice cego HMAC | Só `cryptography`; tag de autenticação por registro | Perde filtro, ordenação e constraints do SQL; cripto própria para manter; catálogos e auditoria precisam de esquema à parte | Mais cripto própria para proteger menos que o arquivo inteiro |
| C. SQLCipher via `apsw-sqlite3mc` | Acompanha cada versão do SQLite; vários cifradores | API do APSW, não DB-API: o código deixa de ser `sqlite3` padrão | Plano B se o `sqlcipher3` falhar no spike |
| **D. SQLCipher via `sqlcipher3`** | Arquivo inteiro cifrado (páginas, índices, schema, WAL); HMAC por página detecta adulteração feita sem a chave; mesma API do `sqlite3`; formato aberto em ferramentas SQLCipher | Dependência nativa no instalador; wheel Windows recente; quem tem a senha pode editar o banco por fora | — |

## Decisão

1. **Banco:** SQLCipher 4, aberto só por `persistencia` via `sqlcipher3`. A primeira
   instrução de toda conexão é `PRAGMA key` com a chave bruta (`x'…'`). Isso dispensa o
   PBKDF2 do SQLCipher, porque a derivação é nossa. Também se aplica
   `temp_store = MEMORY`, para que nenhuma tabela temporária vá para o disco.
2. **Chave de dados:** 256 bits aleatórios gerados na criação do cofre. Nunca é derivada
   da senha.
3. **Arquivo de chave:** `gastroepi.chave` fica ao lado do banco, em JSON versionado,
   com o sal, os parâmetros do Argon2id (t=3, m=64 MiB, p=4) e a chave de dados
   embrulhada em AES-256-GCM pela chave da senha. Trocar a senha só re-embrulha a
   chave; o banco não é recifrado.
4. **Recovery key:** é a própria chave de dados, em base32 sem caracteres ambíguos,
   blocos de 8 e dígito de verificação. Abre o banco mesmo sem o `gastroepi.chave` e
   recria esse arquivo com senha nova. "Gerar nova recovery key" faz `PRAGMA rekey`
   para uma chave nova, o que invalida a anterior.
5. **Chave da auditoria:** 256 bits aleatórios guardados em `metadados`, dentro do banco
   cifrado. É independente da chave de dados e sobrevive a um rekey sem quebrar a cadeia.
6. **Sem cifra por campo.** Tudo dentro do arquivo já está cifrado. Uma segunda camada
   usaria a mesma chave e quebraria a busca e a ordenação.
7. **Backup:** API de backup entre duas conexões SQLCipher com a mesma chave, então o
   backup sai cifrado. O `gastroepi.chave` é copiado junto. Rotação e verificação ficam
   no ADR-0004.
8. **Saída em claro:** a única é a exportação CSV, iniciada pelo usuário e com aviso na tela.

## Consequências

**Ganha:**
- Nenhum campo legível no `.db`, no `-wal` ou nos backups, inclusive prontuário, idade,
  comorbidades e auditoria.
- Adulteração feita sem a chave é barrada pelo HMAC de página antes da verificação da cadeia.
- O SQL volta a funcionar sobre todos os campos (busca por nome, ordenação, `CHECK`,
  `FOREIGN KEY`), o que o Rust tinha perdido ao cifrar o nome.
- Trocar a senha é instantâneo, e a recovery key passa a ter um ciclo de vida próprio.
- Chave da cifra e chave da cadeia ficam separadas.
- A cripto escrita por nós encolhe para embrulhar uma chave.

**Perde:**
- Dependência nativa nova no instalador, com wheel para Windows publicado há semanas.
- O `sqlite3` da stdlib e as ferramentas comuns deixam de abrir o banco. Depurar exige
  o `sqlcipher` de linha de comando ou o DB Browser for SQLCipher, com a chave.
- Dois arquivos para guardar. Sem o `gastroepi.chave`, só a recovery key abre o banco;
  sem os dois, perde-se tudo.
- A recovery key é a chave dos dados: se vazar, quem tiver o arquivo lê tudo até que se
  gere uma nova.
- A CONSTITUTION (Princípio II) cita AES-256-GCM por campo, mas o SQLCipher 4 usa
  AES-256-CBC + HMAC-SHA512 por página. Isso entra na emenda prevista para a Fase 0.

**Aceito conscientemente:**
- Quem tem a senha pode editar o banco por fora e refazer a cadeia, porque a chave HMAC
  está dentro do banco. Com isso, a cadeia passa a proteger contra bug e corrupção, não
  contra o próprio dono da senha.
- O Python não garante zerar a memória: a chave fica na memória enquanto o cofre estiver
  aberto. O bloqueio automático por inatividade (Fase 5) encurta essa janela.
- Revisitar se o spike da Fase 0 falhar no Windows com o app congelado (plano B:
  `apsw-sqlite3mc` com o cifrador compatível com SQLCipher), ou se uma versão nova do
  Python ficar sem wheel do `sqlcipher3`.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| ★ Nada legível no disco | Teste: banco e backup com fictícios conhecidos; procura nome, CPF, prontuário, laudo e comorbidade nos bytes do `.db`, do `-wal`, dos backups e do `gastroepi.chave` | CI | Qualquer achado |
| O arquivo é SQLCipher | Teste: o `sqlite3` da stdlib não lê o arquivo; o cabeçalho não começa com `SQLite format 3` | CI | Abre, ou cabeçalho em claro |
| ★ Adulteração sem chave | Teste: troca 1 byte no meio de uma página → leitura e `PRAGMA cipher_integrity_check` | CI | Nenhum dos dois acusa |
| Chave errada | Teste: senha errada e recovery key errada | CI | O banco abre |
| Recovery sem arquivo de chave | Teste: apaga `gastroepi.chave` → abre pela recovery key → recria com senha nova | CI | Não abre ou não recria |
| Senha nova não recifra | Teste: hash do `.db` igual antes e depois da troca de senha | CI | Hash muda |
| Rekey preserva a cadeia | Teste: gerar nova recovery key → verificação da cadeia e dos dados | CI | Alguma inconsistência, ou a recovery antiga ainda abre |
| Só `persistencia` abre o banco | import-linter: pacote exceto `persistencia` ↛ `sqlcipher3`, `sqlite3` (estende o contrato do ADR-0002) | CI | Contrato quebrado |
| Empacotável no Windows | Spike na Fase 0: `windows-latest` + Python 3.13 congela um script que cria, fecha e reabre um banco SQLCipher | CI | Falha ou wheel ausente |

Regra derivada no `AGENTS.md`: "Só `persistencia` importa `sqlcipher3`" e as linhas de chave na seção Segurança.

## Notas

Autor: Mateus Campelo · Criado em: 2026-10-31 · Aprovado em: 2026-10-31
Estende: 0002
