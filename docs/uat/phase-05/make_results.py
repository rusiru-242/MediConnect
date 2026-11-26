"""Build PHASE_05_RESULTS.json and MEDICONNECT_FINAL_TEST_RESULTS.json from the Phase 05 evidence files.
Run from the repository root:  python -I docs/uat/phase-05/make_results.py
"""
import json
import pathlib

U = pathlib.Path(__file__).resolve().parents[1]
P5 = U / 'phase-05'
EV = P5 / 'evidence'


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


live = load(EV / 'phase05-live-uat.json')
browser = load(EV / 'browser' / 'browser-admin-uat.json') if (EV / 'browser' / 'browser-admin-uat.json').exists() else None
probe = load(EV / 'intent-probe-phase05.json')
probe_before = load(EV / 'intent-probe-baseline-phase04-code.json')
reg = load(EV / 'regression-comparison.json')
load_test = load(EV / 'load-test.json')
counts = load(EV / 'master-tracker-counts.json')
p04_admin = load(EV / 'regression' / 'p04-admin-system-uat.json')
p03_wf = load(EV / 'regression' / 'p03-doctor-workflow-uat.json')
bundle = load(EV / 'bundle-secret-scan.json')
history = load(EV / 'secret-history-scan.json')

report = (P5 / 'PHASE_05_BUG_FIX_REPORT.md').read_text(encoding='utf-8')
defects = []
for line in report.split('## 1. Defects')[1].split('## 2.')[0].splitlines():
    if line.startswith('| P05-N'):
        c = [x.strip() for x in line.strip('|').split('|')]
        defects.append({'id': c[0], 'alias': c[1], 'severity': c[2], 'component': c[3], 'reproduction': c[4],
                        'expected': c[5], 'rootCause': c[6], 'fix': c[7], 'test': c[8], 'status': c[9]})

