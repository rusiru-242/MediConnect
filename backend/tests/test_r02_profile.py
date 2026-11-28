"""R02: profile pictures (patients and doctors), image security and patient profile data integrity (A05-O1).

Isolated local test database (conftest guard). Images are synthetic and generated in the test (solid colours and
gradients); no photograph of a person is used. Storage is redirected to a per-test temporary directory.
Scenario IDs follow the R02 matrices: I (image workflows), S (security), P (profile data).
"""
import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from bson import ObjectId
import pytest
from PIL import Image

from app.config.settings import settings
from app.services import profile_image_service
from tests.test_payment import _make_future_availability, _make_test_doctor, _make_test_patient, client, db  # noqa: F401
from tests.test_phase02_booking_payment import _admin, _auth, _pay_confirmed


@pytest.fixture(autouse=True)
def storage(tmp_path):
    profile_image_service.upload_limiter.reset()
    with patch.object(profile_image_service, "_base_dir", lambda: tmp_path / "profile_images"):
        yield tmp_path / "profile_images"


@pytest.fixture
def people(db):
    tag = str(ObjectId())[-6:]
    return {"patient": _make_test_patient(db, f"r02p{tag}"), "other": _make_test_patient(db, f"r02q{tag}"),
            "doctor": _make_test_doctor(db, f"R02D{tag}"), "doctor2": _make_test_doctor(db, f"R02E{tag}"),
            "admin": _admin(db)}


def _img(fmt="JPEG", size=(900, 600), color=(30, 120, 200), exif=None, mode="RGB") -> bytes:
    im = Image.new(mode, size, color)
    for x in range(0, size[0], 50):  # simple synthetic pattern
        im.paste((255, 255, 255) if mode == "RGB" else 255, (x, 0, min(x + 10, size[0]), size[1]))
    out = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    im.save(out, format=fmt, **kwargs)
    return out.getvalue()


def _upload(user, data, name="avatar.jpg", ctype="image/jpeg", **crop):
    return client.post("/api/profile/me/picture", headers=_auth(user) if user else {},
                       files={"file": (name, data, ctype)}, data={k: str(v) for k, v in crop.items()})


def _get(viewer, target_id):
    return client.get(f"/api/profile/pictures/{target_id}", headers=_auth(viewer))


def _files(storage, user_id):
    d = storage / user_id
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


