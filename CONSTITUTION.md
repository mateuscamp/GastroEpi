# GastroEpi Constitution

## Core Principles

### I. Local Sovereignty (Soberania Local)
Every feature must function 100% offline, executing locally without any external network dependency, tracking, or telemetry. All user data, databases, and logs are kept strictly on the local filesystem, ensuring medical data privacy and compliance with LGPD.

### II. Security-in-Depth (Segurança em Profundidade)
All sensitive patient data (CPF) and histological findings (laudos) must be encrypted at rest using AES-256-GCM. The encryption key must be derived from a user-provided master password via the KDF Argon2id. No plaintext passwords or keys may be stored on the disk.

### III. Verifiable Append-Only Audit (Auditoria Append-Only Verificável)
All CRUD operations on clinical data must be logged to a database-enforced append-only audit table. Triggers at the database level must block manual updates or deletions. The audit log must use a cryptographic SHA-256 hash-chain, where each entry's hash depends on the preceding entry's hash, allowing instant integrity verification.

### IV. Mathematical & Statistical Fidelity (Fidelidade Estatística)
All calculations in the epidemiological module (StatCalc) must use high-precision numerical algorithms (`f64`). Statistical routines (Cochran-Armitage trend test, Wilson score intervals, and Fleiss sample size formulas) must match benchmark scientific results and handle mathematical boundaries gracefully (no crash on divisions by zero).

### V. Strict Frontend Validation (Validação Rigorosa)
Input validation must occur at the boundaries of the UI. Types must be strictly coerced (using Zod), preventing implicit conversions (e.g., rejecting boolean true/false values for integer fields). CPFs must be sanitized and verified for digits validity. Dates must be parsed and stored in ISO 8601 format (`YYYY-MM-DD`).

---

## Technical Constraints

- **Backend Stack:** Rust (for SQLite, encryption, audit verification, and stat calculations).
- **Frontend Stack:** TypeScript + React + Tailwind CSS (compiled via Tauri).
- **Communication:** Strongly typed Tauri IPC (Commands) without local WebSockets.
- **Database:** SQLite (`rusqlite`) running in WAL mode with robust busy timeouts.

---

**Version**: 1.0.0 | **Ratified**: 2026-06-03
