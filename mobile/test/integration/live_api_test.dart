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

    test('1. Registration with duplicate email throws 409 conflict', () async {
      try {
        await authService.registerPatient(
          fullName: 'Test Patient',
          email: 'patient@example.com',
          phone: '0771234567',
          password: 'Password@123',
        );
        fail('Expected 409 conflict');
      } on ApiException catch (e) {
        expect(e.statusCode, 409);
        expect(e.message, 'An account with this email already exists.');
      }
    });

    test('2. Registration of a new patient returns 201 created with pending status', () async {
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final newEmail = 'patient_$timestamp@example.com';
      final newPhone = '077${(timestamp % 10000000).toString().padLeft(7, '0')}';

      final response = await authService.registerPatient(
        fullName: 'New Flow Patient',
        email: newEmail,
        phone: newPhone,
        password: 'Password@123',
      );

      expect(response['message'], 'Patient registered successfully.');
      expect(response['user'], isNotNull);
      final user = response['user'] as Map<String, dynamic>;
      expect(user['email'], newEmail);
      expect(user['role'], 'PATIENT');
      expect(user['emailVerified'], isFalse);
      expect(user['accountStatus'], 'PENDING');
    });

    test('3. Verify email with wrong 6-digit OTP throws 400 bad request', () async {
      final timestamp = DateTime.now().millisecondsSinceEpoch + 1;
      final newEmail = 'otp_test_$timestamp@example.com';
      final newPhone = '077${(timestamp % 10000000).toString().padLeft(7, '0')}';

      await authService.registerPatient(
        fullName: 'OTP Test Patient',
        email: newEmail,
        phone: newPhone,
        password: 'Password@123',
      );

      try {
        await authService.verifyEmail(
          email: newEmail,
          otp: '000000',
        );
        fail('Expected 400 bad request');
      } on ApiException catch (e) {
        expect(e.statusCode, 400);
        expect(e.message, contains('Invalid verification code'));
      }
    });

    test('4. Resend OTP during cooldown period throws 429 too many requests', () async {
      final timestamp = DateTime.now().millisecondsSinceEpoch + 2;
      final newEmail = 'resend_$timestamp@example.com';
      final newPhone = '077${(timestamp % 10000000).toString().padLeft(7, '0')}';

      await authService.registerPatient(
        fullName: 'Resend Patient',
        email: newEmail,
        phone: newPhone,
        password: 'Password@123',
      );

      try {
        await authService.resendVerificationOtp(email: newEmail);
        fail('Expected 429 cooldown');
      } on ApiException catch (e) {
        expect(e.statusCode, 429);
        expect(e.message, contains('wait'));
      }
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
      final session = await authService.login(
        email: 'patient@example.com',
        password: 'Password@123',
      );

      expect(session.accessToken, isNotEmpty);
      expect(session.refreshToken, isNotEmpty);
      expect(session.user.email, 'patient@example.com');
      expect(session.user.role, 'PATIENT');
      expect(session.user.emailVerified, isTrue);

      await storage.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      final profile = await authService.getCurrentUser();
      expect(profile.id, session.user.id);
      expect(profile.email, 'patient@example.com');
      expect(profile.fullName, 'Test Patient');
      expect(profile.role, 'PATIENT');
    });

    test('F & G. Token refresh and rotation', () async {
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

      final refreshResponse = await apiClient.post(
        ApiConstants.refreshEndpoint,
        body: {'refreshToken': refreshToken},
        includeAuth: false,
      ) as Map<String, dynamic>;

      expect(refreshResponse['accessToken'], isNotNull);
      expect(refreshResponse['refreshToken'], isNotNull);
      expect(refreshResponse['tokenType'], 'bearer');

      await storage.saveTokens(
        accessToken: refreshResponse['accessToken'] as String,
        refreshToken: refreshResponse['refreshToken'] as String,
      );

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

      await authService.logout(activeRefreshToken!);
      await storage.clearAll();

      final clearedAccessToken = await storage.getAccessToken();
      expect(clearedAccessToken, isNull);

      expect(
        () async => await authService.getCurrentUser(),
        throwsA(isA<AuthException>()),
      );
    });

    test('5. Forgot password with existing email returns generic response without enumeration', () async {
      final msg = await authService.forgotPassword(email: 'patient@example.com');
      expect(msg, 'If an account exists for this email, a password reset code has been sent.');
    });

    test('6. Forgot password with unknown email returns identical generic response', () async {
      final msg = await authService.forgotPassword(email: 'nonexistent_user_999@example.com');
      expect(msg, 'If an account exists for this email, a password reset code has been sent.');
    });

    test('7. Verify reset OTP with wrong 6-digit OTP throws 400 bad request', () async {
      try {
        await authService.verifyResetOtp(
          email: 'patient@example.com',
          otp: '000000',
        );
        fail('Expected 400 bad request');
      } on ApiException catch (e) {
        expect(e.statusCode, 400);
        expect(e.message, contains('Invalid password reset code'));
      }
    });

    test('8. Reset password with invalid resetToken throws 400 bad request', () async {
      try {
        await authService.resetPassword(
          resetToken: 'invalid_dummy_token_123',
          newPassword: 'NewPassword@123',
          confirmPassword: 'NewPassword@123',
        );
        fail('Expected 400 bad request');
      } on ApiException catch (e) {
        expect(e.statusCode, 400);
        expect(e.message, contains('Invalid or already used reset token'));
      }
    });

    test('I. Backend unavailable / invalid host returns clean NetworkException', () async {
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
