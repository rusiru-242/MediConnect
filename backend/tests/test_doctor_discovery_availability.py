"""Backend test suite for Doctor Discovery, Search, Details, and Availability Management.

Covers tests 1 through 18.
"""

from datetime import datetime, timedelta, timezone
import time
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import get_database
from app.main import app
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.doctor_service import SL_TIMEZONE, get_sl_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


def _setup_test_users():
    """Seed test database with:

    - 1 Patient
    - 1 Approved + Active Doctor (Cardiologist, "Dr. Perera")
    - 1 Approved + Active Doctor (Dermatologist, "Dr. Silva")
    - 1 Pending Doctor (Pediatrician)
    - 1 Rejected Doctor (Neurologist)
    - 1 Inactive Doctor
    """
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Patient
    pat_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "Test Patient",
        "email": f"patient_{ts}@mediconnect.lk",
        "phone": "0771122334",
        "passwordHash": hash_password("Patient@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_token = create_access_token(pat_id, role=UserRole.PATIENT.value)

    # 2. Approved Doctor A: Cardiologist "Dr. Kamal Perera"
    doc_a_id = str(ObjectId())
    doc_a_prof_oid = ObjectId()
    doc_a_num = f"DOC-TEST-A-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(doc_a_id),
        "fullName": "Dr. Kamal Perera",
        "email": f"dr_perera_{ts}@mediconnect.lk",
        "phone": "0772233445",
        "passwordHash": hash_password("DoctorA@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": doc_a_prof_oid,
        "userId": doc_a_id,
        "doctorId": doc_a_num,
        "specialty": "Cardiologist",
        "medicalRegistrationNumber": f"SLMC-TEST-A-{ts}",
        "qualifications": "MBBS, MD Cardiology",
        "hospitalOrClinic": "National Hospital Colombo",
        "experienceYears": 12,
        "bio": "Experienced cardiologist specializing in heart disease.",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })
    doc_a_token = create_access_token(doc_a_id, role=UserRole.DOCTOR.value)

    # 3. Approved Doctor B: Dermatologist "Dr. Nimal Silva"
    doc_b_id = str(ObjectId())
    doc_b_prof_oid = ObjectId()
    doc_b_num = f"DOC-TEST-B-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(doc_b_id),
        "fullName": "Dr. Nimal Silva",
        "email": f"dr_silva_{ts}@mediconnect.lk",
        "phone": "0773344556",
        "passwordHash": hash_password("DoctorB@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": doc_b_prof_oid,
        "userId": doc_b_id,
        "doctorId": doc_b_num,
        "specialty": "Dermatologist",
        "medicalRegistrationNumber": f"SLMC-TEST-B-{ts}",
        "qualifications": "MBBS, MD Dermatology",
        "hospitalOrClinic": "Asiri Central Hospital",
        "experienceYears": 8,
        "bio": "Specialist in skin disorders and cosmetic treatments.",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })
    doc_b_token = create_access_token(doc_b_id, role=UserRole.DOCTOR.value)

    # 4. Pending Doctor: Pediatrician "Dr. Suneth Bandara"
    doc_pend_id = str(ObjectId())
    doc_pend_prof_oid = ObjectId()
    doc_pend_num = f"DOC-TEST-PEND-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(doc_pend_id),
        "fullName": "Dr. Suneth Bandara",
        "email": f"dr_bandara_{ts}@mediconnect.lk",
        "phone": "0774455667",
        "passwordHash": hash_password("DoctorPend@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.PENDING.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": doc_pend_prof_oid,
        "userId": doc_pend_id,
        "doctorId": doc_pend_num,
        "specialty": "Pediatrician",
        "medicalRegistrationNumber": f"SLMC-TEST-P-{ts}",
        "qualifications": "MBBS, DCH",
        "hospitalOrClinic": "Lady Ridgeway Hospital",
        "experienceYears": 4,
        "bio": "Dedicated child health specialist.",
        "verificationStatus": DoctorVerificationStatus.PENDING.value,
        "submittedAt": utc_now(),
    })
    doc_pend_token = create_access_token(doc_pend_id, role=UserRole.DOCTOR.value)

    # 5. Rejected Doctor: Neurologist "Dr. Ruwan Fernando"
    doc_rej_id = str(ObjectId())
    doc_rej_prof_oid = ObjectId()
    doc_rej_num = f"DOC-TEST-REJ-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(doc_rej_id),
        "fullName": "Dr. Ruwan Fernando",
        "email": f"dr_fernando_{ts}@mediconnect.lk",
        "phone": "0775566778",
        "passwordHash": hash_password("DoctorRej@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.SUSPENDED.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": doc_rej_prof_oid,
        "userId": doc_rej_id,
        "doctorId": doc_rej_num,
        "specialty": "Neurologist",
        "medicalRegistrationNumber": f"SLMC-TEST-R-{ts}",
        "qualifications": "MBBS, MD",
        "hospitalOrClinic": "Nawaloka Hospital",
        "experienceYears": 10,
        "bio": "Neurologist.",
        "verificationStatus": DoctorVerificationStatus.REJECTED.value,
        "submittedAt": utc_now(),
    })

    return {
        "pat_token": pat_token,
        "doc_a": {"id": doc_a_id, "doctorId": doc_a_num, "profId": str(doc_a_prof_oid), "token": doc_a_token},
        "doc_b": {"id": doc_b_id, "doctorId": doc_b_num, "profId": str(doc_b_prof_oid), "token": doc_b_token},
        "doc_pend": {"id": doc_pend_id, "doctorId": doc_pend_num, "profId": str(doc_pend_prof_oid), "token": doc_pend_token},
        "doc_rej": {"id": doc_rej_id, "doctorId": doc_rej_num, "profId": str(doc_rej_prof_oid)},
    }


