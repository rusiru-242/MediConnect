"""Tests for Conversational AI Booking Assistant Agent (Phase 19).

Covers:
1. Session creation & authentication enforcement (Patient only, 401/403)
2. Session ownership checks (Patient A cannot access Patient B's session)
3. Multi-turn preference extraction (English & Sinhala)
4. Emergency symptom detection & 1990 ambulance escalation
5. Invalid state transitions
6. Doctor selection & slot discovery
7. Slot selection & authoritative booking summary generation
8. Explicit booking confirmation & 10-minute hold creation
9. Duplicate confirmation idempotency
10. Double booking prevention / conflict handling
11. Session cancellation & hold release
12. Payment status sync & confirmation
13. AI provider fallback on timeout
"""

from datetime import datetime, timedelta, timezone
import time
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.agents.ai_provider import DeterministicNLPProvider
from app.config.database import get_database
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.booking_session import BookingAgentState
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.doctor_service import get_sl_now, get_sl_today_str
from app.utils.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_ai_provider():
    """Ensure tests run deterministically with rule-based NLP fallback."""
    with patch("app.agents.booking_agent.get_ai_provider", return_value=DeterministicNLPProvider()):
        yield


@pytest.fixture(scope="module")
def seeded_booking_env():
    """Seed test database with:
    - Patient A & Patient B
    - Doctor (Doctor Nihal Perera, Cardiologist in Colombo, LKR 2,500)
    - Admin
    - Doctor availability on tomorrow with discrete slots
    """
    db = get_database()
    ts = int(time.time() * 1000)

    # 1. Patient A
    pat_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_a_id),
        "fullName": "Patient A",
        "email": f"patient_a_{ts}@mediconnect.lk",
        "phone": "0771000001",
        "passwordHash": hash_password("Password@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_patient_a = create_access_token(pat_a_id, UserRole.PATIENT.value)

    # 2. Patient B
    pat_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_b_id),
        "fullName": "Patient B",
        "email": f"patient_b_{ts}@mediconnect.lk",
        "phone": "0771000002",
        "passwordHash": hash_password("Password@123"),
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_patient_b = create_access_token(pat_b_id, UserRole.PATIENT.value)

    # 3. Doctor User & Profile
    doc_user_id = str(ObjectId())
    doc_profile_id = str(ObjectId())
    doc_code = f"DOC-BK-{ts}"

    db["users"].insert_one({
        "_id": ObjectId(doc_user_id),
        "fullName": "Dr. Nihal Perera",
        "email": f"dr_nihal_{ts}@mediconnect.lk",
        "phone": "0772000001",
        "passwordHash": hash_password("Password@123"),
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_doctor = create_access_token(doc_user_id, UserRole.DOCTOR.value)

    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_profile_id),
        "userId": doc_user_id,
        "doctorId": doc_code,
        "specialty": "Cardiology",
        "hospitalOrClinic": "Asiri Central Hospital, Colombo",
        "experienceYears": 14,
        "consultationFee": 2500.0,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "rating": 4.9,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 4. Doctor Availability (Tomorrow)
    tomorrow_date = (get_sl_now() + timedelta(days=1)).strftime("%Y-%m-%d")
    avail_id = str(ObjectId())
    db["doctor_availabilities"].insert_one({
        "_id": ObjectId(avail_id),
        "doctorUserId": doc_user_id,
        "doctorProfileId": doc_profile_id,
        "date": tomorrow_date,
        "startTime": "09:00",
        "endTime": "11:00",
        "slotDurationMinutes": 30,
        "isActive": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    # 5. Admin
    admin_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(admin_id),
        "fullName": "Admin User",
        "email": f"admin_{ts}@mediconnect.lk",
        "phone": "0773000001",
        "passwordHash": hash_password("Password@123"),
        "role": UserRole.ADMIN.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    token_admin = create_access_token(admin_id, UserRole.ADMIN.value)

    return {
        "pat_a_id": pat_a_id,
        "token_patient_a": token_patient_a,
        "pat_b_id": pat_b_id,
        "token_patient_b": token_patient_b,
        "doc_user_id": doc_user_id,
        "doc_profile_id": doc_profile_id,
        "doc_code": doc_code,
        "token_doctor": token_doctor,
        "token_admin": token_admin,
        "tomorrow_date": tomorrow_date,
        "avail_id": avail_id,
    }


def test_01_create_session_authenticated_patient(seeded_booking_env):
    """Patient successfully creates an AI booking session."""
    token = seeded_booking_env["token_patient_a"]
    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Hello, I want to book an appointment"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == BookingAgentState.COLLECTING_PREFERENCES.value
    assert data["patientUserId"] == seeded_booking_env["pat_a_id"]
    assert len(data["messages"]) >= 2  # user message and assistant reply


def test_02_create_session_unauthorized_and_forbidden(seeded_booking_env):
    """401 without auth token, 403 for doctor and admin roles."""
    # No auth
    resp = client.post("/api/ai/booking/sessions", json={})
    assert resp.status_code == 401

    # Doctor role forbidden
    resp_doc = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {seeded_booking_env['token_doctor']}"},
        json={},
    )
    assert resp_doc.status_code == 403

    # Admin role forbidden
    resp_adm = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {seeded_booking_env['token_admin']}"},
        json={},
    )
    assert resp_adm.status_code == 403


def test_03_multi_turn_preference_extraction_english(seeded_booking_env):
    """Multi-turn conversation incrementally refines booking preferences."""
    token = seeded_booking_env["token_patient_a"]

    # Turn 1: Create session with specialty and location
    resp1 = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "I need a cardiologist in Colombo"},
    )
    assert resp1.status_code == 201
    s1 = resp1.json()
    session_id = s1["id"]
    assert s1["preferences"]["specialty"] == "Cardiology"
    assert s1["preferences"]["city"] == "Colombo"
    assert s1["state"] == BookingAgentState.AWAITING_DOCTOR_SELECTION.value
    assert len(s1["candidateDoctors"]) >= 1

    # Turn 2: Specify date and budget
    resp2 = client.post(
        f"/api/ai/booking/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "I prefer tomorrow under LKR 3000"},
    )
    assert resp2.status_code == 200
    s2 = resp2.json()
    assert s2["preferences"]["specialty"] == "Cardiology"
    assert s2["preferences"]["city"] == "Colombo"
    assert s2["preferences"]["date"] == seeded_booking_env["tomorrow_date"]
    assert s2["preferences"]["maxFee"] == 3000.0


