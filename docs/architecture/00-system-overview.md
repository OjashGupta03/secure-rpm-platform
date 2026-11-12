# System Overview — Modular Monolith

Academic RPM prototype. SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION throughout.
AI outputs are monitoring/research information only, never a diagnosis.

```mermaid
graph TB
    subgraph Client
        WebApp["React/TS Frontend"]
    end
    subgraph Backend["FastAPI Modular Monolith"]
        AuthN["Authentication"]
        AuthZ["Authorization + Consent Engine"]
        RTG["Realtime Gateway (SSE)"]
        API["REST API Layer (/api/v1)"]
        Ingest["Ingest Handler"]
        AlertEngine["Alert Engine"]
        ClassicalAI["Classical Baseline AI (fast loop)"]
        QuantumAI["Quantum Research Module (slow loop, async)"]
        AuditLog["Audit Logging"]
    end
    subgraph Data
        PG[("PostgreSQL")]
        Queue[["Background Job Queue"]]
    end
    subgraph SyntheticData["Synthetic Data (offline generation)"]
        Gen["Vitals Generator"]
        Synthea["Synthea (optional, demographics)"]
    end

    WebApp -->|REST| API
    WebApp -->|SSE stream, one-directional| RTG
    API --> AuthN --> AuthZ
    API --> Ingest --> AlertEngine
    AlertEngine -->|fast loop push, less than 1s target| RTG
    AlertEngine --> ClassicalAI
    ClassicalAI --> Queue
    Queue --> QuantumAI
    QuantumAI -->|slow loop update push| RTG
    AuthZ -. gates every connection/event .-> RTG
    API --> PG
    AuditLog --> PG
    ClassicalAI --> AuditLog
    QuantumAI -->|execution metadata only, never raw vitals| AuditLog
    Gen --> PG
    Synthea -.-> PG
```

## Principles (unchanged from spec)
Least privilege, defense in depth, secure-by-design, privacy by design, zero trust,
backend-enforced authorization, data minimization, explicit consent, secure key management,
tamper-evident auditing, secure error handling.

## Module boundaries
- **Realtime Gateway** sits beside Authentication/Authorization/Consent as its own trust
  boundary — every SSE connection and every event dispatched through it passes the same
  auth+authz+consent pipeline as REST (see `02-realtime-dataflow.md`).
- **Classical Baseline AI** is fully independent of the quantum module and is the only
  thing the fast loop (ingest → alert push) waits on.
- **Quantum Research Module** never blocks the fast loop; runs as a background job and
  pushes an *update* event when its (benchmarked, non-authoritative) score is ready.
