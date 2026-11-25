"""Phase 04 admin-system UAT fixtures (insert-only).

Safety rules (same as seed_uat_data.py, seed_phase02_fixtures.py and seed_phase03_fixtures.py):
- Runs ONLY when MONGODB_URI points to localhost/127.0.0.1 AND DATABASE_NAME ends with "_uat".
- Inserts synthetic records only; an existing record with the same key is kept unchanged.
- No real people, no real registration numbers (all numbers start with UAT-P04-), no real documents
  (the verification "documents" are tiny synthetic PDF files written under uploads/doctor_verification/).

Run from backend/:
    $env:MONGODB_URI='mongodb://127.0.0.1:27017/mediconnect_uat'; $env:DATABASE_NAME='mediconnect_uat'
    venv\\Scripts\\python.exe -m scripts.seed_phase04_fixtures
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId  # noqa: E402

from scripts.seed_uat_data import DOMAIN, SL_TZ, _guard, _password  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
DOCS_DIR = BACKEND / "uploads" / "doctor_verification"
SYNTHETIC_PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
                 b"% Synthetic MediConnect UAT document. Not a real credential.\ntrailer<</Root 1 0 R>>\n%%EOF\n")


def main() -> int:
    _guard()
    from app.config.database import DatabaseManager
    from app.utils.security import hash_password

    db = DatabaseManager.get_database()
    now = datetime.now(timezone.utc)
    password_hash = hash_password(_password())
    created, kept = [], []

    def user(key, name, role, status="ACTIVE", email_verified=True):
        email = f"{key}@{DOMAIN}"
        row = db["users"].find_one({"email": email}, {"_id": 1})
        if row:
            kept.append(email)
            return str(row["_id"])
        uid = ObjectId()
        db["users"].insert_one({"_id": uid, "fullName": name, "email": email, "phone": None,
                                "passwordHash": password_hash, "role": role, "emailVerified": email_verified,
                                "accountStatus": status, "authProviders": ["LOCAL"], "createdAt": now,
                                "updatedAt": now})
        created.append(email)
        return str(uid)

    def documents(uid):
        folder = DOCS_DIR / uid
        folder.mkdir(parents=True, exist_ok=True)
        out = {}
        for kind in ("identityDocument", "medicalRegistrationDocument", "qualificationDocument"):
            name = f"{kind}_uatp04.pdf"
            (folder / name).write_bytes(SYNTHETIC_PDF)
            out[kind] = {"documentType": kind, "filename": name, "originalFilename": f"synthetic_{kind}.pdf",
                         "contentType": "application/pdf", "fileSize": len(SYNTHETIC_PDF),
                         "storagePath": f"{uid}/{name}", "uploadedAt": now}
        return out

    def application(key, name, specialty, reg, status="PENDING_ADMIN_APPROVAL", account="PENDING", docs=True,
                    fee=2100.0):
        uid = user(key, name, "DOCTOR", status=account)
        if db["doctor_profiles"].find_one({"userId": uid}, {"_id": 1}):
            kept.append(f"profile {key}")
            return uid
        profile = {"userId": uid, "doctorId": f"UAT-P04-{key.split('.')[-1].upper()}", "specialty": specialty,
                   "qualifications": "MBBS (synthetic UAT profile)", "hospitalOrClinic": "UAT P04 Clinic",
                   "city": "Colombo", "experienceYears": 6, "consultationFee": fee,
                   "bio": "Synthetic Phase 04 doctor application.", "verificationStatus": status,
                   "submittedAt": now, "createdAt": now, "updatedAt": now,
                   "verificationDocuments": documents(uid) if docs else {}}
        if reg:
            profile["medicalRegistrationNumber"] = reg
        db["doctor_profiles"].insert_one(profile)
        created.append(f"profile {key}")
        return uid

    patient_a = user("uat.p04.patienta", "P04 Patient A", "PATIENT")
    patient_b = user("uat.p04.patientb", "P04 Patient B", "PATIENT")
    application("uat.p04.doctor.applicant", "Dr. P04 Applicant", "Dermatology", "UAT-P04-APPLICANT")
    application("uat.p04.doctor.reject", "Dr. P04 Reject", "ENT", "UAT-P04-REJECT")
    application("uat.p04.doctor.noreg", "Dr. P04 No Registration", "Pediatrics", None)
    revoke_uid = application("uat.p04.doctor.revoke", "Dr. P04 Revoke", "General Physician", "UAT-P04-REVOKE",
                             status="APPROVED", account="ACTIVE", fee=1900.0)
    revoke_profile = db["doctor_profiles"].find_one({"userId": revoke_uid})

    # A completed, paid visit so Dr. P04 Revoke has a legitimate care relationship with patient A (A-03g).
    key = "UAT-P04-REVOKE-VISIT"
    if not db["appointments"].find_one({"uatFixture": key}, {"_id": 1}):
        day = (datetime.now(SL_TZ) - timedelta(days=3)).strftime("%Y-%m-%d")
        db["appointments"].insert_one({
            "uatFixture": key, "patientUserId": patient_a, "doctorUserId": revoke_uid,
            "doctorProfileId": str(revoke_profile["_id"]), "doctorId": revoke_profile["doctorId"],
            "appointmentDate": day, "startTime": "08:00", "endTime": "08:30", "status": "COMPLETED",
            "paymentStatus": "PAID", "consultationFee": 1900.0, "consultationType": "IN_PERSON",
            "createdAt": now, "updatedAt": now})
        created.append(key)
    if not db["patient_medical_records"].find_one({"recordId": "MED-UAT-P04-A1"}, {"_id": 1}):
        db["patient_medical_records"].insert_one({
            "recordId": "MED-UAT-P04-A1", "patientUserId": patient_a, "recordType": "allergy",
            "title": "P04 synthetic allergy record", "description": "Synthetic record for admin privacy checks.",
            "sourceType": "patient_uploaded", "authorId": patient_a, "authorRole": "PATIENT",
            "clinicalDate": now.strftime("%Y-%m-%d"), "createdAt": now, "updatedAt": now})
        created.append("MED-UAT-P04-A1")

    # A historical appointment whose fee was never stored (P3-B2 / A-05c).
    key = "UAT-P04-NULL-FEE"
    if not db["appointments"].find_one({"uatFixture": key}, {"_id": 1}):
        db["appointments"].insert_one({
            "uatFixture": key, "patientUserId": patient_b, "doctorUserId": revoke_uid,
            "doctorProfileId": str(revoke_profile["_id"]), "appointmentDate": "2026-10-02", "startTime": "07:30",
            "endTime": "08:00", "status": "CANCELLED", "paymentStatus": "UNPAID", "consultationFee": None,
            "cancelledBy": "PATIENT", "cancellationReason": "Synthetic historical record", "createdAt": now,
            "updatedAt": now})
        created.append(key)

    # Three declined card payments in the last 24 hours for patient B (fraud rule A-08c). Synthetic records:
    # Stripe test mode declines are also exercised live by the UAT script.
    for i in range(3):
        pid = f"pi_uat_p04_declined_{i}"
        if not db["payments"].find_one({"stripePaymentIntentId": pid}, {"_id": 1}):
            db["payments"].insert_one({"appointmentId": str(ObjectId()), "patientUserId": patient_b,
                                       "doctorUserId": revoke_uid, "stripePaymentIntentId": pid, "amount": 1900.0,
                                       "currency": "lkr", "status": "FAILED", "failureReason": "card_declined",
                                       "uatFixture": "UAT-P04-DECLINED", "createdAt": now, "updatedAt": now})
            created.append(pid)

    # Availability for the applicant (bookable once approved, A-03h) for the next 7 days.
    applicant = db["users"].find_one({"email": f"uat.p04.doctor.applicant@{DOMAIN}"}, {"_id": 1})
    aprof = db["doctor_profiles"].find_one({"userId": str(applicant["_id"])})
    today = datetime.now(SL_TZ).date()
    for offset in range(1, 8):
        day = (today + timedelta(days=offset)).isoformat()
        q = {"doctorUserId": str(applicant["_id"]), "date": day, "startTime": "10:00"}
        if not db["doctor_availabilities"].find_one(q, {"_id": 1}):
            db["doctor_availabilities"].insert_one({**q, "doctorProfileId": str(aprof["_id"]), "endTime": "12:00",
                                                    "slotDurationMinutes": 30, "isActive": True,
                                                    "createdAt": now, "updatedAt": now})
            created.append(f"availability applicant {day}")

    print(f"database: {db.name}")
    print(f"records created: {len(created)}; existing kept unchanged: {len(kept)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
