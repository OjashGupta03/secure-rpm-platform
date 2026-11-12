# ADR-002: Real-time push transport

- **Decision:** Server-Sent Events (SSE) for the server→client push channel.
- **Reason:** No client→server real-time messages are required (all ingest — manual entry and simulated device stream — goes through REST POST per Section 14A.1 of the spec). SSE is HTTP-native, simpler to authenticate/authorize/rate-limit than WebSocket, and simpler to enforce synchronous consent-revocation against (a single async generator per connection vs. a bidirectional socket).
- **Alternatives considered:** WebSocket — bidirectional, more infrastructure, would be justified if the client ever needs to send real-time messages (e.g. live chat) on the same channel as vitals/alerts. Deferred; the Realtime Gateway module boundary (`backend/app/realtime/`) is designed so WebSocket could replace SSE later without touching the auth/consent/alert-engine layers above it.
- **Status:** Accepted (Phase 1, approved by user 2026-08-24).
