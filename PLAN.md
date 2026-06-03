# Plano de Migração: GastroEpidemio (TS + Rust + Tauri)
### Baseado na Metodologia Spec-Kit (GitHub)

Este plano estabelece as especificações técnicas, princípios arquiteturais e etapas de execução para migrar o sistema GastroEpidemio de Python/NiceGUI para a pilha moderna TypeScript + Rust (usando Tauri v2). 

---

## 📜 1. CONSTITUTION (Princípios e Limites do Projeto)

*   **Soberania dos Dados Clínicos:** O aplicativo continuará operando de forma 100% offline local, sem conexões de rede obrigatórias ou telemetria, mantendo conformidade integral com a LGPD médica.
*   **Criptografia em Repouso Forte:** Dados pessoais sensíveis (CPF) e laudos anatomopatológicos devem permanecer indecifráveis em disco sem a senha mestre de inicialização.
*   **Auditoria Append-Only Verificável:** Qualquer mutação no banco de dados deve produzir um registro indelével na cadeia de auditoria (`hash-chain`), protegida por triggers a nível de banco de dados e hash criptográfico SHA-256.
*   **Fidelidade Estatística:** A transição matemática do StatCalc/Epi Info de Python para Rust não pode sofrer desvios de precisão numérica ou apresentar comportamento indefinido (ex: divisões por zero não tratadas).

---

## 📐 2. SPECIFICATION (Especificações Técnicas de Mapeamento)

### 2.1 Divisão Arquitetural e Fluxo IPC

A reestruturação elimina o interpretador Python e o servidor WebSocket local, usando a arquitetura de IPC (Inter-Process Communication) nativa do Tauri via chamadas fortemente tipadas.

```mermaid
graph TD
    subgraph Frontend [TypeScript Frontend: React ou Vue]
        UI[Interface baseada no NiceGUI]
        State[Controle de estado de formulários]
        Val[Validação e Coerção via Zod]
    end
    subgraph Bridge [Tauri IPC Bridge]
        IPC[Tauri Invoke / Rust Commands]
    end
    subgraph Backend [Tauri Backend: Rust]
        DB[SQLite / rusqlite]
        Crypto[Argon2id + AES-256-GCM]
        Audit[Histórico de Auditoria + Hash-Chain]
        Math[StatCalc Engine: Cochran-Armitage, Wilson, Fleiss via statrs]
    end
    UI -->|Inputs do Usuário| Val
    Val -->|Dados Validados| IPC
    IPC -->|Comando #[tauri::command]| Backend
    DB --> Crypto
    Math --> IPC
```

### 2.2 Camada de Dados e Segurança (Rust)

*   **Banco de Dados:** Utilização do SQLite embutido via crate `rusqlite`. A estrutura original de tabelas será recriada em Rust, contendo as mesmas triggers de restrição de escrita direta na tabela de auditoria.
*   **KDF (Derivação de Chaves):** Substituição do Argon2id (Python) pelo crate `argon2` em Rust, aplicando os mesmos parâmetros conservadores de segurança (`time_cost=3, memory=65536, parallelism=4`).
*   **Cofre Criptográfico (AES-256-GCM):** Criptografia de campos individuais (CPF e Laudo) usando AES-256-GCM (crates `aes-gcm` ou `orion`). *Decisão de design: Não há necessidade de compatibilidade retroativa com o formato Fernet (Python), iniciando a migração com um banco de dados limpo.*
*   **Integridade Semântica e Física:** A rotina de backup preventivo a cada boot e a execução de `PRAGMA integrity_check` serão executadas diretamente pelo Rust através do driver do SQLite com tratamento robusto de locks físicos.

### 2.3 Camada Analítica e Matemática (Rust Engine com `statrs`)

A migração das funções presentes em [estatistica.py](file:///home/mateus/GastroEpidemio/estatistica.py) utilizará o ecossistema matemático de Rust:
*   **Cochran-Armitage Trend Test:** Cálculo do escore $Z$ manual no Rust e p-valor computado via distribuição cumulativa normal padrão obtida a partir do crate `statrs`.
*   **Wilson Score Interval (95%):** Implementado analiticamente em Rust para proporções simples e razões de verossimilhança de ADR (Adenoma Detection Rate) por endoscopista.
*   **Amostragens (Surveys e Fleiss Coorte):** Portabilidade da matemática de Fleiss para cálculo do poder amostral utilizando tipos flutuantes de dupla precisão (`f64`) e funções estatísticas do `statrs`.

### 2.4 Validação e Interface (TypeScript + React)

*   **Zod Schemas:** Substituição do Pydantic v2 ([validacao.py](file:///home/mateus/GastroEpidemio/validacao.py)) por schemas de validação **Zod** no frontend React.
*   **Tratamento de Edge-Cases:** Replicar as garantias do spec-kit:
    *   Coerção rigorosa de inteiros não negativos (rejeitando booleanos `true`/`false` que JS/TS convertem implicitamente em `1`/`0`).
    *   Tratamento de string vazia ou espaços em branco para conversão opcional em `null`.
    *   Normalização de CPFs para string de 11 dígitos e validação de dígitos verificadores (DV).

---

## 🛠️ 3. PLAN (Plano de Implementação / Fases)

### 📈 Fase 1: Scaffold e Core Backend (Rust)
*   [ ] Inicializar o projeto Tauri v2 configurado para TypeScript + React.
*   [ ] Escrever a camada `crypto.rs` (KDF Argon2id + AES-256-GCM).
*   [ ] Criar a camada `db.rs` com migrations SQLite, recriando as tabelas e triggers append-only.
*   [ ] Replicar a validação de integridade física (`PRAGMA`) e cálculo de hash-chain da auditoria em Rust.

### 🧪 Fase 2: Engine Estatística e Fuzzing (Rust com `statrs`)
*   [ ] Implementar o módulo estatístico `math.rs` usando `statrs` para Cochran-Armitage, Wilson e Fleiss.
*   [ ] Implementar testes de propriedade baseados em fuzzing (usando o crate `proptest` para herdar o comportamento do Hypothesis do Python).
*   [ ] Garantir que 100% dos testes unitários estatísticos coincidam com os valores de referência obtidos no Python.

### 💻 Fase 3: Frontend e Integração IPC (TypeScript + React)
*   [ ] Desenvolver os schemas do Zod para pacientes e histórico familiar.
*   [ ] Desenhar a interface em React, mapeando o visual moderno do NiceGUI para componentes nativos React (ex: Tailwind CSS).
*   [ ] Criar os comandos Tauri `#[tauri::command]` para expor operações de CRUD, login com senha mestre, histórico de auditoria e tabelas do StatCalc para o TypeScript.

### 📦 Fase 4: Homologação e Distribuição
*   [ ] Homologar o fluxo de recuperação de chave mestra (recovery key) em TypeScript com tratamento contra falhas.
*   [ ] Executar `tauri build` para gerar executáveis nativos multiplataforma.
*   [ ] Validar que o tamanho do binário final está abaixo do benchmark de **20MB** e que a inicialização ocorre em menos de 1 segundo.
