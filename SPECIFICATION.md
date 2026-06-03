# GastroEpi System Specification

## Feature Overview

A local clinical and epidemiological management system for colonoscopy and colorectal cancer (CRC) screening. It provides patient management with field-level encryption, database audit logging with hash-chain verification, and advanced analytical calculations (inspired by Epi Info's StatCalc).

---

## Functional Requirements

### 1. Database Security & Initialization (SEC)
- **FR-1.1 (Master Password Setup):** Upon first run, the system must prompt the user to set a master password (minimum 8 characters). It must derive an encryption key via Argon2id and create an encrypted canary payload.
- **FR-1.2 (Recovery Key):** After setting the password, the system must display a Fernet-compatible recovery key formatted in blocks of 8 characters separated by spaces.
- **FR-1.3 (Unlock Canary):** On subsequent boots, the user must input the master password. The system must verify it by decrypting the canary.
- **FR-1.4 (Field-level Encryption):** Sensible fields (`cpf` and `resultado_histopatologico`) must be encrypted before storage using AES-256-GCM.

### 2. Patient Management (PAT)
- **FR-2.1 (Unique Prontuário):** Every patient record must have a unique internal record ID (Prontuário, mandatory).
- **FR-2.2 (CPF Validation):** If provided, the CPF must be normalized (11 digits) and checked against digit-validity algorithm.
- **FR-2.3 (Dates):** Data and UI inputs for dates must accept `dd/mm/aaaa` and store in ISO 8601 `YYYY-MM-DD`.
- **FR-2.4 (Clinical Fields):** Support comorbidades (case-insensitive list), histórico familiar (degree of relationship 1st/2nd/3rd), polyp count (integer ≥ 0), and histopathology text.

### 3. Auditing & Integrity (AUD)
- **FR-3.1 (Append-only Audit Log):** Every action (CADASTRAR, EDITAR, EXCLUIR) must write a row to the audit table with UTC timestamp, username, and JSON snapshots.
- **FR-3.2 (SQLite Triggers):** The database schema must contain SQLite triggers preventing any UPDATE or DELETE operations on the `auditoria` table.
- **FR-3.3 (Hash-chaining):** Each row in the audit log must contain a SHA-256 hash calculated from its fields combined with the hash of the preceding row.
- **FR-3.4 (Integrity Check):** The system must provide a routine to verify the entire hash-chain and check the semantic coherence of current patient states against the audit snapshots.

### 4. Epidemiological Analytics (StatCalc)
- **FR-4.1 (Diagnostic Test Acuracy):** Standard 2x2 contingency matrix (Sensitivity, Specificity, VPP, VPN, LR+, LR-) with 95% Wilson confidence intervals.
- **FR-4.2 (Sample Size):**
  - Survey: Sample size calculations for finite and infinite populations.
  - Comparative: Cohort/case-control power calculations using Fleiss formula.
- **FR-4.3 (Cochran-Armitage Trend Test):** Trend test calculating z-score and p-value for ordinal categories (e.g. age groups vs. polyps presence).
- **FR-4.4 (Quality Indicators):** Compute ADR (Adenoma Detection Rate) and PDR (Polyp Detection Rate) grouped by Endoscopista, showing 95% Wilson intervals. Highlight ADR < 25% with visual warnings.

### 5. Export (EXP)
- **FR-5.1 (CSV Export):** Export patient records to UTF-8 BOM CSV using `;` as separator (pt-BR Excel friendly).
- **FR-5.2 (CSV Injection Protection):** Sanitize cells starts with `=`, `+`, `-`, `@` by prefixing with `'`.

---

## User Scenarios (Acceptance Criteria)

### Scenario 1: Setup Master Password
- **Given** an uninitialized database,
- **When** the app starts,
- **Then** a configuration modal must prompt for a master password twice.
- **And** displaying the recovery key upon success.

### Scenario 2: Registering a Patient with Invalid CPF
- **Given** a logged-in user in the Patient Form,
- **When** submitting a record with an invalid CPF (e.g. `111.111.111-11`),
- **Then** the validation schema must fail and display a pt-BR validation error.
- **And** block database insertion.

### Scenario 3: Verify Audit Integrity
- **Given** a database where an external tool directly modified a patient row (bypassing the app),
- **When** running "Verificar Integridade",
- **Then** the hash-chain validation must fail.
- **And** report the first corrupted record ID and timestamp.