# ============================================================================== image workflows (backend part)
def test_i04_i07_patient_upload_view_and_default(db, people, storage):
    p = people["patient"]
    assert db["users"].find_one({"_id": ObjectId(p["id"])}).get("profileImage") is None  # I07 default
    res = _upload(p, _img())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["profileImage"].startswith(f"/api/profile/pictures/{p['id']}?v=") and body["width"] == 512
    got = _get(p, p["id"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
    assert "private" in got.headers["cache-control"]
    assert Image.open(io.BytesIO(got.content)).size == (512, 512)
    me = client.get("/api/auth/me", headers=_auth(p)).json()
    assert (me.get("user") or me)["profileImage"] == body["profileImage"]
    stored = (storage / _files(storage, p["id"])[0]).read_bytes() if False else None  # noqa: F841
    assert len(_files(storage, p["id"])) == 1


def test_i03_crop_is_applied_server_side(people):
    p = people["patient"]
    im = Image.new("RGB", (400, 200), (255, 0, 0))
    im.paste((0, 0, 255), (200, 0, 400, 200))  # right half blue
    buf = io.BytesIO(); im.save(buf, "PNG")
    assert _upload(p, buf.getvalue(), "a.png", "image/png", cropX=0.5, cropY=0, cropSize=1).status_code == 200
    out = Image.open(io.BytesIO(_get(p, p["id"]).content)).convert("RGB")
    r, g, b = out.getpixel((256, 256))
    assert b > 200 and r < 60  # the selected right-hand square, not the default centre crop
    assert _upload(p, buf.getvalue(), "a.png", "image/png", cropX=0.5).status_code == 400  # partial crop refused
    assert _upload(p, buf.getvalue(), "a.png", "image/png", cropX=2, cropY=0, cropSize=1).status_code == 400


def test_i05_i06_replacement_and_removal_clean_up_files(db, people, storage):
    p = people["patient"]
    first = _upload(p, _img(color=(10, 10, 10))).json()
    second = _upload(p, _img(color=(240, 240, 240))).json()
    assert first["version"] != second["version"]
    assert len(_files(storage, p["id"])) == 1  # the replaced file is deleted
    assert Image.open(io.BytesIO(_get(p, p["id"]).content)).convert("L").getpixel((5, 5)) > 200
    res = client.delete("/api/profile/me/picture", headers=_auth(p))
    assert res.status_code == 200 and res.json() == {"profileImage": None}
    assert _files(storage, p["id"]) == []
    user = db["users"].find_one({"_id": ObjectId(p["id"])})
    assert user["profileImage"] is None and "profileImageMeta" not in user
    assert _get(p, p["id"]).status_code == 404  # default avatar on the client


def test_i08_i11_i13_i14_i15_doctor_picture_flows_to_trusted_views(db, people):
    doctor, patient, admin = people["doctor"], people["patient"], people["admin"]
    up = _upload(doctor, _img(color=(0, 150, 120)))
    assert up.status_code == 200, up.text
    url = up.json()["profileImage"]
    # I13 doctor details and I11 search list (both read users.profileImage from the database)
    detail = client.get(f"/api/doctors/{doctor['doctorId']}", headers=_auth(patient))
    assert detail.status_code == 200 and detail.json()["profileImage"] == url
    listing = client.get("/api/doctors", params={"search": doctor["user"]["fullName"]}, headers=_auth(patient)).json()
    items = listing.get("items", listing) if isinstance(listing, dict) else listing
    assert [d["profileImage"] for d in items if d["doctorId"] == doctor["doctorId"]] == [url]
    assert _get(patient, doctor["id"]).status_code == 200  # any signed-in user may view an approved doctor's picture
    # I14 appointments show the doctor's picture
    avail = _make_future_availability(db, doctor, 6)
    appt, _ = _pay_confirmed(db, patient, doctor, avail)
    mine = client.get("/api/appointments/me", headers=_auth(patient))
    assert mine.status_code == 200, mine.text
    rows = mine.json().get("items", mine.json()) if isinstance(mine.json(), dict) else mine.json()
    assert [a["doctorProfileImage"] for a in rows if a["id"] == appt.id] == [url]
    # I15 admin doctor management list and verification detail
    admin_list = client.get("/api/admin/doctors", params={"search": doctor["user"]["fullName"]}, headers=_auth(admin)).json()
    assert [d["profileImage"] for d in admin_list["items"] if d["userId"] == doctor["id"]] == [url]
    app_detail = client.get(f"/api/admin/doctors/applications/{doctor['profileId']}", headers=_auth(admin))
    assert app_detail.status_code == 200 and app_detail.json()["profileImage"] == url
    assert _get(admin, doctor["id"]).status_code == 200


def test_i12_recommendation_cards_use_the_stored_picture_not_model_output(db, people):
    from app.agents.recommendation_engine import RecommendationEngine  # noqa: F401  (import check)
    doctor, patient = people["doctor"], people["patient"]
    url = _upload(doctor, _img()).json()["profileImage"]
    _make_future_availability(db, doctor, 3)
    # The shared test database holds many approved doctors; lift the display cap so this doctor is in the list.
    with patch.object(settings, "AI_MAX_RECOMMENDATIONS", 100000):
        res = client.post("/api/ai/doctor-recommendations", headers=_auth(patient),
                          json={"query": "I need a doctor for a general check-up"})
    assert res.status_code == 200, res.text
    recs = [r for r in res.json()["recommendations"] if r["doctorId"] == doctor["doctorId"]]
    assert recs and recs[0]["profileImage"] == url


def test_i09_i10_doctor_replace_and_remove(db, people, storage):
    d = people["doctor"]
    _upload(d, _img(color=(1, 2, 3)))
    second = _upload(d, _img(color=(200, 0, 0))).json()
    assert len(_files(storage, d["id"])) == 1
    assert client.get(f"/api/doctors/{d['doctorId']}", headers=_auth(people["patient"])).json()["profileImage"] \
        == second["profileImage"]
    assert client.delete("/api/profile/me/picture", headers=_auth(d)).status_code == 200
    assert client.get(f"/api/doctors/{d['doctorId']}", headers=_auth(people["patient"])).json()["profileImage"] is None


def test_i18_backend_restart_persistence_reads_from_disk(db, people, storage):
    p = people["patient"]
    _upload(p, _img())
    before = _get(p, p["id"]).content
    # A restart keeps nothing in memory: reading again goes to MongoDB and the encrypted file on disk.
    import importlib
    importlib.reload(profile_image_service)
    with patch.object(profile_image_service, "_base_dir", lambda: storage):
        assert _get(p, p["id"]).content == before


# =================================================================================================== security
def test_s01_unauthenticated_requests_rejected(people):
    assert _upload(None, _img()).status_code in (401, 403)
    assert client.delete("/api/profile/me/picture").status_code in (401, 403)
    assert client.get(f"/api/profile/pictures/{people['patient']['id']}").status_code in (401, 403)


def test_s02_s03_no_cross_user_modification_or_deletion(db, people, storage):
    p, other = people["patient"], people["other"]
    mine = _upload(other, _img()).json()["profileImage"]
    # A client-supplied owner id is ignored: the picture always belongs to the authenticated user.
    res = client.post("/api/profile/me/picture", headers=_auth(p), files={"file": ("x.jpg", _img(), "image/jpeg")},
                      data={"userId": other["id"]})
    assert res.status_code == 200 and res.json()["profileImage"].startswith(f"/api/profile/pictures/{p['id']}")
    assert db["users"].find_one({"_id": ObjectId(other["id"])})["profileImage"] == mine
    assert client.delete(f"/api/profile/pictures/{other['id']}", headers=_auth(p)).status_code == 405
    assert client.put(f"/api/profile/pictures/{other['id']}", headers=_auth(p)).status_code == 405
    client.delete("/api/profile/me/picture", headers=_auth(p))
    assert db["users"].find_one({"_id": ObjectId(other["id"])})["profileImage"] == mine
    assert len(_files(storage, other["id"])) == 1
    # Administrators have no picture of their own to manage here.
    assert _upload(people["admin"], _img()).status_code == 403


def test_s04_s05_patient_picture_privacy(db, people):
    p, other, doctor, doctor2, admin = (people[k] for k in ("patient", "other", "doctor", "doctor2", "admin"))
    _upload(p, _img())
    assert _get(other, p["id"]).status_code == 404  # unrelated patient
    assert _get(doctor, p["id"]).status_code == 404  # unrelated doctor
    assert _get(admin, p["id"]).status_code == 404  # administrators are not granted patient photographs
    avail = _make_future_availability(db, doctor, 4)
    _pay_confirmed(db, p, doctor, avail)
    assert _get(doctor, p["id"]).status_code == 200  # treating doctor (confirmed appointment)
    assert _get(doctor2, p["id"]).status_code == 404


@pytest.mark.parametrize("label,data,name,ctype", [
    ("gif", None, "a.gif", "image/gif"),
    ("bmp", None, "a.bmp", "image/bmp"),
    ("text-as-jpg", b"just some text pretending to be a photo" * 20, "a.jpg", "image/jpeg"),
    ("script-as-png", b"#!/bin/sh\nrm -rf /\n" * 30, "a.png", "image/png"),
    ("html-with-jpeg-magic", b"\xff\xd8\xff\xe0<html><script>alert(1)</script></html>" * 10, "a.jpg", "image/jpeg"),
    ("exe", b"MZ\x90\x00" + b"\x00" * 400, "a.exe", "application/octet-stream"),
])
def test_s06_s07_invalid_and_disguised_files_rejected(people, storage, label, data, name, ctype):
    if label in ("gif", "bmp"):
        buf = io.BytesIO(); Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, label.upper()); data = buf.getvalue()
    res = _upload(people["patient"], data, name, ctype)
    assert res.status_code == 400, (label, res.status_code, res.text)
    assert _files(storage, people["patient"]["id"]) == []


def test_s08_oversized_upload_rejected(people, storage):
    big = b"\xff\xd8\xff" + b"0" * (settings.PROFILE_IMAGE_MAX_BYTES + 10)
    res = _upload(people["patient"], big)
    assert res.status_code == 413
    assert _files(storage, people["patient"]["id"]) == []


def test_s09_oversized_decoded_dimensions_rejected(people):
    p = people["patient"]
    buf = io.BytesIO(); Image.new("L", (8100, 20)).save(buf, "PNG")  # one side over the limit
    assert _upload(p, buf.getvalue(), "w.png", "image/png").status_code == 400
    with patch.object(settings, "PROFILE_IMAGE_MAX_PIXELS", 1_000_000):  # decompression bomb: tiny file, huge bitmap
        buf = io.BytesIO(); Image.new("L", (1200, 1200)).save(buf, "PNG")
        assert len(buf.getvalue()) < 20_000
        res = _upload(p, buf.getvalue(), "bomb.png", "image/png")
        assert res.status_code == 400 and "dimensions" in res.json()["detail"]


def test_s10_malformed_images_rejected(people):
    p = people["patient"]
    good = _img(fmt="PNG")
    assert _upload(p, good[: len(good) // 3], "t.png", "image/png").status_code == 400  # truncated
    corrupt = bytearray(_img()); corrupt[200:260] = b"\x00" * 60
    res = _upload(p, bytes(corrupt))
    assert res.status_code in (200, 400)  # either rejected, or decoded and fully re-encoded
    assert _upload(p, b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "h.png", "image/png").status_code == 400


def test_s11_metadata_including_gps_is_removed(people):
    p = people["patient"]
    exif = Image.Exif()
    exif[0x010F] = "SyntheticCam"  # Make
    exif[0x0131] = "R02-test-software"
    exif[0x8825] = {1: "N", 2: (6.0, 55.0, 0.0), 3: "E", 4: (79.0, 51.0, 0.0)}  # GPS IFD
    raw = _img(exif=exif.tobytes())
    assert b"SyntheticCam" in raw and Image.open(io.BytesIO(raw)).getexif().get_ifd(0x8825)
    assert _upload(p, raw).status_code == 200
    out = _get(p, p["id"]).content
    img = Image.open(io.BytesIO(out))
    assert not img.getexif() and "exif" not in img.info and "icc_profile" not in img.info
    assert b"SyntheticCam" not in out and b"R02-test-software" not in out and b"Exif" not in out


def test_s12_path_traversal_rejected(people, storage):
    p = people["patient"]
    _upload(p, _img())
    for bad in ("..%2F..%2Fetc%2Fpasswd", "..", "%2e%2e", p["id"] + "%2F..%2F..", "a" * 80, "x;rm", "..\\..\\x"):
        assert client.get(f"/api/profile/pictures/{bad}", headers=_auth(p)).status_code in (404, 422), bad
    res = _upload(p, _img(), name="../../../../etc/evil.jpg")
    assert res.status_code == 200
    names = _files(storage, p["id"])
    assert len(names) == 1 and names[0].endswith(".jpg") and len(names[0]) == 36  # uuid4 hex + .jpg
    assert not any(storage.parent.rglob("evil*"))


def test_s13_concurrent_replacement_keeps_one_consistent_picture(db, people, storage):
    p = people["patient"]
    payloads = [_img(color=(i * 40, 10, 10)) for i in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda data: _upload(p, data).status_code, payloads))
    assert results == [200] * 5
    user = db["users"].find_one({"_id": ObjectId(p["id"])})
    files = _files(storage, p["id"])
    assert files == [user["profileImageMeta"]["storageKey"].split("/")[1]]  # no orphan, reference matches the file
    assert user["profileImage"].endswith(user["profileImageMeta"]["version"])
    assert _get(p, p["id"]).status_code == 200


def test_s14_failed_replacement_preserves_previous_picture(db, people, storage):
    p = people["patient"]
    _upload(p, _img(color=(0, 200, 0)))
    before = _get(p, p["id"]).content
    meta_before = db["users"].find_one({"_id": ObjectId(p["id"])})["profileImageMeta"]
    assert _upload(p, b"not an image" * 50).status_code == 400  # invalid replacement
    with patch.object(profile_image_service, "picture_url", side_effect=RuntimeError("db write failed")):
        with pytest.raises(RuntimeError):
            client.post("/api/profile/me/picture", headers=_auth(p), files={"file": ("x.jpg", _img(), "image/jpeg")})
    assert db["users"].find_one({"_id": ObjectId(p["id"])})["profileImageMeta"]["storageKey"] == meta_before["storageKey"]
    assert _files(storage, p["id"]) == [meta_before["storageKey"].split("/")[1]]  # the new file was cleaned up
    assert _get(p, p["id"]).content == before


def test_s15_unapproved_doctor_picture_is_not_public(db, people):
    d, patient, admin = people["doctor2"], people["patient"], people["admin"]
    db["doctor_profiles"].update_one({"userId": d["id"]}, {"$set": {"verificationStatus": "PENDING"}})
    assert _upload(d, _img()).status_code == 200
    assert _get(patient, d["id"]).status_code == 404
    assert _get(people["doctor"], d["id"]).status_code == 404
    assert _get(d, d["id"]).status_code == 200 and _get(admin, d["id"]).status_code == 200
    assert client.get(f"/api/doctors/{d['doctorId']}", headers=_auth(patient)).status_code == 404  # still undiscoverable
    listing = client.get("/api/doctors", params={"search": d["user"]["fullName"]}, headers=_auth(patient)).json()
    items = listing.get("items", listing) if isinstance(listing, dict) else listing
    assert all(x["doctorId"] != d["doctorId"] for x in items)


def test_upload_rate_limit(people):
    p = people["patient"]
    with patch.object(profile_image_service.upload_limiter, "max_requests", 2):
        assert _upload(p, _img()).status_code == 200
        assert _upload(p, _img()).status_code == 200
        assert _upload(p, _img()).status_code == 429


# ============================================================================================ profile data
def test_p01_p06_new_patient_has_no_invented_values(people):
    res = client.get("/api/profile/me", headers=_auth(people["patient"]))
    assert res.status_code == 200, res.text
    hp = res.json()["healthProfile"]
    assert hp["heightCm"] is None and hp["weightKg"] is None and hp["bmi"] is None and hp["bmiNote"] is None
    assert hp["allergyStatus"] == "not_provided" and hp["allergies"] == [] and hp["emergencyContact"] is None
    assert res.json()["recordedAllergies"] == []
    assert "Penicillin" not in res.text and "penicillin" not in res.text.lower()


def test_p03_p07_p09_valid_updates_persist_and_bmi_only_from_both_values(db, people):
    p = people["patient"]
    r = client.patch("/api/profile/me", headers=_auth(p), json={"heightCm": 170})
    assert r.status_code == 200 and r.json()["healthProfile"]["bmi"] is None  # weight missing
    r = client.patch("/api/profile/me", headers=_auth(p), json={
        "weightKg": 65, "allergyStatus": "has_allergies", "allergies": ["Latex", " latex ", "Peanuts"],
        "emergencyContact": {"name": "Synthetic Contact", "relationship": "Sibling", "phone": "+94 71 000 0000"},
        "fullName": "R02 Updated Name"})
    assert r.status_code == 200, r.text
    hp = r.json()["healthProfile"]
    assert hp["bmi"] == 22.5 and "not a diagnosis" in hp["bmiNote"]
    assert hp["allergies"] == ["Latex", "Peanuts"] and hp["source"] == "patient_reported"
    again = client.get("/api/profile/me", headers=_auth(p)).json()  # P09 persisted
    assert again["healthProfile"]["emergencyContact"]["phone"] == "+94 71 000 0000"
    assert again["fullName"] == "R02 Updated Name"
    r = client.patch("/api/profile/me", headers=_auth(p), json={"allergyStatus": "none_known", "allergies": []})
    assert r.json()["healthProfile"]["allergyStatus"] == "none_known"  # explicit "no known allergies"
    r = client.patch("/api/profile/me", headers=_auth(p), json={"heightCm": None, "emergencyContact": None})
    assert r.json()["healthProfile"]["heightCm"] is None and r.json()["healthProfile"]["bmi"] is None
    assert r.json()["healthProfile"]["emergencyContact"] is None


@pytest.mark.parametrize("body", [
    {"heightCm": 20}, {"heightCm": 400}, {"weightKg": 0}, {"weightKg": 1000},
    {"allergyStatus": "maybe"}, {"allergyStatus": "has_allergies", "allergies": []},
    {"allergyStatus": "none_known", "allergies": ["Latex"]}, {"allergies": ["x" * 81]},
    {"allergyStatus": "has_allergies", "allergies": [f"a{i}" for i in range(21)]},
    {"emergencyContact": {"name": "A", "phone": "call me"}}, {"emergencyContact": {"name": "", "phone": "0710000000"}},
    {"role": "ADMIN"}, {"email": "x@y.z"}, {"fullName": "x"}, {"allergies": ["bad\x00value"]},
])
def test_p08_invalid_updates_rejected(db, people, body):
    p = people["patient"]
    before = db["users"].find_one({"_id": ObjectId(p["id"])})
    res = client.patch("/api/profile/me", headers=_auth(p), json=body)
    assert res.status_code == 422, (body, res.status_code, res.text)
    after = db["users"].find_one({"_id": ObjectId(p["id"])})
    assert after.get("healthProfile") == before.get("healthProfile") and after["role"] == "PATIENT"


def test_p04_recorded_allergies_are_shown_with_provenance_not_invented(db, people):
    p = people["patient"]
    db["patient_medical_records"].insert_one({
        "recordId": f"MED-R02-{ObjectId()}", "patientUserId": p["id"], "recordType": "allergy",
        "sourceType": "clinician_authored", "authorId": people["doctor"]["id"], "authorRole": "DOCTOR",
        "title": "Sulfonamides", "clinicalDate": "2026-11-01", "clinicalData": {"severity": "moderate"},
        "status": "active"})
    body = client.get("/api/profile/me", headers=_auth(p)).json()
    assert body["recordedAllergies"] == [{"allergen": "Sulfonamides", "severity": "moderate",
                                          "source": "clinician_authored", "sourceLabel": "Recorded by a clinician",
                                          "clinicalDate": "2026-11-01"}]
    assert body["healthProfile"]["allergyStatus"] == "not_provided"  # the record is not copied into the self-report
    other = client.get("/api/profile/me", headers=_auth(people["other"])).json()
    assert other["recordedAllergies"] == []  # P10: no leakage across patients


def test_p10_profile_is_patient_only_and_own_only(people):
    for role in ("doctor", "admin"):
        assert client.get("/api/profile/me", headers=_auth(people[role])).status_code == 403
        assert client.patch("/api/profile/me", headers=_auth(people[role]), json={"heightCm": 170}).status_code == 403
    client.patch("/api/profile/me", headers=_auth(people["patient"]), json={"heightCm": 181})
    assert client.get("/api/profile/me", headers=_auth(people["other"])).json()["healthProfile"]["heightCm"] is None
    assert client.get("/api/profile/me").status_code in (401, 403)


# ================================================================== R02-BUG-006 (A05 sweep, found by the R02 run)
def test_fraud_sweep_evaluates_every_active_account_even_beyond_200(db, people):
    """The sweep used ``sorted(ids)[:200]``; with more active accounts the newest were never evaluated."""
    from app.models.appointment import utc_now
    from app.services.fraud_detection_service import FraudDetectionService
    target = people["patient"]["id"]
    # 201 other recently active accounts whose ids sort before the target (ObjectIds sort by creation time).
    fillers = [{"_id": ObjectId(), "patientUserId": "000000000000000000000%03d" % i, "doctorUserId": "x",
                "status": "CANCELLED", "createdAt": utc_now(), "updatedAt": utc_now(), "r02Filler": True}
               for i in range(201)]
    db["appointments"].insert_many(fillers)
    db["appointments"].insert_one({"patientUserId": target, "doctorUserId": "x", "status": "CANCELLED",
                                   "createdAt": utc_now(), "updatedAt": utc_now(), "r02Filler": True})
    seen = []
    with patch.object(FraudDetectionService, "evaluate_account_risk",
                      side_effect=lambda account_id, **kw: seen.append(account_id) or None):
        stats = FraudDetectionService.run_detection_sweep(db, force=True)
    db["appointments"].delete_many({"r02Filler": True})
    assert target in seen
    assert stats["deferred"] == 0 and stats["evaluated"] == stats["candidates"] >= 202
    capped = FraudDetectionService.run_detection_sweep(db, force=True, limit=1)
    assert capped["evaluated"] == 1 and capped["deferred"] == capped["candidates"] - 1  # a cap is reported, not hidden
