"""R02 UAT probe against the local UAT backend (127.0.0.1:8001, mediconnect_uat, synthetic accounts only).

Usage (from backend/):  venv\\Scripts\\python.exe -I ..\\docs\\uat\\release-preparation\\r02\\r02_api_probe.py <command> [args]
  picture <email> [<save-as>]       download the account's stored picture (as that account) and report metadata
  view <viewer-email> <owner-email> try to read owner's picture as viewer (status code only)
  profile <email>                   the patient's /api/profile/me (health profile, recorded allergies)
  appointments <email>              doctorProfileImage of the patient's appointments
The UAT password is read from backend/uat.env and never printed. Only 127.0.0.1:8001 is contacted.
"""
import io
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001/api"
ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent / "evidence"
PASSWORD = re.search(r"^UAT_PASSWORD=(.*)$", (ROOT / "backend" / "uat.env").read_text(encoding="utf-8"),
                     re.M).group(1).strip().strip("\"'")


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status, res.read(), dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def login(email):
    status, raw, _ = call("POST", "/auth/login", body={"email": email, "password": PASSWORD})
    assert status == 200, (email, status)
    data = json.loads(raw)
    return data.get("accessToken") or data["tokens"]["accessToken"], (data.get("user") or {})


def me(token):
    status, raw, _ = call("GET", "/auth/me", token)
    data = json.loads(raw)
    return data.get("user", data)


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "picture":
        token, _ = login(args[0])
        user = me(token)
        url = user.get("profileImage")
        result = {"account": args[0], "profileImage": url}
        if url:
            status, raw, headers = call("GET", url[len("/api"):], token)
            result.update({"status": status, "contentType": headers.get("content-type"),
                           "cacheControl": headers.get("cache-control"), "bytes": len(raw)})
            if status == 200:
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                result.update({"size": im.size, "format": im.format, "exifTags": len(im.getexif()),
                               "gpsPresent": bool(im.getexif().get_ifd(0x8825)), "infoKeys": sorted(im.info),
                               "syntheticCamMarkerPresent": b"R02SyntheticCam" in raw})
                if len(args) > 1:
                    (OUT / args[1]).write_bytes(raw)
                    result["savedAs"] = f"evidence/{args[1]}"
        print(json.dumps(result, indent=1))
    elif cmd == "view":
        viewer, _ = login(args[0])
        owner_token, _ = login(args[1])
        owner = me(owner_token)
        target = owner["id"]
        status, _, _ = call("GET", f"/profile/pictures/{target}", viewer)
        print(json.dumps({"viewer": args[0], "owner": args[1], "ownerHasPicture": bool(owner.get("profileImage")),
                          "status": status}))
    elif cmd == "profile":
        token, _ = login(args[0])
        status, raw, _ = call("GET", "/profile/me", token)
        print(json.dumps({"status": status, **json.loads(raw)}, indent=1, default=str))
    elif cmd == "appointments":
        token, _ = login(args[0])
        status, raw, _ = call("GET", "/appointments/me", token)
        data = json.loads(raw)
        rows = data.get("items", data) if isinstance(data, dict) else data
        print(json.dumps([{"id": r["id"], "doctorName": r.get("doctorName"), "status": r.get("status"),
                           "doctorProfileImage": r.get("doctorProfileImage")} for r in rows][:10], indent=1))


if __name__ == "__main__":
    main()
