import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/admin_doctor_application.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/doctor_application_status.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/admin_provider.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/admin/admin_dashboard_screen.dart';
import 'package:mediconnect/screens/admin/doctor_application_detail_screen.dart';
import 'package:mediconnect/screens/admin/doctor_applications_screen.dart';
import 'package:mediconnect/screens/admin/document_viewer_screen.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_application_status_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_home_screen.dart';
import 'package:mediconnect/screens/welcome_screen.dart';
import 'package:mediconnect/services/admin_service.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:provider/provider.dart';

class MockAdminService extends AdminService {
  List<AdminDoctorApplicationSummary> pendingApps = [
    AdminDoctorApplicationSummary(
      doctorProfileId: 'prof_1',
      userId: 'u_1',
      fullName: 'Dr. Anne Perera',
      email: 'anne@mediconnect.lk',
      phone: '0771234567',
      specialty: 'Cardiologist',
      medicalRegistrationNumber: 'SLMC-1234',
      hospitalOrClinic: 'Colombo General Hospital',
      experienceYears: 10,
      verificationStatus: 'PENDING',
      submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
    ),
    AdminDoctorApplicationSummary(
      doctorProfileId: 'prof_2',
      userId: 'u_2',
      fullName: 'Dr. Ben Silva',
      email: 'ben@mediconnect.lk',
      phone: '0777654321',
      specialty: 'Dermatologist',
      medicalRegistrationNumber: 'SLMC-5678',
      hospitalOrClinic: 'Asiri Hospital',
      experienceYears: 5,
      verificationStatus: 'PENDING',
      submittedAt: DateTime.parse('2026-09-30T11:00:00Z'),
    ),
  ];

  AdminDoctorApplicationDetail detailApp1 = AdminDoctorApplicationDetail(
    doctorProfileId: 'prof_1',
    userId: 'u_1',
    fullName: 'Dr. Anne Perera',
    email: 'anne@mediconnect.lk',
    phone: '0771234567',
    specialty: 'Cardiologist',
    medicalRegistrationNumber: 'SLMC-1234',
    qualifications: 'MBBS, MD Cardiology',
    hospitalOrClinic: 'Colombo General Hospital',
    experienceYears: 10,
    bio: 'Experienced heart specialist.',
    verificationStatus: 'PENDING',
    rejectionReason: null,
    submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
    verifiedAt: null,
    verifiedBy: null,
    documents: const [
      AdminDoctorDocumentMetadata(
        documentKey: 'identityDocument',
        title: 'Identity Document',
        filename: 'nic_copy.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 1024 * 50,
      ),
      AdminDoctorDocumentMetadata(
        documentKey: 'medicalRegistrationDocument',
        title: 'Medical Registration Document',
        filename: 'slmc_cert.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 1024 * 120,
      ),
      AdminDoctorDocumentMetadata(
        documentKey: 'qualificationDocument',
        title: 'Qualification Document',
        filename: 'mbbs_degree.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 1024 * 200,
      ),
    ],
  );

  bool approveCalled = false;
  bool rejectCalled = false;
  String? lastRejectReason;

  @override
  Future<List<AdminDoctorApplicationSummary>> getDoctorApplications({String? status}) async {
    if (status == 'APPROVED') return [];
    if (status == 'REJECTED') return [];
    return pendingApps;
  }

  @override
  Future<AdminDoctorApplicationDetail> getDoctorApplicationDetail(String doctorProfileId) async {
    return detailApp1;
  }

  @override
  Future<List<int>> getDoctorDocumentBytes(String doctorProfileId, String documentKey) async {
    return [0x25, 0x50, 0x44, 0x46, 0x2D, 0x31, 0x2E, 0x34]; // %PDF-1.4
  }

