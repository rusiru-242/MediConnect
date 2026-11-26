"""Phase 05 P4-O1 (one malformed record must not fail a list) and P4-O4 (admin lists page in MongoDB)."""
from unittest.mock import patch
import uuid

from bson import ObjectId

from app.models.appointment import utc_now
from tests.test_payment import _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _admin, _auth


def test_p4o1_malformed_record_is_reported_not_fatal(db):
    patient = _make_test_patient(db, "P05O1")
    ok = client.post("/api/clinical/records", headers=_auth(patient), json={
        "title": "Synthetic history", "recordType": "medical_history", "clinicalDate": "2026-11-01",
        "description": "Synthetic"})
    assert ok.status_code in (200, 201), ok.text
    broken = f"MED-BROKEN-{uuid.uuid4().hex[:8]}"  # unique: the local test database is reused between runs
    db["patient_medical_records"].insert_one({"recordId": broken, "patientUserId": patient["id"],
                                              "status": "active", "clinicalDate": "2026-11-02",
                                              "recordType": "not-a-type", "createdAt": utc_now()})
    res = client.get("/api/clinical/records", headers=_auth(patient))
    assert res.status_code == 200, res.text  # was 500 for the whole list
    body = res.json()
    assert body["unreadableRecords"] == 1 and body["unreadableRecordRefs"] == [broken]
    assert len(body["records"]) == 1


def test_p4o4_admin_appointments_search_count_and_pages_in_mongodb(db):
    admin = _admin(db)
    tag = uuid.uuid4().hex[:8]
    patient = _make_test_patient(db, f"P05O4{tag}")
    db["users"].update_one({"_id": ObjectId(patient["id"])}, {"$set": {"fullName": f"Searchable {tag}"}})
    doctor = _make_test_doctor(db, f"P05O4D{tag}")
    for i in range(5):
        db["appointments"].insert_one({"patientUserId": patient["id"], "doctorUserId": doctor["id"],
                                       "doctorProfileId": doctor["profileId"], "appointmentDate": "2041-01-0%d" % (i + 1),
                                       "startTime": "09:00", "endTime": "09:30", "status": "CONFIRMED",
                                       "paymentStatus": "PAID", "consultationFee": 2500.0, "createdAt": utc_now()})
    first = client.get(f"/api/admin/appointments?search=Searchable%20{tag}&page=1&pageSize=2", headers=_auth(admin)).json()
    second = client.get(f"/api/admin/appointments?search=Searchable%20{tag}&page=2&pageSize=2", headers=_auth(admin)).json()
    third = client.get(f"/api/admin/appointments?search=Searchable%20{tag}&page=3&pageSize=2", headers=_auth(admin)).json()
    assert first["total"] == second["total"] == 5 and first["totalPages"] == 3
    ids = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert len(ids) == 5 and len(set(ids)) == 5
    by_specialty = client.get(f"/api/admin/appointments?search=Cardiology&pageSize=100", headers=_auth(admin)).json()
    assert by_specialty["total"] >= 5
    weird = client.get("/api/admin/appointments?search=.*(a+)+$", headers=_auth(admin))
    assert weird.status_code == 200  # user text is escaped, never used as a raw regular expression


def test_p4o4_page_size_and_totals_are_consistent(db):
    admin = _admin(db)
    res = client.get("/api/admin/appointments?page=1&pageSize=3", headers=_auth(admin)).json()
    assert len(res["items"]) <= 3 and res["total"] >= len(res["items"])
    pay = client.get("/api/admin/payments?page=1&pageSize=3", headers=_auth(admin)).json()
    assert len(pay["items"]) <= 3 and pay["total"] >= len(pay["items"])
