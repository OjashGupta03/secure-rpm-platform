# Secure Real-Time RPM Platform — Research Prototype

> SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION.
> This is an academic/research prototype. It is **not** a clinically validated medical
> device, not FDA approved, not HIPAA certified. AI-generated information is for
> monitoring/research purposes only and is never a diagnosis. See
> [docs/architecture](docs/architecture) for the full design rationale.

## What this is

A secure, real-time-capable Remote Patient Monitoring platform with three roles
(patient, provider, administrator), a transparent classical anomaly-detection baseline,
and an experimental hybrid classical-quantum research module — built per the phased,
STOP-and-approve master specification in `RPM-Hybrid-QML-Master-Spec-v2.md`, then built
out directly per follow-up instruction.

- **Backend:** FastAPI + PostgreSQL + SQLAlchemy/Alembic, session-based auth (Argon2id),
  AES-256-GCM field-level encryption on measurement values, hash-chained audit log.
- **Realtime:** Server-Sent Events gateway (ADR-002), consent-gated, with synchronous
  revocation propagation to open connections.
- **Classical AI:** Rolling Z-score + Isolation Forest ensemble (fast loop, gates alerts).
- **Quantum AI:** Hybrid classical-quantum autoencoder (angle encoding + RealAmplitudes,
  Qiskit 2.0 / Aer 0.17 / Qiskit ML 0.9, V2 primitives), trained offline, run as a bounded
  async job (slow loop) — never blocks the fast loop, never presented without the
  classical score and the experimental-research disclaimer alongside it.
- **Synthetic data:** Dedicated vitals generator (`database/synthetic_data/vitals_generator`)
  with persona baselines, diurnal variation, and labeled injected anomalies.
- **Frontend:** React + TypeScript + Vite. Patient dashboard (manual entry, simulated
  device toggle, consent management, live SSE feed) and provider dashboard (consented
  patients, alerts, acknowledge).

Every module and design decision is validated end-to-end in this repo — not just written:
the backend was exercised through real HTTP requests (register/login/measurement
ingest/alert/consent revoke), the quantum training+inference pipeline was actually run,
and the frontend was driven through a real browser for both patient and provider roles,
including the live SSE alert push and consent-revocation flow.

## Prerequisites

- Docker + Docker Compose (recommended path), **or** Python 3.11+ and Node 20+ for running
  services natively.

## Quick start (Docker Compose)

```bash
cp .env.example .env
# generate a real encryption key and paste it into .env:
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

Then, in a separate shell, seed demo accounts and run the mandatory quantum
training/benchmark pass (Section 9.3 — never skip this; the async quantum job has no
model to run inference with until it's been trained at least once):

```bash
docker compose exec backend python -m scripts.seed_demo
docker compose exec backend python -m app.ai.quantum.training
```

Demo accounts (see script output): `demo.patient@example.com`,
`demo.provider@example.com` (pre-consented to the patient), `demo.admin@example.com`.

## Running natively (no Docker)

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit DATABASE_URL to a local Postgres, or sqlite:///./dev.db for a quick try
alembic upgrade head
python -m app.ai.quantum.training     # trains + benchmarks the quantum module, required once
uvicorn app.main:app --reload

# Frontend (separate shell)
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend
pip install -r requirements.txt pytest
pytest tests/ -v
```

Covers: password hashing, field encryption round-trip, classical scorer behavior
(normal/spike/insufficient-history), and hash-chain audit log integrity (including a
tamper-detection test). The quantum module and full HTTP flow were validated manually
during development (see conversation record) rather than committed as automated tests,
since qiskit-aer is a heavy dependency for a CI smoke suite — recommended next step if
this moves beyond prototype.

## Project layout

See [docs/architecture/01-project-structure.md](docs/architecture/01-project-structure.md).

## Design decisions and their rationale

See [docs/architecture](docs/architecture) and [docs/adr](docs/adr) — real-time transport
choice (SSE), the consent-revocation-vs-open-connection mechanism, the threat model
additions for the realtime and quantum modules, and the quantum benchmarking protocol
(Section 9.3: parameter-matched classical control, k-fold CV, paired significance test —
this prototype's own run found **no** statistically significant quantum advantage over
the classical control, consistent with the current published literature cited in the
spec).

## Known limitations (prototype scope)

- Audit log integrity assumes a single writer (read-last-hash-then-write, no row locking)
  — correct for this prototype's traffic, would need `SELECT … FOR UPDATE` or a proper
  append-only log service under real concurrent write load.
- Messaging (Section 29) and file uploads (Section 31) are modeled in the database
  (`messages` table) but have no API routes or UI yet.
- Administrator role has no dashboard by design (Section 5.3: no default health-data
  access) — nothing to build until an admin-scoped, metadata-only view is specified.
- Field-level encryption uses a single static KEK from environment config — real envelope
  encryption with a KMS-managed key hierarchy is a production hardening item, not
  implemented here (documented as a deliberate prototype simplification in
  `backend/app/core/crypto.py`).
