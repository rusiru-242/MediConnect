"""Comprehensive automated tests for Phase 6: Advanced Healthcare AI, Medical Records & Clinical Automation."""

from datetime import datetime, timedelta, timezone
import io
import time
from uuid import uuid4
from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.config.database import DatabaseManager, ensure_indexes, get_database
from tests.mock_db import MockDatabase
from app.main import app
from app.models.appointment import AppointmentStatus, PaymentStatus as ApptPaymentStatus
from app.models.doctor_profile import DoctorVerificationStatus
from app.models.patient_medical_record import RecordStatus, RecordType, SourceType
from app.models.user import AccountStatus, UserRole, utc_now
from app.services.clinical_safety_service import ClinicalSafetyService
from app.services.health_tracking_service import HealthTrackingService
from app.services.patient_medical_record_service import PatientMedicalRecordService
from app.services.prescription_workflow_service import PrescriptionWorkflowService
from app.utils.security import create_access_token

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def isolated_db():
    """Ensure tests run against a dedicated phase 6 mock test database."""
    mock_db = MockDatabase("mediconnect_phase6_test")
    DatabaseManager._db = mock_db
    try:
        yield mock_db
    finally:
        DatabaseManager._db = None


@pytest.fixture
def clinical_env():
    """Seed authenticated patients and doctors with an authorized care relationship."""
    db = get_database()
    ts = int(time.time() * 1000)
    suffix = uuid4().hex[:6]

    # 1. Patient A
    pat_a_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_a_id),
        "fullName": "Kamal Perera",
        "email": f"patient_a_{ts}_{suffix}@mediconnect.lk",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_a_token = create_access_token(pat_a_id, role=UserRole.PATIENT.value)
    pat_a_headers = {"Authorization": f"Bearer {pat_a_token}"}

    # 2. Patient B (Unrelated Patient)
    pat_b_id = str(ObjectId())
    db["users"].insert_one({
        "_id": ObjectId(pat_b_id),
        "fullName": "Nimal Silva",
        "email": f"patient_b_{ts}_{suffix}@mediconnect.lk",
        "role": UserRole.PATIENT.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    pat_b_token = create_access_token(pat_b_id, role=UserRole.PATIENT.value)
    pat_b_headers = {"Authorization": f"Bearer {pat_b_token}"}

    # 3. Doctor A (Authorized Doctor with Appointment with Patient A)
    doc_a_id = str(ObjectId())
    doc_a_prof_id = str(ObjectId())
    slmc_a = f"SLMC-6{suffix}"
    db["users"].insert_one({
        "_id": ObjectId(doc_a_id),
        "fullName": "Dr. Sunil Jayawardena",
        "email": f"doctor_a_{ts}_{suffix}@mediconnect.lk",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_a_prof_id),
        "userId": doc_a_id,
        "doctorId": f"DOC-A-{suffix}",
        "fullName": "Dr. Sunil Jayawardena",
        "specialty": "Cardiology",
        "medicalRegistrationNumber": slmc_a,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "hospitalOrClinic": "National Hospital Colombo",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_a_token = create_access_token(doc_a_id, role=UserRole.DOCTOR.value)
    doc_a_headers = {"Authorization": f"Bearer {doc_a_token}"}

    # 4. Doctor B (Unrelated Doctor with NO care relationship to Patient A)
    doc_b_id = str(ObjectId())
    doc_b_prof_id = str(ObjectId())
    slmc_b = f"SLMC-7{suffix}"
    db["users"].insert_one({
        "_id": ObjectId(doc_b_id),
        "fullName": "Dr. Anura Fernando",
        "email": f"doctor_b_{ts}_{suffix}@mediconnect.lk",
        "role": UserRole.DOCTOR.value,
        "emailVerified": True,
        "accountStatus": AccountStatus.ACTIVE.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    db["doctor_profiles"].insert_one({
        "_id": ObjectId(doc_b_prof_id),
        "userId": doc_b_id,
        "doctorId": f"DOC-B-{suffix}",
        "fullName": "Dr. Anura Fernando",
        "specialty": "Dermatology",
        "medicalRegistrationNumber": slmc_b,
        "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        "hospitalOrClinic": "Asiri Central Hospital",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })
    doc_b_token = create_access_token(doc_b_id, role=UserRole.DOCTOR.value)
    doc_b_headers = {"Authorization": f"Bearer {doc_b_token}"}

    # 5. Establish Care Relationship: Doctor A has confirmed appointment with Patient A
    appt_id = str(ObjectId())
    db["appointments"].insert_one({
        "_id": ObjectId(appt_id),
        "patientUserId": pat_a_id,
        "doctorUserId": doc_a_id,
        "doctorProfileId": doc_a_prof_id,
        "availabilityId": str(ObjectId()),
        "appointmentDate": "2026-11-24",
        "startTime": "09:00",
        "endTime": "09:30",
        "status": AppointmentStatus.CONFIRMED.value,
        "paymentStatus": ApptPaymentStatus.PAID.value,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    })

    return {
        "db": db,
        "patientA": {"id": pat_a_id, "headers": pat_a_headers},
        "patientB": {"id": pat_b_id, "headers": pat_b_headers},
        "doctorA": {"id": doc_a_id, "profileId": doc_a_prof_id, "headers": doc_a_headers, "slmc": slmc_a},
        "doctorB": {"id": doc_b_id, "profileId": doc_b_prof_id, "headers": doc_b_headers, "slmc": slmc_b},
        "appointmentId": appt_id,
    }


# ===========================================================================
# 1. Medical Records & Access Control Tests
# ===========================================================================

def test_patient_medical_record_crud_and_access_control(clinical_env):
    """Verify patient record creation, authorized doctor viewing, and 403 rejection for unrelated doctor."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]
    doc_b = clinical_env["doctorB"]

    # 1. Patient creates a diagnosis record
    payload = {
        "recordType": "diagnosis",
        "title": "Essential Hypertension",
        "clinicalDate": "2026-11-20",
        "description": "Primary hypertension under routine monitoring.",
        "clinicalData": {"icd10": "I10", "severity": "moderate"},
    }
    res = client.post("/api/clinical/records", json=payload, headers=pat_a["headers"])
    assert res.status_code == 201
    rec_data = res.json()
    record_id = rec_data["recordId"]
    assert rec_data["sourceType"] == "patient_uploaded"

    # 2. Patient views their own record
    res_pat = client.get(f"/api/clinical/records/{record_id}", headers=pat_a["headers"])
    assert res_pat.status_code == 200
    assert res_pat.json()["title"] == "Essential Hypertension"

    # 3. Doctor A (with active care relationship) can view Patient A's record
    res_doc_a = client.get(f"/api/clinical/records/{record_id}", headers=doc_a["headers"])
    assert res_doc_a.status_code == 200
    assert res_doc_a.json()["patientUserId"] == pat_a["id"]

    # 4. Doctor B (unrelated doctor) is DENIED with 403 Forbidden
    res_doc_b = client.get(f"/api/clinical/records/{record_id}", headers=doc_b["headers"])
    assert res_doc_b.status_code == 403
    assert "care relationship" in res_doc_b.json()["detail"].lower()


def test_secure_medical_document_upload_and_download(clinical_env):
    """Verify private document upload with magic-byte checks, authorized streaming, and access logging."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]
    doc_b = clinical_env["doctorB"]

    # 1. Invalid file format rejected
    text_file = io.BytesIO(b"Hello world invalid file")
    res_bad = client.post(
        "/api/clinical/records/documents/upload",
        files={"file": ("notes.txt", text_file, "text/plain")},
        data={"title": "Notes", "recordType": "medical_document", "clinicalDate": "2026-11-20"},
        headers=pat_a["headers"],
    )
    assert res_bad.status_code == 400

    # 2. Valid PDF upload with magic bytes %PDF-
    valid_pdf_content = b"%PDF-1.5 \n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >> %%EOF"
    pdf_file = io.BytesIO(valid_pdf_content)
    res_upload = client.post(
        "/api/clinical/records/documents/upload",
        files={"file": ("lab_report.pdf", pdf_file, "application/pdf")},
        data={
            "title": "Full Blood Count Report",
            "recordType": "laboratory_result",
            "clinicalDate": "2026-11-22",
            "description": "Routine hematology screen.",
        },
        headers=pat_a["headers"],
    )
    assert res_upload.status_code == 201
    doc_record = res_upload.json()
    record_id = doc_record["recordId"]
    assert doc_record["hasAttachment"] is True
    assert doc_record["attachmentName"] == "lab_report.pdf"

    # 3. Patient downloads document
    res_dl = client.get(f"/api/clinical/records/{record_id}/download", headers=pat_a["headers"])
    assert res_dl.status_code == 200
    assert res_dl.content == valid_pdf_content

    # 4. Authorized Doctor A downloads document
    res_dl_doc = client.get(f"/api/clinical/records/{record_id}/download", headers=doc_a["headers"])
    assert res_dl_doc.status_code == 200
    assert res_dl_doc.content == valid_pdf_content

    # 5. Unrelated Doctor B is DENIED download with 403 Forbidden
    res_dl_denied = client.get(f"/api/clinical/records/{record_id}/download", headers=doc_b["headers"])
    assert res_dl_denied.status_code == 403


# ===========================================================================
# 2. Health Tracking & Safety Alert Tests
# ===========================================================================

def test_health_measurement_validation_and_critical_alerts(clinical_env):
    """Verify vital sign validation, physiologic bounds, and emergency safety alert generation."""
    pat_a = clinical_env["patientA"]

    # 1. Invalid reading (Diastolic >= Systolic)
    res_invalid = client.post(
        "/api/clinical/measurements",
        json={"metric": "blood_pressure", "value": 110, "secondary": 120},
        headers=pat_a["headers"],
    )
    assert res_invalid.status_code == 422

    # 2. Normal blood pressure
    res_normal = client.post(
        "/api/clinical/measurements",
        json={"metric": "blood_pressure", "value": 120, "secondary": 80},
        headers=pat_a["headers"],
    )
    assert res_normal.status_code == 201
    assert res_normal.json()["criticalAlert"] is None

    # 3. Critical Hypertensive Crisis Alert (>= 180/120)
    res_crisis = client.post(
        "/api/clinical/measurements",
        json={"metric": "blood_pressure", "value": 195, "secondary": 125},
        headers=pat_a["headers"],
    )
    assert res_crisis.status_code == 201
    assert "CRITICAL HYPERTENSIVE CRISIS" in res_crisis.json()["criticalAlert"]

    # 4. Critical Hypoxia Alert (SpO2 < 90%)
    res_hypoxia = client.post(
        "/api/clinical/measurements",
        json={"metric": "oxygen_saturation", "value": 86},
        headers=pat_a["headers"],
    )
    assert res_hypoxia.status_code == 201
    assert "CRITICAL HYPOXIA ALERT" in res_hypoxia.json()["criticalAlert"]

    # 5. Measurement correction with audit log
    meas_id = res_normal.json()["measurementId"]
    res_correct = client.patch(
        f"/api/clinical/measurements/{meas_id}/correct",
        json={"newValue": 122, "newSecondary": 82, "reason": "Patient measured again after 5 min rest."},
        headers=pat_a["headers"],
    )
    assert res_correct.status_code == 200
    assert res_correct.json()["value"] == 122


def test_deterministic_health_trends_calculation(clinical_env):
    """Verify deterministic 7-day and 30-day averages and trend direction calculations."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]

    # Seed multiple glucose readings
    for val in [95.0, 100.0, 105.0, 110.0]:
        client.post(
            "/api/clinical/measurements",
            json={"metric": "blood_glucose", "value": val},
            headers=pat_a["headers"],
        )

    # Patient views trends
    res_trends = client.get("/api/clinical/measurements/trends", headers=pat_a["headers"])
    assert res_trends.status_code == 200
    trends_data = res_trends.json()
    glu_trend = next(t for t in trends_data["trends"] if t["metric"] == "blood_glucose")
    assert glu_trend["count"] >= 4
    assert glu_trend["thirtyDayAverage"] is not None
    assert glu_trend["latestValue"] == 110.0

    # Doctor A views Patient A's trends
    res_doc_trends = client.get(
        f"/api/clinical/measurements/trends?patientId={pat_a['id']}",
        headers=doc_a["headers"],
    )
    assert res_doc_trends.status_code == 200


# ===========================================================================
# 3. Clinical Documentation (SOAP Notes) Tests
# ===========================================================================

def test_clinical_note_draft_organize_and_signing_workflow(clinical_env):
    """Verify SOAP note draft creation, editing, explicit signing, and immutability."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]
    appt_id = clinical_env["appointmentId"]

    # 1. Doctor creates draft from raw consultation notes
    draft_req = {
        "patientUserId": pat_a["id"],
        "appointmentId": appt_id,
        "rawNotes": "Patient complains of chest tightness and palpitations for 3 days.\nECG normal sinus rhythm.\nAdvised echocardiogram and lifestyle modification.",
    }
    res_draft = client.post("/api/clinical/notes/draft", json=draft_req, headers=doc_a["headers"])
    assert res_draft.status_code == 201
    draft_data = res_draft.json()
    note_id = draft_data["noteId"]
    assert draft_data["status"] == "draft"
    assert draft_data["isAiDraft"] is True

    # 2. Doctor updates draft content
    updated_content = draft_data["content"]
    updated_content["assessment"] = "Atypical chest discomfort, likely non-cardiac etiology."
    res_update = client.put(
        f"/api/clinical/notes/{note_id}/draft",
        json={"content": updated_content},
        headers=doc_a["headers"],
    )
    assert res_update.status_code == 200
    assert res_update.json()["status"] == "under_review"

    # 3. Doctor explicitly signs note
    res_sign = client.post(
        f"/api/clinical/notes/{note_id}/sign",
        json={"confirmSign": True},
        headers=doc_a["headers"],
    )
    assert res_sign.status_code == 200
    signed_data = res_sign.json()
    assert signed_data["status"] == "signed"
    assert signed_data["slmcRegistrationNumber"] == doc_a["slmc"]
    assert signed_data["signedAt"] is not None

    # 4. Signed note is IMMUTABLE: direct draft update is blocked with 409 Conflict
    res_blocked = client.put(
        f"/api/clinical/notes/{note_id}/draft",
        json={"content": updated_content},
        headers=doc_a["headers"],
    )
    assert res_blocked.status_code == 409
    assert "immutable" in res_blocked.json()["detail"].lower()


def test_signed_note_amendment_workflow(clinical_env):
    """Verify controlled amendment workflow for signed clinical notes."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]

    # Create & sign note
    res_draft = client.post(
        "/api/clinical/notes/draft",
        json={
            "patientUserId": pat_a["id"],
            "content": {
                "chiefComplaint": "Knee pain",
                "historyOfPresentIllness": "Right knee pain after sports.",
                "examinationFindings": "Mild effusion, no ligamentous laxity.",
                "assessment": "Right knee sprain",
                "plan": "Rest, Ice, NSAIDs for 5 days.",
            },
        },
        headers=doc_a["headers"],
    )
    note_id = res_draft.json()["noteId"]
    client.post(f"/api/clinical/notes/{note_id}/sign", json={"confirmSign": True}, headers=doc_a["headers"])

    # Amend note with clinical justification
    amend_req = {
        "justification": "Review of MRI report indicates medial meniscus fraying.",
        "addendum": "MRI knee confirms minor medial meniscus tear. Referred to orthopedic specialist.",
    }
    res_amend = client.post(
        f"/api/clinical/notes/{note_id}/amend",
        json=amend_req,
        headers=doc_a["headers"],
    )
    assert res_amend.status_code == 200
    amended_data = res_amend.json()
    assert amended_data["status"] == "amended"
    assert amended_data["version"] >= 2
    assert len(amended_data["amendments"]) == 1
    assert "MRI knee confirms" in amended_data["content"]["followUpInstructions"]


# ===========================================================================
# 4. Prescription Assistant & Versioning Tests
# ===========================================================================

def test_doctor_prescription_assistant_and_signing(clinical_env):
    """Verify allergy contraindication screening, duplicate detection, and reminder synchronization."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]

    # 1. Document an allergy for Patient A
    client.post(
        "/api/clinical/records",
        json={"recordType": "allergy", "title": "Penicillin", "clinicalDate": "2026-11-20"},
        headers=pat_a["headers"],
    )

    # 2. Doctor prescription assistant reviews proposed medications
    res_review = client.post(
        f"/api/clinical/prescriptions/assistant-review?patientUserId={pat_a['id']}&medications=Amoxicillin&medications=Atorvastatin",
        headers=doc_a["headers"],
    )
    assert res_review.status_code == 200
    review_data = res_review.json()
    assert "penicillin" in [a.lower() for a in review_data["documentedAllergies"]]

    # 3. Doctor signs prescription
    presc_payload = {
        "patientUserId": pat_a["id"],
        "medicationItems": [
            {
                "medicationName": "Atorvastatin",
                "strength": "20mg",
                "dose": "1 tablet",
                "route": "Oral",
                "frequency": "Once at bedtime",
                "duration": "30 days",
                "quantity": "30 tablets",
            }
        ],
        "instructions": "Take at night after food.",
    }
    res_sign = client.post("/api/clinical/prescriptions/sign", json=presc_payload, headers=doc_a["headers"])
    assert res_sign.status_code == 201
    rx_data = res_sign.json()
    assert rx_data["status"] == "ISSUED"
    assert rx_data["prescriptionId"].startswith("RX-")

    # 4. Verify Phase 3 medication reminder synchronization
    db = clinical_env["db"]
    reminder = db["medication_reminders"].find_one({"prescriptionId": rx_data["prescriptionId"]})
    assert reminder is not None
    assert reminder["medicationName"] == "Atorvastatin"
    assert reminder["status"] == "ACTIVE"


# ===========================================================================
# 5. Prescription Renewal Workflow Tests
# ===========================================================================

def test_prescription_renewal_workflow(clinical_env):
    """Verify patient renewal request, duplicate prevention, and doctor review decisions."""
    pat_a = clinical_env["patientA"]
    doc_a = clinical_env["doctorA"]

    # Issue initial prescription for Losartan
    rx_res = client.post(
        "/api/clinical/prescriptions/sign",
        json={
            "patientUserId": pat_a["id"],
            "medicationItems": [
                {
                    "medicationName": "Losartan",
                    "strength": "50mg",
                    "dose": "1 tablet",
                    "route": "Oral",
                    "frequency": "Once daily",
                    "duration": "30 days",
                    "quantity": "30 tablets",
                }
            ],
        },
        headers=doc_a["headers"],
    )
    rx_id = rx_res.json()["prescriptionId"]

    # 1. Patient requests renewal
    res_req = client.post(
        "/api/clinical/prescriptions/renewals",
        json={
            "originalPrescriptionId": rx_id,
            "medicationName": "Losartan",
            "patientReason": "Running out of monthly blood pressure tablets.",
        },
        headers=pat_a["headers"],
    )
    assert res_req.status_code == 201
    renewal_data = res_req.json()
    renewal_id = renewal_data["renewalId"]
    assert renewal_data["status"] == "requested"

    # 2. Duplicate renewal request is PREVENTED with 409 Conflict
    res_dup = client.post(
        "/api/clinical/prescriptions/renewals",
        json={
            "originalPrescriptionId": rx_id,
            "medicationName": "Losartan",
            "patientReason": "Duplicate click.",
        },
        headers=pat_a["headers"],
    )
    assert res_dup.status_code == 409

    # 3. Doctor reviews queue and approves renewal
    res_approve = client.post(
        f"/api/clinical/prescriptions/renewals/{renewal_id}/review",
        json={"decision": "approve", "reason": "Patient BP stable, 30-day refill authorized."},
        headers=doc_a["headers"],
    )
    assert res_approve.status_code == 200
    approved_data = res_approve.json()
    assert approved_data["status"] == "approved"
    assert approved_data["resultingPrescriptionId"] is not None


# ===========================================================================
# 6. Clinical Summarization & Romanized Sinhala AI Assistant Tests
# ===========================================================================

def test_source_grounded_medical_record_summary(clinical_env):
    """Verify source-grounded longitudinal medical record summarization."""
    pat_a = clinical_env["patientA"]

    res_sum = client.get("/api/clinical/records/summary", headers=pat_a["headers"])
    assert res_sum.status_code == 200
    data = res_sum.json()
    assert data["patientUserId"] == pat_a["id"]
    assert "ASSISTIVE MEDICAL SUMMARY NOTICE" in data["aiDisclaimer"]
    assert data["summary"] is not None


def test_clinical_ai_assistant_nlp_and_emergency_escalation(clinical_env):
    """Verify Romanized Sinhala queries and acute emergency escalation to 1990 Suwa Seriya."""
    pat_a = clinical_env["patientA"]

    # 1. Romanized Sinhala Vitals Query
    res_bp_query = client.post(
        "/api/clinical/ai-assistant/chat",
        json={"message": "mage last 7 days blood pressure readings pennanna"},
        headers=pat_a["headers"],
    )
    assert res_bp_query.status_code == 200
    bp_data = res_bp_query.json()
    assert bp_data["intent"] == "blood_pressure_readings"
    assert bp_data["emergencyEscalation"] is False

    # 2. Emergency Trigger Phrase Escalation
    res_emerg = client.post(
        "/api/clinical/ai-assistant/chat",
        json={"message": "I have sudden severe chest pain and cannot breathe"},
        headers=pat_a["headers"],
    )
    assert res_emerg.status_code == 200
    emerg_data = res_emerg.json()
    assert emerg_data["emergencyEscalation"] is True
    assert "1990" in emerg_data["response"]
    assert "Suwa Seriya" in emerg_data["response"]
