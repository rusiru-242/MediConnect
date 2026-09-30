import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';
import 'package:mediconnect/core/storage/secure_storage_service.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/google_auth_service.dart';

class FakeGoogleAuthService extends GoogleAuthService {
  String? idTokenToReturn;
  Exception? exceptionToThrow;
  bool signOutCalled = false;

  @override
  Future<String?> authenticate({String? serverClientId}) async {
    if (exceptionToThrow != null) {
      throw exceptionToThrow!;
    }
    return idTokenToReturn;
  }

  @override
  Future<void> signOut() async {
    signOutCalled = true;
  }
}

class FakeAuthApiService extends AuthApiService {
  String? lastIdTokenReceived;
  AuthSession? sessionToReturn;
  Exception? exceptionToThrow;
  String? lastRevokedRefreshToken;

  @override
  Future<AuthSession> authenticateWithGoogle({required String idToken}) async {
    lastIdTokenReceived = idToken;
    if (exceptionToThrow != null) {
      throw exceptionToThrow!;
    }
    return sessionToReturn!;
  }

  @override
  Future<void> logout(String refreshToken) async {
    lastRevokedRefreshToken = refreshToken;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late SecureStorageService storageService;
  late FakeGoogleAuthService fakeGoogleAuth;
  late FakeAuthApiService fakeAuthApi;
  late AuthProvider authProvider;

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    storageService = SecureStorageService();
    fakeGoogleAuth = FakeGoogleAuthService();
    fakeAuthApi = FakeAuthApiService();
    authProvider = AuthProvider(
      authApiService: fakeAuthApi,
      storageService: storageService,
      googleAuthService: fakeGoogleAuth,
    );
  });

  group('AuthProvider Google Sign-In', () {
    test('1. User cleanly cancels Google account picker returns false with no scary error', () async {
      fakeGoogleAuth.idTokenToReturn = null; // null represents user cancellation

      final result = await authProvider.signInWithGoogle();

      expect(result, isFalse);
      expect(authProvider.errorMessage, isNull);
      expect(authProvider.isLoading, isFalse);
      expect(authProvider.isAuthenticated, isFalse);
      expect(fakeAuthApi.lastIdTokenReceived, isNull);
    });

    test('2. Missing or blank ID token returns false with friendly error', () async {
      fakeGoogleAuth.idTokenToReturn = '   ';

      final result = await authProvider.signInWithGoogle();

      expect(result, isFalse);
      expect(authProvider.errorMessage, 'Google authentication did not provide an ID token. Please try again.');
      expect(authProvider.isLoading, isFalse);
      expect(authProvider.isAuthenticated, isFalse);
    });

    test('3. Successful Google authentication exchanges ID token and stores MediConnect session', () async {
      const googleToken = 'sample_google_jwt_id_token';
      fakeGoogleAuth.idTokenToReturn = googleToken;

      final testUser = UserModel(
        id: 'patient_google_123',
        fullName: 'Google Patient',
        email: 'google.patient@example.com',
        role: 'PATIENT',
        emailVerified: true,
        accountStatus: 'ACTIVE',
        authProviders: const ['GOOGLE'],
      );

      fakeAuthApi.sessionToReturn = AuthSession(
        message: 'Google authentication successful.',
        accessToken: 'mediconnect_access_jwt',
        refreshToken: 'mediconnect_refresh_jwt',
        expiresIn: 3600,
        user: testUser,
      );

      final result = await authProvider.signInWithGoogle();

      expect(result, isTrue);
      expect(fakeAuthApi.lastIdTokenReceived, googleToken);
      expect(authProvider.isAuthenticated, isTrue);
      expect(authProvider.user?.id, 'patient_google_123');
      expect(authProvider.user?.email, 'google.patient@example.com');
      expect(authProvider.errorMessage, isNull);

      // Verify tokens are stored in MediConnect secure storage
      expect(await storageService.getAccessToken(), 'mediconnect_access_jwt');
      expect(await storageService.getRefreshToken(), 'mediconnect_refresh_jwt');
    });

    test('4. Backend error (e.g. Account suspended) displays friendly backend message', () async {
      fakeGoogleAuth.idTokenToReturn = 'valid_id_token';
      fakeAuthApi.exceptionToThrow = const ApiException(
        message: 'Your account has been suspended. Please contact support.',
        statusCode: 403,
      );

      final result = await authProvider.signInWithGoogle();

      expect(result, isFalse);
      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.errorMessage, 'Your account has been suspended. Please contact support.');
    });

    test('5. Backend rejection of invalid Google token displays backend error message', () async {
      fakeGoogleAuth.idTokenToReturn = 'invalid_tampered_id_token';
      fakeAuthApi.exceptionToThrow = const ApiException(
        message: 'Invalid or expired Google token.',
        statusCode: 401,
      );

      final result = await authProvider.signInWithGoogle();

      expect(result, isFalse);
      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.errorMessage, 'Invalid or expired Google token.');
    });

    test('6. Google SDK error throws friendly Google Sign-In message', () async {
      fakeGoogleAuth.exceptionToThrow = const GoogleSignInException(
        code: GoogleSignInExceptionCode.unknownError,
        description: 'Internal platform error',
      );

      final result = await authProvider.signInWithGoogle();

      expect(result, isFalse);
      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.errorMessage, 'Google Sign-In could not be completed. Please try again.');
    });

    test('7. Logout revokes MediConnect refresh token, signs out of Google, and clears storage', () async {
      // First populate storage
      await storageService.saveTokens(
        accessToken: 'mediconnect_access',
        refreshToken: 'mediconnect_refresh',
      );

      await authProvider.logout();

      expect(fakeAuthApi.lastRevokedRefreshToken, 'mediconnect_refresh');
      expect(fakeGoogleAuth.signOutCalled, isTrue);
      expect(await storageService.getAccessToken(), isNull);
      expect(await storageService.getRefreshToken(), isNull);
      expect(authProvider.isAuthenticated, isFalse);
    });
  });
}
