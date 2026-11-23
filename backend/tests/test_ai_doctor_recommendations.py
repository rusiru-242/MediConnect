"""Tests for AI Doctor Recommendation Agent (Phase 18).

Covers:
1. Specialty matching (English and Sinhala)
2. Location matching
3. Fee and availability filters
4. Unverified doctor exclusion (Pending, Rejected, Inactive)
5. No matching doctors handling
6. Invalid AI responses & graceful fallback
7. AI provider timeout & fallback
8. Patient authentication requirement (401)
9. Unauthorized role access rejected (403 for DOCTOR / ADMIN)
10. Safe handling of urgent/emergency symptom-related requests
"""

from datetime import datetime, timedelta, timezone
import time
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest
import requests

from app.agents.ai_provider import DeterministicNLPProvider, GeminiAIProvider, get_ai_provider
from app.agents.nlp_parser import parse_query_deterministically
from app.config.database import get_database
from app.config.settings import settings
from app.main import app
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.doctor_service import get_sl_now
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_ai_provider_for_engine(request):
    """Ensure automated test suite runs fast and deterministically with mocked external AI calls."""
    if "test_10" in request.node.name or "test_11" in request.node.name:
        yield
        return
    with patch("app.agents.recommendation_engine.get_ai_provider", return_value=DeterministicNLPProvider()):
        yield