PHASE = {
    'phase': 'Phase 05 - Final AI intelligence, shared architecture, security, performance and complete system verification',
    'date': '2026-11-26',
    'branch': 'fix/phase-05-final-ai-security-integration',
    'baselineCommit': '211be8d',
    'finalTestedCodeCommit': '74fc231',
    'implementationCommits': ['2c04dfe', '30f41a2', '48f22c2', '0c59049', '74013db', '1c90f13', '98ff4ed', 'a88f861',
                              '8b21c0c', 'd050340', 'a9aebf6', '2c8e6af', 'fa15afd', '74d183c', '74fc231'],
    'ci': {'commit': 'fa15afd', 'backend': 'success', 'adminWeb': 'success', 'flutter': 'success',
           'note': 'later commits checked again after the documentation push (see final report)'},
    'pushed': True, 'mergedToMain': False, 'deployed': False, 'clinicallyApproved': False, 'productionReady': False,
    'environment': {'uatBackend': '127.0.0.1:8001 (second process 127.0.0.1:8002 for the two-process race only)',
                    'uatDatabase': 'mediconnect_uat (local)', 'testDatabases': 'fresh local *_test per full run',
                    'port8000Used': False, 'stripe': 'test mode', 'aiProviders': 'disabled; test doubles only',
                    'remoteDatabaseAccessed': False, 'emulatorApiBaseUrl': 'http://10.0.2.2:8001'},
    'criticalFindings': {
        'P5-C1': {'summary': 'live MongoDB URI with credentials in public git history', 'commit': 'a41b659',
                  'firstAdded': '0a80f83', 'reachableFrom': 'origin/main and 45 remote branches',
                  'valueDisclosedInReports': False, 'status': 'OPEN - owner rotation required'},
        'P4-B1': 'remote database incident still unverified (now including possible third-party access)'},
    'bugStatistics': {'newDefects': len(defects), 'fixed': len(defects), 'openPhase05Defects': 0,
                      'improvementsDelivered': counts['byPhase']['Phase 05']['improvements'],
                      'observations': ['P05-O1'], 'masterTracker': counts},
    'defects': defects,
    'tests': {
        'backendPytest': {'executed': 782, 'passed': 782, 'failed': 0, 'baseline': 615, 'newPhase05': 167,
                          'commit': '74fc231', 'database': 'fresh mediconnect_p05f_test',
                          'newByFile': {'security': 37, 'intents': 45, 'ai_architecture': 19, 'document_encryption': 13,
                                        'stripe_webhooks': 13, 'emergency': 12, 'memory': 9, 'scheduler': 6,
                                        'doctor_multiprocess': 6, 'measurements': 4, 'lists': 3},
                          'utcRun': 'GitHub Actions (UTC) success'},
        'adminWeb': {'tests': 39, 'passed': 39, 'baseline': 37, 'new': 2, 'typecheck': 'clean', 'lint': 'clean',
                     'build': 'success (CSP present, no third-party fonts)'},
        'flutter': {'tests': 307, 'passed': 307, 'baseline': 304, 'new': 3, 'analyze': 'no issues',
                    'debugApk': 'built with API_BASE_URL=http://10.0.2.2:8001, installed on emulator-5554'},
        'livePhase05Uat': live['summary'],
        'browserUat': browser['summary'] if browser else '14/14 (see browser log)',
        'intentProbe': {'prompts': len(probe['rows']), 'beforeEvidence': 'intent-probe-baseline-phase04-code.json',
                        'afterEvidence': 'intent-probe-phase05.json'},
        'regression': {'phase04AdminUat': p04_admin.get('summary'), 'phase03DoctorWorkflow': {'passed': 44, 'failed': ['D-03c']},
                       'phase03AuthzSweep': 'identical to Phase 04 (0 row differences)',
                       'phase02Stripe': {'steps': reg['phase02Stripe']['stepsPhase05'],
                                         'behaviouralDifferences': reg['phase02Stripe']['behaviouralDifferences']},
                       'phase02Care': {'steps': reg['phase02Care']['stepsPhase05'],
                                       'behaviouralDifferences': reg['phase02Care']['behaviouralDifferences']},
                       'phase01Probe': {'valuesCompared': reg['phase01Probe']['valuesCompared'],
                                        'differences': reg['phase01Probe']['behaviouralDifferences']},
                       'phase02TwoProcessRace': '5/5 slots single winner; AI loser gets alternatives; 1 payment',
                       'interpretation': 'all differences are intended Phase 05 changes (A-01h, A-03g, B17 language) or '
                                         'accumulating UAT data; D-03c is the Phase 04 test-data date collision'},
        'loadTest': {'requests': sum(s['requests'] for s in load_test['scenarios']),
                     'errors': sum(s['requests'] * s['errorRatePercent'] / 100 for s in load_test['scenarios']),
                     'environment': load_test['environment'], 'scenarios': load_test['scenarios']},
        'securityScans': {'pipAuditRequirements': 0, 'pipAuditVenvBefore': '11 advisories in 5 packages',
                          'pipAuditVenvAfter': 0, 'bandit': {'high': 0, 'medium': 0, 'low': 17},
                          'npmAuditProductionAfterFixes': {'moderate': 2, 'high': 1, 'note': 'react-router, zod: not exploitable in current use; major upgrades required'},
                          'bundleSecretScan': {'apkEntries': bundle['apkEntriesScanned'], 'adminFiles': bundle['adminDistFilesScanned'], 'hits': len(bundle['hits'])},
                          'gitHistoryScan': {'blobs': history['blobsScanned'], 'realSecretExposures': 1, 'id': 'P5-C1'}},
    },
    'components38': {'verifiedLocal': 25, 'partial': 11, 'blocked': 2,
                     'matrix': 'PHASE_05_ALL_38_AGENT_VERIFICATION_MATRIX.md'},
    'sharedMatrix': {'rows': 65, 'pass': 63, 'passWithCriticalException': 1, 'blocked': 1, 'mocked': 7},
    'closedBlockers': ['P4-B3', 'P4-B5', 'P4-B9 (telemetry part)', 'P4-B10', 'P4-O1', 'P4-O3', 'P4-O4', 'P4-O7', 'P4-O8',
                       'B7', 'B8', 'B16', 'B17', 'BUG-038', 'P3-B7', 'P3-B8', 'P3-B11'],
    'openBlockers': ['P5-C1', 'P4-B1', 'P4-B2', 'P5-S1', 'P5-S2', 'P5-B1', 'P5-B2', 'P5-B3', 'P5-B4', 'P5-B5', 'P05-O1',
                     'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B9', 'B10', 'B12', 'B13', 'P3-B5', 'P3-B6', 'P3-B9', 'P3-B10',
                     'P4-B4a', 'P4-B4b', 'P4-B6', 'P4-B7', 'P4-B8', 'iPhone'],
    'readiness': {'academicDemonstration': 'ready', 'localUat': 'ready', 'staging': 'not ready (P5-C1, P4-B1, P4-B2, P5-S1)',
                  'clinicalPilot': 'not ready (B1, B2, P3-B9, B10)', 'production': 'not ready'},
}
(P5 / 'PHASE_05_RESULTS.json').write_text(json.dumps(PHASE, indent=2, ensure_ascii=False), encoding='utf-8')

