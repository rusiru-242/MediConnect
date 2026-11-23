"""AI-assisted doctor verification review service with deterministic safeguards (Phase 5)."""

import logging
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.doctor_profile import DoctorVerificationStatus
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

REQUIRED_DOCUMENTS = {
    "identityDocument": "National Identity Card or Passport",
    "medicalRegistrationDocument": "Medical Council Registration Certificate",
    "qualificationDocument": "Primary Medical Degree Certificate (MBBS / MD)",
}

REQUIRED_PROFILE_FIELDS = [
    ("fullName", "Doctor Full Name"),
    ("medicalRegistrationNumber", "Medical Council Registration Number"),
    ("specialty", "Clinical Specialty"),
    ("qualifications", "Medical Qualifications"),
    ("hospitalOrClinic", "Hospital or Clinic Affiliation"),
    ("experienceYears", "Years of Medical Experience"),
]


class DoctorVerificationAssistant:
    """Deterministic and AI-augmented review analysis for doctor onboarding."""

    @staticmethod
    def _parse_oid(id_str: str) -> ObjectId:
        if not ObjectId.is_valid(id_str):
            raise HTTPException(status_code=400, detail="Invalid doctor profile ID.")
        return ObjectId(id_str)

    @classmethod
    def analyze_application(cls, db: Database, doctor_profile_id: str) -> Dict[str, Any]:
        """Perform comprehensive deterministic completeness, consistency, and risk analysis."""
        prof_oid = cls._parse_oid(doctor_profile_id)
        profile = db["doctor_profiles"].find_one({"_id": prof_oid})
        if not profile:
            raise HTTPException(status_code=404, detail="Doctor profile not found.")

        user_id = profile.get("userId")
        user_query = {"$or": [{"_id": ObjectId(user_id)}, {"_id": user_id}]} if ObjectId.is_valid(str(user_id)) else {"_id": user_id}
        user = db["users"].find_one(user_query) or {}

        full_name = user.get("fullName") or profile.get("fullName", "")
        email_verified = bool(user.get("emailVerified", False))
        reg_num = str(profile.get("medicalRegistrationNumber") or "").strip()
        specialty = str(profile.get("specialty") or "").strip()
        qualifications = str(profile.get("qualifications") or "").strip()
        hospital = str(profile.get("hospitalOrClinic") or "").strip()
        experience = profile.get("experienceYears")

        # 1. Field completeness check
        field_completeness = {
            "fullName": bool(full_name and len(full_name) >= 3),
            "medicalRegistrationNumber": bool(reg_num and len(reg_num) >= 3),
            "specialty": bool(specialty and len(specialty) >= 2),
            "qualifications": bool(qualifications and len(qualifications) >= 2),
            "hospitalOrClinic": bool(hospital and len(hospital) >= 2),
            "experienceYears": experience is not None and int(experience) >= 0,
            "emailVerified": email_verified,
        }

        # 2. Document completeness check
        uploaded_docs = profile.get("verificationDocuments", {}) or {}
        doc_checklist = {}
        missing_docs = []
        for key, label in REQUIRED_DOCUMENTS.items():
            doc_present = key in uploaded_docs and bool(uploaded_docs[key])
            doc_checklist[key] = doc_present
            if not doc_present:
                missing_docs.append(f"{label} ({key})")

        # 3. Consistency and risk detection
        inconsistencies = []
        risk_flags = []

        # Registration pattern check (e.g. SLMC or alphanumeric 3-20 characters)
        if reg_num:
            if not re.match(r"^[A-Za-z0-9\-\/]{3,30}$", reg_num):
                inconsistencies.append(f"Registration number '{reg_num}' has an unusual format.")
        else:
            inconsistencies.append("Missing medical registration number.")

        if not email_verified:
            risk_flags.append("Doctor's email address has not been verified yet.")

        # Experience sanity check
        if experience is not None:
            try:
                exp_val = int(experience)
                if exp_val > 60:
                    risk_flags.append(f"Reported experience of {exp_val} years is unusually high; verify graduation date.")
                elif exp_val < 0:
                    inconsistencies.append("Experience years cannot be negative.")
            except (ValueError, TypeError):
                inconsistencies.append("Experience years must be a valid integer.")

        # Qualifications vs specialty cross-check
        if qualifications and specialty:
            # Common medical degrees
            known_degrees = ["mbbs", "md", "ms", "frcs", "mrcp", "fcps", "bds", "phd"]
            has_standard_degree = any(deg in qualifications.casefold() for deg in known_degrees)
            if not has_standard_degree:
                risk_flags.append(f"Listed qualifications ('{qualifications}') do not contain recognizable primary medical credentials.")

        # 4. Completeness score computation (0-100)
        total_checks = len(field_completeness) + len(REQUIRED_DOCUMENTS)
        passed_checks = sum(1 for v in field_completeness.values() if v) + sum(1 for v in doc_checklist.values() if v)
        completeness_score = int((passed_checks / total_checks) * 100)

        # 5. Recommendation logic
        # Authoritative rule: Medical registration CANNOT be auto-approved by AI; requires external human check.
        if missing_docs or not email_verified:
            recommended_action = "REQUEST_INFO"
            summary = (
                f"Application has {completeness_score}% completeness. "
                f"Missing {len(missing_docs)} required document(s) or pending email verification. "
                f"Request additional information from doctor before approving."
            )
        elif inconsistencies or len(risk_flags) >= 2:
            recommended_action = "MANUAL_VERIFY"
            summary = (
                f"Application has {completeness_score}% completeness but has {len(inconsistencies)} potential inconsistencies "
                f"and {len(risk_flags)} risk flags. Requires thorough manual external medical council verification."
            )
        else:
            recommended_action = "APPROVE"
            summary = (
                f"Application has {completeness_score}% completeness with all standard fields and verification documents submitted. "
                f"Ready for authorized administrator review and manual SLMC registry confirmation."
            )

        return {
            "doctorProfileId": str(profile["_id"]),
            "doctorName": full_name or "Doctor Applicant",
            "completenessScore": completeness_score,
            "fieldCompleteness": field_completeness,
            "documentChecklist": doc_checklist,
            "missingDocuments": missing_docs,
            "inconsistencies": inconsistencies,
            "riskFlags": risk_flags,
            "needsManualExternalCheck": True,  # Mandatory external check requirement
            "summary": summary,
            "recommendedAction": recommended_action,
        }
