"""A01 live vision probe (Agent 04): upload the synthetic fixtures through the real app endpoint and compare.

Run from backend/:  venv\\Scripts\\python.exe ..\\docs\\uat\\agent-completion\\a01\\vision_probe.py OUT.json [names]
Targets only the local UAT backend (127.0.0.1:8001, mediconnect_uat) via the Phase 03 helper. The backend must be
started with  -AiProvider gemini -EnableVision  (owner authorization 2026-11-26: synthetic images only).
Images: backend/tests/fixtures/a01_vision (fictional products; expected label text recorded in expected_labels.json
before this probe ran). Recorded: status, provider/model, extracted fields and the reply text (truncated).
"""
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'phase-03'))
from p03api import BASE, call, login  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'
FIX = pathlib.Path(__file__).resolve().parents[4] / 'backend' / 'tests' / 'fixtures' / 'a01_vision'
EXPECTED = json.loads((FIX / 'expected_labels.json').read_text(encoding='utf-8'))


def multipart(name, data):
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f'Content-Type: image/png\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    return body, {'Content-Type': f'multipart/form-data; boundary={boundary}'}


def compare(name, analysis):
    exp, ext = EXPECTED.get(name, {}), (analysis or {}).get('extracted') or {}
    seen = json.dumps(ext, ensure_ascii=False).lower()
    checks = {}
    for key in ('brand', 'activeIngredient', 'strength', 'manufacturer', 'expiry'):
        if exp.get(key):
            checks[key] = exp[key].lower() in seen
    if exp.get('expectedStatus'):
        checks['status'] = (analysis or {}).get('status') in exp['expectedStatus']
    if exp.get('packageCount'):
        checks['packageCount'] = (analysis or {}).get('packageCount') == exp['packageCount']
    if exp.get('expectedFlag'):
        checks['embeddedTextIgnored'] = bool((analysis or {}).get('embeddedTextIgnored'))
    return checks


def main(out_path, names):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tok = login('uat.patient1')
    out = {'backend': '127.0.0.1:8001', 'database': 'mediconnect_uat', 'live': True, 'rows': []}
    for name in names:
        s, d = call('POST', '/ai/conversations', {}, tok=tok)
        sid = (d or {}).get('id')
        body, headers = multipart(name, (FIX / name).read_bytes())
        s, d = call('POST', f'/ai/booking/sessions/{sid}/image', raw=body, tok=tok, headers=headers)
        a = (d or {}).get('activeImageAnalysis') or {}
        reply = next((m for m in reversed((d or {}).get('messages', [])) if m.get('sender') == 'assistant'), {})
        row = {'fixture': name, 'scenario': EXPECTED.get(name, {}).get('scenario'), 'http': s, 'status': a.get('status'),
               'provider': a.get('provider'), 'model': a.get('model'), 'responseSource': a.get('responseSource'),
               'providerError': a.get('providerError'), 'packageCount': a.get('packageCount'),
               'embeddedTextIgnored': a.get('embeddedTextIgnored'), 'identifiedMedicine': a.get('identifiedMedicine'),
               'extracted': a.get('extracted'), 'reply': (reply.get('content') or '')[:900],
               'checks': compare(name, a)}
        call('DELETE', f'/ai/conversations/{sid}', tok=tok)
        out['rows'].append(row)
        print(name, s, row['status'], row['provider'], row['model'], row['providerError'], row['checks'])
    pathlib.Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    default = [n for n in EXPECTED]
    main(sys.argv[1], sys.argv[2].split(',') if len(sys.argv) > 2 else default)
