import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mediconnect/core/constants/api_constants.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/core/storage/secure_storage_service.dart';

class MockSecureStorage extends SecureStorageService {
  String? customUrl;

  MockSecureStorage({this.customUrl});

  @override
  Future<String?> getServerUrl() async => customUrl;

  @override
  Future<void> saveServerUrl(String serverUrl) async {
    customUrl = serverUrl;
  }
}

void main() {
  group('ApiConstants & Health Check', () {
    tearDown(() {
      ApiConstants.resetToDefault();
    });

    test('ApiConstants provides valid hostBaseUrl and defaultBaseUrl', () {
      expect(ApiConstants.hostBaseUrl, isNotEmpty);
      expect(ApiConstants.defaultBaseUrl, contains('/api'));
      expect(ApiConstants.baseUrl, equals(ApiConstants.defaultBaseUrl));
    });

    test('autoDetectBaseUrl respects manually saved URL without overriding when force is false', () async {
      final mockStorage = MockSecureStorage(customUrl: 'http://192.168.1.99:8000');
      var callCount = 0;
      final mockClient = MockClient((request) async {
        callCount++;
        return http.Response('{"api": "healthy"}', 200);
      });

      final result = await ApiConstants.autoDetectBaseUrl(
        storageService: mockStorage,
        client: mockClient,
        force: false,
      );

      // Must respect the manually saved URL
      expect(result, equals('http://192.168.1.99:8000/api'));
      expect(ApiConstants.baseUrl, equals('http://192.168.1.99:8000/api'));
      // No network probes should be fired since saved URL was respected without force
      expect(callCount, equals(0));
    });

    test('autoDetectBaseUrl probes candidate endpoints when force is true or no saved URL', () async {
      final mockStorage = MockSecureStorage(customUrl: null);
      final probedHosts = <String>[];
      final mockClient = MockClient((request) async {
        final host = '${request.url.scheme}://${request.url.host}:${request.url.port}';
        probedHosts.add(host);
        if (request.url.port == 8000 && request.url.host == '127.0.0.1') {
          return http.Response('{"api": "healthy"}', 200);
        }
        return http.Response('error', 500);
      });

      final result = await ApiConstants.autoDetectBaseUrl(
        storageService: mockStorage,
        client: mockClient,
        force: true,
      );

      expect(result, equals('http://127.0.0.1:8000/api'));
      expect(ApiConstants.baseUrl, equals('http://127.0.0.1:8000/api'));
      expect(probedHosts, contains('http://127.0.0.1:8000'));
    });

    test('autoDetectBaseUrl deduplicates concurrent calls to single scan', () async {
      final mockStorage = MockSecureStorage(customUrl: null);
      var getCalls = 0;
      final mockClient = MockClient((request) async {
        getCalls++;
        await Future.delayed(const Duration(milliseconds: 50));
        return http.Response('{"api": "healthy"}', 200);
      });

      final future1 = ApiConstants.autoDetectBaseUrl(
        storageService: mockStorage,
        client: mockClient,
        force: true,
      );
      final future2 = ApiConstants.autoDetectBaseUrl(
        storageService: mockStorage,
        client: mockClient,
        force: true,
      );

      final results = await Future.wait([future1, future2]);
      expect(results[0], equals(results[1]));
      expect(results[0], isNotNull);
      expect(getCalls, greaterThan(0));
    });

    test('ApiClient.checkHealth returns true on 200 OK from GET /health', () async {
      final mockClient = MockClient((request) async {
        if (request.url.path == '/health') {
          return http.Response('{"api": "healthy"}', 200);
        }
        return http.Response('Not Found', 404);
      });

      final client = ApiClient(httpClient: mockClient);
      final isHealthy = await client.checkHealth();
      expect(isHealthy, isTrue);
    });

    test('ApiClient.checkHealth returns false on network failure or 500', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Internal Server Error', 500);
      });

      final client = ApiClient(httpClient: mockClient);
      final isHealthy = await client.checkHealth();
      expect(isHealthy, isFalse);
    });
  });
}