def test_doctor_discovery_and_search():
    """Runs TESTS 1-8:

    TEST 1: Patient requests doctor list -> only APPROVED + ACTIVE doctors
    TEST 2: Pending doctor -> not returned
    TEST 3: Rejected doctor -> not returned
    TEST 4: Search by doctor name -> matching approved doctors
    TEST 5: Search by specialty -> matching approved doctors
    TEST 6: Specialty filter -> correct doctors
    TEST 7: Patient opens approved doctor details -> 200
    TEST 8: Patient attempts pending doctor details -> not exposed (404)
    """
    data = _setup_test_users()
    pat_headers = {"Authorization": f"Bearer {data['pat_token']}"}

    # TEST 1: Patient requests doctor list -> only APPROVED + ACTIVE
    res = client.get("/api/doctors", headers=pat_headers)
    assert res.status_code == 200, f"Expected 200, got: {res.text}"
    body = res.json()
    assert "items" in body
    items = body["items"]

    # Verify doctor IDs in returned list
    returned_doctor_ids = [item["doctorId"] for item in items]
    assert data["doc_a"]["doctorId"] in returned_doctor_ids
    assert data["doc_b"]["doctorId"] in returned_doctor_ids

    # TEST 2: Pending doctor is NOT returned
    assert data["doc_pend"]["doctorId"] not in returned_doctor_ids, "Pending doctor must NEVER appear in patient discovery!"

    # TEST 3: Rejected doctor is NOT returned
    assert data["doc_rej"]["doctorId"] not in returned_doctor_ids, "Rejected doctor must NEVER appear in patient discovery!"

    # Verify no sensitive data leaked
    for doc in items:
        assert doc["verificationStatus"] == "APPROVED"
        assert "passwordHash" not in doc
        assert "medicalVerificationDocuments" not in doc
        assert "otp" not in doc

    # TEST 4: Search by doctor name
    res_search_name = client.get("/api/doctors?search=perera", headers=pat_headers)
    assert res_search_name.status_code == 200
    found_names = [d["fullName"] for d in res_search_name.json()["items"]]
    assert any("Perera" in n for n in found_names)
    assert not any("Silva" in n for n in found_names)

    # TEST 5: Search by specialty (search param)
    res_search_spec = client.get("/api/doctors?search=Cardiologist", headers=pat_headers)
    assert res_search_spec.status_code == 200
    found_specs = [d["specialty"] for d in res_search_spec.json()["items"]]
    assert all("Cardiologist" in s for s in found_specs)

    # TEST 6: Specialty filter
    res_filter = client.get("/api/doctors?specialty=Dermatologist", headers=pat_headers)
    assert res_filter.status_code == 200
    items_spec = res_filter.json()["items"]
    assert len(items_spec) >= 1
    assert all(d["specialty"] == "Dermatologist" for d in items_spec)
    assert data["doc_b"]["doctorId"] in [d["doctorId"] for d in items_spec]
    assert data["doc_a"]["doctorId"] not in [d["doctorId"] for d in items_spec]

    # TEST 7: Patient opens approved doctor details -> 200
    res_detail = client.get(f"/api/doctors/{data['doc_a']['doctorId']}", headers=pat_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["doctorId"] == data["doc_a"]["doctorId"]
    assert detail["fullName"] == "Dr. Kamal Perera"
    assert detail["specialty"] == "Cardiologist"
    assert detail["verificationStatus"] == "APPROVED"
    assert "medicalRegistrationNumber" not in detail  # Safe public representation
    assert "documentUrl" not in detail

    # TEST 8: Patient attempts pending doctor details -> not exposed (404)
    res_pend_detail = client.get(f"/api/doctors/{data['doc_pend']['doctorId']}", headers=pat_headers)
    assert res_pend_detail.status_code == 404, "Pending doctor must return 404 on patient-facing details!"

    # Inactive/rejected doctor details -> 404
    res_rej_detail = client.get(f"/api/doctors/{data['doc_rej']['doctorId']}", headers=pat_headers)
    assert res_rej_detail.status_code == 404, "Rejected doctor must return 404 on patient-facing details!"


def test_doctor_availability_workflow():
    """Runs TESTS 9-18:

    TEST 9: Approved doctor creates valid availability -> success
    TEST 10: Pending doctor creates availability -> 403
    TEST 11: Patient creates availability -> 403
    TEST 12: Doctor creates past availability -> rejected
    TEST 13: startTime >= endTime -> rejected
    TEST 14: Overlapping availability -> rejected
    TEST 15: Doctor updates own availability -> success
    TEST 16: Doctor updates another doctor's availability -> 403/404
    TEST 17: Generate 30-minute slots from 09:00–12:00 -> correct boundaries
    TEST 18: Past slots -> not returned
    """
    data = _setup_test_users()
    doc_a_headers = {"Authorization": f"Bearer {data['doc_a']['token']}"}
    doc_b_headers = {"Authorization": f"Bearer {data['doc_b']['token']}"}
    doc_pend_headers = {"Authorization": f"Bearer {data['doc_pend']['token']}"}
    pat_headers = {"Authorization": f"Bearer {data['pat_token']}"}

    future_date = (get_sl_now() + timedelta(days=7)).strftime("%Y-%m-%d")
    past_date = (get_sl_now() - timedelta(days=2)).strftime("%Y-%m-%d")

    # TEST 9: Approved doctor creates valid availability -> success (201)
    payload_valid = {
        "date": future_date,
        "startTime": "09:00",
        "endTime": "12:00",
        "slotDurationMinutes": 30,
    }
    res_create = client.post("/api/doctors/me/availability", json=payload_valid, headers=doc_a_headers)
    assert res_create.status_code == 201, f"Expected 201, got: {res_create.text}"
    created_avail = res_create.json()
    assert created_avail["date"] == future_date
    assert created_avail["startTime"] == "09:00"
    assert created_avail["endTime"] == "12:00"
    assert created_avail["slotDurationMinutes"] == 30
    assert created_avail["isActive"] is True
    avail_id = created_avail["id"]

    # TEST 10: Pending doctor creates availability -> 403
    res_pend_avail = client.post("/api/doctors/me/availability", json=payload_valid, headers=doc_pend_headers)
    assert res_pend_avail.status_code == 403, "Pending doctor must be forbidden from creating availability!"

    # TEST 11: Patient creates availability -> 403
    res_pat_avail = client.post("/api/doctors/me/availability", json=payload_valid, headers=pat_headers)
    assert res_pat_avail.status_code == 403, "Patient must be forbidden from creating availability!"

    # TEST 12: Doctor creates past availability -> rejected (400)
    payload_past = {
        "date": past_date,
        "startTime": "09:00",
        "endTime": "12:00",
        "slotDurationMinutes": 30,
    }
    res_past = client.post("/api/doctors/me/availability", json=payload_past, headers=doc_a_headers)
    assert res_past.status_code == 400, "Past date availability must be rejected!"

    # TEST 13: startTime >= endTime -> rejected (400)
    payload_bad_time = {
        "date": future_date,
        "startTime": "14:00",
        "endTime": "13:00",
        "slotDurationMinutes": 30,
    }
    res_bad_time = client.post("/api/doctors/me/availability", json=payload_bad_time, headers=doc_a_headers)
    assert res_bad_time.status_code == 400, "startTime >= endTime must be rejected!"

    payload_equal_time = {
        "date": future_date,
        "startTime": "10:00",
        "endTime": "10:00",
        "slotDurationMinutes": 30,
    }
    res_equal_time = client.post("/api/doctors/me/availability", json=payload_equal_time, headers=doc_a_headers)
    assert res_equal_time.status_code == 400

    # TEST 14: Overlapping availability -> rejected (400)
    # Existing is 09:00 - 12:00 on future_date. An overlapping schedule 11:00 - 13:00 must fail.
    payload_overlap = {
        "date": future_date,
        "startTime": "11:00",
        "endTime": "13:00",
        "slotDurationMinutes": 30,
    }
    res_overlap = client.post("/api/doctors/me/availability", json=payload_overlap, headers=doc_a_headers)
    assert res_overlap.status_code == 400, "Overlapping availability must be rejected!"
    assert "overlaps" in res_overlap.json()["detail"].lower()

    # TEST 15: Doctor updates own availability -> success (200)
    res_update = client.put(
        f"/api/doctors/me/availability/{avail_id}",
        json={"startTime": "08:30", "endTime": "11:30"},
        headers=doc_a_headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["startTime"] == "08:30"
    assert res_update.json()["endTime"] == "11:30"

    # Reset back to 09:00 - 12:00 for slot testing
    res_reset = client.put(
        f"/api/doctors/me/availability/{avail_id}",
        json={"startTime": "09:00", "endTime": "12:00"},
        headers=doc_a_headers,
    )
    assert res_reset.status_code == 200

    # TEST 16: Doctor B updates Doctor A's availability -> 403
    res_hack = client.put(
        f"/api/doctors/me/availability/{avail_id}",
        json={"startTime": "10:00"},
        headers=doc_b_headers,
    )
    assert res_hack.status_code == 403, "Doctor must not be allowed to modify another doctor's availability!"

    # TEST 17: Generate 30-minute slots from 09:00–12:00 -> correct slot boundaries
    # Window: 09:00 - 12:00, duration: 30 min.
    # Expected slots:
    # 09:00-09:30, 09:30-10:00, 10:00-10:30, 10:30-11:00, 11:00-11:30, 11:30-12:00 (6 slots)
    res_slots = client.get(
        f"/api/doctors/{data['doc_a']['doctorId']}/availability?date={future_date}",
        headers=pat_headers,
    )
    assert res_slots.status_code == 200
    slots_data = res_slots.json()
    assert slots_data["date"] == future_date
    slots = slots_data["slots"]
    assert len(slots) == 6, f"Expected 6 slots, got {len(slots)}: {slots}"
    expected_pairs = [
        ("09:00", "09:30"),
        ("09:30", "10:00"),
        ("10:00", "10:30"),
        ("10:30", "11:00"),
        ("11:00", "11:30"),
        ("11:30", "12:00"),
    ]
    for i, (exp_start, exp_end) in enumerate(expected_pairs):
        assert slots[i]["startTime"] == exp_start
        assert slots[i]["endTime"] == exp_end

    # Also verify without date query param
    res_slots_all = client.get(
        f"/api/doctors/{data['doc_a']['doctorId']}/availability",
        headers=pat_headers,
    )
    assert res_slots_all.status_code == 200
    all_data = res_slots_all.json()
    # It either returns DayAvailabilitySlots if 1 day or List
    if isinstance(all_data, dict):
        assert all_data["date"] == future_date
        assert len(all_data["slots"]) == 6
    elif isinstance(all_data, list):
        matching = [d for d in all_data if d["date"] == future_date]
        assert len(matching) == 1
        assert len(matching[0]["slots"]) == 6

    # TEST 18: Past slots -> not returned
    # Create availability on TODAY in Sri Lanka time with some early morning time that has already passed
    # If currently it's late night, an early morning slot (e.g. 01:00-03:00) is in the past!
    today_str = get_sl_now().strftime("%Y-%m-%d")
    current_time_str = get_sl_now().strftime("%H:%M")
    current_h = int(current_time_str[:2])

    if current_h >= 2:
        # Schedule window earlier than now today: 00:00 - 01:00
        db = get_database()
        db["doctor_availabilities"].insert_one({
            "_id": ObjectId(),
            "doctorUserId": str(data["doc_a"]["id"]),
            "doctorProfileId": str(data["doc_a"]["profId"]),
            "date": today_str,
            "startTime": "00:00",
            "endTime": "01:00",
            "slotDurationMinutes": 30,
            "isActive": True,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        })

        res_today_slots = client.get(
            f"/api/doctors/{data['doc_a']['doctorId']}/availability?date={today_str}",
            headers=pat_headers,
        )
        assert res_today_slots.status_code == 200
        today_slots = res_today_slots.json()["slots"]
        # Slots at 00:00 and 00:30 are in the past, so should NOT be returned
        past_starts = [s["startTime"] for s in today_slots if s["startTime"] < current_time_str]
        assert len(past_starts) == 0, f"Past slots should not be returned: {past_starts}"

    # Verify soft-delete of availability
    res_del = client.delete(f"/api/doctors/me/availability/{avail_id}", headers=doc_a_headers)
    assert res_del.status_code == 200
    res_after_del = client.get(
        f"/api/doctors/{data['doc_a']['doctorId']}/availability?date={future_date}",
        headers=pat_headers,
    )
    assert len(res_after_del.json()["slots"]) == 0, "Deleted availability slots must not be returned!"
