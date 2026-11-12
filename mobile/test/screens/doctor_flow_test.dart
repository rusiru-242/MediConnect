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
import 'package:mediconnect/screens/doctor/doctor_application_submitted_screen.dart';
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
        find.text('Your doctor application has been submitted successfully and is currently under administrative review.'),
        findsOneWidget,
      );
      expect(
        find.text('Our medical administration team is reviewing your professional information and verification documents. Once approved, you will receive an approval email with your registration details and portal login link.'),
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
    testWidgets('TEST 19: DoctorApplicationSubmittedScreen displays waiting notice, submitted details and login navigation',
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
        child: const DoctorApplicationSubmittedScreen(
          fullName: 'Kamal Perera',
          email: 'kamal.p@doctor.lk',
          phone: '0771234567',
          specialty: 'Cardiologist',
          medicalRegistrationNumber: 'SLMC-987654',
          hospitalOrClinic: 'Colombo National Hospital',
          autoRedirect: false,
        ),
        authProvider: authProvider,
      ));

      await tester.pumpAndSettle();

      expect(find.text('Thank You for Your Application!'), findsOneWidget);
      expect(find.text('Application Submitted Successfully!'), findsOneWidget);
      expect(
        find.text('Your doctor registration application has been submitted successfully. Our admin team will review your details. You will be notified once your application is approved.'),
        findsOneWidget,
      );
      expect(find.text('Awaiting Administrative Review'), findsOneWidget);
      expect(find.text('Pending Review'), findsOneWidget);
      expect(find.text('Dr. Kamal Perera'), findsOneWidget);
      expect(find.text('kamal.p@doctor.lk'), findsOneWidget);
      expect(find.text('SLMC-987654'), findsOneWidget);
      expect(find.text('Cardiologist'), findsOneWidget);
      expect(find.text('Colombo National Hospital'), findsOneWidget);
      expect(find.byKey(const Key('submitted_back_to_login_button')), findsOneWidget);
      expect(find.byKey(const Key('submitted_back_to_home_button')), findsOneWidget);

      // Scroll and tap Back to Login
      await tester.ensureVisible(find.byKey(const Key('submitted_back_to_login_button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('submitted_back_to_login_button')));
      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('TEST 20: DoctorApplicationSubmittedScreen automatically redirects to Login screen after delay',
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
        child: const DoctorApplicationSubmittedScreen(
          fullName: 'Nimali Senanayake',
          email: 'nimali@doctor.lk',
          phone: '0779876543',
          specialty: 'Dermatologist',
          medicalRegistrationNumber: 'SLMC-123456',
          hospitalOrClinic: 'Kandy National Hospital',
          redirectDelay: Duration(seconds: 3),
        ),
        authProvider: authProvider,
      ));

      expect(find.byType(DoctorApplicationSubmittedScreen), findsOneWidget);
      expect(find.text('Thank You for Your Application!'), findsOneWidget);

      // Advance clock past the 3-second redirect delay
      await tester.pump(const Duration(seconds: 1));
      await tester.pump(const Duration(seconds: 1));
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();

      // Verified redirect to Login screen
      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('TEST 21: DoctorHomeScreen intercepts pending doctor and redirects to Application Status screen',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockService = MockDoctorAuthApiService();
      mockService.currentStatus = DoctorApplicationStatus(
        doctorId: 'DOC-999999',
        specialty: 'Surgeon',
        verificationStatus: 'PENDING',
        submittedAt: DateTime.parse('2026-10-01T10:00:00Z'),
        rejectionReason: null,
      );

      final authProvider = AuthProvider(authApiService: mockService);
      authProvider.setSessionForTesting(const AuthSession(
        message: 'Doctor authenticated',
        accessToken: 'access_doc_token',
        refreshToken: 'refresh_doc_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_pending',
          fullName: 'Kasun Bandara',
          email: 'kasun@doctor.lk',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(buildTestApp(
        child: const DoctorHomeScreen(),
        authProvider: authProvider,
      ));

      await tester.pumpAndSettle();

      // Guard redirects pending doctor away from DoctorHomeScreen to status screen
      expect(find.byType(DoctorApplicationStatusScreen), findsOneWidget);
      expect(find.text('Your doctor registration is pending admin approval.'), findsAtLeastNWidgets(1));
    });
  });
}
