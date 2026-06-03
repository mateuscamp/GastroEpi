# GastroEpi Implementation Tasks

## 📈 Phase 1: Scaffold and Core Backend (Rust)
- [x] **TSK-1.1:** Initialize the Tauri v2 project structure (`npm create tauri-app@latest . -- --template react-ts`).
- [x] **TSK-1.2:** Implement `crypto.rs` containing KDF Argon2id and AES-256-GCM logic.
- [x] **TSK-1.3:** Setup SQLite database connection (`db.rs`) with schema migrations.
- [x] **TSK-1.4:** Create SQLite schema tables (`pacientes` and `auditoria`).
- [x] **TSK-1.5:** Write database level SQL triggers to lock `auditoria` table as append-only.
- [x] **TSK-1.6:** Implement the audit logging hash-chaining algorithm (SHA-256 link check).
- [x] **TSK-1.7:** Code physical integrity check (`PRAGMA integrity_check`) and backup boot tasks.

## 🧪 Phase 2: Engine Estatística (Rust with `statrs`)
- [x] **TSK-2.1:** Implement Cochran-Armitage Trend Test in `math/cochran_armitage.rs`.
- [x] **TSK-2.2:** Code Wilson confidence intervals (95%) for proportions and LRs in `math/wilson.rs`.
- [x] **TSK-2.3:** Port Fleiss sample size cohort formulas to Rust in `math/fleiss.rs`.
- [x] **TSK-2.4:** Write ADR (Adenoma Detection Rate) and PDR (Polyp Detection Rate) calculator in `math/quality.rs`.
- [x] **TSK-2.5:** Set up unit tests and property-based fuzz tests in Rust using `proptest`.

## 💻 Phase 3: Frontend UI and IPC Commands (TypeScript + React)
- [x] **TSK-3.1:** Setup React application environment with Tailwind CSS and Zod validation.
- [x] **TSK-3.2:** Write Zod schemas matching patient and family history validations, checking CPFs and dates.
- [x] **TSK-3.3:** Implement Tauri commands (`#[tauri::command]`) for auth, CRUD, integrity, and calculations.
- [x] **TSK-3.4:** Design the Main Dashboard, Patient Grid, and Modal Forms.
- [x] **TSK-3.5:** Build the StatCalc interface with manual calculators and DB stats.
- [x] **TSK-3.6:** Build the Audit History panel with real-time integrity verification trigger.

## 📦 Phase 4: Homologation and Distribution
- [x] **TSK-4.1:** Verify end-to-end integration tests for IPC commands.
- [x] **TSK-4.2:** Compile production executables via `tauri build`.
- [x] **TSK-4.3:** Verify bundle footprint (ensure size < 20MB) and test launch speed.
