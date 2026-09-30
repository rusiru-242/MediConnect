import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/doctor_application_status.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_application_status_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_home_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_registration_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:provider/provider.dart';

class MockDoctorAuthApiService extends AuthApiService {
  bool registerCalled = false;
  bool fetchStatusCalled = false;
  bool logoutCalled = false;
  DoctorApplicationStatus currentStatus = DoctorApplicationStatus(
    doctorId: 'DOC-123456',
    specialty: 'Cardiologist',
    verificationStatus: 'PENDING',
    submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
    rejectionReason: null,
  );

  @override
  Future<Map<String, dynamic>> registerDoctor({
    required String fullName,
    required String email,
    required String phone,
    required String password,
    required String specialty,
    required String medicalRegistrationNumber,
    required String qualifications,
    required String hospitalOrClinic,
    required int experienceYears,
    String? bio,
    required http.MultipartFile identityDocument,
    required http.MultipartFile medicalRegistrationDocument,
    required http.MultipartFile qualificationDocument,
  }) async {
    registerCalled = true;
    return {
      'message': 'Doctor registration successful. Verification OTP sent to email.',
      'email': email,
      'role': 'DOCTOR',
      'accountStatus': 'PENDING',
      'verificationStatus': 'PENDING',
    };
  }

  @override
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async {
    fetchStatusCalled = true;
    return currentStatus;
  }

  @override
  Future<void> logout(String refreshToken) async {
    logoutCalled = true;
  }
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  Widget buildTestApp({
    required Widget child,
    required AuthProvider authProvider,
  }) {
    return ChangeNotifierProvider<AuthProvider>.value(
      value: authProvider,
      child: MaterialApp(
        routes: {
          '/welcome': (context) => const WelcomeScreen(),
          '/login': (context) => const LoginScreen(),
          '/doctor/register': (context) => const DoctorRegistrationScreen(),
          '/doctor/application-status': (context) => const DoctorApplicationStatusScreen(),
          '/doctor/home': (context) => const DoctorHomeScreen(),
          '/patient/home': (context) => const Scaffold(body: Text('PatientHome')),
        },
        home: child,
      ),
    );
  }

  group('Doctor Flow UI Tests', () {
    testWidgets('TEST 11: WelcomeScreen contains Doctor Registration entry point',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      final authProvider = AuthProvider(authApiService: mockService);

      await tester.pumpWidget(buildTestApp(
        child: const WelcomeScreen(),
        authProvider: authProvider,
      ));

      expect(find.byKey(const Key('welcome_doctor_register_link')), findsOneWidget);
      expect(find.text('Register as a Doctor'), findsOneWidget);

      await tester.tap(find.byKey(const Key('welcome_doctor_register_link')));
      await tester.pumpAndSettle();

      expect(find.byType(DoctorRegistrationScreen), findsOneWidget);
      expect(find.text('Doctor Registration'), findsOneWidget);
      expect(find.text('Personal Information'), findsOneWidget);
    });

    testWidgets('TEST 11b: LoginScreen contains Doctor Registration entry point',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      final authProvider = AuthProvider(authApiService: mockService);

      await tester.pumpWidget(buildTestApp(
        child: const LoginScreen(),
        authProvider: authProvider,
      ));

      expect(find.byKey(const Key('login_doctor_register_link')), findsOneWidget);
      await tester.tap(find.byKey(const Key('login_doctor_register_link')));
      await tester.pumpAndSettle();

      expect(find.byType(DoctorRegistrationScreen), findsOneWidget);
      expect(find.text('Doctor Registration'), findsOneWidget);
    });

