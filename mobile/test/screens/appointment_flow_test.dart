import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/doctor.dart';
import 'package:mediconnect/models/doctor_availability.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/doctor/doctor_appointment_detail_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_appointments_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_home_screen.dart';
import 'package:mediconnect/screens/patient/appointment_detail_screen.dart';
import 'package:mediconnect/screens/patient/booking_confirmation_screen.dart';
import 'package:mediconnect/screens/patient/doctor_detail_screen.dart';
import 'package:mediconnect/screens/patient/my_appointments_screen.dart';
import 'package:mediconnect/screens/patient/patient_home_screen.dart';
import 'package:mediconnect/services/appointment_service.dart';
import 'package:mediconnect/services/auth_api_service.dart';
import 'package:mediconnect/services/doctor_service.dart';
import 'package:provider/provider.dart';

// ---------------------------------------------------------------------------
// MOCKS
// ---------------------------------------------------------------------------

class MockAuthApiService extends AuthApiService {
  @override
  Future<void> logout([String? refreshToken]) async {}
}

class MockDoctorService extends DoctorService {
  final Doctor sampleDoctor = Doctor(
    doctorId: 'DR-TEST-001',
    fullName: 'Dr. Anne Wickramasinghe',
    specialty: 'Pediatrics',
    hospitalOrClinic: 'Lady Ridgeway Hospital',
    experienceYears: 10,
    bio: 'Experienced pediatrician.',
    qualifications: 'MBBS, DCH, MD',
    verificationStatus: 'APPROVED',
  );

  bool availabilityRefreshed = false;

  @override
  Future<Doctor> getDoctorDetail(String doctorId) async {
    return sampleDoctor;
  }

  @override
  Future<List<DayAvailabilitySlots>> getDoctorAvailability(
    String doctorId, {
    String? date,
  }) async {
    availabilityRefreshed = true;
    return [
      DayAvailabilitySlots(
        date: '2026-10-15',
        slots: [
          TimeSlot(
            startTime: '09:00',
            endTime: '09:30',
            availabilityId: 'AVAIL-01',
          ),
          TimeSlot(
            startTime: '09:30',
            endTime: '10:00',
            availabilityId: 'AVAIL-01',
          ),
        ],
      ),
    ];
  }
}

class MockAppointmentService extends AppointmentService {
  bool simulateConflict = false;
  List<Appointment> appointments = [];

  MockAppointmentService() {
    appointments = [
      Appointment(
        id: 'APPT-101',
        patientUserId: 'PAT-001',
        doctorUserId: 'DOC-USER-001',
        doctorProfileId: 'PROF-001',
        availabilityId: 'AVAIL-01',
        appointmentDate: '2026-10-15',
        startTime: '09:00',
        endTime: '09:30',
        status: 'PENDING',
        doctorName: 'Dr. Anne Wickramasinghe',
        specialty: 'Pediatrics',
        hospitalOrClinic: 'Lady Ridgeway Hospital',
        patientName: 'John Patient',
        patientNote: 'General checkup',
        createdAt: DateTime.now(),
      ),
      Appointment(
        id: 'APPT-102',
        patientUserId: 'PAT-001',
        doctorUserId: 'DOC-USER-001',
        doctorProfileId: 'PROF-001',
        availabilityId: 'AVAIL-01',
        appointmentDate: '2026-10-10',
        startTime: '10:00',
        endTime: '10:30',
        status: 'CONFIRMED',
        doctorName: 'Dr. Anne Wickramasinghe',
        specialty: 'Pediatrics',
        hospitalOrClinic: 'Lady Ridgeway Hospital',
        patientName: 'John Patient',
        createdAt: DateTime.now(),
      ),
    ];
  }