  @override
  Future<String> approveDoctor(String doctorProfileId) async {
    approveCalled = true;
    detailApp1 = AdminDoctorApplicationDetail(
      doctorProfileId: detailApp1.doctorProfileId,
      userId: detailApp1.userId,
      fullName: detailApp1.fullName,
      email: detailApp1.email,
      phone: detailApp1.phone,
      specialty: detailApp1.specialty,
      medicalRegistrationNumber: detailApp1.medicalRegistrationNumber,
      qualifications: detailApp1.qualifications,
      hospitalOrClinic: detailApp1.hospitalOrClinic,
      experienceYears: detailApp1.experienceYears,
      bio: detailApp1.bio,
      verificationStatus: 'APPROVED',
      rejectionReason: null,
      submittedAt: detailApp1.submittedAt,
      verifiedAt: DateTime.now(),
      verifiedBy: 'admin_1',
      documents: detailApp1.documents,
    );
    return 'Doctor application approved successfully.';
  }

  @override
  Future<String> rejectDoctor(String doctorProfileId, String reason) async {
    rejectCalled = true;
    lastRejectReason = reason;
    detailApp1 = AdminDoctorApplicationDetail(
      doctorProfileId: detailApp1.doctorProfileId,
      userId: detailApp1.userId,
      fullName: detailApp1.fullName,
      email: detailApp1.email,
      phone: detailApp1.phone,
      specialty: detailApp1.specialty,
      medicalRegistrationNumber: detailApp1.medicalRegistrationNumber,
      qualifications: detailApp1.qualifications,
      hospitalOrClinic: detailApp1.hospitalOrClinic,
      experienceYears: detailApp1.experienceYears,
      bio: detailApp1.bio,
      verificationStatus: 'REJECTED',
      rejectionReason: reason,
      submittedAt: detailApp1.submittedAt,
      verifiedAt: DateTime.now(),
      verifiedBy: 'admin_1',
      documents: detailApp1.documents,
    );
    return 'Doctor application rejected.';
  }
}

class MockAdminAuthApiService extends AuthApiService {
  AuthSession? sessionToReturn;
  DoctorApplicationStatus statusToReturn = DoctorApplicationStatus(
    doctorId: 'DOC-1234',
    specialty: 'Cardiologist',
    verificationStatus: 'PENDING',
    submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
    rejectionReason: null,
  );

  @override
  Future<AuthSession> login({required String email, required String password}) async {
    return sessionToReturn!;
  }

  @override
  Future<void> logout(String refreshToken) async {}

