import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/storage/secure_storage_service.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/doctor_application_status.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/admin_access_blocked_screen.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/google_auth_service.dart';
import 'package:provider/provider.dart';

class MockPhase32AuthApiService extends Fake implements AuthApiService {
  AuthSession? loginSessionToReturn;
  UserModel? currentUserToReturn;
  DoctorApplicationStatus? doctorStatusToReturn;
  bool shouldThrowAuthException = false;

  @override
  Future<AuthSession> login({required String email, required String password}) async {
    if (loginSessionToReturn != null) {
      return loginSessionToReturn!;
    }
    throw Exception('Invalid credentials');
  }

  @override
  Future<AuthSession> authenticateWithGoogle({required String idToken}) async {
    if (loginSessionToReturn != null) {
      return loginSessionToReturn!;
    }
    throw Exception('Google auth failed');
  }

  @override
  Future<UserModel> getCurrentUser() async {
    if (shouldThrowAuthException) {
      throw Exception('Unauthenticated');
    }
    if (currentUserToReturn != null) {
      return currentUserToReturn!;
    }
    throw Exception('User not found');
  }

  @override
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async {
    return doctorStatusToReturn ??
        DoctorApplicationStatus(
          doctorId: 'doc_mock_1',
          specialty: 'Cardiology',
          verificationStatus: 'APPROVED',
          submittedAt: DateTime.now(),
        );
  }
}

