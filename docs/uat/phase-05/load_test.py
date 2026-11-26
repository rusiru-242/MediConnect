"""Phase 05 bounded local load test against the isolated UAT backend (127.0.0.1:8001, mediconnect_uat).

Run from backend/:  venv\\Scripts\\python.exe -I ..\\docs\\uat\\phase-05\\load_test.py OUT.json BACKEND_PID

* Read-only endpoints only (no bookings, payments or messages are created), synthetic UAT accounts.
* Each scenario sends a fixed number of requests at a fixed concurrency; nothing runs longer than a few minutes.
* The AI assistant scenarios stay under the per-user limit (30/min) so they measure latency, not 429s.
* CPU and memory of the backend process are sampled during each scenario when psutil is available.
These numbers describe one developer laptop and a single uvicorn worker; they are not production capacity.
"""
import json
import pathlib
import platform
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'phase-03'))
from p03api import BASE, login  # noqa: E402

assert BASE == 'http://127.0.0.1:8001/api'
ROOT = 'http://127.0.0.1:8001'


def one(method, url, token=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, method=method, data=data, headers={
        'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0
    return code, (time.perf_counter() - t0) * 1000


def sampler(pid, stop, out):
    try:
        import psutil
        proc = psutil.Process(pid)
        proc.cpu_percent(None)
        while not stop.is_set():
            time.sleep(0.5)
            out.append((proc.cpu_percent(None), proc.memory_info().rss / 1e6))
    except Exception as exc:  # psutil missing or process not found
        out.append(('unavailable', type(exc).__name__))


def scenario(name, method, url, total, concurrency, token=None, body=None, pid=None):
    samples, stop = [], threading.Event()
    th = threading.Thread(target=sampler, args=(pid, stop, samples), daemon=True) if pid else None
    if th:
        th.start()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(concurrency) as pool:
        results = list(pool.map(lambda _: one(method, url, token, body), range(total)))
    wall = time.perf_counter() - t0
    stop.set()
    if th:
        th.join(2)
    lat = sorted(r[1] for r in results)
    codes = {}
    for c, _ in results:
        codes[str(c)] = codes.get(str(c), 0) + 1
    ok = sum(v for k, v in codes.items() if k.startswith('2'))
    numeric = [s for s in samples if isinstance(s[0], (int, float))]
    row = {
        'scenario': name, 'requests': total, 'concurrency': concurrency, 'wallSeconds': round(wall, 2),
        'throughputRps': round(total / wall, 1), 'statusCodes': codes, 'errorRatePercent': round((total - ok) / total * 100, 2),
        'latencyMs': {'median': round(statistics.median(lat), 1), 'p95': round(lat[int(0.95 * (len(lat) - 1))], 1),
                      'max': round(lat[-1], 1), 'min': round(lat[0], 1)},
        'backendCpuPercentPeak': max((s[0] for s in numeric), default=None),
        'backendRssMbPeak': round(max((s[1] for s in numeric), default=0), 1) or None,
    }
    print(json.dumps(row))
    return row


def main(out_path, pid):
    pid = int(pid) if pid else None
    patient, doctor, admin = login('uat.patient1'), login('uat.doctor.cardio'), login('uat.admin')
    env = {'machine': platform.machine(), 'processor': platform.processor(), 'os': platform.platform(),
           'python': platform.python_version(), 'backend': '127.0.0.1:8001, one uvicorn worker, local MongoDB 127.0.0.1',
           'database': 'mediconnect_uat (synthetic)'}
    try:
        import psutil
        env.update({'logicalCpus': psutil.cpu_count(), 'ramGb': round(psutil.virtual_memory().total / 1e9, 1)})
    except Exception:
        pass
    rows = [
        scenario('liveness probe', 'GET', ROOT + '/health/live', 400, 20, pid=pid),
        scenario('readiness probe (database ping)', 'GET', ROOT + '/health/ready', 300, 20, pid=pid),
        scenario('authenticated profile (/auth/me)', 'GET', BASE + '/auth/me', 300, 20, token=patient, pid=pid),
        scenario('doctor search (signed-in patient)', 'GET', BASE + '/doctors?specialty=Cardiologist', 200, 10, token=patient, pid=pid),
        scenario('patient appointments list', 'GET', BASE + '/appointments/me', 200, 10, token=patient, pid=pid),
        scenario('doctor appointment list', 'GET', BASE + '/doctors/me/appointments', 200, 10, token=doctor, pid=pid),
        scenario('admin dashboard analytics (30 days)', 'GET', BASE + '/admin/analytics/overview', 100, 5, token=admin, pid=pid),
        scenario('admin payments list (page 1)', 'GET', BASE + '/admin/payments?page=1&pageSize=20', 150, 10, token=admin, pid=pid),
        scenario('admin appointments search', 'GET', BASE + '/admin/appointments?search=UAT&pageSize=20', 150, 10, token=admin, pid=pid),
        scenario('platform monitoring snapshot', 'GET', BASE + '/security/monitoring/platform', 100, 5, token=admin, pid=pid),
        # Deterministic AI assistants (no external provider), under the 30/min per-user limit.
        scenario('admin AI assistant (deterministic)', 'POST', BASE + '/admin/workflow/assistant', 25, 5, token=admin,
                 body={'message': 'How many successful payments were recorded this week?'}, pid=pid),
        scenario('doctor AI assistant (deterministic)', 'POST', BASE + '/doctor/workflow/assistant', 25, 5, token=doctor,
                 body={'message': 'Show my appointments for tomorrow.'}, pid=pid),
    ]
    pathlib.Path(out_path).write_text(json.dumps({'environment': env, 'scenarios': rows}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
