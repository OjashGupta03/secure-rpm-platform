"""Input validation ranges (Section 27). Demonstration/configuration thresholds,
not medical guidelines — used only to reject obviously invalid sensor/manual-entry
input before it reaches storage or the AI pipeline."""

from app.models.measurement import MeasurementType

VALID_RANGES: dict[MeasurementType, tuple[float, float]] = {
    MeasurementType.heart_rate: (20, 250),
    MeasurementType.bp_systolic: (50, 260),
    MeasurementType.bp_diastolic: (30, 180),
    MeasurementType.spo2: (50, 100),
    MeasurementType.body_temperature: (30, 43),
    MeasurementType.blood_glucose: (20, 600),
    MeasurementType.respiratory_rate: (4, 60),
    MeasurementType.weight: (2, 400),
}

UNITS: dict[MeasurementType, str] = {
    MeasurementType.heart_rate: "bpm",
    MeasurementType.bp_systolic: "mmHg",
    MeasurementType.bp_diastolic: "mmHg",
    MeasurementType.spo2: "%",
    MeasurementType.body_temperature: "C",
    MeasurementType.blood_glucose: "mg/dL",
    MeasurementType.respiratory_rate: "breaths/min",
    MeasurementType.weight: "kg",
}


def is_within_valid_range(measurement_type: MeasurementType, value: float) -> bool:
    lo, hi = VALID_RANGES[measurement_type]
    return lo <= value <= hi
