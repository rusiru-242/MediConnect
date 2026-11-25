"""Phase 02 helper for the local UAT API (127.0.0.1:8001 only).

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
assert BASE.startswith('http://127.0.0.1:8001/'), 'Phase 02 probes may only target the local UAT backend'
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
