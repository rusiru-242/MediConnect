import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/google_auth_service.dart';
import 'package:provider/provider.dart';

class MockGoogleAuthService extends GoogleAuthService {
  String? tokenToReturn;
  bool throwException = false;

  @override
  Future<String?> authenticate({String? serverClientId}) async {
    if (throwException) {
      throw const GoogleSignInException(
        code: GoogleSignInExceptionCode.unknownError,
        description: 'SDK failure',
      );
    }
    return tokenToReturn;
  }
}

class MockAuthApiService extends AuthApiService {
  bool failBackend = false;

  @override
  Future<AuthSession> authenticateWithGoogle({required String idToken}) async {
    if (failBackend) {
      throw Exception('Backend failure');
    }
    return const AuthSession(
      message: 'Google authentication successful.',
      accessToken: 'access_123',
      refreshToken: 'refresh_123',
      expiresIn: 3600,
      user: UserModel(
        id: 'u_1',
        fullName: 'Google User',
        email: 'google@test.com',
        role: 'PATIENT',
        emailVerified: true,
        accountStatus: 'ACTIVE',
        authProviders: ['GOOGLE'],
      ),
    );
  }
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  Widget createTestWidget({
    required Widget child,
    required AuthProvider authProvider,
  }) {
    return ChangeNotifierProvider<AuthProvider>.value(
      value: authProvider,
      child: MaterialApp(
        routes: {
          '/patient/home': (context) => const Scaffold(body: Text('PatientHomeScreen')),
          '/register': (context) => const Scaffold(body: Text('RegisterScreen')),
          '/login': (context) => const Scaffold(body: Text('LoginScreenRoute')),
        },
        home: child,
      ),
    );
  }

  group('Google Sign-In UI Tests', () {
    testWidgets('WelcomeScreen: Continue with Google clean cancellation does not show snackbar',
        (tester) async {
      final mockGoogle = MockGoogleAuthService();
      mockGoogle.tokenToReturn = null; // Clean cancellation

      final authProvider = AuthProvider(
        authApiService: MockAuthApiService(),
        googleAuthService: mockGoogle,
      );

      await tester.pumpWidget(createTestWidget(
        child: const WelcomeScreen(),
        authProvider: authProvider,
      ));

      expect(find.byKey(const Key('welcome_google_button')), findsOneWidget);
      expect(find.text('Continue with Google'), findsOneWidget);

      await tester.tap(find.byKey(const Key('welcome_google_button')));
      await tester.pumpAndSettle();

      // No snackbar or error should be visible
      expect(find.byType(SnackBar), findsNothing);
      expect(find.text('PatientHomeScreen'), findsNothing);
    });

    testWidgets('WelcomeScreen: Continue with Google navigates to PatientHomeScreen on success',
        (tester) async {
      final mockGoogle = MockGoogleAuthService();
      mockGoogle.tokenToReturn = 'valid_google_token';

      final authProvider = AuthProvider(
        authApiService: MockAuthApiService(),
        googleAuthService: mockGoogle,
      );

      await tester.pumpWidget(createTestWidget(
        child: const WelcomeScreen(),
        authProvider: authProvider,
      ));

      await tester.tap(find.byKey(const Key('welcome_google_button')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('PatientHomeScreen'), findsOneWidget);
    });

    testWidgets('LoginScreen: Continue with Google button invokes Google Sign-In and navigates on success',
        (tester) async {
      final mockGoogle = MockGoogleAuthService();
      mockGoogle.tokenToReturn = 'valid_google_token';

      final authProvider = AuthProvider(
        authApiService: MockAuthApiService(),
        googleAuthService: mockGoogle,
      );

      await tester.pumpWidget(createTestWidget(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      expect(find.byKey(const Key('login_google_button')), findsOneWidget);

      await tester.tap(find.byKey(const Key('login_google_button')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('PatientHomeScreen'), findsOneWidget);
    });

    testWidgets('LoginScreen: Continue with Google cancellation does not display error banner',
        (tester) async {
      final mockGoogle = MockGoogleAuthService();
      mockGoogle.tokenToReturn = null; // Canceled

      final authProvider = AuthProvider(
        authApiService: MockAuthApiService(),
        googleAuthService: mockGoogle,
      );

      await tester.pumpWidget(createTestWidget(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      await tester.tap(find.byKey(const Key('login_google_button')));
      await tester.pumpAndSettle();

      expect(find.text('PatientHomeScreen'), findsNothing);
      expect(find.byIcon(Icons.error_outline_rounded), findsNothing);
    });

    testWidgets('WelcomeScreen: Continue with Google failure displays error snackbar',
        (tester) async {
      final mockGoogle = MockGoogleAuthService();
      mockGoogle.throwException = true; // Simulates Google SDK failure

      final authProvider = AuthProvider(
        authApiService: MockAuthApiService(),
        googleAuthService: mockGoogle,
      );

      await tester.pumpWidget(createTestWidget(
        child: const WelcomeScreen(),
        authProvider: authProvider,
      ));

      await tester.tap(find.byKey(const Key('welcome_google_button')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Google Sign-In could not be completed. Please try again.'), findsOneWidget);
    });

    testWidgets('LoginScreen: Continue with Google failure displays error banner',
        (tester) async {
      final mockGoogle = MockGoogleAuthService();
      mockGoogle.throwException = true; // Simulates Google SDK failure

      final authProvider = AuthProvider(
        authApiService: MockAuthApiService(),
        googleAuthService: mockGoogle,
      );

      await tester.pumpWidget(createTestWidget(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      await tester.tap(find.byKey(const Key('login_google_button')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
      expect(find.text('Google Sign-In could not be completed. Please try again.'), findsOneWidget);
    });
  });
}
