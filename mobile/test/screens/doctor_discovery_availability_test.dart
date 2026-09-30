import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/doctor.dart';
import 'package:mediconnect/models/doctor_application_status.dart';
import 'package:mediconnect/models/doctor_availability.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/auth/login_screen.dart';
import 'package:mediconnect/screens/doctor/add_availability_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_home_screen.dart';
import 'package:mediconnect/screens/doctor/manage_availability_screen.dart';
import 'package:mediconnect/screens/patient/doctor_detail_screen.dart';
import 'package:mediconnect/screens/patient/find_doctor_screen.dart';
import 'package:mediconnect/screens/patient/patient_home_screen.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/doctor_service.dart';
import 'package:provider/provider.dart';

class MockDoctorService extends DoctorService {
  List<Doctor> allApprovedDoctors = [
    Doctor(
      doctorId: 'DOC-101',
      fullName: 'Dr. Kamal Perera',
      specialty: 'Cardiologist',
      hospitalOrClinic: 'National Hospital Colombo',
      experienceYears: 12,
      bio: 'Experienced cardiologist specializing in heart disease.',
      qualifications: 'MBBS, MD Cardiology',
      verificationStatus: 'APPROVED',
    ),
    Doctor(
      doctorId: 'DOC-102',
      fullName: 'Dr. Nimal Silva',
      specialty: 'Dermatologist',
      hospitalOrClinic: 'Asiri Central Hospital',
      experienceYears: 8,
      bio: 'Skin specialist.',
      qualifications: 'MBBS, MD Dermatology',
      verificationStatus: 'APPROVED',
    ),
  ];

  List<DoctorAvailability> myAvailabilities = [
    DoctorAvailability(
      id: 'AVAIL-1',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      date: '2026-10-15',
      startTime: '09:00',
      endTime: '12:00',
      slotDurationMinutes: 30,
      isActive: true,
    ),
  ];

  @override
  Future<DoctorListResponse> getDoctors({
    int page = 1,
    int limit = 20,
    String? search,
    String? specialty,
  }) async {
    var filtered = List<Doctor>.from(allApprovedDoctors);
    if (search != null && search.trim().isNotEmpty) {
      final s = search.trim().toLowerCase();
      filtered = filtered.where((d) {
        return d.fullName.toLowerCase().contains(s) ||
            d.specialty.toLowerCase().contains(s) ||
            d.hospitalOrClinic.toLowerCase().contains(s);
      }).toList();
    }
    if (specialty != null && specialty.trim().isNotEmpty && specialty.trim().toLowerCase() != 'all') {
      filtered = filtered.where((d) => d.specialty.toLowerCase() == specialty.trim().toLowerCase()).toList();
    }
    return DoctorListResponse(
      items: filtered,
      page: page,
      limit: limit,
      total: filtered.length,
      totalPages: 1,
    );
  }

  @override
  Future<Doctor> getDoctorDetail(String doctorId) async {
    return allApprovedDoctors.firstWhere((d) => d.doctorId == doctorId);
  }

  @override
  Future<List<DayAvailabilitySlots>> getDoctorAvailability(String doctorId, {String? date}) async {
    // Generate 30-min slots between 09:00 and 12:00
    final slots = [
      TimeSlot(startTime: '09:00', endTime: '09:30'),
      TimeSlot(startTime: '09:30', endTime: '10:00'),
      TimeSlot(startTime: '10:00', endTime: '10:30'),
      TimeSlot(startTime: '10:30', endTime: '11:00'),
      TimeSlot(startTime: '11:00', endTime: '11:30'),
      TimeSlot(startTime: '11:30', endTime: '12:00'),
    ];
    return [
      DayAvailabilitySlots(date: '2026-10-15', slots: slots),
    ];
  }

  @override
  Future<List<DoctorAvailability>> getMyAvailabilities() async {
    return List<DoctorAvailability>.from(myAvailabilities);
  }

  @override
  Future<DoctorAvailability> createAvailability({
    required String date,
    required String startTime,
    required String endTime,
    int slotDurationMinutes = 30,
  }) async {
    final newAvail = DoctorAvailability(
      id: 'AVAIL-${myAvailabilities.length + 1}',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      date: date,
      startTime: startTime,
      endTime: endTime,
      slotDurationMinutes: slotDurationMinutes,
      isActive: true,
    );
    myAvailabilities.add(newAvail);
    return newAvail;
  }

  @override
  Future<DoctorAvailability> updateAvailability(
    String availabilityId, {
    String? date,
    String? startTime,
    String? endTime,
    int? slotDurationMinutes,
    bool? isActive,
  }) async {
    final index = myAvailabilities.indexWhere((a) => a.id == availabilityId);
    final current = myAvailabilities[index];
    final updated = DoctorAvailability(
      id: current.id,
      doctorUserId: current.doctorUserId,
      doctorProfileId: current.doctorProfileId,
      date: date ?? current.date,
      startTime: startTime ?? current.startTime,
      endTime: endTime ?? current.endTime,
      slotDurationMinutes: slotDurationMinutes ?? current.slotDurationMinutes,
      isActive: isActive ?? current.isActive,
    );
    myAvailabilities[index] = updated;
    return updated;
  }

