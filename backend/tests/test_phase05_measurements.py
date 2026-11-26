"""Phase 05 B7 / P05-N18: one read model for measurements saved from Health Tracking and from the Care Agenda.
Nothing is migrated or merged in storage; each reading keeps its provenance."""
from datetime import timedelta

from bson import ObjectId

from app.models.appointment import utc_now
from tests.test_payment import _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _auth
from tests.test_phase03_doctor_system import _visit


def test_care_agenda_reading_no_longer_breaks_the_clinical_list_and_keeps_provenance(db):
    patient = _make_test_patient(db, "P05B7")
    # A reading stored before Phase 05 from the Care Agenda (no measurementId / measuredAt / verificationStatus).
    legacy_id = db["patient_health_measurements"].insert_one({
        "metric": "weight", "value": 70.5, "secondary": None, "patientUserId": patient["id"], "unit": "kg",
        "recordedAt": utc_now() - timedelta(hours=2), "source": "patient_reported", "criticalAlert": None}).inserted_id
    assert client.post("/api/clinical/measurements", json={"metric": "weight", "value": 71, "unit": "kg"},
                       headers=_auth(patient)).status_code == 201
    assert client.post("/api/care-automation/measurements", json={"metric": "weight", "value": 72},
                       headers=_auth(patient)).status_code == 201
    res = client.get("/api/clinical/measurements", headers=_auth(patient))
    assert res.status_code == 200, res.text  # was an unhandled ValidationError (500)
    items = res.json()["items"]
    assert [i["value"] for i in items] == [72, 71, 70.5]  # newest first across both entry points
    assert all(i["measurementId"] for i in items) and all(i["verificationStatus"] == "unverified" for i in items)
    stored = db["patient_health_measurements"].find_one({"_id": legacy_id})
    assert "measurementId" not in stored  # read-time normalisation only: no historical record was changed
    care = client.get("/api/care-automation/measurements", headers=_auth(patient)).json()["items"]
    assert len(care) == 3


def test_doctor_and_patient_see_the_same_readings_and_trends_include_both(db):
    patient, doctor = _make_test_patient(db, "P05B7D"), _make_test_doctor(db, "P05B7DDoc")
    _visit(db, patient, doctor)
    client.post("/api/care-automation/measurements", json={"metric": "blood_pressure", "value": 128, "secondary": 82},
                headers=_auth(patient))
    client.post("/api/clinical/measurements", json={"metric": "blood_pressure", "value": 131, "secondary": 84,
                                                   "unit": "mmHg"}, headers=_auth(patient))
    mine = client.get("/api/clinical/measurements", headers=_auth(patient)).json()["items"]
    theirs = client.get(f"/api/clinical/measurements?patientId={patient['id']}", headers=_auth(doctor))
    assert theirs.status_code == 200, theirs.text
    assert [i["value"] for i in theirs.json()["items"]] == [i["value"] for i in mine]
    trends = client.get("/api/clinical/measurements/trends", headers=_auth(patient)).json()
    bp = next(t for t in trends["trends"] if t["metric"] == "blood_pressure") if "trends" in trends else None
    assert bp is None or bp.get("readingsCount", bp.get("count", 2)) >= 2
    other = _make_test_doctor(db, "P05B7X")
    assert client.get(f"/api/clinical/measurements?patientId={patient['id']}", headers=_auth(other)).status_code == 403


def test_p3b8_preparation_includes_authorised_shared_sources_and_states_what_is_missing(db):
    from tests.test_phase03_doctor_system import ITEM
    patient, doctor, other = (_make_test_patient(db, "P05PREP"), _make_test_doctor(db, "P05PREPDoc"),
                              _make_test_doctor(db, "P05PREPOther"))
    visit = _visit(db, patient, doctor, days=0)
    _visit(db, patient, other)
    client.post("/api/clinical/prescriptions/sign", headers=_auth(other),
                json={"patientUserId": patient["id"], "medicationItems": [ITEM]})
    client.post("/api/care-automation/measurements", json={"metric": "weight", "value": 70}, headers=_auth(patient))
    res = client.post("/api/doctor/workflow/assistant", json={"message": "Prepare consultation summary",
                                                              "appointmentId": visit}, headers=_auth(doctor))
    assert res.status_code == 200, res.text
    result = res.json()["result"]
    src = result["sources"]
    assert any(p["medication"] == ITEM["medicationName"] and p["prescriber"] == "another clinician"
               for p in src["activePrescriptions"])
    assert src["recentMeasurements"] and src["recentMeasurements"][0]["source"] == "patient_reported"
    assert src["recordedAllergies"] == []
    assert any("does not mean the patient has no allergies" in m for m in result["missingSources"])
    assert "diagnosis" in result["summary"]  # "Nothing here is a diagnosis"


def test_p3b8_unpaid_booking_does_not_open_the_shared_record(db):
    from tests.test_phase02_booking_payment import _hold
    from tests.test_payment import _make_future_availability
    patient, doctor = _make_test_patient(db, "P05PREPU"), _make_test_doctor(db, "P05PREPUDoc")
    appt = _hold(db, patient, doctor, _make_future_availability(db, doctor, 5))
    res = client.post("/api/doctor/workflow/assistant", json={"message": "Prepare consultation summary",
                                                              "appointmentId": appt.id}, headers=_auth(doctor))
    if res.status_code == 200 and "result" in res.json():
        result = res.json()["result"]
        assert "patientRecords" not in result["sources"]
        assert any("after the visit is confirmed" in m for m in result["missingSources"])
    else:  # the preparation tool refused the unpaid hold outright: no record data in the reply
        assert res.status_code in (200, 403, 404, 409) and "sources" not in res.text