class MockPhase32GoogleAuthService extends Fake implements GoogleAuthService {
  String? idTokenToReturn;
  @override
  Future<String?> authenticate({String? serverClientId}) async => idTokenToReturn;
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  Widget createTestApp({
    required Widget child,
    required AuthProvider authProvider,
  }) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
      ],
      child: MaterialApp(
        onGenerateRoute: (settings) {
          if (settings.name != null && settings.name!.startsWith('/admin')) {
            return MaterialPageRoute(
              builder: (context) => const AdminAccessBlockedScreen(),
              settings: settings,
            );
          }
          return null;
        },
        routes: {
          '/welcome': (context) => const WelcomeScreen(),
          '/login': (context) => const LoginScreen(),
          '/patient/home': (context) => const Scaffold(body: Text('PatientHomeScreenView')),
          '/doctor/application-status': (context) => const Scaffold(body: Text('DoctorApplicationStatusView')),
          '/doctor/home': (context) => const Scaffold(body: Text('DoctorHomeScreenView')),
        },
        home: child,
      ),
    );
  }

  group('Phase 32: Mobile Role Restrictions & Web-Only Admin Migration Tests', () {
    testWidgets('1. Admin mobile login rejection displays exact notice and clears tokens',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockPhase32AuthApiService();
      mockAuthApi.loginSessionToReturn = const AuthSession(
        message: 'Login successful',
        accessToken: 'admin_test_jwt_token',
        refreshToken: 'admin_test_refresh_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'admin_001',
          fullName: 'MediConnect Administrator',
          email: 'admin@mediconnect.lk',
          role: 'ADMIN',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);

      await tester.pumpWidget(createTestApp(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'admin@mediconnect.lk',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'AdminSecurePassword@123',
      );

      await tester.tap(find.byKey(const Key('login_submit_button')));
      await tester.pumpAndSettle();

      // Verified: Session rejected, not authenticated
      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.user, isNull);

      // Verified: Clear rejection error banner displayed
      const expectedMessage =
          'Admin accounts are supported on the MediConnect Web Admin Portal. Please sign in through the web portal.';
      expect(find.text(expectedMessage), findsOneWidget);
      expect(authProvider.errorMessage, expectedMessage);

      // Verified: Tokens were not stored in secure storage
      final storageService = SecureStorageService();
      final storedToken = await storageService.getAccessToken();
      expect(storedToken, isNull);
    });

    testWidgets('2. Admin session restoration rejection wipes storage and navigates to welcome',
        (tester) async {
      final mockAuthApi = MockPhase32AuthApiService();
      mockAuthApi.currentUserToReturn = const UserModel(
        id: 'admin_002',
        fullName: 'System Administrator',
        email: 'sysadmin@mediconnect.lk',
        role: 'ADMIN',
        emailVerified: true,
        accountStatus: 'ACTIVE',
        authProviders: ['LOCAL'],
      );

      final storageService = SecureStorageService();
      await storageService.saveTokens(
        accessToken: 'stale_admin_token',
        refreshToken: 'stale_admin_refresh',
      );

      final authProvider = AuthProvider(
        authApiService: mockAuthApi,
        storageService: storageService,
      );

      await authProvider.checkAuthSession();

      // Verified: Admin session rejected during restoration
      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.user, isNull);
      expect(
        authProvider.errorMessage,
        'Admin accounts are supported on the MediConnect Web Admin Portal. Please sign in through the web portal.',
      );

      // Verified: Secure storage cleared
      final tokenAfter = await storageService.getAccessToken();
      expect(tokenAfter, isNull);
    });

    testWidgets('3. Deep-link to /admin route intercepts and loads AdminAccessBlockedScreen',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final authProvider = AuthProvider(authApiService: MockPhase32AuthApiService());

      late BuildContext capturedContext;
      await tester.pumpWidget(createTestApp(
        child: Builder(
          builder: (context) {
            capturedContext = context;
            return const Scaffold(body: Text('InitialScreen'));
          },
        ),
        authProvider: authProvider,
      ));

      // Attempt navigation to /admin/dashboard
      Navigator.of(capturedContext).pushNamed('/admin/dashboard');
      await tester.pumpAndSettle();

      // Verified: Intercepted by route guard
      expect(find.byType(AdminAccessBlockedScreen), findsOneWidget);
      expect(find.text('Web Portal Only'), findsOneWidget);
      expect(
        find.text(
          'Admin accounts are supported on the MediConnect Web Admin Portal. Please sign in through the web portal.',
        ),
        findsOneWidget,
      );

      // Tap return to login button
      await tester.tap(find.byKey(const Key('admin_blocked_back_to_login_button')));
      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('4. Patient login routes correctly to PatientHomeScreen',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockPhase32AuthApiService();
      mockAuthApi.loginSessionToReturn = const AuthSession(
        message: 'Login successful',
        accessToken: 'patient_jwt_token',
        refreshToken: 'patient_refresh_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'pat_001',
          fullName: 'Kasun Perera',
          email: 'kasun@test.com',
          role: 'PATIENT',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);

      await tester.pumpWidget(createTestApp(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'kasun@test.com',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'PatientPassword@123',
      );

      await tester.tap(find.byKey(const Key('login_submit_button')));
      await tester.pumpAndSettle();

      expect(authProvider.isAuthenticated, isTrue);
      expect(authProvider.user?.role, 'PATIENT');
      expect(find.text('PatientHomeScreenView'), findsOneWidget);
    });

    testWidgets('5. Doctor login routes correctly to DoctorHomeScreen when approved',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockPhase32AuthApiService();
      mockAuthApi.loginSessionToReturn = const AuthSession(
        message: 'Login successful',
        accessToken: 'doctor_jwt_token',
        refreshToken: 'doctor_refresh_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_001',
          fullName: 'Dr. Anne Silva',
          email: 'anne@test.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      );
      mockAuthApi.doctorStatusToReturn = DoctorApplicationStatus(
        doctorId: 'doc_001',
        specialty: 'Cardiology',
        verificationStatus: 'APPROVED',
        submittedAt: DateTime.now(),
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);

      await tester.pumpWidget(createTestApp(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'anne@test.com',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'DoctorPassword@123',
      );

      await tester.tap(find.byKey(const Key('login_submit_button')));
      await tester.pumpAndSettle();

      expect(authProvider.isAuthenticated, isTrue);
      expect(authProvider.user?.role, 'DOCTOR');
      expect(find.text('DoctorHomeScreenView'), findsOneWidget);
    });

    testWidgets('6. Doctor login routes to application status when verification is pending',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockPhase32AuthApiService();
      mockAuthApi.loginSessionToReturn = const AuthSession(
        message: 'Login successful',
        accessToken: 'doctor_pending_jwt_token',
        refreshToken: 'doctor_pending_refresh_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_002',
          fullName: 'Dr. Ben Silva',
          email: 'ben@test.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING_VERIFICATION',
          authProviders: ['LOCAL'],
        ),
      );
      mockAuthApi.doctorStatusToReturn = DoctorApplicationStatus(
        doctorId: 'doc_002',
        specialty: 'Dermatology',
        verificationStatus: 'PENDING',
        submittedAt: DateTime.now(),
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);

      await tester.pumpWidget(createTestApp(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'ben@test.com',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'DoctorPassword@123',
      );

      await tester.tap(find.byKey(const Key('login_submit_button')));
      await tester.pumpAndSettle();

      expect(authProvider.isAuthenticated, isTrue);
      expect(authProvider.user?.role, 'DOCTOR');
      expect(find.text('DoctorApplicationStatusView'), findsOneWidget);
    });

    testWidgets('7. Logout clears user profile and tokens securely',
        (tester) async {
      final mockAuthApi = MockPhase32AuthApiService();
      final storageService = SecureStorageService();
      await storageService.saveTokens(
        accessToken: 'active_token',
        refreshToken: 'active_refresh',
      );

      final authProvider = AuthProvider(
        authApiService: mockAuthApi,
        storageService: storageService,
      );

      authProvider.setSessionForTesting(const AuthSession(
        message: 'Session active',
        accessToken: 'active_token',
        refreshToken: 'active_refresh',
        expiresIn: 3600,
        user: UserModel(
          id: 'user_123',
          fullName: 'Test User',
          email: 'test@user.com',
          role: 'PATIENT',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      ));

      expect(authProvider.isAuthenticated, isTrue);

      await authProvider.logout();

      expect(authProvider.isAuthenticated, isFalse);
      expect(authProvider.user, isNull);

      final tokenAfter = await storageService.getAccessToken();
      expect(tokenAfter, isNull);
    });
  });
}
