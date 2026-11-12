# Threat model additions (STRIDE) — realtime + quantum

| # | Category | Threat | Mitigation |
|---|---|---|---|
| 1 | Spoofing | SSE connection hijacking via stolen session cookie | Same session validation pipeline as REST at connect time; Secure/HttpOnly/SameSite cookies; connection dropped if session invalidated |
| 2 | Information Disclosure | Push-channel consent-revocation race: an event is enqueued for delivery before a just-processed revocation takes effect | Realtime Connection Registry re-checks `authorized_patient_ids` at event-dispatch time, invalidated synchronously within the revocation's own request/transaction (see `02-realtime-dataflow.md`) |
| 3 | Information Disclosure | Health data leaking into transport-layer logs or push payloads | Push messages carry event metadata only (id, severity, timestamp) — never raw vitals; full detail fetched via consent-checked REST GET |
| 4 | Denial of Service | Quantum-job-pattern abuse: resource-abusive circuit submissions (large qubit count / shot count / depth) used to exhaust simulator capacity | Per-user rate limiting/queueing on quantum job submission; every job's qubit count, shot count, circuit depth, and requesting user logged to audit; bounded `QUANTUM_MAX_QUBITS` and strict timeout in prototype mode |
| 5 | Elevation of Privilege | Stale-privilege SSE connection continues delivering events after a role downgrade or session expiry | Registry entry's role/scope re-validated per event dispatch, not cached for connection lifetime; heartbeat/reconnect never silently re-authorizes a stale session |
| 6 | Repudiation | No record of who connected/disconnected to the realtime channel, or of rejected connection attempts | New audit event types: `REALTIME_CONNECTION_OPENED`, `REALTIME_CONNECTION_CLOSED`, `REALTIME_CONNECTION_REJECTED` |
| 7 | Tampering / Repudiation | Quantum job audit trail could leak raw medical data if implemented naively | Quantum execution logs store job ID, circuit hash, timestamps, resource usage, and a reference to the input record — never the raw vitals values |

These are additions to the existing threat model (Section 42 of the spec); base rows
(auth bypass, IDOR, injection, CSRF, etc.) are unchanged from the original.