  @override
  Future<Appointment> createAppointment({
    required String doctorId,
    String? availabilityId,
    required String date,
    required String startTime,
    String? patientNote,
  }) async {
    if (simulateConflict) {
      throw const ConflictException(
        message: 'This time slot is no longer available.',
        statusCode: 409,
      );
    }

    final created = Appointment(
      id: 'APPT-${DateTime.now().millisecondsSinceEpoch}',
      patientUserId: 'PAT-001',
      doctorUserId: 'DOC-USER-001',
      doctorProfileId: 'PROF-001',
      availabilityId: availabilityId ?? 'AVAIL-01',
      appointmentDate: date,
      startTime: startTime,
      endTime: '09:30',
      status: 'PENDING',
      doctorName: 'Dr. Anne Wickramasinghe',
      specialty: 'Pediatrics',
      hospitalOrClinic: 'Lady Ridgeway Hospital',
      patientName: 'John Patient',
      patientNote: patientNote,
      createdAt: DateTime.now(),
    );
    appointments.add(created);
    return created;
  }

  @override
  Future<AppointmentListResponse> getMyAppointments({
    int page = 1,
    int limit = 20,
    String? status,
  }) async {
    var filtered = List<Appointment>.from(appointments);
    if (status != null && status.isNotEmpty && status.toUpperCase() != 'ALL') {
      filtered = filtered.where((a) => a.status == status.toUpperCase()).toList();
    }
    return AppointmentListResponse(
      items: filtered,
      page: page,
      limit: limit,
      total: filtered.length,
      totalPages: 1,
    );
  }

  @override
  Future<Appointment> getAppointmentDetail(String appointmentId) async {
    return appointments.firstWhere(
      (a) => a.id == appointmentId,
      orElse: () => appointments.first,
    );
  }

  @override
  Future<Appointment> cancelPatientAppointment(
    String appointmentId, {
    String? reason,
  }) async {
    final idx = appointments.indexWhere((a) => a.id == appointmentId);
    final existing = appointments[idx];
    final updated = Appointment(
      id: existing.id,
      patientUserId: existing.patientUserId,
      doctorUserId: existing.doctorUserId,
      doctorProfileId: existing.doctorProfileId,
      availabilityId: existing.availabilityId,
      appointmentDate: existing.appointmentDate,
      startTime: existing.startTime,
      endTime: existing.endTime,
      status: 'CANCELLED',
      cancelledBy: 'PATIENT',
      cancellationReason: reason,
      doctorName: existing.doctorName,
      specialty: existing.specialty,
      hospitalOrClinic: existing.hospitalOrClinic,
      patientName: existing.patientName,
      patientNote: existing.patientNote,
      createdAt: existing.createdAt,
      updatedAt: DateTime.now(),
    );
    appointments[idx] = updated;
    return updated;
  }

  @override
  Future<AppointmentListResponse> getDoctorAppointments({
    int page = 1,
    int limit = 20,
    String? date,
    String? status,
  }) async {
    var filtered = List<Appointment>.from(appointments);
    if (status != null && status.isNotEmpty && status.toUpperCase() != 'ALL') {
      filtered = filtered.where((a) => a.status == status.toUpperCase()).toList();
    }
    return AppointmentListResponse(
      items: filtered,
      page: page,
      limit: limit,
      total: filtered.length,
      totalPages: 1,
    );
  }

  @override
  Future<Appointment> confirmDoctorAppointment(String appointmentId) async {
    final idx = appointments.indexWhere((a) => a.id == appointmentId);
    final existing = appointments[idx];
    final updated = Appointment(
      id: existing.id,
      patientUserId: existing.patientUserId,
      doctorUserId: existing.doctorUserId,
      doctorProfileId: existing.doctorProfileId,
      availabilityId: existing.availabilityId,
      appointmentDate: existing.appointmentDate,
      startTime: existing.startTime,
      endTime: existing.endTime,
      status: 'CONFIRMED',
      doctorName: existing.doctorName,
      specialty: existing.specialty,
      hospitalOrClinic: existing.hospitalOrClinic,
      patientName: existing.patientName,
      patientNote: existing.patientNote,
      createdAt: existing.createdAt,
      updatedAt: DateTime.now(),
    );
    appointments[idx] = updated;
    return updated;
  }

