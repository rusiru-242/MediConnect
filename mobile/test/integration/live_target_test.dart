import 'package:flutter_test/flutter_test.dart';

import 'live_target.dart';

void main() {
  group('Live API target guard (Phase 02)', () {
    test('requires an explicit URL', () {
      expect(refuseLiveTarget(null), isNotNull);
      expect(refuseLiveTarget('  '), isNotNull);
    });
    test('refuses the production-like port 8000 and remote hosts', () {
      expect(refuseLiveTarget('http://127.0.0.1:8000/api'), contains('8000'));
      expect(refuseLiveTarget('http://localhost:8000/api'), contains('8000'));
      expect(refuseLiveTarget('https://api.mediconnect.lk/api'), isNotNull);
      expect(refuseLiveTarget('http://192.168.1.5:8001/api'), isNotNull);
    });
    test('accepts the local UAT backend', () {
      expect(refuseLiveTarget('http://127.0.0.1:8001/api'), isNull);
      expect(refuseLiveTarget('http://10.0.2.2:8001/api'), isNull);
    });
    test('requires the backend to report isolated test data', () {
      expect(refuseHealth({'database': {'connected': true}, 'environment': 'staging'}), isNotNull);
      expect(refuseHealth({'database': {'connected': true, 'isolatedTestData': true}, 'environment': 'production'}),
          isNotNull);
      expect(refuseHealth({'database': {'connected': true, 'isolatedTestData': true}, 'environment': 'staging'}),
          isNull);
    });
  });
}
