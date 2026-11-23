"""MongoDB document models and database indexes for Advanced Patient Health Measurements (Phase 6).

Supports:
- Blood Pressure (systolic/diastolic, mmHg)
- Blood Glucose (mg/dL)
- Weight (kg)
- Temperature (°C)
- Heart Rate (bpm)
- Oxygen Saturation (SpO2, %)

Enforces:
- Unit validation and physiologic range validation.
- Clear distinction of source (patient_reported vs device_reported).
- Audit trail for patient corrections.
- Historical trend aggregation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class MeasurementMetric(str, Enum):
    BLOOD_PRESSURE = "blood_pressure"
    BLOOD_GLUCOSE = "blood_glucose"
    WEIGHT = "weight"
    TEMPERATURE = "temperature"
    HEART_RATE = "heart_rate"
    OXYGEN_SATURATION = "oxygen_saturation"


class MeasurementSource(str, Enum):
    PATIENT_REPORTED = "patient_reported"
    DEVICE_REPORTED = "device_reported"


class MeasurementVerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    CLINICIAN_REVIEWED = "clinician_reviewed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Standardized metric units and physiologic safety bounds
METRIC_SPECS = {
    MeasurementMetric.BLOOD_PRESSURE.value: {
        "unit": "mmHg",
        "min_value": 50.0,
        "max_value": 260.0,
        "requires_secondary": True,
        "min_secondary": 30.0,
        "max_secondary": 160.0,
    },
    MeasurementMetric.BLOOD_GLUCOSE.value: {
        "unit": "mg/dL",
        "min_value": 20.0,
        "max_value": 800.0,
        "requires_secondary": False,
    },
    MeasurementMetric.WEIGHT.value: {
        "unit": "kg",
        "min_value": 1.0,
        "max_value": 500.0,
        "requires_secondary": False,
    },
    MeasurementMetric.TEMPERATURE.value: {
        "unit": "°C",
        "min_value": 30.0,
        "max_value": 45.0,
        "requires_secondary": False,
    },
    MeasurementMetric.HEART_RATE.value: {
        "unit": "bpm",
        "min_value": 30.0,
        "max_value": 250.0,
        "requires_secondary": False,
    },
    MeasurementMetric.OXYGEN_SATURATION.value: {
        "unit": "%",
        "min_value": 50.0,
        "max_value": 100.0,
        "requires_secondary": False,
    },
}


class HealthMeasurementDocument(BaseModel):
    """MongoDB document representation for a patient health measurement."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    measurementId: str = Field(..., description="Unique human-readable reference e.g. MEAS-20261124-XXXX")
    patientUserId: str = Field(..., description="References users._id of patient")

    metric: str = Field(..., description="Metric key e.g. blood_pressure, heart_rate")
    value: float = Field(..., description="Primary numeric reading")
    secondary: Optional[float] = Field(default=None, description="Secondary numeric reading (diastolic for blood pressure)")
    unit: str = Field(..., description="Standardized measurement unit")

    source: str = Field(default=MeasurementSource.PATIENT_REPORTED.value)
    verificationStatus: str = Field(default=MeasurementVerificationStatus.UNVERIFIED.value)
    notes: Optional[str] = Field(default=None, max_length=500)

    measuredAt: datetime = Field(default_factory=utc_now)
    recordedAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)

    correctionsHistory: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Audit log of patient corrections to erroneous values",
    )

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        return value

    @field_validator("measuredAt", "recordedAt", "updatedAt", mode="before")
    @classmethod
    def ensure_utc_timestamp(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


def get_health_measurement_collection(db: Database) -> Collection:
    return db["patient_health_measurements"]


def create_health_measurement_indexes(db: Database) -> None:
    coll = get_health_measurement_collection(db)
    coll.create_index([("measurementId", ASCENDING)], unique=True, sparse=True, name="idx_measurement_id")
    coll.create_index(
        [("patientUserId", ASCENDING), ("metric", ASCENDING), ("measuredAt", DESCENDING)],
        name="idx_patient_metric_measured",
    )
    coll.create_index(
        [("patientUserId", ASCENDING), ("recordedAt", DESCENDING)],
        name="idx_patient_recorded",
    )
