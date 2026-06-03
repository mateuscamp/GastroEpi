# GastroEpi

**GastroEpi** é um sistema desktop local e offline-first para gerenciamento clínico, endoscópico e epidemiológico de colonoscopia e rastreamento de câncer colorretal (CRC). Construído com a moderna stack **TypeScript + React + Tailwind CSS + Rust + Tauri v2**.

---

## 🚀 Funcionalidades Principais

*   **🔒 Segurança Extrema (LGPD):** 100% offline. Criptografia em repouso de dados pessoais sensíveis (CPF) e laudos de biópsia usando AES-256-GCM com chaves derivadas de senha mestre via KDF Argon2id.
*   **⛓️ Cadeia de Auditoria Verificável (Hash-Chain):** Registros de todas as operações (criar, editar, excluir) gravados em tabela SQLite append-only protegida por triggers e encadeados por hashes SHA-256. Detecção imediata de adulterações externas.
*   **📊 StatCalc Engine (Epi Info Rust):**
    *   Tabela de contingência 2x2 com Odds Ratio, Risco Relativo, Qui-Quadrado (Pearson, Yates) e Teste Exato de Fisher.
    *   Acurácia diagnóstica (Sensibilidade, Especificidade, VPP, VPN, Razão de Verossimilhança) com intervalos de confiança de Wilson de 95%.
    *   Cálculo de tamanho amostral (survey com correção de população finita e coorte comparativa via fórmula de Fleiss).
    *   Teste de Tendência Linear Cochran-Armitage.
    *   Acompanhamento de Indicadores de Qualidade (ADR e PDR) por endoscopista com avisos visuais.
*   **📤 Exportação Segura:** Geração de relatórios CSV formatados para Excel (pt-BR) com proteção integrada contra CSV Injection.


---

## 📥 Instalação e Configuração

Para obter o código fonte e instalar as dependências do projeto localmente:

### 1. Clonar o repositório
Escolha o protocolo de sua preferência (SSH ou HTTPS):

```bash
# Via SSH (Recomendado)
git clone git@github.com:mateuscamp/GastroEpi.git
cd GastroEpi

# Ou via HTTPS
git clone https://github.com/mateuscamp/GastroEpi.git
cd GastroEpi
```

### 2. Instalar dependências de frontend
```bash
npm install
```

---

## 🛠️ Requisitos de Ambiente

*   **Node.js** (versão 18+) e **npm**
*   **Rust** (cargo e compilador `rustc` versão 1.75+)
*   Bibliotecas do sistema necessárias para compilação do Tauri (como `webkit2gtk-4.1` ou `webkit2gtk-4.0` no Linux, dependendo da distribuição).

---

## 💻 Comandos Úteis

### 1. Ambiente de Desenvolvimento
Para rodar o aplicativo localmente com hot-reload no frontend e recompilação automática do backend Rust:
```bash
npm run tauri dev
```

### 2. Compilar Executável de Produção
Para compilar a versão final otimizada do executável desktop:
```bash
npm run tauri build
```
O executável compilado de produção estará localizado em:
*   **Linux:** `src-tauri/target/release/tauri-app` ou pacotes `.deb`/`.rpm` na pasta `src-tauri/target/release/bundle/`.

### 3. Rodar Testes Unitários e de Propriedade
Os testes estatísticos e de criptografia estão implementados em Rust. Para rodá-los:
```bash
cd src-tauri
cargo test
```

### 4. Build do Frontend
Para buildar estaticamente apenas os arquivos do frontend React + TypeScript:
```bash
npm run build
```

---

## 📂 Estrutura de Diretórios Importante

*   `src/`: Contém a interface em React e TypeScript.
    *   [App.tsx](file:///home/mateus/GastroEpi/src/App.tsx): Dashboard de controle principal (LockScreen, Cadastro Clínico, StatCalc e Auditoria).
    *   [validation.ts](file:///home/mateus/GastroEpi/src/validation.ts): Esquemas de validação do Zod (CPF brasileiro, datas e pre-processamento).
*   `src-tauri/`: Contém a infraestrutura nativa e segurança em Rust.
    *   [src/crypto.rs](file:///home/mateus/GastroEpi/src-tauri/src/crypto.rs): Algoritmos de encriptação, KDF e canary de segurança.
    *   [src/db.rs](file:///home/mateus/GastroEpi/src-tauri/src/db.rs): Driver SQLite, migrations, triggers de auditoria e rotinas de integridade.
    *   [src/math/](file:///home/mateus/GastroEpi/src-tauri/src/math/): Engine estatística e analítica pura.
