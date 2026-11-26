"""Compare Phase 05 re-runs of the Phase 01-02 live scripts with the Phase 04 runs, field by field.

Run from the repository root:  python -I docs/uat/phase-05/compare_regression.py
Behavioural fields (HTTP codes, statuses, outcomes, booleans, card types) are compared exactly. Fields that
legitimately change between runs (ids, dates, timestamps, counts of accumulating UAT data, free-text) are
reported separately as data differences.
"""
import json
import pathlib

U = pathlib.Path(__file__).resolve().parents[1]
P4, P5 = U / 'phase-04' / 'evidence', U / 'phase-05' / 'evidence' / 'regression'
VOLATILE = ('id', 'Id', 'date', 'Date', 'At', 'time', 'Time', 'new', 'count', 'Count', 'slot', 'pi', 'intent',
            'reference', 'ref', 'detail', 'message', 'content', 'text', 'reply', 'version', 'notifications',
            'unread', 'free', 'amount', 'secret', 'token', 'session')


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def volatile(key):
    return any(v in key for v in VOLATILE)


def flatten(obj, prefix=''):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f'{prefix}.{k}' if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f'{prefix}[{i}]'))
    else:
        out[prefix] = obj
    return out


def compare_steps(a_steps, b_steps, key='step'):
    a = {s.get(key, i): s for i, s in enumerate(a_steps)}
    b = {s.get(key, i): s for i, s in enumerate(b_steps)}
    behaviour, data = [], []
    for name in a:
        if name not in b:
            behaviour.append({'step': name, 'issue': 'missing in Phase 05 run'})
            continue
        fa, fb = flatten(a[name]), flatten(b[name])
        for field in sorted(set(fa) | set(fb)):
            if fa.get(field) == fb.get(field):
                continue
            leaf = field.split('.')[-1]
            row = {'step': name, 'field': field, 'phase04': fa.get(field), 'phase05': fb.get(field)}
            (data if volatile(leaf) or isinstance(fa.get(field), str) and len(str(fa.get(field))) > 40
             else behaviour).append(row)
    return {'stepsPhase04': len(a), 'stepsPhase05': len(b), 'behaviouralDifferences': behaviour,
            'dataDifferences': len(data), 'dataDifferenceExamples': data[:12]}


def main():
    result = {}
    s4, s5 = load(P4 / 'regression-p02-stripe.json'), load(P5 / 'p02-stripe.json')
    result['phase02Stripe'] = compare_steps(s4['steps'], s5['steps'])
    c4, c5 = load(P4 / 'regression-p02-patient-care.json'), load(P5 / 'p02-care.json')
    def care_steps(d):  # {"components": {name: [steps]}} -> one list with component-qualified step names
        return [{**s, 'step': f"{comp}:{s.get('step', i)}"} for comp, rows in d['components'].items()
                for i, s in enumerate(rows)]
    result['phase02Care'] = compare_steps(care_steps(c4), care_steps(c5))
    p4, p5 = load(P4 / 'regression-p01-probe.json'), load(P5 / 'p01-probe.json')
    fa, fb = flatten(p4), flatten(p5)
    behaviour = [{'field': f, 'phase04': fa.get(f), 'phase05': fb.get(f)} for f in sorted(set(fa) | set(fb))
                 if fa.get(f) != fb.get(f) and not volatile(f.split('.')[-1]) and fa.get(f) is not None
                 and not (isinstance(fa.get(f), str) and len(fa.get(f)) > 40)]
    result['phase01Probe'] = {'valuesCompared': len(set(fa) & set(fb)), 'behaviouralDifferences': behaviour[:40],
                              'behaviouralDifferenceCount': len(behaviour)}
    for name in ('p03-doctor-workflow-uat', 'p04-admin-system-uat'):
        d = load(P5 / f'{name}.json')
        result[name] = d.get('summary') or {'steps': len(d.get('steps', []))}
    out = U / 'phase-05' / 'evidence' / 'regression-comparison.json'
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    for k, v in result.items():
        print(k, {x: (len(y) if isinstance(y, list) else y) for x, y in v.items() if x != 'dataDifferenceExamples'})


if __name__ == '__main__':
    main()
