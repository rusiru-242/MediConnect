/// Safety guard for live API integration tests (Phase 02).
///
/// Live tests run only when RUN_LIVE_TESTS=true AND LIVE_API_BASE_URL is supplied explicitly, e.g.
///   RUN_LIVE_TESTS=true LIVE_API_BASE_URL=http://127.0.0.1:8001/api flutter test test/integration/live_api_test.dart
/// There is no default URL and no fallback. Only local hosts are accepted, port 8000 (the production-like
/// backend) is always refused, and the backend must report an isolated local test database
/// (`database.isolatedTestData == true` from /api/health, reported only outside production).
library;

const _localHosts = {'127.0.0.1', 'localhost', '10.0.2.2'};

/// Returns null when [raw] is an acceptable live-test target, otherwise the reason it is refused.
String? refuseLiveTarget(String? raw) {
  if (raw == null || raw.trim().isEmpty) {
    return 'LIVE_API_BASE_URL is required (for example http://127.0.0.1:8001/api); there is no default.';
  }
  final uri = Uri.tryParse(raw.trim());
  if (uri == null || !(uri.scheme == 'http' || uri.scheme == 'https') || uri.host.isEmpty) {
    return 'LIVE_API_BASE_URL is not a valid http(s) URL.';
  }
  if (!_localHosts.contains(uri.host.toLowerCase())) {
    return 'Live tests may only target a local UAT backend, not ${uri.host}.';
  }
  if (uri.port == 8000) {
    return 'Port 8000 is the production-like backend and is never used for tests.';
  }
  if (!uri.path.endsWith('/api')) {
    return 'LIVE_API_BASE_URL must end with /api.';
  }
  return null;
}

/// The /api/health body must confirm an isolated local test database.
String? refuseHealth(Map<String, dynamic> health) {
  final database = health['database'];
  if (database is! Map || database['connected'] != true) {
    return 'The backend database is not connected.';
  }
  if (database['isolatedTestData'] != true) {
    return 'The backend does not report an isolated local test database (_uat or _test).';
  }
  if ((health['environment'] ?? '').toString().toLowerCase() == 'production') {
    return 'The backend reports a production environment.';
  }
  return null;
}