  @override
  Future<Appointment> completeDoctorAppointment(String appointmentId) async {
    final idx = appointments.indexWhere((a) => a.id == appointmentId);
    final existing = appointments[idx];
    final updated = Appointment(
      id: existing.id,
      patientUserId: existing.patientUserId,
      doctorUserId: existing.doctorUserId,
      doctorProfileId: existing.doctorProfileId,
      availabilityId: existing.availabilityId,
      appointmentDate: existing.appointmentDate,
      startTime: existing.startTime,
      endTime: existing.endTime,
      status: 'COMPLETED',
      doctorName: existing.doctorName,
      specialty: existing.specialty,
      hospitalOrClinic: existing.hospitalOrClinic,
      patientName: existing.patientName,
      patientNote: existing.patientNote,
      createdAt: existing.createdAt,
      updatedAt: DateTime.now(),
    );
    appointments[idx] = updated;
    return updated;
  }

  @override
  Future<Appointment> cancelDoctorAppointment(
    String appointmentId, {
    String? reason,
  }) async {
    final idx = appointments.indexWhere((a) => a.id == appointmentId);
    final existing = appointments[idx];
    final updated = Appointment(
      id: existing.id,
      patientUserId: existing.patientUserId,
      doctorUserId: existing.doctorUserId,
      doctorProfileId: existing.doctorProfileId,
      availabilityId: existing.availabilityId,
      appointmentDate: existing.appointmentDate,
      startTime: existing.startTime,
      endTime: existing.endTime,
      status: 'CANCELLED',
      cancelledBy: 'DOCTOR',
      cancellationReason: reason,
      doctorName: existing.doctorName,
      specialty: existing.specialty,
      hospitalOrClinic: existing.hospitalOrClinic,
      patientName: existing.patientName,
      patientNote: existing.patientNote,
      createdAt: existing.createdAt,
      updatedAt: DateTime.now(),
    );
    appointments[idx] = updated;
    return updated;
  }
}

// ---------------------------------------------------------------------------
// TEST HELPER
// ---------------------------------------------------------------------------

Widget createTestApp({
  required Widget child,
  AuthProvider? authProvider,
}) {
  FlutterSecureStorage.setMockInitialValues({});
  return MultiProvider(
    providers: [
      ChangeNotifierProvider<AuthProvider>(
        create: (_) =>
            authProvider ?? AuthProvider(authApiService: MockAuthApiService()),
      ),
    ],
    child: MaterialApp(
      home: child,
      routes: {
        '/patient/home': (context) => const PatientHomeScreen(),
        '/patient/my-appointments': (context) => const MyAppointmentsScreen(),
        '/patient/appointment-detail': (context) =>
            const AppointmentDetailScreen(),
        '/doctor/home': (context) => const DoctorHomeScreen(),
        '/doctor/appointments': (context) => const DoctorAppointmentsScreen(),
        '/doctor/appointment-detail': (context) =>
            const DoctorAppointmentDetailScreen(),
      },
    ),
  );
}

