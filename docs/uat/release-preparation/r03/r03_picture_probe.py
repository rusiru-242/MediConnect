"""R03 Workflow F: profile pictures through the local UAT API (127.0.0.1:8001, mediconnect_uat, synthetic accounts).

Images are generated here: abstract synthetic patterns (no photograph of a person), tagged with a synthetic EXIF
GPS block so metadata removal can be checked. Writes evidence/r03_picture_probe.json.

Usage (repository root):  backend\\venv\\Scripts\\python.exe -I docs\\uat\\release-preparation\\r03\\r03_picture_probe.py [upload|check]
  upload: patient2 and doctor.neuro upload, then the doctor replaces the picture; then the checks run.
  check:  only the checks (used after a backend restart for persistence).
"""
import hashlib
import io
import json
import pathlib
import sys
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "phase-02"))
from p02api import BASE, call, login, unwrap  # noqa: E402  (127.0.0.1:8001 only)
from PIL import Image  # noqa: E402

D = "@uat.mediconnect.lk"
PATIENT, OTHER, DOC, UNRELATED, ADMIN = "uat.patient2", "uat.patient1", "uat.doctor.neuro", "uat.doctor.gp", "uat.admin"
OUT = HERE / "evidence" / "r03_picture_probe.json"


def synthetic(color, seed):
    im = Image.new("RGB", (900, 700), color)
    for i in range(0, 900, 60):
        im.paste(((seed * 37 + i) % 255, 200, 255 - i % 255), (i, 0, i + 24, 700))
    exif = Image.Exif()
    exif[0x010E] = "R03 synthetic test image"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (6.0, 55.0, 0.0)  # synthetic coordinates
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def upload(tok, data):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"r03.jpg\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/profile/me/picture", data=body, method="POST", headers={
        "Authorization": "Bearer " + tok, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read())


def fetch(tok, user_id):
    req = urllib.request.Request(f"{BASE}/profile/pictures/{user_id}", headers={"Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, b"", {}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "upload"
    tok = {k: login(k) for k in (PATIENT, OTHER, DOC, UNRELATED, ADMIN)}
    me = {k: unwrap(call("GET", "/auth/me", tok=t)[1]) for k, t in tok.items()}
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if mode == "upload":
        out = {"uploads": {}}
        out["uploads"]["patient"] = upload(tok[PATIENT], synthetic((40, 120, 200), 1))[1]
        out["uploads"]["doctorFirst"] = upload(tok[DOC], synthetic((200, 90, 40), 2))[1]
        out["uploads"]["doctorReplaced"] = upload(tok[DOC], synthetic((40, 170, 90), 3))[1]
        me = {k: unwrap(call("GET", "/auth/me", tok=t)[1]) for k, t in tok.items()}
    checks = {}
    for owner in (PATIENT, DOC):
        for viewer in (PATIENT, OTHER, DOC, UNRELATED, ADMIN):
            status, raw, headers = fetch(tok[viewer], me[owner]["id"])
            checks[f"{viewer} -> {owner}"] = status
    status, raw, headers = fetch(tok[PATIENT], me[DOC]["id"])
    im = Image.open(io.BytesIO(raw))
    meta = {"size": im.size, "format": im.format, "exifTags": len(im.getexif()), "gps": bool(im.getexif().get_ifd(0x8825)),
            "cacheControl": {k.lower(): v for k, v in headers.items()}.get("cache-control"), "sha256": hashlib.sha256(raw).hexdigest()}
    p_status, p_raw, _ = fetch(tok[PATIENT], me[PATIENT]["id"])
    doc_url = me[DOC].get("profileImage")
    search = unwrap(call("GET", "/doctors?search=Neuro", tok=tok[PATIENT])[1])
    items = search.get("items", search) if isinstance(search, dict) else search
    in_search = [x.get("profileImage") for x in items if x.get("userId") == me[DOC]["id"] or x.get("fullName", "").endswith("Neuro")]
    appts = unwrap(call("GET", "/appointments/me", tok=tok[PATIENT])[1])
    appts = appts.get("items", appts) if isinstance(appts, dict) else appts
    appt_images = sorted({a.get("doctorProfileImage") for a in appts if a.get("doctorProfileImage")})
    result = {"mode": mode, "visibility": checks, "doctorPicture": meta,
              "patientPictureSha256": hashlib.sha256(p_raw).hexdigest() if p_status == 200 else None,
              "doctorProfileImage": doc_url, "searchCardImages": in_search, "appointmentDoctorImages": appt_images}
    expected = {f"{PATIENT} -> {PATIENT}": 200, f"{OTHER} -> {PATIENT}": 404, f"{UNRELATED} -> {PATIENT}": 404,
                f"{ADMIN} -> {PATIENT}": 404, f"{DOC} -> {PATIENT}": 200,
                **{f"{v} -> {DOC}": 200 for v in (PATIENT, OTHER, DOC, UNRELATED, ADMIN)}}
    result["visibilityAsDesigned"] = checks == expected
    result["metadataStripped"] = meta["exifTags"] == 0 and not meta["gps"] and meta["size"] == (512, 512)
    result["searchUsesTrustedUrl"] = bool(in_search) and all(u == doc_url for u in in_search)
    result["appointmentsUseTrustedUrl"] = appt_images in ([], [doc_url])
    out[mode] = result
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