@pytest.fixture(scope="module")
def seeded_env():
    """Seed test database with:
    - 1 Patient
    - 1 Doctor (DOCTOR role)
    - 1 Admin (ADMIN role)
    - 1 Approved Cardiologist in Colombo ("Dr. Nihal Perera", LKR 2,500) with availability slots
    - 1 Approved Dermatologist in Kandy ("Dr. Sunethra Silva", LKR 3,500) with availability slots
    - 1 Approved General Practitioner in Colombo ("Dr. Samantha Fernando", LKR 1,500)
    - 1 Pending Doctor (Pediatrician)
    - 1 Rejected Doctor (Neurologist)
    - 1 Suspended/Inactive Doctor
    """
    db = get_database()
    db["doctor_profiles"].delete_many({"doctorId": {"$regex": "^DOC-AI-"}})
    ts = int(time.time() * 1000)

    # 1. Patient
    pat_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_id),
        "fullName": "Test Patient 18",
        "email": f"patient18_{ts}@mediconnect.lk",
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

    # 2. Doctor user (for unauthorized role testing)
    doc_user_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(doc_user_id),
        "fullName": "Unauthorized Doctor User",
        "email": f"unauth_doc_{ts}@mediconnect.lk",
        "phone": "0779988776",
        "passwordHash": hash_password("Doctor@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_token = create_access_token(doc_user_id, role=UserRole.DOCTOR.value)

    # 3. Admin user
    admin_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Admin User",
        "email": f"admin18_{ts}@mediconnect.lk",
        "phone": "0771112223",
        "passwordHash": hash_password("Admin@123"),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "authProviders": ["LOCAL"],
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    admin_token = create_access_token(admin_id, role=UserRole.ADMIN.value)

    # 4. Approved Cardiologist in Colombo
    cardio_uid = str(ObjectId())
    cardio_prof_oid = ObjectId()
    cardio_doc_id = f"DOC-AI-CARDIO-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(cardio_uid),
        "fullName": "Dr. Nihal Perera",
        "email": f"nihal_{ts}@mediconnect.lk",
        "phone": "0772233111",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": cardio_prof_oid,
        "userId": cardio_uid,
        "doctorId": cardio_doc_id,
        "specialty": "Cardiologist",
        "medicalRegistrationNumber": f"SLMC-CARDIO-{ts}",
        "qualifications": "MBBS, MD Cardiology",
        "hospitalOrClinic": "Asiri Central Hospital, Colombo",
        "experienceYears": 14,
        "consultationFee": 2500.0,
        "bio": "Consultant Cardiologist at Asiri Central",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })

    # Add availability slot for tomorrow
    sl_tomorrow = (get_sl_now() + timedelta(days=1)).strftime("%Y-%m-%d")
    db["doctor_availabilities"].insert_one({
        "_id": ObjectId(),
        "doctorUserId": cardio_uid,
        "doctorProfileId": str(cardio_prof_oid),
        "date": sl_tomorrow,
        "startTime": "18:00",
        "endTime": "19:00",
        "slotDurationMinutes": 30,
        "isActive": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 5. Approved Dermatologist in Kandy
    derma_uid = str(ObjectId())
    derma_prof_oid = ObjectId()
    derma_doc_id = f"DOC-AI-DERMA-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(derma_uid),
        "fullName": "Dr. Sunethra Silva",
        "email": f"sunethra_{ts}@mediconnect.lk",
        "phone": "0773344222",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": derma_prof_oid,
        "userId": derma_uid,
        "doctorId": derma_doc_id,
        "specialty": "Dermatologist",
        "medicalRegistrationNumber": f"SLMC-DERMA-{ts}",
        "qualifications": "MBBS, MD Dermatology",
        "hospitalOrClinic": "Kandy General Hospital",
        "experienceYears": 9,
        "consultationFee": 3500.0,
        "bio": "Consultant Dermatologist",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })
    db["doctor_availabilities"].insert_one({
        "_id": ObjectId(),
        "doctorUserId": derma_uid,
        "doctorProfileId": str(derma_prof_oid),
        "date": sl_tomorrow,
        "startTime": "09:00",
        "endTime": "10:00",
        "slotDurationMinutes": 30,
        "isActive": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 6. Approved GP in Colombo
    gp_uid = str(ObjectId())
    gp_prof_oid = ObjectId()
    gp_doc_id = f"DOC-AI-GP-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(gp_uid),
        "fullName": "Dr. Samantha Fernando",
        "email": f"samantha_{ts}@mediconnect.lk",
        "phone": "0774455333",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": gp_prof_oid,
        "userId": gp_uid,
        "doctorId": gp_doc_id,
        "specialty": "General Practitioner",
        "medicalRegistrationNumber": f"SLMC-GP-{ts}",
        "qualifications": "MBBS",
        "hospitalOrClinic": "Nawaloka Hospital, Colombo",
        "experienceYears": 6,
        "consultationFee": 1500.0,
        "bio": "General Practitioner",
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })

    # 7. Pending Doctor (MUST BE EXCLUDED)
    pend_uid = str(ObjectId())
    pend_doc_id = f"DOC-AI-PEND-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(pend_uid),
        "fullName": "Dr. Pending Pediatrician",
        "email": f"pending_{ts}@mediconnect.lk",
        "phone": "0775566444",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.PENDING.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(),
        "userId": pend_uid,
        "doctorId": pend_doc_id,
        "specialty": "Pediatrician",
        "medicalRegistrationNumber": f"SLMC-PEND-{ts}",
        "qualifications": "MBBS, DCH",
        "hospitalOrClinic": "Lady Ridgeway Hospital, Colombo",
        "experienceYears": 5,
        "consultationFee": 2000.0,
        "verificationStatus": DoctorVerificationStatus.PENDING.value,
        "submittedAt": utc_now(),
    })

    # 8. Rejected Doctor (MUST BE EXCLUDED)
    rej_uid = str(ObjectId())
    rej_doc_id = f"DOC-AI-REJ-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(rej_uid),
        "fullName": "Dr. Rejected Neurologist",
        "email": f"rej_{ts}@mediconnect.lk",
        "phone": "0776677555",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.PENDING.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(),
        "userId": rej_uid,
        "doctorId": rej_doc_id,
        "specialty": "Neurologist",
        "medicalRegistrationNumber": f"SLMC-REJ-{ts}",
        "qualifications": "MBBS",
        "hospitalOrClinic": "Colombo Central",
        "experienceYears": 3,
        "consultationFee": 2200.0,
        "verificationStatus": DoctorVerificationStatus.REJECTED.value,
        "submittedAt": utc_now(),
    })

    # 9. Suspended Doctor (MUST BE EXCLUDED)
    susp_uid = str(ObjectId())
    susp_doc_id = f"DOC-AI-SUSP-{ts}"
    db["users"].insert_one({
        "_id": ObjectId(susp_uid),
        "fullName": "Dr. Suspended Doctor",
        "email": f"susp_{ts}@mediconnect.lk",
        "phone": "0777788666",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.SUSPENDED.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(),
        "userId": susp_uid,
        "doctorId": susp_doc_id,
        "specialty": "Cardiologist",
        "medicalRegistrationNumber": f"SLMC-SUSP-{ts}",
        "qualifications": "MBBS",
        "hospitalOrClinic": "Colombo Clinic",
        "experienceYears": 10,
        "consultationFee": 2000.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "submittedAt": utc_now(),
        "verifiedAt": utc_now(),
    })

    return {
        "pat_token": pat_token,
        "doc_token": doc_token,
        "admin_token": admin_token,
        "cardio_doc_id": cardio_doc_id,
        "derma_doc_id": derma_doc_id,
        "gp_doc_id": gp_doc_id,
        "pend_doc_id": pend_doc_id,
        "rej_doc_id": rej_doc_id,
        "susp_doc_id": susp_doc_id,
        "sl_tomorrow": sl_tomorrow,
    }


