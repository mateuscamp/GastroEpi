# GastroEpi — Plano de Endurecimento de Segurança (Security Hardening)

> **Status:** CONCLUÍDO — Todas as etapas de endurecimento foram implementadas e validadas com sucesso.
> **Origem:** auditoria de segurança/anti-corrupção de 2026-06-03 (23 testes Rust passando + verificação empírica de cifra em repouso, detecção de corrupção e detecção de adulteração da auditoria).
> **Para:** execução concluída na ordem planejada.

A ordem vai do **menor risco / sem migração de dados** para o **mais invasivo**. Não pule passos: o Passo 3 mexe em índice, busca e migração dos 10k registros existentes — só encare depois que 1 e 2 estiverem verdes.

---

## Passo 1 — Proteção do arquivo no Windows (TSK-5.1)

**Lacuna:** `proteger_arquivo()` em `src-tauri/src/db.rs` aplica `chmod 0600` no Unix, mas é **no-op no Windows** — justamente o alvo de produção principal. No Windows o `gastroepi.db` e os backups ficam com permissões herdadas da pasta, legíveis por outros usuários da máquina.

**Por quê primeiro:** isolado, sem migração de dados, sem mudança na constituição. Bom aquecimento e ganho real no SO mais usado.

**Arquivos:** `src-tauri/src/db.rs` (`#[cfg(not(unix))] fn proteger_arquivo`), `src-tauri/Cargo.toml`.

**Sub-passos:**
1. Trocar o stub no-op do Windows por uma implementação real de ACL restringindo o arquivo ao usuário atual (ex.: crate `windows`/`windows-acl`, ou `icacls` via `std::process::Command` como fallback best-effort).
2. Aplicar tanto no `gastroepi.db` quanto em cada arquivo de backup criado em `realizar_backup`.
3. Falhar de forma graciosa (best-effort + log), nunca derrubar o app se a ACL não puder ser aplicada.

**Critérios de aceite:**
- No Windows, o arquivo recém-criado fica acessível só ao usuário corrente (verificar com `icacls`).
- No Linux/macOS o comportamento atual (`0600`) permanece intacto.
- Nenhum teste existente quebra; idealmente um teste `#[cfg(windows)]` cobrindo a ACL.

**Impacto na constituição:** nenhum (reforça Princípios I e II).

---

## Passo 2 — Cadeia de auditoria com HMAC (TSK-5.2)

**Lacuna:** `calcular_hash_auditoria` usa **SHA-256 puro (não-chaveado)**. Detecta corrupção acidental e adulteração ingênua (✅ verificado), mas um atacante com acesso de escrita ao arquivo pode **recalcular toda a cadeia adiante** e forjar um histórico consistente. Um HMAC com a chave do cofre torna a cadeia inforjável sem a senha-mestra.

**Por quê depois do 1:** contido a `crypto.rs` + `db.rs`, mas exige **versionamento da cadeia** (registros antigos foram gravados com SHA-256) e **emenda à constituição**.

**Arquivos:** `src-tauri/src/crypto.rs`, `src-tauri/src/db.rs` (`auditar`, `verificar_integridade`, catálogos), `CONSTITUTION.md`.

**Sub-passos:**
1. Adicionar `calcular_hmac_auditoria(chave, ...)` usando HMAC-SHA256 (crate `hmac` + `sha2`) com a chave do cofre (`Cofre::key()`).
2. Versionar o algoritmo: gravar um marcador de versão por entrada (ex.: coluna `hash_algo` ou prefixo `v2:` em `hash_atual`) para que `verificar_integridade` valide entradas antigas com SHA-256 e novas com HMAC, sem quebrar a cadeia histórica.
3. **Decisão de migração** (consultar Mateus): manter as entradas legadas como estão (cadeia mista versionada) **ou** re-selar a partir de um ponto âncora assinado. Não reescrever silenciosamente o histórico — as triggers append-only e o próprio princípio de auditoria proíbem isso.
4. Tratar o caso "cofre bloqueado": a verificação HMAC precisa da chave; definir o comportamento quando o banco está bloqueado (hoje `verificar_integridade` roda sem o cofre).

**Critérios de aceite:**
- Adulterar uma entrada e recalcular o SHA-256 adiante **não** produz cadeia válida sem a chave.
- Bancos antigos (cadeia SHA-256) continuam verificáveis sem falso positivo.
- Testes novos: detecção de forja HMAC + compatibilidade retroativa.

**Impacto na constituição:** **emenda o Princípio III** (que hoje exige literalmente "cryptographic SHA-256 hash-chain"). Atualizar o texto do Princípio III e subir a versão em `CONSTITUTION.md`.

---

## Passo 3 — Cifrar nome e demais PII em repouso (TSK-5.3)

**Lacuna:** apenas CPF e laudo são cifrados. **Nome, nº de prontuário, idade, sexo, pólipo e data ficam em texto claro no `.db`** (confirmado lendo os bytes do arquivo). Quem obtiver o arquivo lê o nome dos 10k pacientes.

**Por quê por último:** é o mais invasivo. Cifrar o `nome` quebra `idx_pacientes_nome`, o `ORDER BY nome`, e a busca `buscar_por_termo` (LIKE em `nome`). Exige migração dos registros existentes e repensar a indexação.

**Arquivos:** `src-tauri/src/db.rs` (schema, `cifrar_campo`/`decifrar_campo`, `para_paciente`, `cadastrar`, `editar`, `listar`, `buscar_por_termo`, índice, hash de integridade), possivelmente migração dedicada.

**Sub-passos:**
1. **Decisão de escopo** (consultar Mateus): cifrar só o `nome`, ou também prontuário/idade/sexo? Definir o conjunto de PII a proteger.
2. Resolver a **busca**: campo cifrado não pode usar LIKE/índice direto. Opções — busca em memória pós-decifragem (simples, ok para ~10k), ou índice cego/blind index (HMAC determinístico do termo normalizado) para busca exata sem expor o valor.
3. Migrar os dados existentes: ler em claro → cifrar → regravar, **dentro de transação e auditado**, com backup automático antes.
4. Recalcular `_integridade_hash` dos snapshots? Não — o hash é sobre o valor lógico em claro, que não muda; validar que `verificar_integridade_dados` continua verde após a migração.
5. Ajustar exportação CSV e qualquer query que ordene/filtre por `nome`.

**Critérios de aceite:**
- O `nome` (e demais PII escolhidas) não aparece em texto claro nos bytes do `.db` (mesmo teste usado na auditoria).
- Busca por nome/prontuário continua funcionando.
- Migração idempotente e reversível via backup; `verificar_integridade_dados` verde antes e depois.

**Impacto na constituição:** **estende o Princípio II** (hoje exige cifrar só CPF e laudos). Atualizar Princípio II e citar a meta LGPD do Princípio I como justificativa; subir a versão em `CONSTITUTION.md`.

---

### Resumo da sequência

| Passo | Tarefa | Risco | Migração de dados | Emenda à constituição |
|------|--------|-------|-------------------|------------------------|
| 1 | ACL do arquivo no Windows | Baixo | Não | Não |
| 2 | Auditoria com HMAC | Médio | Versionar cadeia | Princípio III |
| 3 | Cifrar nome/PII em repouso | Alto | Sim (10k registros) | Princípio II |
