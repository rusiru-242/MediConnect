"""Phase 03 helper for the local UAT API (127.0.0.1:8001 only).

Reads the synthetic UAT password from backend/uat.env and never prints it.
Refuses any other host/port so production-like port 8000 cannot be hit by accident.
"""
import json
import pathlib
import re
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8001/api'
assert BASE.startswith('http://127.0.0.1:8001/'), 'Phase 03 probes may only target the local UAT backend'
ROOT = pathlib.Path(__file__).resolve().parents[3]
_ENV = (ROOT / 'backend' / 'uat.env').read_text(encoding='utf-8')
_PW = re.search(r'^UAT_PASSWORD=(.*)$', _ENV, re.M).group(1).strip().strip('"\'')
DOMAIN = 'uat.mediconnect.lk'


def call(method, path, body=None, tok=None, raw=None, headers=None):
    if '/ai/' in path:
        time.sleep(2.2)  # AI endpoints: 30 requests/minute
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    req = urllib.request.Request(BASE + path, method=method, data=data, headers={
        'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + tok} if tok else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read()
            return r.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as e:
        text = e.read()
        try:
            return e.code, json.loads(text or b'{}')
        except ValueError:
            return e.code, {'raw': text[:300].decode(errors='replace')}


def login(key):
    status, data = call('POST', '/auth/login', {'email': f'{key}@{DOMAIN}', 'password': _PW})
    assert status == 200, (key, status)
    return data.get('access_token') or data.get('accessToken')


def unwrap(data):
    return data.get('data', data) if isinstance(data, dict) else data


# ---- Phase 03 additions -------------------------------------------------------------------------------------
import os as _os
import pathlib as _pathlib
from datetime import datetime as _datetime, timedelta as _timedelta, timezone as _timezone

COLOMBO = _timezone(_timedelta(hours=5, minutes=30))


def env_value(name):
    """Read one value from backend/.env (used only for the Stripe TEST key; never printed)."""
    for line in (ROOT / 'backend' / '.env').read_text(encoding='utf-8').splitlines():
        if line.strip().startswith(name + '='):
            return line.split('=', 1)[1].strip().strip('"\'')
    return ''


def colombo_now():
    return _datetime.now(COLOMBO)


def me(tok):
    return unwrap(call('GET', '/auth/me', tok=tok)[1])


def free_slots(tok, doctor_public_id, date):
    day = unwrap(call('GET', f'/doctors/{doctor_public_id}/availability?date={date}', tok=tok)[1])
    return list(day.get('slots', [])) if isinstance(day, dict) else []


def book(tok, doctor_public_id, date, slot):
    s, d = call('POST', '/appointments', {'doctorId': doctor_public_id, 'availabilityId': slot['availabilityId'],
                                          'date': date, 'startTime': slot['startTime']}, tok=tok)
    return s, (unwrap(d).get('appointment') or unwrap(d))