def test_01_nlp_parser_english_specialties_and_relative_dates():
    """Verify deterministic NLP parses English requests for specialties, relative dates, and fees."""
    # Test Cardiologist
    res = parse_query_deterministically("I have heart palpitations and high blood pressure, need doctor tomorrow under 3000 LKR")
    assert res["specialty"] == "Cardiologist"
    assert res["maxFee"] == 3000.0
    assert res["date"] is not None
    assert res["isUrgent"] is False

    # Test Dermatologist
    res_derma = parse_query_deterministically("Looking for a skin specialist for acne and severe itching")
    assert res_derma["specialty"] == "Dermatologist"

    # Test ENT Specialist
    res_ent = parse_query_deterministically("Severe ear infection and sore throat")
    assert res_ent["specialty"] == "ENT Specialist"


def test_02_nlp_parser_sinhala_queries_and_dates():
    """Verify deterministic NLP parses Sinhala requests accurately."""
    # ළමා වෛද්‍ය -> Pediatrician
    res_si = parse_query_deterministically("මගේ බබාට උණ, ළමා වෛද්‍යවරයෙක් හෙට උදේට කොළඹින් ඕනේ")
    assert res_si["specialty"] == "Pediatrician"
    assert res_si["city"] == "Colombo"
    assert res_si["timeRange"] == "morning"
    assert res_si["language"] == "si"

    # චර්ම -> Dermatologist
    res_derma_si = parse_query_deterministically("සමේ කැසීමකට චර්ම රෝග දොස්තර මහතෙක් හමුවෙන්න")
    assert res_derma_si["specialty"] == "Dermatologist"


def test_03_unauthenticated_request_rejected(seeded_env):
    """Unauthenticated request must return 401 Unauthorized."""
    resp = client.post(
        "/api/ai/doctor-recommendations",
        json={"query": "I need a doctor for chest checkup"},
    )
    assert resp.status_code == 401


def test_04_unauthorized_role_access_rejected(seeded_env):
    """Doctors and Admins are forbidden from calling patient doctor recommendation endpoint (403)."""
    # Doctor token
    resp_doc = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['doc_token']}"},
        json={"query": "I need a doctor for my health"},
    )
    assert resp_doc.status_code == 403

    # Admin token
    resp_admin = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['admin_token']}"},
        json={"query": "I need a doctor for my health"},
    )
    assert resp_admin.status_code == 403


def test_05_specialty_matching_and_recommendation(seeded_env):
    """Patient asking for heart doctor gets Approved Cardiologist ranked first."""
    resp = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "I have heart palpitations and need a cardiologist"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["interpretedPreferences"]["specialty"] == "Cardiologist"
    assert data["totalMatches"] > 0
    top_doc = data["recommendations"][0]
    assert top_doc["doctorId"] == seeded_env["cardio_doc_id"]
    assert top_doc["specialty"] == "Cardiologist"
    assert any("Cardiologist" in r for r in top_doc["matchReasons"])
    assert data["disclaimer"] is not None


def test_06_location_matching_recommendation(seeded_env):
    """Location preference in Kandy elevates the Kandy-based doctor."""
    resp = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "I need a doctor in Kandy"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["interpretedPreferences"]["city"] == "Kandy"
    top_doc = data["recommendations"][0]
    assert top_doc["doctorId"] == seeded_env["derma_doc_id"]
    assert "Kandy" in top_doc["hospitalOrClinic"]
    assert any("Kandy" in r for r in top_doc["matchReasons"])


