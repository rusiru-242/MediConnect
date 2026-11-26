"""Health Tracking & Vitals Analytics Service (Phase 6).

Implements:
1. Advanced health measurement capture with range and unit validation.
2. Physiologic safety alert screening.
3. Patient measurement correction with an immutable audit trail.
4. Deterministic trend analytics (7-day average, 30-day average, min/max, delta).
5. Conversational NLP interpretation for English and Romanized Sinhala inquiries.
"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional
import uuid

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.health_measurement import (
    METRIC_SPECS,
    HealthMeasurementDocument,
    MeasurementMetric,
    MeasurementSource,
    MeasurementVerificationStatus,
    get_health_measurement_collection,
    utc_now,
)
from app.models.user import UserRole
from app.schemas.clinical_workflow import (
    CorrectHealthMeasurementRequest,
    HealthMeasurementListResponse,
    HealthMeasurementResponse,
    HealthTrendsResponse,
    MetricTrendSummary,
    RecordHealthMeasurementRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.clinical_safety_service import ClinicalSafetyService



def normalize_measurement(doc: Dict[str, Any]) -> Dict[str, Any]:
    """One read model for both entry points (B7, Phase 05). Readings saved from the Care Agenda
    (/care-automation/measurements) have no measurementId, measuredAt or verificationStatus; they are filled
    *at read time* (nothing is written back) and the entry point is kept as provenance."""
    row = dict(doc)
    legacy = not row.get("measurementId")
    row.setdefault("measuredAt", row.get("recordedAt"))
    if row.get("measuredAt") is None:
        row["measuredAt"] = row.get("recordedAt")
    row.setdefault("verificationStatus", "unverified")
    row.setdefault("source", "patient_reported")
    if legacy:
        row["measurementId"] = f"CARE-{str(row.get('_id'))[-10:].upper()}"
    row["entryPoint"] = "care_agenda" if legacy else "health_tracking"
    return row


def measurement_rows(db: Database, query: Dict[str, Any], *, since=None, newest_first: bool = True,
                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Measurements from both entry points, ordered by when they were measured (measuredAt, or recordedAt for
    Care Agenda readings), in MongoDB."""
    pipeline: List[Dict[str, Any]] = [{"$match": query},
                                      {"$addFields": {"_at": {"$ifNull": ["$measuredAt", "$recordedAt"]}}}]
    if since is not None:
        pipeline.append({"$match": {"_at": {"$gte": since}}})
    pipeline.append({"$sort": {"_at": -1 if newest_first else 1}})
    if limit:
        pipeline.append({"$limit": int(limit)})
    pipeline.append({"$project": {"_at": 0}})
    coll = get_health_measurement_collection(db)
    if not callable(getattr(coll, "aggregate", None)):  # minimal collection doubles: previous query shape
        filt = {**query, **({"measuredAt": {"$gte": since}} if since is not None else {})}
        cursor = coll.find(filt).sort("measuredAt", -1 if newest_first else 1)
        return [normalize_measurement(d) for d in (cursor.limit(int(limit)) if limit else cursor)]
    return [normalize_measurement(d) for d in coll.aggregate(pipeline)]


