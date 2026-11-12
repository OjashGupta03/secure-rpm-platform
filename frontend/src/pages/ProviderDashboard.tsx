import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useRealtime } from "../hooks/useRealtime";
import type { AlertOut, ConsentedPatientOut } from "../api/types";

export function ProviderDashboard() {
  const [patients, setPatients] = useState<ConsentedPatientOut[]>([]);
  const [alerts, setAlerts] = useState<AlertOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { events, connected } = useRealtime(true);

  async function loadPatients() {
    const rows = await api.get<ConsentedPatientOut[]>("/consent/my-patients");
    setPatients(rows);
  }

  async function loadAlerts() {
    const rows = await api.get<AlertOut[]>("/alerts");
    setAlerts(rows);
  }

  useEffect(() => {
    loadPatients();
    loadAlerts();
  }, []);

  useEffect(() => {
    const latest = events.find((e) => e.event === "new_alert" || e.event === "scope_revoked");
    if (latest) {
      loadAlerts();
      loadPatients();
    }
  }, [events]);

  async function acknowledgeAlert(alertId: string) {
    setError(null);
    try {
      await api.patch(`/alerts/${alertId}`, { status: "acknowledged" });
      await loadAlerts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update alert");
    }
  }

  return (
    <div className="dashboard">
      <p className="banner">SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION</p>
      <p className="realtime-status">Realtime channel: {connected ? "connected" : "connecting..."}</p>

      <section className="card">
        <h2>My patients (active consent)</h2>
        {patients.length === 0 ? (
          <p>
            No patients have granted you consent yet. Ask a patient to grant consent to your
            provider account from their dashboard.
          </p>
        ) : (
          <ul>
            {patients.map((p) => (
              <li key={p.patient_id}>{p.display_name}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Alerts</h2>
        {error && <p className="error">{error}</p>}
        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Message</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className={`severity-${a.severity}`}>
                <td>{patients.find((p) => p.patient_id === a.patient_id)?.display_name ?? a.patient_id}</td>
                <td>{a.severity}</td>
                <td>{a.status}</td>
                <td>{a.message}</td>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td>
                  {a.status === "open" && (
                    <button onClick={() => acknowledgeAlert(a.id)}>Acknowledge</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="disclaimer">
          AI-generated information is for monitoring/research purposes and is not a medical diagnosis.
        </p>
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
    </div>
  );
}

