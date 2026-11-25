"""Insert dedicated synthetic Phase 03 (doctor system) fixtures into the isolated UAT database.

Safety rules (same as seed_uat_data.py and seed_phase02_fixtures.py):
- Runs ONLY when MONGODB_URI points to localhost/127.0.0.1 AND DATABASE_NAME ends with "_uat".
- Insert-only: nothing existing is updated or deleted, so owner-created bookings are preserved.
- Synthetic people only (uat.mediconnect.lk); the shared UAT password comes from backend/uat.env.

Fixtures:
- Patients uat.p03.patienta / uat.p03.patientb.
- Approved doctors "Dr. P03 Alpha" (UAT-P03-ALPHA, LKR 2000) and "Dr. P03 Beta" (UAT-P03-BETA, LKR 1800),
  General Physician, Colombo. Availability for today and the next 14 days: 06:00-12:00 and 13:00-23:30
  (a 12:00-13:00 break), 30-minute slots, so UAT can book "today" at any time of day. The extended hours are
  synthetic test data, not a real clinic schedule.
- Doctor uat.p03.doctor.rejected (verificationStatus REJECTED) and uat.p03.doctor.suspended
  (accountStatus SUSPENDED) for authorization tests. The existing uat.doctor.pending1 covers PENDING.

Usage (from backend/):
    $env:MONGODB_URI='mongodb://127.0.0.1:27017/mediconnect_uat'; $env:DATABASE_NAME='mediconnect_uat'
    python scripts/seed_phase03_fixtures.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.seed_uat_data import DOMAIN, SL_TZ, _guard, _password  # noqa: E402


def main() -> int:
    _guard()
    from app.config.database import DatabaseManager
    from app.utils.security import hash_password

    db = DatabaseManager.get_database()
    now = datetime.now(timezone.utc)
    password_hash = hash_password(_password())
    created: list[str] = []

    def user(key, name, role, phone=None, account_status="ACTIVE"):
        email = f"{key}@{DOMAIN}"
        found = db["users"].find_one({"email": email}, {"_id": 1})
        if found:
            return str(found["_id"])
        uid = ObjectId()
        db["users"].insert_one({
            "_id": uid, "fullName": name, "email": email, "phone": phone, "passwordHash": password_hash,
            "role": role, "emailVerified": True, "accountStatus": account_status, "authProviders": ["LOCAL"],
            "createdAt": now, "updatedAt": now,
        })
        created.append(email)
        return str(uid)

    for suffix, phone in (("a", "0774000001"), ("b", "0774000002")):
        user(f"uat.p03.patient{suffix}", f"P03 Patient {suffix.upper()}", "PATIENT", phone)

    def doctor(key, name, doctor_id, fee, *, verification="APPROVED", account_status="ACTIVE", slots=True):
        doctor_uid = user(key, name, "DOCTOR", "0774000009", account_status)
        profile = db["doctor_profiles"].find_one({"userId": doctor_uid}, {"_id": 1})
        if profile:
            pid = str(profile["_id"])
        else:
            pid_obj = ObjectId()
            db["doctor_profiles"].insert_one({
                "_id": pid_obj, "userId": doctor_uid, "doctorId": doctor_id,
                "medicalRegistrationNumber": f"SLMC-{doctor_id}", "specialty": "General Physician",
                "qualifications": "MBBS (synthetic Phase 03 profile)", "hospitalOrClinic": "UAT Colombo Clinic",
                "city": "Colombo", "experienceYears": 8, "consultationFee": fee,
                "bio": "Synthetic doctor profile for Phase 03 doctor-system testing.",
                "verificationStatus": verification, "submittedAt": now,
                **({"verifiedAt": now} if verification == "APPROVED" else {}),
                **({"rejectionReason": "Synthetic rejected profile for authorization tests"}
                   if verification == "REJECTED" else {}),
                "createdAt": now, "updatedAt": now,
            })
            pid = str(pid_obj)
            created.append(f"profile {doctor_id}")
        if not slots:
            return
        today = datetime.now(SL_TZ).date()
        for offset in range(0, 15):
            day = (today + timedelta(days=offset)).isoformat()
            for start, end in (("06:00", "12:00"), ("13:00", "23:30")):
                k = {"doctorUserId": doctor_uid, "date": day, "startTime": start}
                if db["doctor_availabilities"].find_one(k, {"_id": 1}):
                    continue
                db["doctor_availabilities"].insert_one({
                    **k, "doctorProfileId": pid, "endTime": end, "slotDurationMinutes": 30, "isActive": True,
                    "createdAt": now, "updatedAt": now,
                })
                created.append(f"availability {doctor_id} {day} {start}")

    doctor("uat.p03.doctor.alpha", "Dr. P03 Alpha", "UAT-P03-ALPHA", 2000.0)
    doctor("uat.p03.doctor.beta", "Dr. P03 Beta", "UAT-P03-BETA", 1800.0)
    doctor("uat.p03.doctor.rejected", "Dr. P03 Rejected", "UAT-P03-REJ", 1500.0, verification="REJECTED", slots=False)
    doctor("uat.p03.doctor.suspended", "Dr. P03 Suspended", "UAT-P03-SUS", 1500.0,
           account_status="SUSPENDED", slots=False)

    print(f"database: {db.name}; records created: {len(created)} (insert-only, nothing modified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
