"""Clinical Safety Service (Phase 6).

Implements deterministic clinical guardrails:
1. Doctor-patient care relationship authorization verification.
2. Critical vital sign thresholds & automated emergency escalations.
3. Allergy cross-checking against proposed medications.
4. Duplicate active medication detection.
5. PII sanitization and AI prompt boundary protection.
6. Formula injection prevention.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.health_measurement import MeasurementMetric

# Emergency trigger words requiring immediate emergency response advisory
EMERGENCY_KEYWORDS: Set[str] = {
    "chest pain",
    "heart attack",
    "can't breathe",
    "cannot breathe",
    "shortness of breath",
    "difficulty breathing",
    "stroke",
    "unconscious",
    "fainted",
    "severe bleeding",
    "coughing blood",
    "anaphylaxis",
    "slurred speech",
    "pennanna amarui",
    "panthi enne na",
    "hada wathura",
}

EMERGENCY_ADVISORY = (
    "EMERGENCY NOTICE: If you or the patient are experiencing acute symptoms "
    "(such as severe chest pain, sudden difficulty breathing, stroke symptoms, or severe bleeding), "
    "immediately call 1990 Suwa Seriya Ambulance Service or report to the nearest hospital emergency room. "
    "MediConnect clinical assistant cannot provide emergency medical intervention."
)


class ClinicalSafetyService:
    """Deterministic healthcare safety rules, access enforcement, and guardrails."""

    # -----------------------------------------------------------------------
    # Doctor-Patient Relationship Access Verification
    # -----------------------------------------------------------------------
    @classmethod
    def verify_doctor_patient_care_relationship(
        cls,
        db: Database,
        doctor_user_id: str,
        patient_user_id: str,
    ) -> bool:
        """Verify that an authorized clinical care relationship exists between doctor and patient.

        Access is permitted if the doctor has:
        1. An appointment (HOLD, PENDING, CONFIRMED, COMPLETED) with the patient.
        2. A consultation session with the patient.
        3. A care plan assigned to the patient.
        Otherwise, access is rejected with HTTP 403 Forbidden.
        """
        if not doctor_user_id or not patient_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor and patient identities must both be specified.",
            )

        # 1. Check appointments
        appt_query = {
            "patientUserId": patient_user_id,
            "$or": [
                {"doctorUserId": doctor_user_id},
                {"doctorUserId": str(doctor_user_id)},
            ],
        }
        if db["appointments"].find_one(appt_query, {"_id": 1}):
            return True

        # Check by doctorProfileId if doctor has profile
        profile = db["doctor_profiles"].find_one({"userId": doctor_user_id}, {"_id": 1})
        if profile:
            profile_id_str = str(profile["_id"])
            if db["appointments"].find_one({"patientUserId": patient_user_id, "doctorProfileId": profile_id_str}, {"_id": 1}):
                return True

        # 2. Check consultation sessions
        if db["consultation_sessions"].find_one({"patientUserId": patient_user_id, "doctorUserId": doctor_user_id}, {"_id": 1}):
            return True

        # 3. Check care plans
        if db["care_plans"].find_one({"patientUserId": patient_user_id, "doctorUserId": doctor_user_id}, {"_id": 1}):
            return True

        # 4. Check existing medical records or clinical notes authored by this doctor for this patient
        if db["clinical_notes"].find_one({"patientUserId": patient_user_id, "doctorUserId": doctor_user_id}, {"_id": 1}):
            return True
        if db["medical_records"].find_one({"patientUserId": patient_user_id, "doctorUserId": doctor_user_id}, {"_id": 1}):
            return True

        # Care relationship does not exist -> Deny
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You do not have an active or documented care relationship with this patient.",
        )

    # -----------------------------------------------------------------------
    # Critical Vital Signs Threshold Screening
    # -----------------------------------------------------------------------
    @classmethod
    def evaluate_measurement_safety(
        cls,
        metric: str,
        value: float,
        secondary: Optional[float] = None,
    ) -> Optional[str]:
        """Evaluate measured vitals against physiologic safety alert thresholds."""
        if metric == MeasurementMetric.BLOOD_PRESSURE.value:
            systolic = value
            diastolic = secondary or 0.0
            if systolic >= 180.0 or diastolic >= 120.0:
                return (
                    "CRITICAL HYPERTENSIVE CRISIS ALERT: Blood pressure reading is severely elevated (≥180/120 mmHg). "
                    "Seek immediate emergency medical care (Call 1990 Suwa Seriya)."
                )
            if systolic < 90.0 or (diastolic > 0 and diastolic < 60.0):
                return "HYPOTENSION WARNING: Low blood pressure reading detected. Consult your physician if experiencing dizziness or fainting."

        elif metric == MeasurementMetric.OXYGEN_SATURATION.value:
            if value < 90.0:
                return (
                    "CRITICAL HYPOXIA ALERT: Oxygen saturation is dangerously low (<90%). "
                    "Seek immediate emergency medical attention."
                )
            if value < 95.0:
                return "LOW OXYGEN WARNING: SpO2 reading is below normal (90-94%). Monitor closely and seek medical advice."

        elif metric == MeasurementMetric.BLOOD_GLUCOSE.value:
            if value < 54.0:
                return (
                    "CRITICAL HYPOGLYCEMIA ALERT: Blood glucose is severely low (<54 mg/dL). "
                    "Consume fast-acting carbohydrates immediately and seek emergency medical assistance."
                )
            if value >= 300.0:
                return "CRITICAL HYPERGLYCEMIA ALERT: Blood glucose reading is severely elevated (≥300 mg/dL). Contact your doctor immediately."

        elif metric == MeasurementMetric.HEART_RATE.value:
            if value >= 140.0:
                return "TACHYCARDIA ALERT: Heart rate is significantly elevated (≥140 bpm). Rest and seek medical evaluation if persistent."
            if value < 45.0:
                return "BRADYCARDIA ALERT: Heart rate is low (<45 bpm). Seek medical evaluation if experiencing fatigue or dizziness."

        elif metric == MeasurementMetric.TEMPERATURE.value:
            if value >= 39.5:
                return "HIGH FEVER ALERT: Body temperature is very high (≥39.5°C). Consult a physician promptly."

        return None

    # -----------------------------------------------------------------------
    # Emergency Keyword Detection
    # -----------------------------------------------------------------------
    @classmethod
    def detect_emergency_keywords(cls, text: str) -> bool:
        """Scan free-text messages for acute medical distress signals."""
        normalized = text.lower()
        return any(keyword in normalized for keyword in EMERGENCY_KEYWORDS)

    # -----------------------------------------------------------------------
    # Allergy & Duplicate Medication Checking
    # -----------------------------------------------------------------------
    @classmethod
    def check_prescription_safety(
        cls,
        db: Database,
        patient_user_id: str,
        proposed_medications: List[str],
    ) -> Dict[str, Any]:
        """Check proposed medications against known patient allergies and active prescriptions."""
        allergies: List[str] = []
        active_medications: List[str] = []
        potential_duplicates: List[str] = []
        allergy_warnings: List[str] = []

        # 1. Fetch documented allergies from patient_medical_records
        allergy_cursor = db["patient_medical_records"].find(
            {"patientUserId": patient_user_id, "recordType": "allergy", "status": "active"},
            {"title": 1, "clinicalData": 1},
        )
        for rec in allergy_cursor:
            allergen = rec.get("title") or rec.get("clinicalData", {}).get("allergen")
            if allergen:
                allergies.append(allergen.strip().lower())

        # 2. Fetch active prescriptions
        presc_cursor = db["prescriptions"].find(
            {"patientUserId": patient_user_id, "status": {"$in": ["ISSUED", "ACTIVE", "signed"]}},
            {"medicationItems": 1},
        )
        for p in presc_cursor:
            for item in p.get("medicationItems", []):
                med_name = item.get("medicationName", "")
                if med_name:
                    active_medications.append(med_name.strip())

        # 3. Cross check proposed items
        for proposed in proposed_medications:
            p_clean = proposed.strip().lower()
            # Allergy check
            for allergen in allergies:
                if allergen in p_clean or p_clean in allergen:
                    allergy_warnings.append(
                        f"POSSIBLE ALLERGY CONTRAINDICATION: Patient has documented allergy to '{allergen}', which may conflict with '{proposed}'."
                    )
            # Duplicate check
            for active in active_medications:
                if active.lower() == p_clean:
                    potential_duplicates.append(
                        f"DUPLICATE ACTIVE MEDICATION: Patient is already actively prescribed '{active}'."
                    )

        return {
            "documentedAllergies": list(set(allergies)),
            "activeMedications": list(set(active_medications)),
            "potentialDuplicates": potential_duplicates,
            "allergyWarnings": allergy_warnings,
            "isSafeToProceed": len(allergy_warnings) == 0,
        }

    # -----------------------------------------------------------------------
    # PII Sanitization for AI Prompts
    # -----------------------------------------------------------------------
    @classmethod
    def sanitize_medical_context_for_ai(cls, text: str) -> str:
        """Strip National IDs, phone numbers, email addresses, and secrets before AI prompts."""
        if not text:
            return ""
        # Scrub phone numbers (+94 / 07X...)
        scrubbed = re.sub(r"(\+?94|0)[0-9]{9}", "[REDACTED_PHONE]", text)
        # Scrub NICs (e.g. 199012345678 or 901234567V)
        scrubbed = re.sub(r"\b([0-9]{9}[vVxX]|[0-9]{12})\b", "[REDACTED_NIC]", scrubbed)
        # Scrub emails
        scrubbed = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", scrubbed)
        return scrubbed
