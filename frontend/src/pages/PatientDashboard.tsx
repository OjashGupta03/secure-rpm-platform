import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { useRealtime } from "../hooks/useRealtime";
import {
  MEASUREMENT_TYPES,
  type ConsentOut,
  type MeasurementOut,
  type MeasurementType,
  type ProviderDirectoryEntry,
} from "../api/types";

const UNIT_HINT: Record<MeasurementType, string> = {
  heart_rate: "bpm",
  bp_systolic: "mmHg",
  bp_diastolic: "mmHg",
  spo2: "%",
  body_temperature: "C",
  blood_glucose: "mg/dL",
  respiratory_rate: "breaths/min",
  weight: "kg",
};

export function PatientDashboard() {
  const { user, refresh } = useAuth();
  const [measurements, setMeasurements] = useState<MeasurementOut[]>([]);
  const [measurementType, setMeasurementType] = useState<MeasurementType>("heart_rate");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deviceBusy, setDeviceBusy] = useState(false);
  const [providers, setProviders] = useState<ProviderDirectoryEntry[]>([]);
  const [consents, setConsents] = useState<ConsentOut[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [consentError, setConsentError] = useState<string | null>(null);
  const [consentBusy, setConsentBusy] = useState(false);

  const { events, connected } = useRealtime(true);

  async function loadMeasurements() {
    const rows = await api.get<MeasurementOut[]>("/measurements?limit=20");
    setMeasurements(rows);
  }

  async function loadConsentData() {
    const [providerRows, consentRows] = await Promise.all([
      api.get<ProviderDirectoryEntry[]>("/auth/providers"),
      api.get<ConsentOut[]>("/consent"),
    ]);
    setProviders(providerRows);
    setConsents(consentRows);
    if (!selectedProviderId && providerRows.length > 0) {
      setSelectedProviderId(providerRows[0].id);
    }
  }

  useEffect(() => {
    loadMeasurements();
    loadConsentData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function grantConsent() {
    if (!selectedProviderId) return;
    setConsentError(null);
    setConsentBusy(true);
    try {
      await api.post("/consent", { provider_id: selectedProviderId });
      await loadConsentData();
    } catch (err) {
      setConsentError(err instanceof ApiError ? err.message : "Failed to grant consent");
    } finally {
      setConsentBusy(false);
    }
  }

  async function revokeConsent(consentId: string) {
    setConsentError(null);
    setConsentBusy(true);
    try {
      await api.delete(`/consent/${consentId}`);
      await loadConsentData();
    } catch (err) {
      setConsentError(err instanceof ApiError ? err.message : "Failed to revoke consent");
    } finally {
      setConsentBusy(false);
    }
  }

  // Slow-loop quantum re-score events refresh the affected measurement's analysis.
  useEffect(() => {
    const latest = events.find((e) => e.event === "quantum_rescore_available" || e.event === "new_alert");
    if (latest) loadMeasurements();
  }, [events]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/measurements", { measurement_type: measurementType, value: Number(value) });
      setValue("");
      await loadMeasurements();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleDevice() {
    if (!user) return;
    setDeviceBusy(true);
    try {
      await api.patch("/auth/me/device", {
        simulated_device_enabled: !user.simulated_device_enabled,
        synthetic_persona: user.synthetic_persona,
      });
      await refresh();
    } finally {
      setDeviceBusy(false);
    }
  }

  return (
    <div className="dashboard">
      <p className="banner">SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION</p>
      <section className="card">
        <h2>Simulated device stream</h2>
        <p>
          {user?.simulated_device_enabled
            ? "Enabled — a synthetic wearable feed is being ingested automatically every couple of minutes."
            : "Disabled — submit measurements manually below, or enable the simulated device stream."}
        </p>
        <button onClick={toggleDevice} disabled={deviceBusy}>
          {user?.simulated_device_enabled ? "Disable simulated device" : "Enable simulated device"}
        </button>
        <p className="realtime-status">
          Realtime channel: {connected ? "connected" : "connecting..."}
        </p>
      </section>

      <section className="card">
        <h2>Submit a measurement (manual entry)</h2>
        <form onSubmit={onSubmit} className="inline-form">
          <select value={measurementType} onChange={(e) => setMeasurementType(e.target.value as MeasurementType)}>
            {MEASUREMENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <input
            type="number"
            step="0.1"
            placeholder={UNIT_HINT[measurementType]}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
          <button type="submit" disabled={submitting}>
            {submitting ? "Submitting..." : "Submit"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h2>Provider access (consent)</h2>
        <p>Only providers you grant active consent to can see your measurements and alerts.</p>
        {providers.length === 0 ? (
          <p>No providers have registered yet.</p>
        ) : (
          <div className="inline-form">
            <select value={selectedProviderId} onChange={(e) => setSelectedProviderId(e.target.value)}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name} ({p.email})
                </option>
              ))}
            </select>
            <button onClick={grantConsent} disabled={consentBusy}>
              Grant access
            </button>
          </div>
        )}
        {consentError && <p className="error">{consentError}</p>}
        <ul>
          {consents.map((c) => {
            const provider = providers.find((p) => p.id === c.provider_id);
            return (
              <li key={c.id}>
                {provider?.display_name ?? c.provider_id} — {c.status}
                {c.status === "active" && (
                  <button onClick={() => revokeConsent(c.id)} disabled={consentBusy}>
                    Revoke
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="card">
        <h2>Live events</h2>
        {events.length === 0 && <p>No realtime events yet.</p>}
        <ul className="event-list">
          {events.map((e, i) => (
            <li key={i}>
              <strong>{e.event}</strong> — {JSON.stringify(e.data)}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Recent measurements</h2>
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Value</th>
              <th>Recorded at</th>
              <th>Source</th>
              <th>Risk</th>
              <th>Explanation</th>
            </tr>
          </thead>
          <tbody>
            {measurements.map((m) => (
              <tr key={m.id} className={m.analysis ? `risk-${m.analysis.risk_level}` : ""}>
                <td>{m.measurement_type.replace(/_/g, " ")}</td>
                <td>
                  {m.value} {m.unit}
                </td>
                <td>{new Date(m.recorded_at).toLocaleString()}</td>
                <td>{m.source.replace(/_/g, " ")}</td>
                <td>{m.analysis?.risk_level ?? "—"}</td>
                <td>{m.analysis?.explanation ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {measurements[0]?.analysis && (
          <>
            <p className="disclaimer">{measurements[0].analysis.banner}</p>
            <p className="disclaimer">{measurements[0].analysis.quantum_banner}</p>
          </>
        )}
      </section>
    </div>
  );
}
