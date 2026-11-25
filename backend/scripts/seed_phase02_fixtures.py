"""Insert dedicated synthetic Phase 02 fixtures into the isolated UAT database.

Safety rules (same as seed_uat_data.py):
- Runs ONLY when MONGODB_URI points to localhost/127.0.0.1 AND DATABASE_NAME ends with "_uat".
- Insert-only: nothing existing is updated or deleted, so owner-created bookings are preserved.
- Synthetic people only (uat.mediconnect.lk); the shared UAT password comes from backend/uat.env.

Fixtures: three patients (uat.p02.patienta/b/c) and two approved Orthopedic Surgeon doctors in Kandy,
"Dr. P02 Ortho" (LKR 3000) and "Dr. P02 Spine" (LKR 2800), with 09:00-12:00 and 14:00-17:00 windows for the next 14 days.

Usage (from backend/):
    $env:MONGODB_URI='mongodb://127.0.0.1:27017/mediconnect_uat'; $env:DATABASE_NAME='mediconnect_uat'
    python scripts/seed_phase02_fixtures.py
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

    def user(key, name, role, phone=None):
        email = f"{key}@{DOMAIN}"
        found = db["users"].find_one({"email": email}, {"_id": 1})
        if found:
            return str(found["_id"])
        uid = ObjectId()
        db["users"].insert_one({
            "_id": uid, "fullName": name, "email": email, "phone": phone, "passwordHash": password_hash,
            "role": role, "emailVerified": True, "accountStatus": "ACTIVE", "authProviders": ["LOCAL"],
            "createdAt": now, "updatedAt": now,
        })
        created.append(email)
        return str(uid)

    for suffix, phone in (("a", "0773000001"), ("b", "0773000002"), ("c", "0773000003")):
        user(f"uat.p02.patient{suffix}", f"P02 Patient {suffix.upper()}", "PATIENT", phone)

    for key, name, doctor_id, clinic, fee in (
        ("uat.p02.doctor.ortho", "Dr. P02 Ortho", "UAT-P02-ORTHO", "UAT Kandy Bone Clinic", 3000.0),
        ("uat.p02.doctor.spine", "Dr. P02 Spine", "UAT-P02-SPINE", "UAT Kandy Spine Centre", 2800.0),
    ):
        _doctor(db, user, created, now, key, name, doctor_id, clinic, fee)

    print(f"database: {db.name}; records created: {len(created)} (insert-only, nothing modified)")
    return 0


def _doctor(db, user, created, now, key, name, doctor_id, clinic, fee):
    doctor_uid = user(key, name, "DOCTOR", "0773000009")
    profile = db["doctor_profiles"].find_one({"userId": doctor_uid}, {"_id": 1})
    if profile:
        pid = str(profile["_id"])
    else:
        pid_obj = ObjectId()
        db["doctor_profiles"].insert_one({
            "_id": pid_obj, "userId": doctor_uid, "doctorId": doctor_id,
            "medicalRegistrationNumber": f"SLMC-{doctor_id}", "specialty": "Orthopedic Surgeon",
            "qualifications": "MBBS (synthetic Phase 02 profile)", "hospitalOrClinic": clinic,
            "city": "Kandy", "experienceYears": 9, "consultationFee": fee,
            "bio": "Synthetic doctor profile for Phase 02 booking and payment testing.",
            "verificationStatus": "APPROVED", "submittedAt": now, "verifiedAt": now,
            "createdAt": now, "updatedAt": now,
        })
        pid = str(pid_obj)
        created.append(f"profile {doctor_id}")

    today = datetime.now(SL_TZ).date()
    for offset in range(1, 15):
        day = (today + timedelta(days=offset)).isoformat()
        for start, end in (("09:00", "12:00"), ("14:00", "17:00")):
            key = {"doctorUserId": doctor_uid, "date": day, "startTime": start}
            if db["doctor_availabilities"].find_one(key, {"_id": 1}):
                continue
            db["doctor_availabilities"].insert_one({
                **key, "doctorProfileId": pid, "endTime": end, "slotDurationMinutes": 30, "isActive": True,
                "createdAt": now, "updatedAt": now,
            })
            created.append(f"availability {day} {start}")


if __name__ == "__main__":
    sys.exit(main())