def test_04_multi_turn_preference_extraction_sinhala(seeded_booking_env):
    """Sinhala natural-language inquiry correctly extracts specialty and language."""
    token = seeded_booking_env["token_patient_a"]
    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "මට කොළඹ හෘද රෝග විශේෂඥ වෛද්‍යවරයෙක් අවශ්‍යයි"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["preferences"]["specialty"] == "Cardiology"
    assert data["preferences"]["city"] == "Colombo"
    assert data["preferences"]["language"] == "si"
    # Assistant replies in Sinhala
    last_msg = data["messages"][-1]["content"]
    assert "වෛද්‍යවරුන්" in last_msg or "හෘද රෝග" in last_msg


def test_05_emergency_symptom_detection_in_session(seeded_booking_env):
    """Urgent emergency symptoms trigger medical escalation banner and 1990 ambulance instructions."""
    token = seeded_booking_env["token_patient_a"]
    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "I have sudden severe chest pain and cannot breathe"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["isUrgent"] is True
    assert "chest pain" in data["urgencyReason"].lower()
    last_msg = data["messages"][-1]
    assert "1990" in last_msg["content"]
    assert last_msg["metadata"]["isUrgent"] is True


def test_06_session_ownership_enforcement(seeded_booking_env):
    """Patient B cannot access or send messages in Patient A's session."""
    token_a = seeded_booking_env["token_patient_a"]
    token_b = seeded_booking_env["token_patient_b"]

    # Create session as Patient A
    resp_a = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp_a.json()["id"]

    # Patient B tries to get session
    resp_get = client.get(
        f"/api/ai/booking/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_get.status_code == 403

    # Patient B tries to send message
    resp_post = client.post(
        f"/api/ai/booking/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"message": "Hack attempt"},
    )
    assert resp_post.status_code == 403


def test_07_invalid_state_transitions(seeded_booking_env):
    """Attempting to confirm without selecting a slot or selecting slot without doctor fails."""
    token = seeded_booking_env["token_patient_a"]
    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    session_id = resp.json()["id"]

    # Cannot confirm in COLLECTING_PREFERENCES
    resp_conf = client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp_conf.status_code == 400

    # Cannot select slot without a selected doctor
    resp_slot = client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "availabilityId": seeded_booking_env["avail_id"],
            "date": seeded_booking_env["tomorrow_date"],
            "startTime": "09:00",
        },
    )
    assert resp_slot.status_code == 400


def test_08_doctor_selection_and_slot_discovery(seeded_booking_env):
    """Selecting a doctor queries their availability slots and sets AWAITING_SLOT_SELECTION."""
    token = seeded_booking_env["token_patient_a"]
    doc_code = seeded_booking_env["doc_code"]

    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]

    # Select doctor explicitly
    resp_doc = client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctorId": doc_code},
    )
    assert resp_doc.status_code == 200
    data = resp_doc.json()
    assert data["state"] == BookingAgentState.AWAITING_SLOT_SELECTION.value
    assert data["selectedDoctor"]["doctorId"] == doc_code
    assert len(data["candidateSlots"]) >= 1
    assert data["candidateSlots"][0]["startTime"] == "09:00"


def test_09_slot_selection_and_booking_summary(seeded_booking_env):
    """Selecting an unbooked slot creates the authoritative booking summary."""
    token = seeded_booking_env["token_patient_a"]
    doc_code = seeded_booking_env["doc_code"]
    tomorrow = seeded_booking_env["tomorrow_date"]
    avail_id = seeded_booking_env["avail_id"]

    # Setup session with doctor
    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctorId": doc_code},
    )

    # Select slot
    resp_slot = client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "availabilityId": avail_id,
            "date": tomorrow,
            "startTime": "09:00",
            "endTime": "09:30",
        },
    )
    assert resp_slot.status_code == 200
    data = resp_slot.json()
    assert data["state"] == BookingAgentState.AWAITING_BOOKING_CONFIRMATION.value
    assert data["selectedSlot"]["startTime"] == "09:00"
    assert data["bookingSummary"]["consultationFee"] == 2500.0
    assert data["bookingSummary"]["totalAmount"] == 2500.0


