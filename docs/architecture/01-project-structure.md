# Planned project structure

Documentation only at this stage — directories below are created as each phase actually
implements them, not scaffolded ahead of need.

```
isc-project/
  backend/
    app/
      auth/               # authentication
      authorization/      # RBAC + resource-based checks
      consent/             # consent grant/revoke, gates REST and realtime
      realtime/            # NEW: SSE gateway + Connection Registry
      api/v1/               # REST routers
      ingest/               # manual entry + simulated device stream endpoints
      alerts/               # alert engine
      ai/
        classical/           # rolling z-score + Isolation Forest baseline
        quantum/              # async hybrid autoencoder, benchmarking harness
      audit/                # audit log writer (tamper-evident)
      models/                # SQLAlchemy models
      db/                    # session/engine setup
    alembic/                # migrations
    tests/
  frontend/
    src/
  database/
    synthetic_data/
      vitals_generator/     # NEW: dedicated time-series synthetic generator (37.1)
  quantum_ml/
    notebooks/               # offline benchmarking only, never wired into the live app
  docs/
    architecture/
    adr/
  docker-compose.yml
  .env.example
```

## Env config additions (Section 41)
```
REALTIME_TRANSPORT=sse
REALTIME_MAX_CONNECTIONS_PER_USER=<int>
REALTIME_MESSAGE_RATE_LIMIT=<per-second or per-minute limit>
QUANTUM_MAX_QUBITS=<4-8>
```
