import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mediconnect/core/constants/api_constants.dart';
import 'package:mediconnect/core/network/api_client.dart';

void main() {
  group('ApiConstants & Health Check', () {
    test('ApiConstants provides valid hostBaseUrl and defaultBaseUrl', () {
      expect(ApiConstants.hostBaseUrl, isNotEmpty);
      expect(ApiConstants.defaultBaseUrl, contains('/api'));
      expect(ApiConstants.baseUrl, equals(ApiConstants.defaultBaseUrl));
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
