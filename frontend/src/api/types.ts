export type UserRole = "patient" | "provider" | "admin";

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  simulated_device_enabled: boolean;
  synthetic_persona: string;
}

export type MeasurementType =
  | "heart_rate"
  | "bp_systolic"
  | "bp_diastolic"
  | "spo2"
  | "body_temperature"
  | "blood_glucose"
  | "respiratory_rate"
  | "weight";

export const MEASUREMENT_TYPES: MeasurementType[] = [
  "heart_rate",
  "bp_systolic",
  "bp_diastolic",
  "spo2",
  "body_temperature",
  "blood_glucose",
  "respiratory_rate",
  "weight",
];

export interface AnalysisOut {
  classical_score: number;
  quantum_score: number | null;
  combined_score: number | null;
  risk_level: "normal" | "watch" | "elevated" | "high";
  explanation: string;
  contributing_features: Record<string, unknown>;
  evaluation_protocol_version: string | null;
  banner: string;
  quantum_banner: string;
}

export interface MeasurementOut {
  id: string;
  measurement_type: MeasurementType;
  value: number;
  unit: string;
  source: string;
  recorded_at: string;
  data_label: string;
  analysis?: AnalysisOut | null;
}

export interface AlertOut {
  id: string;
  patient_id: string;
  severity: "low" | "medium" | "high";
  status: "open" | "acknowledged" | "resolved";
  message: string;
  created_at: string;
}

export interface ProviderDirectoryEntry {
  id: string;
  display_name: string;
  email: string;
}

export interface ConsentedPatientOut {
  patient_id: string;
  display_name: string;
  consent_id: string;
}

export interface ConsentOut {
  id: string;
  patient_id: string;
  provider_id: string;
  status: string;
  scope: string[] | null;
}