def test_07_fee_and_availability_filters(seeded_env):
    """Applying maxFee filter excludes doctors whose consultation fee exceeds the budget."""
    resp = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "I need a doctor under 2000 LKR", "maxFee": 2000.0},
    )
    assert resp.status_code == 200
    data = resp.json()

    # The GP has fee 1500, which is <= 2000
    for doc in data["recommendations"]:
        assert doc["consultationFee"] <= 2000.0

    # Cardiologist (2500) and Dermatologist (3500) must be excluded
    doc_ids = [d["doctorId"] for d in data["recommendations"]]
    assert seeded_env["cardio_doc_id"] not in doc_ids
    assert seeded_env["derma_doc_id"] not in doc_ids


def test_08_unverified_doctors_strictly_excluded(seeded_env):
    """Pending, rejected, and suspended doctors must NEVER appear in recommendations."""
    resp = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "Find any doctor in Sri Lanka"},
    )
    assert resp.status_code == 200
    data = resp.json()

    recommended_ids = [d["doctorId"] for d in data["recommendations"]]
    assert seeded_env["pend_doc_id"] not in recommended_ids, "Pending doctor must be excluded"
    assert seeded_env["rej_doc_id"] not in recommended_ids, "Rejected doctor must be excluded"
    assert seeded_env["susp_doc_id"] not in recommended_ids, "Suspended doctor must be excluded"


def test_09_no_matching_doctors_handled_gracefully(seeded_env):
    """Querying for a non-existent specialty or impossible budget returns empty list with disclaimer."""
    resp = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "I need a brain neurologist", "specialty": "Neurologist"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["recommendations"], list)
    assert "disclaimer" in data


def test_10_invalid_ai_response_falls_back_to_deterministic_nlp(seeded_env):
    """When external AI provider returns invalid JSON, fallback to deterministic parser is seamless."""
    provider = GeminiAIProvider(api_key="mock-key-for-test")

    with patch("requests.post") as mock_post:
        # Mock API returning malformed non-JSON response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "THIS_IS_NOT_VALID_JSON!!!"}]}}
            ]
        }
        mock_post.return_value = mock_response

        parsed, source = provider.parse_request("I have heart palpitations in Colombo")
        # Should gracefully fall back to deterministic parser
        assert source == "deterministic_fallback"
        assert parsed["specialty"] == "Cardiologist"
        assert parsed["city"] == "Colombo"


def test_11_ai_provider_timeout_falls_back(seeded_env):
    """When AI provider network request times out, it seamlessly falls back without crashing."""
    provider = GeminiAIProvider(api_key="mock-key-for-test", timeout_seconds=1)

    with patch("requests.post", side_effect=requests.Timeout("Connection timed out")):
        parsed, source = provider.parse_request("Skin rash and acne treatment")
        assert source == "deterministic_fallback"
        assert parsed["specialty"] == "Dermatologist"


def test_12_safe_handling_of_urgent_symptoms_english_and_sinhala(seeded_env):
    """Urgent emergency symptoms flag isUrgent=True and attach safety guidance with emergency hotline."""
    # 1. English acute chest pain
    resp_en = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "I am experiencing severe chest pain and left arm numbness"},
    )
    assert resp_en.status_code == 200
    data_en = resp_en.json()
    assert data_en["isUrgent"] is True
    assert data_en["safetyGuidance"] is not None
    assert "1990" in data_en["safetyGuidance"]

    # 2. Sinhala acute chest pain
    resp_si = client.post(
        "/api/ai/doctor-recommendations",
        headers={"Authorization": f"Bearer {seeded_env['pat_token']}"},
        json={"query": "මට හදිසියේ පපුවේ කැක්කුම සහ හුස්ම ගන්න අමාරුයි"},
    )
    assert resp_si.status_code == 200
    data_si = resp_si.json()
    assert data_si["isUrgent"] is True
    assert data_si["safetyGuidance"] is not None
    assert "1990" in data_si["safetyGuidance"]