    testWidgets('TEST 12: DoctorRegistrationScreen required-field validation',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      final authProvider = AuthProvider(authApiService: mockService);

      await tester.pumpWidget(buildTestApp(
        child: const DoctorRegistrationScreen(),
        authProvider: authProvider,
      ));

      // Attempt to proceed without entering required Step 1 fields
      await tester.tap(find.byKey(const Key('doctor_reg_continue_button')));
      await tester.pumpAndSettle();

      expect(find.text('Full name is required.'), findsOneWidget);
      expect(find.text('Email address is required.'), findsOneWidget);
      expect(find.text('Phone number is required.'), findsOneWidget);
      expect(find.text('Password is required.'), findsOneWidget);
    });

    testWidgets('TEST 16: DoctorApplicationStatusScreen displays PENDING and Refresh Status works',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      mockService.currentStatus = DoctorApplicationStatus(
        doctorId: 'DOC-123456',
        specialty: 'Cardiologist',
        verificationStatus: 'PENDING',
        submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
        rejectionReason: null,
      );

      final authProvider = AuthProvider(authApiService: mockService);
      // Simulate doctor user logged in
      authProvider.setSessionForTesting(const AuthSession(
        message: 'Doctor authenticated',
        accessToken: 'access_doc_token',
        refreshToken: 'refresh_doc_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_1',
          fullName: 'Saman Perera',
          email: 'saman@doctor.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(buildTestApp(
        child: const DoctorApplicationStatusScreen(),
        authProvider: authProvider,
      ));

      await tester.pumpAndSettle();

      expect(find.text('Application Under Review'), findsOneWidget);
      expect(
        find.text('Your email has been verified and your doctor application has been submitted successfully.'),
        findsOneWidget,
      );
      expect(
        find.text('Our team will review your professional information and verification documents.'),
        findsOneWidget,
      );
      expect(find.text('Status: Pending'), findsOneWidget);
      expect(find.byKey(const Key('refresh_status_button')), findsOneWidget);

      // Tap refresh
      await tester.tap(find.byKey(const Key('refresh_status_button')));
      await tester.pumpAndSettle();

      expect(mockService.fetchStatusCalled, isTrue);
      expect(find.text('Status: Pending'), findsOneWidget);
    });

    testWidgets('TEST 17: DoctorApplicationStatusScreen displays REJECTED state when rejected',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      mockService.currentStatus = DoctorApplicationStatus(
        doctorId: 'DOC-654321',
        specialty: 'Pediatrician',
        verificationStatus: 'REJECTED',
        submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
        rejectionReason: 'SLMC Registration number could not be validated with the medical council.',
      );

      final authProvider = AuthProvider(authApiService: mockService);
      authProvider.setSessionForTesting(const AuthSession(
        message: 'Doctor authenticated',
        accessToken: 'access_doc_token',
        refreshToken: 'refresh_doc_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_2',
          fullName: 'Nimal Silva',
          email: 'nimal@doctor.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(buildTestApp(
        child: const DoctorApplicationStatusScreen(),
        authProvider: authProvider,
      ));

      await tester.pumpAndSettle();

      expect(find.text('Application Rejected'), findsOneWidget);
      expect(
        find.text('SLMC Registration number could not be validated with the medical council.'),
        findsOneWidget,
      );
      expect(find.text('Status: Rejected'), findsOneWidget);
    });

    testWidgets('TEST 18: DoctorApplicationStatusScreen logout clears session',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      final authProvider = AuthProvider(authApiService: mockService);
      authProvider.setSessionForTesting(const AuthSession(
        message: 'Doctor authenticated',
        accessToken: 'access_doc_token',
        refreshToken: 'refresh_doc_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_3',
          fullName: 'Anura Dias',
          email: 'anura@doctor.com',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(buildTestApp(
        child: const DoctorApplicationStatusScreen(),
        authProvider: authProvider,
      ));

      await tester.pumpAndSettle();
      expect(authProvider.isAuthenticated, isTrue);

      await tester.tap(find.byKey(const Key('status_logout_button')));
      await tester.pumpAndSettle();

      expect(authProvider.isAuthenticated, isFalse);
      expect(find.byType(WelcomeScreen), findsOneWidget);
    });
  });
}
