# GastroEpi Constitution

## Core Principles

### I. Local Sovereignty (Soberania Local)
Every feature must function 100% offline, executing locally without any external network dependency, tracking, or telemetry. The application opens no network socket, not even on 127.0.0.1 (ADR-0002). All user data, databases, and logs are kept strictly on the local filesystem, ensuring medical data privacy and compliance with LGPD.

### II. Security-in-Depth (Segurança em Profundidade)
The entire database file is encrypted at rest with SQLCipher 4, including every patient field, the catalogs, the audit table, the WAL, and every backup (ADR-0003). The SQLCipher key is a random 256-bit data key, never derived from the password. It is stored on disk only wrapped (AES-256-GCM) by a key derived from the user's master password via the KDF Argon2id (t=3, m=64 MiB, p=4). The recovery key is the data key itself, shown once and never written to disk. No plaintext passwords or keys may be stored on the disk. The only plaintext exit is a CSV export started by the user.

### III. Verifiable Append-Only Audit (Auditoria Append-Only Verificável)
All CRUD operations on clinical data must be logged, in the same transaction as the change, to a database-enforced append-only audit table. Triggers at the database level must block manual updates or deletions. The audit log is an HMAC-SHA256 hash-chain keyed by a dedicated audit key stored inside the encrypted database, so that a data-key rotation does not break the chain. It allows instant, authenticated integrity verification of both the chain and the current patient states.

### IV. Mathematical & Statistical Fidelity (Fidelidade Estatística)
All calculations in the epidemiological module (`estatistica`) use 64-bit floating point. Every public statistical routine (Cochran-Armitage trend test, Wilson score intervals, Fleiss sample size, contingency tables, Mantel-Haenszel, quality indicators) must have a test against a cited reference value (R, Epi Info, or a published article) and must handle mathematical boundaries gracefully (no crash on divisions by zero).

### V. Strict Domain Validation (Validação Rigorosa)
Input validation happens once, in the domain layer (`dominio`, strict pydantic), and every shell (desktop, CLI) uses it; no shell re-implements a rule. Types must be strictly coerced, preventing implicit conversions (e.g., rejecting boolean true/false values for integer fields). CPFs must be sanitized and verified for digits validity. Dates are entered as `dd/mm/aaaa` and stored in ISO 8601 format (`YYYY-MM-DD`).

---

## Technical Constraints

- **Language:** Python 3.13, managed with `uv` (ADR-0002).
- **Architecture:** one executable and one database; a pure core (`dominio`, `cofre`, `auditoria`, `persistencia`, `estatistica`, `exportacao`, `servicos`) and two shells (`ui_qt`, `cli`). Boundaries are enforced by import-linter in CI.
- **Desktop shell:** PySide6 (Qt), single process, no local server.
- **Database:** SQLite through SQLCipher 4 (`sqlcipher3`), opened only by `persistencia`, in WAL mode with busy timeouts.
- **Legacy:** the Tauri v0.1.16 code (`src-tauri/`, TypeScript frontend) is a frozen oracle until parity, then removed (tag `v0.1.16` preserves it).

---

## Session Startup Protocol (Agent)

No startup check. Commands and rules live in `AGENTS.md`. The former `cargo audit` check for GTK4 bindings was removed with the move to Python; dependency vulnerabilities are checked by `pip-audit` in CI.

---

**Version**: 2.0.0 | **Ratified**: 2026-06-04 | **Amended**: 2026-10-31 (ADR-0002, ADR-0003)