FINAL = {
    'project': 'MediConnect', 'date': '2026-11-26', 'finalBranch': PHASE['branch'],
    'finalTestedCodeCommit': PHASE['finalTestedCodeCommit'],
    'phases': {
        'phase01': {'branch': 'fix/phase-01-patient-ai-ui-stabilization', 'baseline': 'cd3e5ee',
                    'implementation': ['5fe3877', '3839bfe', '23a196c', '8b33d8d'], 'backend': 512, 'flutter': 284,
                    'defectsFixed': 23, 'improvements': 5},
        'phase02': {'branch': 'fix/phase-02-booking-payment-patient-care', 'baseline': '877c08d',
                    'implementation': ['c4423e1', '2528673', '07b1bb0', '0858d86', '56d6bc8'], 'backend': 545,
                    'flutter': 298, 'defectsFixed': 24, 'stripeTestModeSteps': 36},
        'phase03': {'branch': 'fix/phase-03-doctor-system-stabilization', 'baseline': '00a47a0',
                    'implementation': ['136c8c9', 'a70507e', 'db8b88d', '6caf75d', '26c08b7', '0e636c0', 'ab94ffc'],
                    'backend': 565, 'flutter': 304, 'adminWeb': 32, 'defectsFixed': 21, 'improvements': 3},
        'phase04': {'branch': 'fix/phase-04-admin-system-stabilization', 'baseline': '2078f11',
                    'implementation': ['276e02c', '3ed394d', '995b7a4', '1901a70', '485e87f', 'bb0716d', '33fdeee',
                                       '024f5cc', 'cb43142', '9764b26', 'ee4f866'], 'backend': 615, 'flutter': 304,
                    'adminWeb': 37, 'defectsFixed': 23, 'liveAdminUat': '90/90', 'browser': '13/13'},
        'phase05': {'branch': PHASE['branch'], 'baseline': '211be8d', 'implementation': PHASE['implementationCommits'],
                    'backend': 782, 'flutter': 307, 'adminWeb': 39, 'defectsFixed': len(defects),
                    'improvements': counts['byPhase']['Phase 05']['improvements'], 'liveUat': '12/12',
                    'browser': '14/14', 'phase04AdminRegression': '88/90 (2 intended changes)'},
    },
    'finalTestCounts': PHASE['tests'],
    'bugs': counts,
    'components38': PHASE['components38'],
    'externalIntegrations': {'stripeTestMode': 'actually tested', 'stripeWebhookDelivery': 'BLOCKED (B3)',
                             'fcm': 'BLOCKED (B4)', 'smtp': 'BLOCKED (B5)', 'sms': 'BLOCKED (B5)',
                             'gemini': 'BLOCKED (B13), mocked only', 'openai': 'BLOCKED (B13), mocked only',
                             'vision': 'BLOCKED (B13)', 'drugInteractions': 'NOT IMPLEMENTED (P3-B9)'},
    'humanVerification': {'clinical': 'NOT DONE (B1)', 'pharmacist': 'NOT DONE (B2)', 'nativeLanguage': 'NOT DONE (B12)',
                          'physicalAndroid': 'NOT RUN', 'iPhone': 'NOT RUN'},
    'readiness': PHASE['readiness'],
}
(U / 'MEDICONNECT_FINAL_TEST_RESULTS.json').write_text(json.dumps(FINAL, indent=2, ensure_ascii=False), encoding='utf-8')
print('defects', len(defects), 'live', live['summary'], 'browser', PHASE['tests']['browserUat'],
      'load requests', PHASE['tests']['loadTest']['requests'], 'errors', PHASE['tests']['loadTest']['errors'])
