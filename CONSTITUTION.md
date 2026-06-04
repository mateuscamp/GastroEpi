# GastroEpi Constitution

## Core Principles

### I. Local Sovereignty (Soberania Local)
Every feature must function 100% offline, executing locally without any external network dependency, tracking, or telemetry. All user data, databases, and logs are kept strictly on the local filesystem, ensuring medical data privacy and compliance with LGPD.

### II. Security-in-Depth (Segurança em Profundidade)
All sensitive patient data (CPF, name/nome) and histological findings (laudos) must be encrypted at rest using AES-256-GCM, ensuring patient privacy and LGPD compliance (supporting Principle I). The encryption key must be derived from a user-provided master password via the KDF Argon2id. No plaintext passwords or keys may be stored on the disk.

### III. Verifiable Append-Only Audit (Auditoria Append-Only Verificável)
All CRUD operations on clinical data must be logged to a database-enforced append-only audit table. Triggers at the database level must block manual updates or deletions. The audit log must use a cryptographic HMAC-SHA256 hash-chain (linked to the vault key), while supporting legacy SHA-256 hash-chain entries for backward compatibility, allowing instant, authenticated integrity verification.

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

## Session Startup Protocol (Agent)

> **MANDATORY:** At the start of every new session working on this project, the agent MUST run the following check **once** before any other task:

```bash
cd src-tauri && cargo audit 2>&1 | grep -E "^(Crate|Warning|Title|ID):" | grep -A3 "gtk\|gdk\|atk"
```

**If the output shows NO results** (i.e., the GTK3 binding warnings for `gtk`, `gdk`, `atk`, `gdkwayland`, `gdkx11` are gone), it means Tauri has migrated to GTK4. In that case:

```bash
cd src-tauri && cargo update
```

Then commit with message: `chore(deps): cargo update — GTK4 bindings now available`.

**If the warnings are still present**, skip silently and proceed with the session normally. Do NOT repeat this check mid-session.

---

**Version**: 1.3.0 | **Ratified**: 2026-06-04
