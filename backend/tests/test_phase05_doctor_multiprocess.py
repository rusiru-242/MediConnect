"""Phase 05 P3-B11: doctor-side mutations under real multi-process concurrency.

Each attempt runs in its own OS process (its own interpreter, MongoClient and connection pool) against the same
local test database; all processes wait for one shared start instant, then send the same request through the
FastAPI app. Phase 03 only tested threads inside one process.
"""
from datetime import datetime, timedelta
import json
import os
import subprocess
import sys
import textwrap
import time

from bson import ObjectId

from tests.test_payment import _make_future_availability, _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _auth, _pay_confirmed
from tests.test_phase03_doctor_system import ITEM, _soap, _visit

WORKER = textwrap.dedent("""
    import json, sys, time
    from fastapi.testclient import TestClient
    from app.main import app
    spec = json.loads(sys.argv[1])
    c = TestClient(app)          # no lifespan: no background worker in these processes
    while time.time() < spec["start"]:
        time.sleep(0.005)
    r = c.request(spec["method"], spec["path"], json=spec.get("json"), headers=spec["headers"])
    print("STATUS", r.status_code)
""")


def _race(method, path, headers, body=None, processes=4, bodies=None):
    root = os.path.dirname(os.path.dirname(__file__))
    start = time.time() + 12  # every process has imported the app before this instant
    procs = []
    for i in range(processes):
        spec = {"method": method, "path": path, "headers": headers, "start": start,
                "json": bodies[i] if bodies else body}
        procs.append(subprocess.Popen([sys.executable, "-c", WORKER, json.dumps(spec)], cwd=root,
                                      env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
    codes = []
    for p in procs:
        out, err = p.communicate(timeout=240)
        assert "STATUS" in out, err[-800:]
        codes.append(int(out.split("STATUS")[1].split()[0]))
    return codes


def test_appointment_completion_applies_once_across_processes(db):
    patient, doctor = _make_test_patient(db, "P05MP1"), _make_test_doctor(db, "P05MP1Doc")
    past = _visit(db, patient, doctor)
    codes = _race("POST", f"/api/doctors/me/appointments/{past}/complete", _auth(doctor))
    assert codes.count(200) == 1 and all(c in (200, 400, 409) for c in codes), codes
    assert db["appointment_events"].count_documents({"appointmentId": past, "event": "APPOINTMENT_COMPLETED"}) == 1


def test_paid_cancellation_creates_one_refund_request_across_processes(db):
    patient, doctor = _make_test_patient(db, "P05MP2"), _make_test_doctor(db, "P05MP2Doc")
    appt, _ = _pay_confirmed(db, patient, doctor, _make_future_availability(db, doctor, 7))
    codes = _race("POST", f"/api/doctors/me/appointments/{appt.id}/cancel", _auth(doctor), {})
    assert codes.count(200) == 1, codes
    assert db["refund_requests"].count_documents({"appointmentId": appt.id}) == 1


def test_renewal_approval_issues_one_prescription_across_processes(db):
    patient, doctor = _make_test_patient(db, "P05MP3"), _make_test_doctor(db, "P05MP3Doc")
    _visit(db, patient, doctor)
    rx = client.post("/api/clinical/prescriptions/sign", headers=_auth(doctor),
                     json={"patientUserId": patient["id"], "medicationItems": [ITEM]}).json()
    rid = client.post("/api/clinical/prescriptions/renewals", headers=_auth(patient),
                      json={"originalPrescriptionId": rx["prescriptionId"],
                            "medicationName": ITEM["medicationName"]}).json()["renewalId"]
    before = db["prescriptions"].count_documents({"patientUserId": patient["id"]})
    codes = _race("POST", f"/api/clinical/prescriptions/renewals/{rid}/review", _auth(doctor),
                  {"decision": "approve", "reason": "Stable"})
    assert codes.count(200) == 1, codes
    assert db["prescriptions"].count_documents({"patientUserId": patient["id"]}) == before + 1


def test_note_signing_signs_once_across_processes(db):
    patient, doctor = _make_test_patient(db, "P05MP4"), _make_test_doctor(db, "P05MP4Doc")
    visit = _visit(db, patient, doctor)
    note_id = client.post("/api/clinical/notes/draft", headers=_auth(doctor), json={
        "patientUserId": patient["id"], "appointmentId": visit, "rawNotes": "Synthetic"}).json()["noteId"]
    assert client.put(f"/api/clinical/notes/{note_id}/draft", json={"content": _soap()},
                      headers=_auth(doctor)).status_code == 200
    codes = _race("POST", f"/api/clinical/notes/{note_id}/sign", _auth(doctor), {"confirmSign": True})
    assert codes.count(200) == 1, codes
    note = db["clinical_notes"].find_one({"noteId": note_id})
    assert note["status"] in ("signed", "SIGNED", "final", "FINAL") or note.get("signedAt")


def test_concurrent_care_plan_updates_lose_no_version(db):
    patient, doctor = _make_test_patient(db, "P05MP5"), _make_test_doctor(db, "P05MP5Doc")
    visit = _visit(db, patient, doctor)
    day = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    plan = client.post("/api/care-plans", headers=_auth(doctor), json={
        "appointmentId": visit, "followUpDate": day, "reason": "Initial", "instructions": "Synthetic"})
    assert plan.status_code in (200, 201), plan.text
    plan_id = plan.json()["id"]
    bodies = [{"reason": f"Update {i}", "instructions": f"Synthetic {i}", "followUpDate": day} for i in range(4)]
    codes = _race("PUT", f"/api/care-plans/{plan_id}", _auth(doctor), bodies=bodies)
    ok = codes.count(200)
    assert ok >= 1 and all(c in (200, 409) for c in codes), codes
    stored = db["care_plans"].find_one({"_id": ObjectId(plan_id)})
    assert stored["version"] == 1 + ok, (stored["version"], codes)  # every accepted update counted, none lost
    assert stored["reason"] in {b["reason"] for b in bodies}


def test_blocked_time_is_created_once_across_processes(db):
    from app.models.doctor_blocked_time import create_doctor_blocked_time_indexes
    create_doctor_blocked_time_indexes(db)  # created at API start-up; TestClient here runs no lifespan
    doctor = _make_test_doctor(db, "P05MP6Doc")
    day = (datetime.now() + timedelta(days=40)).strftime("%Y-%m-%d")
    body = {"date": day, "startTime": "14:00", "endTime": "15:00", "reason": "Synthetic", "confirm": True}
    codes = _race("POST", "/api/doctor/workflow/blocked-time", _auth(doctor), body)
    blocks = db["doctor_blocked_times"].count_documents({"doctorUserId": doctor["id"], "date": day})
    assert codes.count(201) == 1 and codes.count(409) == 3 and blocks == 1, (codes, blocks)  # was 4 x 201, 4 blocks
    again = client.post("/api/doctor/workflow/blocked-time", json=body, headers=_auth(doctor))
    assert again.status_code == 409  # sequential duplicate also refused
    block_id = db["doctor_blocked_times"].find_one({"doctorUserId": doctor["id"], "date": day})["_id"]
    assert client.delete(f"/api/doctors/me/blocked-time/{block_id}", headers=_auth(doctor)).status_code == 200
    assert client.post("/api/doctor/workflow/blocked-time", json=body, headers=_auth(doctor)).status_code == 201
