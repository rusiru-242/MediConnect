"""Seed synthetic data for manual staging UAT (docs/MANUAL_UAT_TEST_PLAN.md).

Safety rules enforced by this script:
- Runs ONLY when MONGODB_URI points to localhost/127.0.0.1 AND DATABASE_NAME ends with "_uat".
- Never updates or deletes existing documents: every record is inserted only if its natural key
  (email, doctorId, reviewId, availability date/time) does not exist yet. Re-running is safe.
- All people are synthetic. Email addresses use the uat.mediconnect.lk domain; the UAT backend is
  started with SMTP disabled, so nothing is emailed.
- The shared UAT password is read from UAT_PASSWORD, or generated once and saved to the
  git-ignored file backend/uat.env. It is never printed in full.

Usage (from backend/):
    powershell -ExecutionPolicy Bypass -File scripts/start_uat_backend.ps1 -SeedOnly
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit

from bson import ObjectId

BACKEND_DIR = Path(__file__).resolve().parent.parent
UAT_ENV_FILE = BACKEND_DIR / "uat.env"
DOMAIN = "uat.mediconnect.lk"
SL_TZ = timezone(timedelta(hours=5, minutes=30))


def _guard() -> tuple[str, str]:
    uri = os.environ.get("MONGODB_URI", "")
    db_name = os.environ.get("DATABASE_NAME", "")
    host = (urlsplit(uri).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1"} or not db_name.endswith("_uat"):
        sys.exit(
            "Refusing to seed: MONGODB_URI must point to localhost and DATABASE_NAME must end with '_uat' "
            f"(got host={host or 'none'!r}, database={db_name or 'none'!r})."
        )
    return uri, db_name


def _password() -> str:
    password = os.environ.get("UAT_PASSWORD", "").strip()
    if password:
        return password
    if UAT_ENV_FILE.exists():
        for line in UAT_ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("UAT_PASSWORD="):
                return line.split("=", 1)[1].strip()
    password = f"Uat-{secrets.token_urlsafe(9)}-7a!"
    with UAT_ENV_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"UAT_PASSWORD={password}\n")
    return password


def main() -> int:
    _guard()
    from app.config.database import DatabaseManager
    from app.models.appointment import create_appointment_indexes
    from app.models.doctor_availability import create_doctor_availability_indexes
    from app.models.doctor_profile import create_doctor_profile_indexes
    from app.models.review import create_review_indexes, get_review_collection
    from app.utils.security import hash_password

    db = DatabaseManager.get_database()
    for create in (create_doctor_profile_indexes, create_doctor_availability_indexes, create_review_indexes,
                   create_appointment_indexes):
        try:
            create(db)
        except Exception as exc:  # index creation is best effort; the app also creates them at startup
            print(f"note: index setup skipped ({type(exc).__name__})")

    password_hash = hash_password(_password())
    now = datetime.now(timezone.utc)
    report = {"created": [], "kept": []}

    def user(key: str, name: str, role: str, phone: str | None = None) -> str:
        email = f"{key}@{DOMAIN}"
        existing = db["users"].find_one({"email": email}, {"_id": 1})
        if existing:
            report["kept"].append(email)
            return str(existing["_id"])
        uid = ObjectId()
        db["users"].insert_one({
            "_id": uid, "fullName": name, "email": email, "phone": phone, "passwordHash": password_hash,
            "role": role, "emailVerified": True, "accountStatus": "ACTIVE", "authProviders": ["LOCAL"],
            "createdAt": now, "updatedAt": now,
        })
        report["created"].append(email)
        return str(uid)

    def doctor(key, name, specialty, city, fee, years, status="APPROVED"):
        uid = user(key, name, "DOCTOR", "0770000000")
        doctor_id = f"UAT-{key.upper()}"
        profile = db["doctor_profiles"].find_one({"userId": uid}, {"_id": 1, "doctorId": 1})
        if profile:
            return uid, str(profile["_id"]), profile.get("doctorId", doctor_id)
        pid = ObjectId()
        db["doctor_profiles"].insert_one({
            "_id": pid, "userId": uid, "doctorId": doctor_id, "medicalRegistrationNumber": f"SLMC-{doctor_id}",
            "specialty": specialty, "qualifications": "MBBS (synthetic UAT profile)",
            "hospitalOrClinic": f"UAT {city} Medical Centre", "city": city, "experienceYears": years,
            "consultationFee": fee, "bio": "Synthetic doctor profile for user acceptance testing.",
            "verificationStatus": status, "submittedAt": now,
            "verifiedAt": now if status == "APPROVED" else None, "createdAt": now, "updatedAt": now,
        })
        report["created"].append(f"profile {doctor_id}")
        return uid, str(pid), doctor_id

    # Patients and admin
    patient1 = user("uat.patient1", "UAT Patient One", "PATIENT", "0771111111")
    user("uat.patient2", "UAT Patient Two", "PATIENT", "0772222222")
    user("uat.admin", "UAT Admin", "ADMIN")
    reviewers = [user(f"uat.reviewer{i}", f"UAT Reviewer {i}", "PATIENT") for i in range(1, 4)]

    doctors = {
        "cardio": doctor("uat.doctor.cardio", "Dr. UAT Cardio One", "Cardiology", "Colombo", 2000.0, 12),
        "cardio2": doctor("uat.doctor.cardio2", "Dr. UAT Cardio Two", "Cardiology", "Colombo", 3500.0, 20),
        "derm1": doctor("uat.doctor.derm1", "Dr. UAT Derm Senior", "Dermatology", "Colombo", 3000.0, 22),
        "derm2": doctor("uat.doctor.derm2", "Dr. UAT Derm Junior", "Dermatology", "Colombo", 2500.0, 6),
        "derm3": doctor("uat.doctor.derm3", "Dr. UAT Derm LowRated", "Dermatology", "Colombo", 2000.0, 30),
        "neuro": doctor("uat.doctor.neuro", "Dr. UAT Neuro", "Neurology", "Colombo", 2500.0, 10),
        "gp": doctor("uat.doctor.gp", "Dr. UAT General", "General Practice", "Colombo", 1500.0, 8),
    }
    # Pending applications for admin verification tests (A-02)
    doctor("uat.doctor.pending1", "Dr. UAT Pending One", "Pediatrics", "Kandy", 2200.0, 5, status="PENDING")
    doctor("uat.doctor.pending2", "Dr. UAT Pending Two", "ENT", "Galle", 2400.0, 7, status="PENDING")

    # Published reviews: derm1/derm2 average >= 4.5, derm3 average < 4.5 (UAT P-04f)
    review_plan = {"derm1": (5, 5, 4), "derm2": (5, 4, 5), "derm3": (4, 4, 3), "cardio": (5, 4, 5)}
    reviews = get_review_collection(db)
    for key, ratings in review_plan.items():
        uid, pid, doctor_id = doctors[key]
        for index, rating in enumerate(ratings, 1):
            review_id = f"UAT-REV-{doctor_id}-{index}"
            if reviews.find_one({"reviewId": review_id}, {"_id": 1}):
                continue
            reviews.insert_one({
                "reviewId": review_id, "appointmentId": f"UAT-APPT-{doctor_id}-{index}",
                "doctorUserId": uid, "doctorProfileId": pid, "patientUserId": reviewers[index - 1],
                "rating": rating, "comment": "Synthetic UAT review.", "status": "PUBLISHED",
                "createdAt": now, "updatedAt": now,
            })
            report["created"].append(review_id)

    # Availability: every approved doctor, the next 10 days 09:00-12:00 and 14:00-17:00 (Sri Lanka time),
    # plus Dr. UAT Neuro on the next 5 December 15:00-18:00 for UAT P-05.
    today = datetime.now(SL_TZ).date()
    december_5 = date(today.year if (today.month, today.day) <= (12, 5) else today.year + 1, 12, 5)

    def window(uid, pid, day: date, start: str, end: str):
        key = {"doctorUserId": uid, "date": day.isoformat(), "startTime": start}
        if db["doctor_availabilities"].find_one(key, {"_id": 1}):
            return
        overlapping = db["doctor_availabilities"].find_one({
            "doctorUserId": uid, "date": day.isoformat(), "isActive": True,
            "startTime": {"$lt": end}, "endTime": {"$gt": start},
        }, {"_id": 1})
        if overlapping:
            return
        db["doctor_availabilities"].insert_one({
            **key, "doctorProfileId": pid, "endTime": end, "slotDurationMinutes": 30, "isActive": True,
            "createdAt": now, "updatedAt": now,
        })
        report["created"].append(f"availability {day} {start}")

    for key, (uid, pid, _) in doctors.items():
        for offset in range(1, 11):
            day = today + timedelta(days=offset)
            window(uid, pid, day, "09:00", "12:00")
            window(uid, pid, day, "14:00", "17:00")
    neuro_uid, neuro_pid, _ = doctors["neuro"]
    window(neuro_uid, neuro_pid, december_5, "15:00", "18:00")

    created_people = [e for e in report["created"] if "@" in e]
    print(f"database: {db.name}")
    print(f"accounts created: {len(created_people)}; existing accounts kept unchanged: {len(report['kept'])}")
    print(f"other records created: {len(report['created']) - len(created_people)}")
    print("accounts:", ", ".join(f"{k}@{DOMAIN}" for k in (
        "uat.patient1", "uat.patient2", "uat.admin", "uat.doctor.cardio", "uat.doctor.cardio2", "uat.doctor.derm1",
        "uat.doctor.derm2", "uat.doctor.derm3", "uat.doctor.neuro", "uat.doctor.gp", "uat.doctor.pending1",
        "uat.doctor.pending2")))
    print(f"shared password: stored in {UAT_ENV_FILE.name} (UAT_PASSWORD) - not printed")
    print(f"Dr. UAT Neuro extra window: {december_5} 15:00-18:00")
    return 0


if __name__ == "__main__":
    sys.exit(main())