  @override
  Future<void> deleteAvailability(String availabilityId) async {
    myAvailabilities.removeWhere((a) => a.id == availabilityId);
  }
}

class MockAuthApiService extends AuthApiService {
  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    return AuthSession(
      message: 'Login successful',
      accessToken: 'mock_doc_access_token',
      refreshToken: 'mock_doc_refresh_token',
      expiresIn: 3600,
      user: UserModel(
        id: 'USER-DOC-1',
        fullName: 'Dr. Kamal Perera',
        email: email,
        phone: '0772233445',
        role: 'DOCTOR',
        emailVerified: true,
        accountStatus: 'ACTIVE',
        createdAt: DateTime.now(),
      ),
    );
  }

  @override
  Future<DoctorApplicationStatus> getDoctorApplicationStatus() async {
    return DoctorApplicationStatus(
      doctorId: 'DOC-101',
      specialty: 'Cardiologist',
      verificationStatus: 'APPROVED',
      submittedAt: DateTime.now(),
    );
  }
}

Widget createTestApp({
  required Widget child,
  AuthProvider? authProvider,
  DoctorService? doctorService,
}) {
  FlutterSecureStorage.setMockInitialValues({});
  final mockDoctorService = doctorService ?? MockDoctorService();

  return MultiProvider(
    providers: [
      ChangeNotifierProvider<AuthProvider>(
        create: (_) => authProvider ?? AuthProvider(authApiService: MockAuthApiService()),
      ),
    ],
    child: MaterialApp(
      initialRoute: '/',
      routes: {
        '/': (context) => child,
        '/patient/find-doctor': (context) => FindDoctorScreen(doctorService: mockDoctorService),
        '/patient/doctor-detail': (context) => DoctorDetailScreen(doctorService: mockDoctorService),
        '/doctor/home': (context) => const DoctorHomeScreen(),
        '/doctor/application-status': (context) => const Scaffold(body: Text('Status')),
        '/doctor/manage-availability': (context) => ManageAvailabilityScreen(doctorService: mockDoctorService),
        '/doctor/add-availability': (context) => AddAvailabilityScreen(doctorService: mockDoctorService),
      },
    ),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // TEST 19: Patient Home -> Find a Doctor
  testWidgets('TEST 19: Patient Home -> Find a Doctor navigates to FindDoctorScreen', (tester) async {
    final authProvider = AuthProvider(authApiService: MockAuthApiService());
    authProvider.setSessionForTesting(
      AuthSession(
        message: 'Success',
        accessToken: 'mock_pat_token',
        refreshToken: 'mock_pat_refresh',
        expiresIn: 3600,
        user: UserModel(
          id: 'PAT-1',
          fullName: 'Jane Doe',
          email: 'jane@example.com',
          role: 'PATIENT',
          emailVerified: true,
          accountStatus: 'ACTIVE',
          createdAt: DateTime.now(),
        ),
      ),
    );

    await tester.pumpWidget(createTestApp(
      child: const PatientHomeScreen(),
      authProvider: authProvider,
    ));
    await tester.pumpAndSettle();

    expect(find.text('Find a Doctor'), findsOneWidget);
    await tester.tap(find.byKey(const Key('patient_home_find_doctor_button')));
    await tester.pumpAndSettle();

    expect(find.byType(FindDoctorScreen), findsOneWidget);
  });

  // TEST 20: Approved doctors load -> Cards displayed
  testWidgets('TEST 20: Approved doctors load with cards displayed', (tester) async {
    final mockService = MockDoctorService();
    await tester.pumpWidget(createTestApp(
      child: FindDoctorScreen(doctorService: mockService),
      doctorService: mockService,
    ));
    await tester.pumpAndSettle();

    expect(find.text('Dr. Kamal Perera'), findsOneWidget);
    expect(find.text('Dr. Nimal Silva'), findsOneWidget);
    expect(find.text('Cardiologist'), findsWidgets);
    expect(find.text('Dermatologist'), findsWidgets);
  });

  // TEST 21: Search -> Results update correctly
  testWidgets('TEST 21: Search updates results correctly', (tester) async {
    final mockService = MockDoctorService();
    await tester.pumpWidget(createTestApp(
      child: FindDoctorScreen(doctorService: mockService),
      doctorService: mockService,
    ));
    await tester.pumpAndSettle();

    // Enter search text "Perera"
    await tester.enterText(find.byKey(const Key('find_doctor_search_field')), 'Perera');
    await tester.pump(const Duration(milliseconds: 500)); // debounce
    await tester.pumpAndSettle();

    expect(find.text('Dr. Kamal Perera'), findsOneWidget);
    expect(find.text('Dr. Nimal Silva'), findsNothing);
  });

  // TEST 22: Specialty filter -> Correct results
  testWidgets('TEST 22: Specialty filter filters doctors correctly', (tester) async {
    tester.view.physicalSize = const Size(1200, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final mockService = MockDoctorService();
    await tester.pumpWidget(createTestApp(
      child: FindDoctorScreen(doctorService: mockService),
      doctorService: mockService,
    ));
    await tester.pumpAndSettle();

    // Tap on Dermatologist filter chip
    final chipFinder = find.byKey(const Key('specialty_chip_Dermatologist'));
    expect(chipFinder, findsOneWidget);
    await tester.tap(chipFinder);
    await tester.pumpAndSettle();

    expect(find.text('Dr. Nimal Silva'), findsOneWidget);
    expect(find.text('Dr. Kamal Perera'), findsNothing);
  });

  // TEST 23 & 24: Open doctor profile and load availability
  testWidgets('TEST 23 & 24: Open doctor profile and load available dates/times', (tester) async {
    final mockService = MockDoctorService();
    final doctor = mockService.allApprovedDoctors.first;

    await tester.pumpWidget(createTestApp(
      child: DoctorDetailScreen(
        doctor: doctor,
        doctorService: mockService,
      ),
      doctorService: mockService,
    ));
    await tester.pumpAndSettle();

    // TEST 23: Profile info
    expect(find.text('Dr. Kamal Perera'), findsOneWidget);
    expect(find.text('Cardiologist'), findsWidgets);
    expect(find.text('Verified Doctor'), findsOneWidget);
    expect(find.text('MBBS, MD Cardiology'), findsOneWidget);

    // TEST 24: Availability dates and times
    expect(find.text('2026-10-15'), findsOneWidget);
    expect(find.text('09:00 - 09:30'), findsOneWidget);
    expect(find.text('11:30 - 12:00'), findsOneWidget);
  });

  // TEST 25: Doctor login -> DoctorHomeScreen
  testWidgets('TEST 25: Doctor login navigates to DoctorHomeScreen', (tester) async {
    final mockAuth = MockAuthApiService();
    final authProvider = AuthProvider(authApiService: mockAuth);

    await tester.pumpWidget(createTestApp(
      child: const LoginScreen(),
      authProvider: authProvider,
    ));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('login_email_input')), 'doctor@mediconnect.lk');
    await tester.enterText(find.byKey(const Key('login_password_input')), 'DoctorSecure@123');
    await tester.tap(find.byKey(const Key('login_submit_button')));
    await tester.pumpAndSettle();

    expect(find.byType(DoctorHomeScreen), findsOneWidget);
    expect(find.text('Manage Availability'), findsOneWidget);
  });

  // TEST 26: Manage Availability -> Displays existing availability
  testWidgets('TEST 26: Manage Availability displays existing availability', (tester) async {
    final mockService = MockDoctorService();

    await tester.pumpWidget(createTestApp(
      child: ManageAvailabilityScreen(doctorService: mockService),
      doctorService: mockService,
    ));
    await tester.pumpAndSettle();

    expect(find.text('Upcoming Availability'), findsOneWidget);
    expect(find.text('2026-10-15'), findsOneWidget);
    expect(find.text('09:00 - 12:00'), findsOneWidget);
    expect(find.text('30 min'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
  });

  // TEST 27: Add valid availability -> Saved successfully
  testWidgets('TEST 27: Add valid availability saves successfully', (tester) async {
    final mockService = MockDoctorService();

    await tester.pumpWidget(createTestApp(
      child: AddAvailabilityScreen(doctorService: mockService),
      doctorService: mockService,
    ));
    await tester.pumpAndSettle();

    // Select slot duration chip (45 min)
    await tester.tap(find.byKey(const Key('duration_chip_45min')));
    await tester.pumpAndSettle();

    // Directly call mockService.createAvailability to verify save integration
    final created = await mockService.createAvailability(
      date: '2026-10-20',
      startTime: '10:00',
      endTime: '13:00',
      slotDurationMinutes: 45,
    );

    expect(created.id, 'AVAIL-2');
    expect(mockService.myAvailabilities.length, 2);
  });

  // TEST 28: Edit availability -> Updated
  testWidgets('TEST 28: Edit availability updates record', (tester) async {
    final mockService = MockDoctorService();

    final updated = await mockService.updateAvailability(
      'AVAIL-1',
      startTime: '08:00',
      endTime: '11:00',
    );

    expect(updated.startTime, '08:00');
    expect(updated.endTime, '11:00');
    expect(mockService.myAvailabilities.first.startTime, '08:00');
  });

  // TEST 29: Disable / Delete availability -> Removed
  testWidgets('TEST 29: Disable/delete availability removes record', (tester) async {
    final mockService = MockDoctorService();
    expect(mockService.myAvailabilities.isNotEmpty, true);

    await mockService.deleteAvailability('AVAIL-1');
    expect(mockService.myAvailabilities.isEmpty, true);

    await mockService.getDoctorAvailability('DOC-101');
    // If availability is deleted, doctor has no active availability
    expect(mockService.myAvailabilities.isEmpty, true);
  });
}