  @override
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async {
    return statusToReturn;
  }
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  Widget createAdminTestWidget({
    required Widget child,
    required AuthProvider authProvider,
    required AdminProvider adminProvider,
  }) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
        ChangeNotifierProvider<AdminProvider>.value(value: adminProvider),
      ],
      child: MaterialApp(
        routes: {
          '/welcome': (context) => const WelcomeScreen(),
          '/login': (context) => const LoginScreen(),
          '/patient/home': (context) => const Scaffold(body: Text('PatientHome')),
          '/doctor/application-status': (context) => const DoctorApplicationStatusScreen(),
          '/doctor/home': (context) => const DoctorHomeScreen(),
          '/admin/dashboard': (context) => const AdminDashboardScreen(),
          '/admin/doctor-applications': (context) => const DoctorApplicationsScreen(),
        },
        home: child,
      ),
    );
  }

  group('Admin Doctor Verification UI Tests', () {
    testWidgets('TEST 16: Login as admin routes to AdminDashboardScreen',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockAdminAuthApiService();
      mockAuthApi.sessionToReturn = const AuthSession(
        message: 'Admin login successful',
        accessToken: 'admin_access_token',
        refreshToken: 'admin_refresh_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'admin_1',
          fullName: 'Super Administrator',
          email: 'admin@mediconnect.lk',
          role: 'ADMIN',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          authProviders: ['LOCAL'],
        ),
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);
      final adminProvider = AdminProvider(adminService: MockAdminService());

      await tester.pumpWidget(createAdminTestWidget(
        child: const LoginScreen(),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      // Enter login credentials
      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'admin@mediconnect.lk',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'AdminPassword@123',
      );

      await tester.tap(find.byKey(const Key('login_submit_button')));
      await tester.pumpAndSettle();

      // Expected: AdminDashboardScreen loaded
      expect(find.byType(AdminDashboardScreen), findsOneWidget);
      expect(find.text('MediConnect Admin'), findsOneWidget);
      expect(find.text('Super Administrator'), findsOneWidget);
    });

    testWidgets('TEST 17: Open Doctor Applications displays pending applications',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAdmin = MockAdminService();
      final adminProvider = AdminProvider(adminService: mockAdmin);
      final authProvider = AuthProvider();

      await tester.pumpWidget(createAdminTestWidget(
        child: const AdminDashboardScreen(),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();

      // Tap "View Doctor Applications"
      expect(find.byKey(const Key('open_doctor_applications_button')), findsOneWidget);
      await tester.tap(find.byKey(const Key('open_doctor_applications_button')));
      await tester.pumpAndSettle();

      expect(find.byType(DoctorApplicationsScreen), findsOneWidget);
      expect(find.text('Dr. Anne Perera'), findsOneWidget);
      expect(find.text('Dr. Ben Silva'), findsOneWidget);
      expect(find.text('SLMC: SLMC-1234'), findsOneWidget);
    });

    testWidgets('TEST 18: Open application displays professional details',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAdmin = MockAdminService();
      final adminProvider = AdminProvider(adminService: mockAdmin);
      final authProvider = AuthProvider();

      await tester.pumpWidget(createAdminTestWidget(
        child: const DoctorApplicationsScreen(),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();

      // Tap on Dr. Anne Perera's card
      await tester.tap(find.byKey(const Key('doctor_app_card_prof_1')));
      await tester.pumpAndSettle();

      expect(find.byType(DoctorApplicationDetailScreen), findsOneWidget);
      expect(find.text('Personal Information'), findsOneWidget);
      expect(find.text('Professional Information'), findsOneWidget);
      expect(find.text('Verification Documents'), findsOneWidget);
      expect(find.text('SLMC-1234'), findsOneWidget);
      expect(find.text('MBBS, MD Cardiology'), findsOneWidget);
      expect(find.byKey(const Key('approve_doctor_button')), findsOneWidget);
      expect(find.byKey(const Key('reject_doctor_button')), findsOneWidget);
    });

    testWidgets('TEST 19: View verification document securely opens DocumentViewerScreen',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAdmin = MockAdminService();
      final adminProvider = AdminProvider(adminService: mockAdmin);
      final authProvider = AuthProvider();

      await tester.pumpWidget(createAdminTestWidget(
        child: const DoctorApplicationDetailScreen(doctorProfileId: 'prof_1'),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();

      await tester.ensureVisible(find.byKey(const Key('view_doc_identityDocument')));
      expect(find.byKey(const Key('view_doc_identityDocument')), findsOneWidget);
      await tester.tap(find.byKey(const Key('view_doc_identityDocument')));
      await tester.pumpAndSettle();

      expect(find.byType(DocumentViewerScreen), findsOneWidget);
      expect(find.text('Identity Document'), findsWidgets);
      expect(find.text('File: nic_copy.pdf'), findsOneWidget);
    });

    testWidgets('TEST 20: Approve application prompts confirmation dialog and succeeds',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAdmin = MockAdminService();
      final adminProvider = AdminProvider(adminService: mockAdmin);
      final authProvider = AuthProvider();

      await tester.pumpWidget(createAdminTestWidget(
        child: const DoctorApplicationDetailScreen(doctorProfileId: 'prof_1'),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();

      // Scroll to approve button and tap
      await tester.ensureVisible(find.byKey(const Key('approve_doctor_button')));
      await tester.tap(find.byKey(const Key('approve_doctor_button')));
      await tester.pumpAndSettle();

      // Confirmation dialog must appear
      expect(find.text('Approve Doctor?'), findsOneWidget);
      expect(find.text('Approve'), findsOneWidget);

      // Confirm approval
      await tester.tap(find.text('Approve'));
      await tester.pumpAndSettle();

      expect(mockAdmin.approveCalled, isTrue);
      expect(find.text('Doctor application approved successfully.'), findsOneWidget);
    });

    testWidgets('TEST 21: Reject application requires reason and confirms rejection',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAdmin = MockAdminService();
      final adminProvider = AdminProvider(adminService: mockAdmin);
      final authProvider = AuthProvider();

      await tester.pumpWidget(createAdminTestWidget(
        child: const DoctorApplicationDetailScreen(doctorProfileId: 'prof_1'),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();

      // Scroll to reject button and tap
      await tester.ensureVisible(find.byKey(const Key('reject_doctor_button')));
      await tester.tap(find.byKey(const Key('reject_doctor_button')));
      await tester.pumpAndSettle();

      expect(find.text('Reject Application'), findsWidgets);
      expect(find.byKey(const Key('reject_reason_input')), findsOneWidget);

      // Tap confirm without reason -> validation error
      await tester.tap(find.byKey(const Key('confirm_reject_button')));
      await tester.pumpAndSettle();

      expect(find.text('A reason for rejection is required.'), findsOneWidget);
      expect(mockAdmin.rejectCalled, isFalse);

      // Enter valid reason
      await tester.enterText(
        find.byKey(const Key('reject_reason_input')),
        'SLMC registration certificate is expired.',
      );
      await tester.tap(find.byKey(const Key('confirm_reject_button')));
      await tester.pumpAndSettle();

      expect(mockAdmin.rejectCalled, isTrue);
      expect(mockAdmin.lastRejectReason, 'SLMC registration certificate is expired.');
      expect(find.text('Doctor application rejected.'), findsOneWidget);
    });

    testWidgets('TEST 22: Refresh status as approved doctor routes to DoctorHomeScreen placeholder',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockAdminAuthApiService();
      mockAuthApi.statusToReturn = DoctorApplicationStatus(
        doctorId: 'DOC-1234',
        specialty: 'Cardiologist',
        verificationStatus: 'PENDING',
        submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
        rejectionReason: null,
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);
      final adminProvider = AdminProvider(adminService: MockAdminService());

      authProvider.setSessionForTesting(const AuthSession(
        message: 'Doctor authenticated',
        accessToken: 'access_doc_token',
        refreshToken: 'refresh_doc_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_1',
          fullName: 'Alice Perera',
          email: 'alice@mediconnect.lk',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(createAdminTestWidget(
        child: const DoctorApplicationStatusScreen(),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();
      expect(find.text('Application Under Review'), findsOneWidget);

      // Backend admin has now approved the doctor application
      mockAuthApi.statusToReturn = DoctorApplicationStatus(
        doctorId: 'DOC-1234',
        specialty: 'Cardiologist',
        verificationStatus: 'APPROVED',
        submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
        rejectionReason: null,
      );

      // Refresh status -> navigates to DoctorHomeScreen
      expect(find.byKey(const Key('refresh_status_button')), findsOneWidget);
      await tester.tap(find.byKey(const Key('refresh_status_button')));
      await tester.pumpAndSettle();

      expect(find.byType(DoctorHomeScreen), findsOneWidget);
      expect(find.text('Doctor Portal'), findsOneWidget);
    });

    testWidgets('TEST 23: Rejected doctor sees Application Rejected and reason',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final mockAuthApi = MockAdminAuthApiService();
      mockAuthApi.statusToReturn = DoctorApplicationStatus(
        doctorId: 'DOC-2',
        specialty: 'Dermatologist',
        verificationStatus: 'REJECTED',
        submittedAt: DateTime.parse('2026-09-30T10:00:00Z'),
        rejectionReason: 'Invalid medical degree credentials.',
      );

      final authProvider = AuthProvider(authApiService: mockAuthApi);
      final adminProvider = AdminProvider(adminService: MockAdminService());

      authProvider.setSessionForTesting(const AuthSession(
        message: 'Doctor authenticated',
        accessToken: 'access_doc_token',
        refreshToken: 'refresh_doc_token',
        expiresIn: 3600,
        user: UserModel(
          id: 'doc_2',
          fullName: 'Charlie Silva',
          email: 'charlie@mediconnect.lk',
          role: 'DOCTOR',
          emailVerified: true,
          accountStatus: 'PENDING',
          authProviders: ['LOCAL'],
        ),
      ));

      await tester.pumpWidget(createAdminTestWidget(
        child: const DoctorApplicationStatusScreen(),
        authProvider: authProvider,
        adminProvider: adminProvider,
      ));

      await tester.pumpAndSettle();

      expect(find.text('Application Rejected'), findsOneWidget);
      expect(find.text('Invalid medical degree credentials.'), findsOneWidget);
      expect(find.text('Status: Rejected'), findsOneWidget);
    });
  });
}