// ---------------------------------------------------------------------------
// TESTS: TEST 18 to TEST 25
// ---------------------------------------------------------------------------

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // TEST 18: Patient selects available slot -> BookingConfirmationScreen
  testWidgets('TEST 18: Patient selects available slot and proceeds to BookingConfirmationScreen',
      (tester) async {
    final mockDoctorService = MockDoctorService();

    await tester.pumpWidget(createTestApp(
      child: DoctorDetailScreen(
        doctor: mockDoctorService.sampleDoctor,
        doctorService: mockDoctorService,
      ),
    ));
    await tester.pumpAndSettle();

    // Verify slots rendered
    expect(find.text('09:00 - 09:30'), findsOneWidget);

    // Scroll into view and select the 09:00 slot
    final slotChip = find.byKey(const Key('slot_chip_09:00'));
    await tester.ensureVisible(slotChip);
    await tester.pumpAndSettle();
    await tester.tap(slotChip);
    await tester.pumpAndSettle();

    // Verify continue button is enabled with selected slot
    expect(find.text('Continue to Booking (09:00)'), findsOneWidget);

    // Tap continue to booking button
    final bookButton = find.byKey(const Key('book_appointment_button'));
    await tester.ensureVisible(bookButton);
    await tester.pumpAndSettle();
    await tester.tap(bookButton);
    await tester.pumpAndSettle();

    // Expect BookingConfirmationScreen is displayed
    expect(find.byType(BookingConfirmationScreen), findsOneWidget);
    expect(find.text('Confirm Booking'), findsOneWidget);
    expect(find.text('Request Appointment'), findsOneWidget);
  });

  // TEST 19: Request appointment -> PENDING appointment created
  testWidgets('TEST 19: Request appointment creates PENDING appointment',
      (tester) async {
    final mockApptService = MockAppointmentService();
    final mockDoctorService = MockDoctorService();

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-15',
        slot: TimeSlot(
          startTime: '09:00',
          endTime: '09:30',
          availabilityId: 'AVAIL-01',
        ),
        appointmentService: mockApptService,
      ),
    ));
    await tester.pumpAndSettle();

    // Enter optional note
    await tester.enterText(
      find.byKey(const Key('booking_patient_note_input')),
      'Routine follow-up consultation',
    );

    // Tap Request Appointment
    await tester.tap(find.byKey(const Key('request_appointment_button')));
    await tester.pumpAndSettle();

    // Verify success feedback and navigation to detail screen
    expect(find.text('Appointment request submitted.'), findsOneWidget);
    expect(find.byType(AppointmentDetailScreen), findsOneWidget);
    expect(find.text('PENDING'), findsWidgets);
  });

  // TEST 20: Double-book conflict -> Friendly message + slots refresh
  testWidgets('TEST 20: Double-book conflict displays friendly 409 message',
      (tester) async {
    final mockApptService = MockAppointmentService();
    mockApptService.simulateConflict = true; // Simulate 409
    final mockDoctorService = MockDoctorService();

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-15',
        slot: TimeSlot(
          startTime: '09:00',
          endTime: '09:30',
          availabilityId: 'AVAIL-01',
        ),
        appointmentService: mockApptService,
      ),
    ));
    await tester.pumpAndSettle();

    // Tap Request Appointment
    await tester.tap(find.byKey(const Key('request_appointment_button')));
    await tester.pumpAndSettle();

    // Verify friendly 409 message displayed in dialog
    expect(find.text('Slot Unavailable'), findsOneWidget);
    expect(
      find.text('This time slot is no longer available.'),
      findsOneWidget,
    );

    // Tap Select Another Slot dialog action
    await tester.tap(find.text('Select Another Slot'));
    await tester.pumpAndSettle();
  });

  // TEST 21: My Appointments -> Appointment displayed
  testWidgets('TEST 21: My Appointments displays patient appointment list and cards',
      (tester) async {
    final mockApptService = MockAppointmentService();

    await tester.pumpWidget(createTestApp(
      child: MyAppointmentsScreen(appointmentService: mockApptService),
    ));
    await tester.pumpAndSettle();

    expect(find.text('My Appointments'), findsOneWidget);
    expect(find.text('Upcoming'), findsOneWidget);
    expect(find.text('Completed'), findsOneWidget);
    expect(find.text('Cancelled'), findsOneWidget);

    // Should display existing PENDING and CONFIRMED appointments under Upcoming
    expect(find.byKey(const Key('appointment_card_APPT-101')), findsOneWidget);
    expect(find.text('Dr. Anne Wickramasinghe'), findsWidgets);
    expect(find.text('PENDING'), findsOneWidget);
  });

  // TEST 22: Patient cancels -> Status updates
  testWidgets('TEST 22: Patient cancels appointment and status updates to CANCELLED',
      (tester) async {
    final mockApptService = MockAppointmentService();
    final appt = mockApptService.appointments.first; // PENDING appointment

    await tester.pumpWidget(createTestApp(
      child: AppointmentDetailScreen(
        appointment: appt,
        appointmentId: appt.id,
        appointmentService: mockApptService,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('PENDING'), findsOneWidget);
    expect(find.byKey(const Key('cancel_appointment_button')), findsOneWidget);

    // Tap Cancel Appointment
    await tester.tap(find.byKey(const Key('cancel_appointment_button')));
    await tester.pumpAndSettle();

    // Dialog pops up
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('cancellation_reason_input')),
      'Cannot attend due to work schedule.',
    );

    // Confirm cancel
    await tester.tap(find.byKey(const Key('confirm_cancel_button')));
    await tester.pumpAndSettle();

    // Verify status updated to CANCELLED
    expect(find.text('CANCELLED'), findsOneWidget);
    expect(find.text('Appointment has been cancelled.'), findsOneWidget);
    expect(find.text('Cancelled by PATIENT'), findsOneWidget);
  });

  // TEST 23: Doctor opens appointments -> Pending appointment visible
  testWidgets('TEST 23: Doctor opens appointments screen and sees pending appointment',
      (tester) async {
    final mockApptService = MockAppointmentService();

    await tester.pumpWidget(createTestApp(
      child: DoctorAppointmentsScreen(appointmentService: mockApptService),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Appointments'), findsOneWidget);
    expect(find.text('Pending'), findsOneWidget);

    // Pending appointment card visible
    expect(
      find.byKey(const Key('doctor_appointment_card_APPT-101')),
      findsOneWidget,
    );
    expect(find.text('John Patient'), findsWidgets);
    expect(find.text('PENDING'), findsOneWidget);
  });

  // TEST 24: Doctor confirms -> Appointment status becomes CONFIRMED
  testWidgets('TEST 24: Doctor confirms appointment and status becomes CONFIRMED',
      (tester) async {
    final mockApptService = MockAppointmentService();
    final appt = mockApptService.appointments.first; // PENDING

    await tester.pumpWidget(createTestApp(
      child: DoctorAppointmentDetailScreen(
        appointment: appt,
        appointmentId: appt.id,
        appointmentService: mockApptService,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('PENDING'), findsOneWidget);
    expect(find.byKey(const Key('doctor_confirm_button')), findsOneWidget);

    // Tap Confirm Appointment
    await tester.tap(find.byKey(const Key('doctor_confirm_button')));
    await tester.pumpAndSettle();

    // Confirm in dialog
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm_action_dialog_button')));
    await tester.pumpAndSettle();

    // Verify updated status
    expect(find.text('CONFIRMED'), findsOneWidget);
    expect(find.text('Appointment confirmed successfully.'), findsOneWidget);
  });

  // TEST 25: Doctor marks valid appointment completed -> COMPLETED
  testWidgets('TEST 25: Doctor marks confirmed appointment completed -> COMPLETED',
      (tester) async {
    final mockApptService = MockAppointmentService();
    final confirmedAppt = mockApptService.appointments[1]; // CONFIRMED

    await tester.pumpWidget(createTestApp(
      child: DoctorAppointmentDetailScreen(
        appointment: confirmedAppt,
        appointmentId: confirmedAppt.id,
        appointmentService: mockApptService,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('CONFIRMED'), findsOneWidget);
    expect(find.byKey(const Key('doctor_complete_button')), findsOneWidget);

    // Tap Complete Appointment
    await tester.tap(find.byKey(const Key('doctor_complete_button')));
    await tester.pumpAndSettle();

    // Dialog appears
    expect(find.text('Complete Consultation'), findsOneWidget);
    await tester.tap(find.byKey(const Key('complete_action_dialog_button')));
    await tester.pumpAndSettle();

    // Verify updated to COMPLETED
    expect(find.text('COMPLETED'), findsOneWidget);
    expect(find.text('Appointment marked as completed.'), findsOneWidget);
  });
}
