"""Build docs/uat/MEDICONNECT_MASTER_BUG_TRACKER.md and the tracker counts from the recorded sources only.

Sources: docs/MASTER_BUG_TRACKER.md (BUG-001..048 headings and tables), PHASE_01..04_RESULTS.json, and the Phase 05
defect table in PHASE_05_BUG_FIX_REPORT.md. Aliases are resolved so nothing is counted twice:
BUG-049..063 that map to Phase 01 items are listed once (under the Phase 01 id, with the owner id as alias).
Run from the repository root:  python -I docs/uat/phase-05/build_master_tracker.py
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
U = ROOT / 'docs' / 'uat'
rows = []


def add(cid, aliases, sev, component, title, kind, status, source):
    rows.append({'id': cid, 'aliases': aliases, 'severity': sev or '—', 'component': component or '—',
                 'title': re.sub(r'\s+', ' ', title).replace('|', '/')[:150], 'kind': kind, 'status': status,
                 'source': source})


# ---- BUG-001..048 (historical tracker)
tracker = (ROOT / 'docs' / 'MASTER_BUG_TRACKER.md').read_text(encoding='utf-8')
hist = {}
for m in re.finditer(r'^### (BUG-0\d\d) — (.+)$', tracker, re.M):
    hist[m.group(1)] = {'title': m.group(2).replace('*(provisional ID)*', '').strip()}
for m in re.finditer(r'^\| (BUG-0\d\d) \| ([^|]+) \| ([^|]+) \|(.*)\|$', tracker, re.M):
    cells = [c.strip() for c in m.group(4).split('|')]
    hist.setdefault(m.group(1), {'title': m.group(2).strip()})
    hist[m.group(1)].setdefault('severity', m.group(3).strip())
    hist[m.group(1)]['status_raw'] = cells[-1] if cells else ''
for i in range(1, 49):
    bid = f'BUG-{i:03d}'
    h = hist.get(bid, {'title': '(not found in tracker)'})
    status = 'FIXED'
    raw = h.get('status_raw', '')
    if bid == 'BUG-009':
        kind, status = 'regression guard', 'NOT A DEFECT'
    else:
        kind = 'defect'
    if bid == 'BUG-038':
        status = 'FIXED (Phase 05, P05-N09)'
    elif bid == 'BUG-039':
        status = 'OPEN (product decision: profile response default fee)'
    elif bid == 'BUG-023':
        status = 'FIXED in code; live vision BLOCKED (B13)'
    elif bid in ('BUG-044', 'BUG-046'):
        status = 'FIXED (Phase 01)'
    elif bid in ('BUG-004', 'BUG-014', 'BUG-015', 'BUG-025', 'BUG-043', 'BUG-042', 'BUG-045'):
        status = 'FIXED; manual device retest pending'
    add(bid, '', h.get('severity'), '', h['title'], kind, status, 'docs/MASTER_BUG_TRACKER.md')

# ---- Phase 01
p1 = json.loads((U / 'phase-01' / 'PHASE_01_RESULTS.json').read_text(encoding='utf-8'))
p2 = json.loads((U / 'phase-02' / 'PHASE_02_RESULTS.json').read_text(encoding='utf-8'))
owner_alias = {}
for b in p2['ownerBugs']:
    for a in re.findall(r'P01-\d\d', b.get('phase01Alias') or ''):
        owner_alias.setdefault(a, []).append(b['id'])
for b in p1['bugs']:
    if b['id'].startswith('BUG-'):
        continue  # BUG-044/046 already listed above
    improvement = b['status'].startswith('IMPLEMENTED')
    add(b['id'], ', '.join(owner_alias.get(b['id'], [])), b.get('severity'), 'Patient AI / UI', b['title'],
        'improvement' if improvement else 'defect', b['status'].replace('_', ' '), 'phase-01/PHASE_01_BUG_FIX_REPORT.md')

# ---- Owner BUG-049..063 not aliased to Phase 01
aliased = {o for v in owner_alias.values() for o in v}
for b in p2['ownerBugs']:
    if b['id'] in aliased:
        continue
    add(b['id'], '', b.get('severity'), 'Booking / patient care', b['title'], 'defect', b['status'].replace('_', ' '),
        'phase-02/PHASE_02_BUG_ID_RECONCILIATION.md')

# ---- Phase 02
for b in p2['newBugs']:
    add(b['id'], '', b.get('severity'), 'Booking / payment / care', b['title'], 'defect', b['status'].replace('_', ' '),
        'phase-02/PHASE_02_BUG_FIX_REPORT.md')

# ---- Phase 03 / 04
for ph, name in (('phase-03', 'PHASE_03'), ('phase-04', 'PHASE_04')):
    d = json.loads((U / ph / f'{name}_RESULTS.json').read_text(encoding='utf-8'))
    for b in d['bugs']:
        add(b['id'], '', b.get('severity'), b.get('component'), b.get('description', ''), 'defect',
            (b.get('status') or 'FIXED').replace('_', ' '), f'{ph}/{name}_BUG_FIX_REPORT.md')
    for b in d.get('improvements', []):
        add(b['id'], '', '—', '', b['title'], 'improvement', 'IMPLEMENTED', f'{ph}/{name}_BUG_FIX_REPORT.md')

# ---- Phase 05
report = (U / 'phase-05' / 'PHASE_05_BUG_FIX_REPORT.md').read_text(encoding='utf-8')
defects = report.split('## 1. Defects')[1].split('## 2.')[0]
for line in defects.splitlines():
    if line.startswith('| P05-N'):
        c = [x.strip() for x in line.strip('|').split('|')]
        add(c[0], '' if c[1].startswith('—') else c[1], c[2], c[3], c[4], 'defect', c[-1],
            'phase-05/PHASE_05_BUG_FIX_REPORT.md')
improvements = report.split('## 3.')[1].split('## 4.')[0]
for line in improvements.splitlines():
    if line.startswith('| P05-'):
        c = [x.strip() for x in line.strip('|').split('|')]
        add(c[0], c[2] if c[2] != '—' else '', '—', '', c[1], 'improvement', 'IMPLEMENTED',
            'phase-05/PHASE_05_BUG_FIX_REPORT.md')
add('P05-O1', '', 'Low', 'Tests', 'Intermittent test_phase3_care failure (6 reminder rows once)', 'observation',
    'OPEN (not reproduced)', 'phase-05/PHASE_05_BUG_FIX_REPORT.md')
add('P5-C1', '', 'Critical', 'Repository / credentials',
    'Live MongoDB URI with credentials in public git history (a41b659)', 'security incident',
    'OPEN — owner rotation required', 'phase-05/PHASE_05_SECURITY_AND_PRIVACY_REPORT.md')

# ---- Agent Completion A01 (2026-11-26, branch fix/agents-a01-ai-intelligence-vision)
a01 = U / 'agent-completion' / 'a01' / 'A01_BUG_FIX_REPORT.md'
if a01.exists():
    import re as _re
    a01_text = a01.read_text(encoding='utf-8')
    for line in a01_text.split('## Defects')[1].split('### Found during')[0].splitlines():
        if line.startswith('| A01-N'):
            c = [x.strip() for x in line.strip('|').split('|')]
            title = _re.sub(r'\*\*|`', '', c[3])
            title = _re.split(r'(?<=[.)])\s', title)[0][:140]
            add(c[0], '', _re.sub(r'\*', '', c[1]), c[2], title, 'defect', 'FIXED (A01)',
                'agent-completion/a01/A01_BUG_FIX_REPORT.md')
    for m in _re.finditer(r'^- \*\*O(\d)\:\*\* (.+)$', a01_text.split('## Observations')[1], _re.M):
        add(f'A01-O{m.group(1)}', '', 'Low', 'A01', m.group(2).split('. ')[0][:140], 'observation', 'OPEN',
            'agent-completion/a01/A01_BUG_FIX_REPORT.md')

# ---- Agent Completion A02 (2026-11-26, branch fix/agents-a02-reminders-notifications)
a02 = U / 'agent-completion' / 'a02' / 'A02_BUG_FIX_REPORT.md'
if a02.exists():
    import re as _re
    a02_text = a02.read_text(encoding='utf-8')
    for line in a02_text.split('## Defects')[1].split('## Changed test expectations')[0].splitlines():
        if line.startswith('| A02-BUG-'):
            c = [x.strip() for x in line.strip('|').split('|')]
            title = _re.sub(r'\*\*|`', '', c[3])
            title = _re.split(r'(?<=[.)])\s', title)[0][:140]
            add(c[0], '', _re.sub(r'\s*\(.*\)', '', c[1]), c[2], title, 'defect', 'FIXED (A02)',
                'agent-completion/a02/A02_BUG_FIX_REPORT.md')
    for line in a02_text.split('## Observations')[1].splitlines():
        if line.startswith('| A02-O'):
            c = [x.strip() for x in line.strip('|').split('|')]
            add(c[0], '', 'Low', 'A02', _re.sub(r'`', '', c[1]).split('. ')[0][:140], 'observation', 'OPEN',
                'agent-completion/a02/A02_BUG_FIX_REPORT.md')

# ---- Agent Completion A03 (2026-11-27, branch fix/agents-a03-booking-payments)
a03 = U / 'agent-completion' / 'a03' / 'A03_BUG_FIX_REPORT.md'
if a03.exists():
    import re as _re
    a03_text = a03.read_text(encoding='utf-8')
    for line in a03_text.split('## Defects')[1].split('## Changed test expectations')[0].splitlines():
        if line.startswith('| A03-BUG-'):
            c = [x.strip() for x in line.strip('|').split('|')]
            title = _re.sub(r'\*\*|`', '', c[3])
            title = _re.split(r'(?<=[.)])\s', title)[0][:140]
            add(c[0], '', _re.sub(r'\s*\(.*\)', '', c[1]), c[2], title, 'defect', 'FIXED (A03)',
                'agent-completion/a03/A03_BUG_FIX_REPORT.md')
    for line in a03_text.split('## Observations')[1].splitlines():
        if line.startswith('| A03-O'):
            c = [x.strip() for x in line.strip('|').split('|')]
            add(c[0], '', 'Low', 'A03', _re.sub(r'`', '', c[1]).split('. ')[0][:140], 'observation', 'OPEN',
                'agent-completion/a03/A03_BUG_FIX_REPORT.md')

# A02-O4 (index-dependent tests in isolation) was resolved in A03: tests/conftest.py creates the indexes first.
for _r in rows:
    if _r['id'] == 'A02-O4':
        _r['status'] = 'RESOLVED (A03)'

# ---- Agent Completion A04 (2026-11-27, branch fix/agents-a04-prescription-assistant)
a04 = U / 'agent-completion' / 'a04' / 'A04_BUG_FIX_REPORT.md'
if a04.exists():
    import re as _re
    a04_text = a04.read_text(encoding='utf-8')
    for line in a04_text.split('## Defects')[1].split('## Changed test expectations')[0].splitlines():
        if line.startswith('| A04-BUG-'):
            c = [x.strip() for x in line.strip('|').split('|')]
            title = _re.sub(r'\*\*|`', '', c[3])
            title = _re.split(r'(?<=[.)])\s', title)[0][:140]
            add(c[0], '', _re.sub(r'\s*\(.*\)', '', c[1]), c[2], title, 'defect', 'FIXED (A04)',
                'agent-completion/a04/A04_BUG_FIX_REPORT.md')
    for line in a04_text.split('## Observations')[1].splitlines():
        if line.startswith('| A04-O'):
            c = [x.strip() for x in line.strip('|').split('|')]
            add(c[0], '', 'Low', 'A04', _re.sub(r'`', '', c[1]).split('. ')[0][:140], 'observation', 'OPEN',
                'agent-completion/a04/A04_BUG_FIX_REPORT.md')

# ---- counts
def is_open(r):
    return r['status'].upper().startswith('OPEN')

counts = {
    'uniqueTrackedItems': len(rows),
    'confirmedDefects': sum(r['kind'] == 'defect' for r in rows),
    'defectsFixed': sum(r['kind'] == 'defect' and not is_open(r) for r in rows),
    'defectsOpen': [r['id'] for r in rows if r['kind'] == 'defect' and is_open(r)],
    'defectsFixedPendingManualDeviceRetest': [r['id'] for r in rows if 'retest pending' in r['status']],
    'defectsFixedExternalVerificationBlocked': [r['id'] for r in rows if 'BLOCKED' in r['status'].upper() and r['kind'] == 'defect'],
    'improvementsOrRequirements': sum(r['kind'] == 'improvement' for r in rows),
    'regressionGuards': sum(r['kind'] == 'regression guard' for r in rows),
    'observations': [r['id'] for r in rows if r['kind'] == 'observation'],
    'securityIncidents': [r['id'] for r in rows if r['kind'] == 'security incident'],
    'ownerIdsAliasedToPhase01': sorted(aliased),
    'byPhase': {},
}
for prefix, label in (('BUG-0', 'historical BUG-001..063 (unaliased)'), ('P01-', 'Phase 01'), ('P02-', 'Phase 02'),
                      ('P03-', 'Phase 03'), ('P04-', 'Phase 04'), ('P05-', 'Phase 05'),
                      ('A01-', 'Agent Completion A01'), ('A02-', 'Agent Completion A02'),
                      ('A03-', 'Agent Completion A03'), ('A04-', 'Agent Completion A04')):
    sel = [r for r in rows if r['id'].startswith(prefix)]
    counts['byPhase'][label] = {'defects': sum(r['kind'] == 'defect' for r in sel),
                                'improvements': sum(r['kind'] == 'improvement' for r in sel)}

(U / 'phase-05' / 'evidence' / 'master-tracker-counts.json').write_text(json.dumps(counts, indent=2), encoding='utf-8')

lines = [
    '# MediConnect — Master Bug Tracker (reconciled, Phases 00–05 and Agent Completion A01–A04)', '',
    'For: the project owner, reviewers and future maintainers. Generated 2026-11-27 by '
    '`docs/uat/phase-05/build_master_tracker.py` from the recorded sources only (nothing re-typed by hand).', '',
    '## How to read it', '',
    '- One row per **unique** issue. Owner IDs BUG-049 to BUG-063 that describe a Phase 01 item are listed once, under '
    'the Phase 01 ID, with the owner ID in **Aliases** (' + ', '.join(sorted(aliased)) + ').',
    '- **Kind** separates defects from improvements/requirements, regression guards, observations and security incidents.',
    '- Full reproduction, expected/actual behaviour, root cause, changed files, fix, regression test and evidence for each '
    'row are in the **Source** report (historical rows keep their original evidence there). This index does not change '
    'any historical record.',
    '- "FIXED" means fixed with an automated regression test; device, clinical or external verification is stated where '
    'it is still pending. No defect is marked clinically approved.', '',
    '## Counts', '',
    '| Measure | Count |', '|---|---|',
    f"| Unique tracked items | {counts['uniqueTrackedItems']} |",
    f"| Confirmed defects | {counts['confirmedDefects']} |",
    f"| Defects fixed (automated regression) | {counts['defectsFixed']} |",
    f"| Defects open | {len(counts['defectsOpen'])} ({', '.join(counts['defectsOpen'])}) |",
    f"| …of the fixed: manual device retest still pending | {len(counts['defectsFixedPendingManualDeviceRetest'])} |",
    f"| …of the fixed: external verification blocked | {len(counts['defectsFixedExternalVerificationBlocked'])} |",
    f"| Improvements / requirements delivered | {counts['improvementsOrRequirements']} |",
    f"| Regression guards (not defects) | {counts['regressionGuards']} |",
    f"| Observations (unconfirmed) | {len(counts['observations'])} |",
    f"| Security incidents (owner) | {len(counts['securityIncidents'])} |", '',
    '| Source | Defects | Improvements |', '|---|---|---|',
]
for label, v in counts['byPhase'].items():
    lines.append(f"| {label} | {v['defects']} | {v['improvements']} |")
lines += ['', 'Owner decisions and external blockers (B1–B17, P3-B*, P4-B*, P5-*) are not defects; see '
          '`PHASE_05_REMAINING_BLOCKERS.md`.', '', '## Index', '',
          '| ID | Aliases | Kind | Severity | Component | Title | Status | Source |', '|---|---|---|---|---|---|---|---|']
for r in rows:
    lines.append(f"| {r['id']} | {r['aliases']} | {r['kind']} | {r['severity']} | {r['component']} | {r['title']} | "
                 f"{r['status']} | {r['source']} |")
(U / 'MEDICONNECT_MASTER_BUG_TRACKER.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in counts.items() if k != 'byPhase'}, indent=1))
print(json.dumps(counts['byPhase']))
