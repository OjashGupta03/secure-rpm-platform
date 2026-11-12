# Real-time send/receive flow (required diagram #11)

## Fast loop + slow loop

```mermaid
sequenceDiagram
    participant Device as Simulated Device / Manual Entry
    participant API as REST Ingest API
    participant Val as Validation
    participant Classical as Classical Baseline (fast loop)
    participant Alert as Alert Engine
    participant SSE as Realtime Gateway (SSE)
    participant UI as Patient/Provider Browser
    participant Queue as Background Job Queue
    participant Quantum as Quantum Module (slow loop)
    participant DB as PostgreSQL

    Device->>API: POST /measurements (synthetic vitals)
    API->>Val: validate ranges/schema
    Val->>DB: persist measurement
    Val->>Classical: score (rolling z-score + Isolation Forest)
    Classical->>DB: persist classical_score, explanation
    Classical->>Alert: evaluate thresholds
    alt anomaly detected
        Alert->>DB: create alert record
        Alert->>SSE: publish alert event (metadata only, no raw vitals)
        SSE-->>UI: push "new alert" (id, severity, timestamp)
        UI->>API: GET /alerts/{id} (full detail, consent-checked)
    end
    Classical->>Queue: enqueue quantum re-score job (async, never blocks response)
    Queue->>Quantum: dequeue, run autoencoder on simulator (bounded qubits/shots/timeout)
    Quantum->>DB: persist quantum_score, combined_score, benchmark/eval_protocol_version
    Quantum->>SSE: publish "quantum re-score available" event (reference only)
    SSE-->>UI: push update notification
    UI->>API: GET /measurements/{id}/analysis (classical_score + quantum_score + combined + banner)
```

Fast loop target: ingest → validation → classical score → alert push, under 1s, and never
waits on the quantum module. Slow loop is best-effort seconds-to-minutes; UI shows
"classical: available now" / "quantum research score: pending → available".

## Consent revocation vs. an open SSE connection

```mermaid
sequenceDiagram
    participant Provider as Provider or Patient Browser
    participant API as REST API
    participant ConsentSvc as Consent Service
    participant Registry as Realtime Connection Registry
    participant SSE as Open SSE Connection (provider session)

    Provider->>API: DELETE /consent/{patient_id}
    API->>ConsentSvc: revoke consent record (single DB transaction)
    ConsentSvc->>Registry: on commit, invalidate authorized_patient_ids for any open<br/>connections scoped to (provider, patient)
    Registry->>SSE: connection's per-event filter now excludes this patient
    SSE-->>Provider: close stream OR emit "scope_revoked" and stop future sends for that patient
    ConsentSvc-->>API: 200 OK
    API-->>Provider: consent revoked confirmation
    Note over Registry,SSE: Applied synchronously within the same request cycle that<br/>processes the revocation — not on next reconnect or heartbeat.
```

### Mechanism
- `Realtime Connection Registry`: in-process map, `session_id -> {user_id, role, authorized_patient_ids}`.
- Every event about to be yielded by an SSE generator is filtered against the registry entry's
  current `authorized_patient_ids`, re-read at dispatch time — not cached for the connection's
  lifetime.
- The consent-revocation endpoint, inside the same DB transaction/request that commits the
  revocation, calls into the registry to update (or close) any matching open connections
  before returning its HTTP response. No polling delay, no reliance on the client disconnecting.
- Single-process prototype: in-process registry is sufficient (per spec's "don't add a broker
  unless the job queue already needs one" rule). If the background job queue later requires
  a broker (Redis/etc.) for the quantum module, reuse it to fan out revocation signals across
  workers rather than adding a second piece of infrastructure.
