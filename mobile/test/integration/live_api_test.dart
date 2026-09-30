import 'dart:io';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/constants/api_constants.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';
import 'package:mediconnect/core/storage/secure_storage_service.dart';
import 'package:mediconnect/services/auth_api_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = null; // Enable live HTTP connections in Flutter test runner

  setUp(() {
    ApiConstants.baseUrl = 'http://127.0.0.1:8000/api';
    FlutterSecureStorage.setMockInitialValues({});
  });

  group('Live MediConnect FastAPI End-to-End Integration', () {
    late SecureStorageService storage;
    late ApiClient apiClient;
    late AuthApiService authService;

    setUp(() {
      storage = SecureStorageService();
      apiClient = ApiClient(storageService: storage);
      authService = AuthApiService(apiClient: apiClient);
    });

    test('B. Invalid email/password throws user-friendly AuthException', () async {
      try {
        await authService.login(
          email: 'patient@example.com',
          password: 'IncorrectPassword@999',
        );
        fail('Expected AuthException to be thrown');
      } on AuthException catch (e) {
        expect(e.message, 'Invalid email or password.');
        expect(e.statusCode, 401);
      }
    });

    test('C & D. Valid verified patient logs in and accesses GET /api/auth/me', () async {
      // Login with verified test credentials
      final session = await authService.login(
        email: 'patient@example.com',
        password: 'Password@123',
      );

      expect(session.accessToken, isNotEmpty);
      expect(session.refreshToken, isNotEmpty);
      expect(session.user.email, 'patient@example.com');
      expect(session.user.role, 'PATIENT');
      expect(session.user.emailVerified, isTrue);

      // Save tokens to storage to simulate active session
      await storage.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      // D. Verify GET /api/auth/me with active access token
      final profile = await authService.getCurrentUser();
      expect(profile.id, session.user.id);
      expect(profile.email, 'patient@example.com');
      expect(profile.fullName, 'Test Patient');
      expect(profile.role, 'PATIENT');
    });

    test('F & G. Token refresh and rotation', () async {
      // Login to obtain active session
      final session = await authService.login(
        email: 'patient@example.com',
        password: 'Password@123',
      );
      await storage.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      final refreshToken = await storage.getRefreshToken();
      expect(refreshToken, isNotNull);

      // Perform direct refresh call via ApiClient
      final refreshResponse = await apiClient.post(
        ApiConstants.refreshEndpoint,
        body: {'refreshToken': refreshToken},
        includeAuth: false,
      ) as Map<String, dynamic>;

      expect(refreshResponse['accessToken'], isNotNull);
      expect(refreshResponse['refreshToken'], isNotNull);
      expect(refreshResponse['tokenType'], 'bearer');

      // Update storage with rotated tokens
      await storage.saveTokens(
        accessToken: refreshResponse['accessToken'] as String,
        refreshToken: refreshResponse['refreshToken'] as String,
      );

      // Verify the new rotated access token can access /api/auth/me
      final profile = await authService.getCurrentUser();
      expect(profile.email, 'patient@example.com');
    });

    test('H. Logout revokes refresh token and clears storage', () async {
      final session = await authService.login(
        email: 'patient@example.com',
        password: 'Password@123',
      );
      await storage.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      final activeRefreshToken = await storage.getRefreshToken();
      expect(activeRefreshToken, isNotNull);

      // Call backend logout
      await authService.logout(activeRefreshToken!);

      // Clear local storage
      await storage.clearAll();

      final clearedAccessToken = await storage.getAccessToken();
      expect(clearedAccessToken, isNull);

      // Verify subsequent GET /api/auth/me fails with AuthException
      expect(
        () async => await authService.getCurrentUser(),
        throwsA(isA<AuthException>()),
      );
    });

    test('I. Backend unavailable / invalid host returns clean NetworkException', () async {
      // Point temporarily to an unreachable port
      ApiConstants.baseUrl = 'http://127.0.0.1:59999/api';

      try {
        await authService.login(
          email: 'patient@example.com',
          password: 'Password@123',
        );
        fail('Expected NetworkException');
      } on NetworkException catch (e) {
        expect(
          e.message,
          'Unable to connect to MediConnect. Please check your internet connection and try again.',
        );
      } finally {
        ApiConstants.baseUrl = 'http://127.0.0.1:8000/api';
      }
    });
  });
}