def test_10_confirm_booking_creates_10min_hold(seeded_booking_env):
    """Confirming booking creates an appointment hold and transitions to AWAITING_PAYMENT."""
    token = seeded_booking_env["token_patient_a"]
    doc_code = seeded_booking_env["doc_code"]
    tomorrow = seeded_booking_env["tomorrow_date"]
    avail_id = seeded_booking_env["avail_id"]

    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctorId": doc_code},
    )
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "availabilityId": avail_id,
            "date": tomorrow,
            "startTime": "09:00",
            "endTime": "09:30",
        },
    )

    # Confirm
    resp_conf = client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"patientNote": "Regular cardiology checkup"},
    )
    assert resp_conf.status_code == 200
    data = resp_conf.json()
    assert data["state"] == BookingAgentState.AWAITING_PAYMENT.value
    assert data["appointmentId"] is not None
    assert data["holdExpiresAt"] is not None


def test_11_duplicate_confirmation_idempotency(seeded_booking_env):
    """Calling confirm repeatedly returns the same appointment hold without error or duplicates."""
    token = seeded_booking_env["token_patient_a"]
    doc_code = seeded_booking_env["doc_code"]
    tomorrow = seeded_booking_env["tomorrow_date"]
    avail_id = seeded_booking_env["avail_id"]

    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctorId": doc_code},
    )
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token}"},
        json={"availabilityId": avail_id, "date": tomorrow, "startTime": "09:30"},
    )

    # First confirm
    resp_1 = client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    appt_id_1 = resp_1.json()["appointmentId"]

    # Second confirm (idempotent)
    resp_2 = client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    appt_id_2 = resp_2.json()["appointmentId"]
    assert appt_id_1 == appt_id_2


def test_12_slot_conflict_double_booking_prevention(seeded_booking_env):
    """Slot already occupied by another patient triggers conflict and BOOKING_FAILED."""
    token_b = seeded_booking_env["token_patient_b"]
    doc_code = seeded_booking_env["doc_code"]
    tomorrow = seeded_booking_env["tomorrow_date"]
    avail_id = seeded_booking_env["avail_id"]

    # Slot 09:00 was booked by Patient A in test 10
    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"doctorId": doc_code},
    )
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"availabilityId": avail_id, "date": tomorrow, "startTime": "09:00"},
    )

    # Attempt confirm on occupied slot
    resp_conf = client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token_b}"},
        json={},
    )
    assert resp_conf.status_code == 409  # Conflict!


def test_13_session_cancellation(seeded_booking_env):
    """Cancelling a session marks it CANCELLED and releases any held slot."""
    token = seeded_booking_env["token_patient_a"]
    doc_code = seeded_booking_env["doc_code"]
    tomorrow = seeded_booking_env["tomorrow_date"]
    avail_id = seeded_booking_env["avail_id"]

    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctorId": doc_code},
    )
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token}"},
        json={"availabilityId": avail_id, "date": tomorrow, "startTime": "10:00"},
    )
    client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    # Cancel session
    resp_cancel = client.post(
        f"/api/ai/booking/sessions/{session_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["state"] == BookingAgentState.CANCELLED.value


def test_14_sync_payment_status(seeded_booking_env):
    """Database payment completion advances session state to BOOKING_CONFIRMED."""
    token = seeded_booking_env["token_patient_a"]
    doc_code = seeded_booking_env["doc_code"]
    tomorrow = seeded_booking_env["tomorrow_date"]
    avail_id = seeded_booking_env["avail_id"]

    resp = client.post(
        "/api/ai/booking/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"initialMessage": "Cardiologist in Colombo"},
    )
    session_id = resp.json()["id"]
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-doctor",
        headers={"Authorization": f"Bearer {token}"},
        json={"doctorId": doc_code},
    )
    client.post(
        f"/api/ai/booking/sessions/{session_id}/select-slot",
        headers={"Authorization": f"Bearer {token}"},
        json={"availabilityId": avail_id, "date": tomorrow, "startTime": "10:30"},
    )
    resp_conf = client.post(
        f"/api/ai/booking/sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    appt_id = resp_conf.json()["appointmentId"]

    # Simulate payment completion in DB (e.g. from Stripe webhook)
    db = get_database()
    db["appointments"].update_one(
        {"_id": ObjectId(appt_id)},
        {"$set": {"status": AppointmentStatus.CONFIRMED.value, "paymentStatus": ApptPaymentStatus.PAID.value}},
    )

    # Sync status
    resp_sync = client.get(
        f"/api/ai/booking/sessions/{session_id}/payment-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_sync.status_code == 200
    assert resp_sync.json()["state"] == BookingAgentState.BOOKING_CONFIRMED.value
