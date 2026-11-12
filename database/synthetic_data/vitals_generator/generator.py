"""Dedicated synthetic vitals time-series generator (Section 37.1).

SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION.

Produces per-patient baseline vitals for a persona, with diurnal variation and sensor
noise, and injects labeled synthetic anomalies (spikes, sustained drift, dropout) at a
configurable rate — giving classical/quantum models and test suites ground truth.
Reproducible via a fixed random seed.
"""

import dataclasses
import datetime
import enum
import math
import random


class Persona(str, enum.Enum):
    normotensive_adult = "normotensive_adult"
    hypertensive_adult = "hypertensive_adult"
    post_surgical_recovery = "post_surgical_recovery"


class AnomalyType(str, enum.Enum):
    none = "none"
    spike = "spike"
    sustained_drift = "sustained_drift"
    sensor_dropout = "sensor_dropout"


# Plausible physiological bounds used purely to make synthetic data statistically
# realistic (Section 4) — NOT a source of clinical thresholds.
PERSONA_BASELINES = {
    Persona.normotensive_adult: {
        "heart_rate": (72, 6),
        "bp_systolic": (118, 6),
        "bp_diastolic": (76, 5),
        "spo2": (98, 1),
        "body_temperature": (36.8, 0.2),
        "blood_glucose": (95, 8),
        "respiratory_rate": (15, 2),
        "weight": (72, 0.3),
    },
    Persona.hypertensive_adult: {
        "heart_rate": (80, 7),
        "bp_systolic": (148, 8),
        "bp_diastolic": (94, 6),
        "spo2": (97, 1),
        "body_temperature": (36.9, 0.2),
        "blood_glucose": (110, 10),
        "respiratory_rate": (16, 2),
        "weight": (85, 0.3),
    },
    Persona.post_surgical_recovery: {
        "heart_rate": (92, 9),
        "bp_systolic": (128, 9),
        "bp_diastolic": (82, 6),
        "spo2": (95, 2),
        "body_temperature": (37.4, 0.4),
        "blood_glucose": (105, 12),
        "respiratory_rate": (19, 3),
        "weight": (78, 0.4),
    },
}

# Mirrors backend/app/ingest/validation.py's VALID_RANGES. Injected anomalies (spikes,
# drift) are deliberately extreme but must still land inside what the backend's own
# input validation accepts — otherwise the "anomaly" is silently rejected before it ever
# reaches the AI pipeline, instead of being scored and flagged as intended.
PLAUSIBLE_BOUNDS = {
    "heart_rate": (20, 250),
    "bp_systolic": (50, 260),
    "bp_diastolic": (30, 180),
    "spo2": (50, 100),
    "body_temperature": (30, 43),
    "blood_glucose": (20, 600),
    "respiratory_rate": (4, 60),
    "weight": (2, 400),
}

UNITS = {
    "heart_rate": "bpm",
    "bp_systolic": "mmHg",
    "bp_diastolic": "mmHg",
    "spo2": "%",
    "body_temperature": "C",
    "blood_glucose": "mg/dL",
    "respiratory_rate": "breaths/min",
    "weight": "kg",
}


@dataclasses.dataclass
class SyntheticMeasurement:
    measurement_type: str
    value: float | None  # None on dropout
    unit: str
    recorded_at: datetime.datetime
    anomaly_label: AnomalyType
    data_label: str = "SYNTHETIC / DEMO DATA — NOT REAL PATIENT INFORMATION"


def _diurnal_factor(hour: float) -> float:
    """Mild day/night variation, peaking mid-afternoon."""
    return 0.03 * math.sin((hour - 6) / 24 * 2 * math.pi)


class VitalsGenerator:
    def __init__(self, persona: Persona, seed: int, anomaly_rate: float = 0.05):
        self.persona = persona
        self.rng = random.Random(seed)
        self.anomaly_rate = anomaly_rate
        self._drift_state: dict[str, float] = {}

    def _pick_anomaly(self) -> AnomalyType:
        if self.rng.random() >= self.anomaly_rate:
            return AnomalyType.none
        return self.rng.choice([AnomalyType.spike, AnomalyType.sustained_drift, AnomalyType.sensor_dropout])

    def generate_window(
        self, start: datetime.datetime, count: int, interval_seconds: int
    ) -> list[SyntheticMeasurement]:
        baselines = PERSONA_BASELINES[self.persona]
        out: list[SyntheticMeasurement] = []
        for i in range(count):
            ts = start + datetime.timedelta(seconds=i * interval_seconds)
            hour = ts.hour + ts.minute / 60
            anomaly = self._pick_anomaly()
            for mtype, (mean, std) in baselines.items():
                value = mean * (1 + _diurnal_factor(hour)) + self.rng.gauss(0, std)

                label = AnomalyType.none
                if anomaly == AnomalyType.spike and mtype in ("heart_rate", "bp_systolic", "respiratory_rate"):
                    value += self.rng.choice([-1, 1]) * std * self.rng.uniform(4, 7)
                    label = AnomalyType.spike
                elif anomaly == AnomalyType.sustained_drift:
                    drift = self._drift_state.get(mtype, 0.0) + std * 0.15
                    self._drift_state[mtype] = drift
                    value += drift
                    label = AnomalyType.sustained_drift
                elif anomaly == AnomalyType.sensor_dropout and mtype == "spo2":
                    out.append(
                        SyntheticMeasurement(mtype, None, UNITS[mtype], ts, AnomalyType.sensor_dropout)
                    )
                    continue

                lo, hi = PLAUSIBLE_BOUNDS[mtype]
                value = max(lo, min(hi, value))
                out.append(SyntheticMeasurement(mtype, round(value, 2), UNITS[mtype], ts, label))
        return out


def generate_patient_history(
    persona: Persona, seed: int, days: int = 3, interval_seconds: int = 120, anomaly_rate: float = 0.05
) -> list[SyntheticMeasurement]:
    """Mimics a continuous wearable's cadence (~2 minutes, per Section 37.1)."""
    gen = VitalsGenerator(persona, seed, anomaly_rate)
    start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    count = int(days * 24 * 3600 / interval_seconds)
    return gen.generate_window(start, count, interval_seconds)