class HealthTrackingService:
    """Core service for patient health measurements, validation, and deterministic trend calculations."""

    # -----------------------------------------------------------------------
    # Record Health Measurement
    # -----------------------------------------------------------------------
    @classmethod
    def record_measurement(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        req: RecordHealthMeasurementRequest,
        target_patient_id: Optional[str] = None,
    ) -> HealthMeasurementResponse:
        """Validate and store a patient health measurement."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not target_patient_id:
                raise HTTPException(status_code=400, detail="Doctor must specify target_patient_id.")
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, target_patient_id)
            patient_id = target_patient_id
            verif_status = MeasurementVerificationStatus.CLINICIAN_REVIEWED.value
        else:
            patient_id = user_id_str
            verif_status = MeasurementVerificationStatus.UNVERIFIED.value

        # 1. Validate metric spec
        metric_key = req.metric.lower().strip()
        if metric_key not in METRIC_SPECS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported health metric '{req.metric}'. Allowed: {', '.join(METRIC_SPECS.keys())}.",
            )

        spec = METRIC_SPECS[metric_key]
        unit = req.unit or spec["unit"]

        # Range validation
        if req.value < spec["min_value"] or req.value > spec["max_value"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Value {req.value} {unit} is outside physiologic validation range ({spec['min_value']} - {spec['max_value']} {unit}).",
            )

        # Secondary (e.g. Diastolic for BP)
        if spec.get("requires_secondary"):
            if req.secondary is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Metric '{metric_key}' requires a secondary diastolic reading.",
                )
            if req.secondary < spec["min_secondary"] or req.secondary > spec["max_secondary"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Secondary value {req.secondary} is outside valid range ({spec['min_secondary']} - {spec['max_secondary']} {unit}).",
                )
            if req.secondary >= req.value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Diastolic reading cannot be greater than or equal to systolic reading.",
                )

        # 2. Check clinical safety alert thresholds
        critical_alert = ClinicalSafetyService.evaluate_measurement_safety(metric_key, req.value, req.secondary)

        now = utc_now()
        measured_at = req.measuredAt or now
        measurement_id = f"MEAS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        doc = HealthMeasurementDocument(
            measurementId=measurement_id,
            patientUserId=patient_id,
            metric=metric_key,
            value=float(req.value),
            secondary=float(req.secondary) if req.secondary is not None else None,
            unit=unit,
            source=req.source or MeasurementSource.PATIENT_REPORTED.value,
            verificationStatus=verif_status,
            notes=req.notes.strip() if req.notes else None,
            measuredAt=measured_at,
            recordedAt=now,
            updatedAt=now,
        )

        coll = get_health_measurement_collection(db)
        inserted = coll.insert_one(doc.model_dump(by_alias=True, exclude_none=True))

        return cls._to_response(doc, str(inserted.inserted_id), critical_alert)

    # -----------------------------------------------------------------------
    # Correct Measurement
    # -----------------------------------------------------------------------
    @classmethod
    def correct_measurement(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        measurement_id: str,
        req: CorrectHealthMeasurementRequest,
    ) -> HealthMeasurementResponse:
        """Correct an erroneous measurement with an auditable change log."""
        coll = get_health_measurement_collection(db)
        query = {"$or": [{"_id": ObjectId(measurement_id)}, {"measurementId": measurement_id}]} if ObjectId.is_valid(measurement_id) else {"measurementId": measurement_id}
        doc = coll.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="Health measurement not found.")

        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, doc["patientUserId"])
        elif doc["patientUserId"] != user_id_str:
            raise HTTPException(status_code=403, detail="You do not have permission to correct this measurement.")

        spec = METRIC_SPECS[doc["metric"]]
        if req.newValue < spec["min_value"] or req.newValue > spec["max_value"]:
            raise HTTPException(status_code=422, detail="Corrected value is outside valid physiologic range.")

        now = utc_now()
        correction_entry = {
            "correctedAt": now,
            "correctedByUserId": user_id_str,
            "previousValue": doc["value"],
            "previousSecondary": doc.get("secondary"),
            "reason": req.reason.strip(),
        }

        critical_alert = ClinicalSafetyService.evaluate_measurement_safety(doc["metric"], req.newValue, req.newSecondary)

        coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "value": float(req.newValue),
                    "secondary": float(req.newSecondary) if req.newSecondary is not None else None,
                    "updatedAt": now,
                },
                "$push": {"correctionsHistory": correction_entry},
            },
        )

        updated = coll.find_one({"_id": doc["_id"]})
        return cls._to_response(HealthMeasurementDocument.model_validate(updated), str(updated["_id"]), critical_alert)

    # -----------------------------------------------------------------------
    # List Measurements & Deterministic Trends
    # -----------------------------------------------------------------------
    @classmethod
    def list_measurements(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        patient_id: Optional[str] = None,
        metric: Optional[str] = None,
        limit: int = 50,
    ) -> HealthMeasurementListResponse:
        """Retrieve recent measurements for a patient."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not patient_id:
                raise HTTPException(status_code=400, detail="Doctor must specify patient_id.")
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, patient_id)
            target_patient = patient_id
        else:
            target_patient = user_id_str

        query: Dict[str, Any] = {"patientUserId": target_patient}
        if metric:
            query["metric"] = metric.lower()

        # P05-N18: both entry points through one normalized read (a Care Agenda reading made this list fail).
        cursor = measurement_rows(db, query, limit=limit)

        items: List[HealthMeasurementResponse] = []
        for doc in cursor:
            alert = ClinicalSafetyService.evaluate_measurement_safety(doc["metric"], doc["value"], doc.get("secondary"))
            items.append(cls._to_response(HealthMeasurementDocument.model_validate(doc), str(doc["_id"]), alert))

        return HealthMeasurementListResponse(items=items, total=len(items))

    @classmethod
    def calculate_health_trends(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        patient_id: Optional[str] = None,
    ) -> HealthTrendsResponse:
        """Calculate deterministic 7-day, 30-day averages, trends, and min/max metrics."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            if not patient_id:
                raise HTTPException(status_code=400, detail="Doctor must specify patient_id.")
            ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, patient_id)
            target_patient = patient_id
        else:
            target_patient = user_id_str

        now = utc_now()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        docs = measurement_rows(db, {"patientUserId": target_patient}, since=thirty_days_ago, newest_first=False)

        # Group by metric
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            m = d["metric"]
            grouped.setdefault(m, []).append(d)

        trend_summaries: List[MetricTrendSummary] = []
        all_alerts: List[str] = []

        for metric_name, spec in METRIC_SPECS.items():
            records = grouped.get(metric_name, [])
            if not records:
                trend_summaries.append(
                    MetricTrendSummary(
                        metric=metric_name,
                        unit=spec["unit"],
                        count=0,
                        trendDirection="INSUFFICIENT_DATA",
                        clinicalNotice="No measurements recorded in the last 30 days.",
                    )
                )
                continue

            values_30d = [r["value"] for r in records]
            values_7d = [r["value"] for r in records if r["measuredAt"] >= seven_days_ago]

            avg_30d = sum(values_30d) / len(values_30d) if values_30d else None
            avg_7d = sum(values_7d) / len(values_7d) if values_7d else None
            min_v = min(values_30d)
            max_v = max(values_30d)

            latest_record = records[-1]
            latest_val = latest_record["value"]
            latest_sec = latest_record.get("secondary")
            latest_date = latest_record["measuredAt"]

            # Evaluate trend direction
            direction: str = "STABLE"
            if len(values_30d) >= 2:
                recent_half = values_30d[len(values_30d) // 2:]
                older_half = values_30d[:len(values_30d) // 2]
                rec_avg = sum(recent_half) / len(recent_half)
                old_avg = sum(older_half) / len(older_half)
                pct_diff = ((rec_avg - old_avg) / old_avg) * 100 if old_avg > 0 else 0
                if pct_diff > 5.0:
                    direction = "RISING"
                elif pct_diff < -5.0:
                    direction = "FALLING"

            alert = ClinicalSafetyService.evaluate_measurement_safety(metric_name, latest_val, latest_sec)
            if alert:
                all_alerts.append(alert)

            trend_summaries.append(
                MetricTrendSummary(
                    metric=metric_name,
                    unit=spec["unit"],
                    count=len(values_30d),
                    latestValue=round(latest_val, 1),
                    latestSecondary=round(latest_sec, 1) if latest_sec is not None else None,
                    latestDate=latest_date,
                    sevenDayAverage=round(avg_7d, 1) if avg_7d is not None else None,
                    thirtyDayAverage=round(avg_30d, 1) if avg_30d is not None else None,
                    minValue=round(min_v, 1),
                    maxValue=round(max_v, 1),
                    trendDirection=direction,
                    clinicalNotice=alert,
                )
            )

        return HealthTrendsResponse(
            patientUserId=target_patient,
            trends=trend_summaries,
            criticalAlerts=all_alerts,
        )

    # -----------------------------------------------------------------------
    # Conversational NLP Interpretation (English + Romanized Sinhala)
    # -----------------------------------------------------------------------
    @classmethod
    def answer_health_query(
        cls,
        db: Database,
        current_user: UserResponseSchema,
        query: str,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Interpret natural language queries in English or Romanized Sinhala."""
        user_id_str = str(current_user.id)
        if current_user.role == UserRole.DOCTOR.value:
            target_patient = patient_id or user_id_str
            if patient_id:
                ClinicalSafetyService.verify_doctor_patient_care_relationship(db, user_id_str, patient_id)
        else:
            target_patient = user_id_str

        q_lower = query.lower()

        # Check for emergency symptoms
        if ClinicalSafetyService.detect_emergency_keywords(q_lower):
            return {
                "query": query,
                "intent": "emergency_escalation",
                "response": (
                    "URGENT CLINICAL WARNING: Your message describes acute medical symptoms that require immediate intervention.\n\n"
                    "Please call 1990 Suwa Seriya Ambulance Service immediately or visit the nearest emergency room. "
                    "Do not wait for a chat reply or attempt to self-medicate."
                ),
                "emergencyEscalation": True,
                "requiresDoctorAction": True,
                "aiDisclaimer": "AI emergency screening notice.",
            }

        # 1. Blood Pressure query (e.g. "mage last 7 days blood pressure readings pennanna")
        if "blood pressure" in q_lower or "bp" in q_lower or "pressure" in q_lower:
            seven_days_ago = utc_now() - timedelta(days=7)
            readings = measurement_rows(db, {"patientUserId": target_patient, "metric": "blood_pressure"},
                                        since=seven_days_ago)
            if not readings:
                return {
                    "query": query,
                    "intent": "blood_pressure_readings",
                    "response": "No blood pressure measurements recorded in the last 7 days. You can log a reading anytime using the Health Tracking dashboard.",
                    "structuredData": {"count": 0},
                    "emergencyEscalation": False,
                    "requiresDoctorAction": False,
                    "aiDisclaimer": "Measurements are patient-reported unless clinician verified.",
                }

            items_str = []
            for r in readings[:5]:
                d_str = r["measuredAt"].strftime("%b %d, %H:%M")
                items_str.append(f"• {d_str}: {r['value']:.0f}/{r.get('secondary', 0):.0f} mmHg ({r.get('source', 'patient_reported')})")

            avg_sys = sum(r["value"] for r in readings) / len(readings)
            avg_dia = sum(r.get("secondary", 0) for r in readings) / len(readings)

            return {
                "query": query,
                "intent": "blood_pressure_readings",
                "response": (
                    f"You have {len(readings)} blood pressure readings over the last 7 days with an average of {avg_sys:.0f}/{avg_dia:.0f} mmHg.\n\n"
                    f"Recent readings:\n" + "\n".join(items_str)
                ),
                "structuredData": {"count": len(readings), "averageSystolic": avg_sys, "averageDiastolic": avg_dia},
                "emergencyEscalation": False,
                "requiresDoctorAction": False,
                "aiDisclaimer": "AI vitals summary notice: Vitals trends are assistive.",
            }

        # 2. Weight trend query (e.g. "mage weight trend eka kohomada?")
        if "weight" in q_lower or "bara" in q_lower:
            trends = cls.calculate_health_trends(db, current_user, target_patient)
            weight_summary = next((t for t in trends.trends if t.metric == "weight"), None)
            if not weight_summary or weight_summary.count == 0:
                return {
                    "query": query,
                    "intent": "weight_trend",
                    "response": "No weight readings logged in the last 30 days. Log your body weight regularly to track progress.",
                    "structuredData": {"count": 0},
                    "emergencyEscalation": False,
                    "requiresDoctorAction": False,
                    "aiDisclaimer": "Health tracking notice.",
                }
            return {
                "query": query,
                "intent": "weight_trend",
                "response": (
                    f"Your weight trend is currently {weight_summary.trendDirection}.\n"
                    f"Latest reading: {weight_summary.latestValue} kg.\n"
                    f"30-day range: {weight_summary.minValue} kg to {weight_summary.maxValue} kg across {weight_summary.count} entries."
                ),
                "structuredData": weight_summary.model_dump(),
                "emergencyEscalation": False,
                "requiresDoctorAction": False,
                "aiDisclaimer": "Assisted health metrics notice.",
            }

        # 3. Glucose query (e.g. "ada glucose reading eka save karanna" or "glucose status")
        if "glucose" in q_lower or "seeni" in q_lower or "sugar" in q_lower:
            trends = cls.calculate_health_trends(db, current_user, target_patient)
            glu_summary = next((t for t in trends.trends if t.metric == "blood_glucose"), None)
            return {
                "query": query,
                "intent": "glucose_trend",
                "response": (
                    f"Blood glucose 30-day tracking: {glu_summary.count if glu_summary else 0} readings logged. "
                    f"Latest: {glu_summary.latestValue if glu_summary and glu_summary.latestValue else 'None'} mg/dL. "
                    "To save a new reading, please tap 'Add Measurement' in the dashboard or specify value and measurement time."
                ),
                "structuredData": glu_summary.model_dump() if glu_summary else {},
                "emergencyEscalation": False,
                "requiresDoctorAction": False,
                "aiDisclaimer": "Blood glucose tracking notice.",
            }

        # General overview
        trends = cls.calculate_health_trends(db, current_user, target_patient)
        return {
            "query": query,
            "intent": "general_vitals_summary",
            "response": f"Vitals overview calculated for {len(trends.trends)} health metrics. Active critical alerts: {len(trends.criticalAlerts)}.",
            "structuredData": {"metricsMonitored": len(trends.trends), "criticalAlerts": trends.criticalAlerts},
            "emergencyEscalation": False,
            "requiresDoctorAction": False,
            "aiDisclaimer": "Healthcare tracking assistant notice.",
        }

    @classmethod
    def _to_response(
        cls,
        doc: HealthMeasurementDocument,
        obj_id: str,
        critical_alert: Optional[str] = None,
    ) -> HealthMeasurementResponse:
        return HealthMeasurementResponse(
            id=obj_id,
            measurementId=doc.measurementId,
            patientUserId=doc.patientUserId,
            metric=doc.metric,
            value=doc.value,
            secondary=doc.secondary,
            unit=doc.unit,
            source=doc.source,
            verificationStatus=doc.verificationStatus,
            notes=doc.notes,
            criticalAlert=critical_alert,
            measuredAt=doc.measuredAt,
            recordedAt=doc.recordedAt,
        )
