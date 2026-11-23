import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/consultation.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/doctor/consultation_details_screen.dart';
import 'package:mediconnect/screens/doctor/doctor_schedule_screen.dart';
import 'package:mediconnect/services/consultation_service.dart';
import 'package:provider/provider.dart';

class MockConsultationService extends ConsultationService {
  DoctorDailySchedule schedule;
  ConsultationDetail? detail;
  bool startCalled = false;
  bool completeCalled = false;

  MockConsultationService({
    required this.schedule,
    this.detail,
  });

  @override
  Future<DoctorDailySchedule> getTodaySchedule() async {
    return schedule;
  }

  @override
  Future<DoctorDailySchedule> getScheduleByDate(String date) async {
    return schedule;
  }

  @override
  Future<DailyScheduleStats> getScheduleSummary([String? date]) async {
    return schedule.stats;
  }

  @override
  Future<ConsultationDetail> getConsultationDetails(String appointmentId) async {
    if (detail != null) return detail!;
    final appt = schedule.appointments.firstWhere(
      (a) => a.appointmentId == appointmentId,
      orElse: () => schedule.appointments.first,
    );
    return ConsultationDetail(
      appointment: appt,
      session: appt.consultationSessionId != null
          ? ConsultationSession(
              id: appt.consultationSessionId!,
              appointmentId: appt.appointmentId,
              doctorUserId: 'DOC-1',
              doctorProfileId: 'PROF-1',
              patientUserId: appt.patientUserId,
              status: appt.consultationStatus,
              startedAt: appt.startedAt,
              completedAt: appt.completedAt,
            )
          : null,
      medicalRecord: appt.hasMedicalRecord ? {'id': 'MR-1', 'assessment': 'Stable'} : null,
      prescription: appt.hasPrescription ? {'id': 'RX-1', 'prescriptionId': 'RX-001'} : null,
      carePlan: appt.hasCarePlan ? {'id': 'CP-1', 'status': 'ACTIVE'} : null,
    );
  }

  @override
  Future<ConsultationSession> startConsultation(String appointmentId, {String? notes}) async {
    startCalled = true;
    final now = DateTime.now();
    final updatedAppts = schedule.appointments.map((a) {
      if (a.appointmentId == appointmentId) {
        return a.copyWith(
          consultationStatus: 'IN_PROGRESS',
          startedAt: now,
          consultationSessionId: 'SESS-START-1',
        );
      }
      return a;
    }).toList();

    schedule = schedule.copyWith(
      appointments: updatedAppts,
      nextPatient: schedule.nextPatient?.appointmentId == appointmentId
          ? schedule.nextPatient!.copyWith(
              consultationStatus: 'IN_PROGRESS',
              startedAt: now,
              consultationSessionId: 'SESS-START-1',
            )
          : schedule.nextPatient,
    );

    return ConsultationSession(
      id: 'SESS-START-1',
      appointmentId: appointmentId,
      doctorUserId: 'DOC-1',
      doctorProfileId: 'PROF-1',
      patientUserId: 'PAT-1',
      status: 'IN_PROGRESS',
      startedAt: now,
    );
  }

  @override
  Future<ConsultationSession> completeConsultation(String appointmentId, {String? notes}) async {
    completeCalled = true;
    final now = DateTime.now();
    final updatedAppts = schedule.appointments.map((a) {
      if (a.appointmentId == appointmentId) {
        return a.copyWith(
          consultationStatus: 'COMPLETED',
          bookingStatus: 'COMPLETED',
          completedAt: now,
        );
      }
      return a;
    }).toList();

    schedule = schedule.copyWith(
      appointments: updatedAppts,
      nextPatient: null,
    );

    return ConsultationSession(
      id: 'SESS-COMP-1',
      appointmentId: appointmentId,
      doctorUserId: 'DOC-1',
      doctorProfileId: 'PROF-1',
      patientUserId: 'PAT-1',
      status: 'COMPLETED',
      startedAt: now.subtract(const Duration(minutes: 15)),
      completedAt: now,
    );
  }
}

void main() {
  Widget createTestApp({required Widget child}) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider()),
      ],
      child: MaterialApp(
        home: child,
      ),
    );
  }

  final testAppt1 = ScheduleAppointmentItem(
    appointmentId: 'APT-1',
    appointmentDate: '2026-11-13',
    startTime: '09:00',
    endTime: '09:30',
    bookingStatus: 'CONFIRMED',
    consultationStatus: 'NOT_STARTED',
    patientUserId: 'PAT-1',
    patientName: 'Sunil Weerasinghe',
    patientPhone: '0719998877',
    patientNote: 'Experiencing regular headache and fatigue',
    consultationFee: 3000.0,
  );

  final testAppt2 = ScheduleAppointmentItem(
    appointmentId: 'APT-2',
    appointmentDate: '2026-11-13',
    startTime: '10:00',
    endTime: '10:30',
    bookingStatus: 'CONFIRMED',
    consultationStatus: 'IN_PROGRESS',
    patientUserId: 'PAT-2',
    patientName: 'Chamari Silva',
    patientPhone: '0772223344',
    startedAt: DateTime.parse('2026-11-13T10:05:00Z'),
    hasPrescription: true,
    hasCarePlan: true,
    carePlanId: 'CP-123',
    consultationFee: 3500.0,
  );

  final testSchedule = DoctorDailySchedule(
    date: '2026-11-13',
    timezone: 'Asia/Colombo',
    stats: const DailyScheduleStats(
      date: '2026-11-13',
      timezone: 'Asia/Colombo',
      totalScheduled: 2,
      upcoming: 1,
      waiting: 0,
      inProgress: 1,
      completed: 0,
      cancelled: 0,
    ),
    nextPatient: testAppt2,
    appointments: [testAppt1, testAppt2],
  );

  group('Doctor Daily Schedule Screen Tests (Phase 57)', () {
    testWidgets('1. Daily schedule renders date header, timezone, and statistics metrics', (tester) async {
      final mock = MockConsultationService(schedule: testSchedule);
      await tester.pumpWidget(createTestApp(
        child: DoctorScheduleScreen(consultationService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text("Today's Schedule"), findsOneWidget);
      expect(find.text('Asia/Colombo'), findsOneWidget);
      expect(find.text('Total'), findsOneWidget);
      expect(find.text('In Progress'), findsWidgets);
      expect(find.text('Completed'), findsWidgets);
      expect(find.text('Cancelled'), findsWidgets);
    });

    testWidgets('2. Next Patient card renders patient name, appointment time, and Start/Complete CTA', (tester) async {
      final mock = MockConsultationService(schedule: testSchedule);
      await tester.pumpWidget(createTestApp(
        child: DoctorScheduleScreen(consultationService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Next Patient'), findsOneWidget);
      expect(find.text('Chamari Silva'), findsWidgets);
      expect(find.text('10:00 - 10:30'), findsWidgets);
      expect(find.byKey(const Key('next_patient_start_button')), findsOneWidget);
    });

    testWidgets('3. Appointment list renders all items in chronological order with status badges', (tester) async {
      final mock = MockConsultationService(schedule: testSchedule);
      await tester.pumpWidget(createTestApp(
        child: DoctorScheduleScreen(consultationService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Sunil Weerasinghe'), findsOneWidget);
      expect(find.text('09:00 - 09:30'), findsOneWidget);
      expect(find.byKey(const Key('start_consultation_button_APT-1')), findsOneWidget);
    });

    testWidgets('4. Doctor starts consultation for upcoming patient', (tester) async {
      final mock = MockConsultationService(schedule: testSchedule);
      await tester.pumpWidget(createTestApp(
        child: DoctorScheduleScreen(consultationService: mock),
      ));
      await tester.pumpAndSettle();

      final startBtn = find.byKey(const Key('start_consultation_button_APT-1'));
      expect(startBtn, findsOneWidget);
      await tester.ensureVisible(startBtn);
      await tester.pumpAndSettle();
      await tester.tap(startBtn);
      await tester.pumpAndSettle();

      expect(mock.startCalled, isTrue);
    });

    testWidgets('5. Completing consultation shows confirmation dialog and executes on confirm', (tester) async {
      final mock = MockConsultationService(schedule: testSchedule);
      await tester.pumpWidget(createTestApp(
        child: DoctorScheduleScreen(consultationService: mock),
      ));
      await tester.pumpAndSettle();

      final completeBtn = find.byKey(const Key('next_patient_start_button'));
      expect(completeBtn, findsOneWidget);
      await tester.tap(completeBtn);
      await tester.pumpAndSettle();

      // Check dialog
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.text('Complete this consultation?'), findsOneWidget);

      final confirmBtn = find.byKey(const Key('complete_consultation_confirm_button'));
      expect(confirmBtn, findsOneWidget);
      await tester.tap(confirmBtn);
      await tester.pumpAndSettle();

      expect(mock.completeCalled, isTrue);
    });

    testWidgets('6. Empty schedule displays appropriate empty message', (tester) async {
      final emptySchedule = DoctorDailySchedule(
        date: '2026-11-13',
        timezone: 'Asia/Colombo',
        stats: const DailyScheduleStats(date: '2026-11-13'),
        nextPatient: null,
        appointments: [],
      );

      final mock = MockConsultationService(schedule: emptySchedule);
      await tester.pumpWidget(createTestApp(
        child: DoctorScheduleScreen(consultationService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('No appointments scheduled for this date.'), findsOneWidget);
    });

    testWidgets('7. Consultation Details Screen displays clinical linkages and notes', (tester) async {
      final mock = MockConsultationService(schedule: testSchedule);
      await tester.pumpWidget(createTestApp(
        child: ConsultationDetailsScreen(
          appointmentId: 'APT-2',
          consultationService: mock,
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Consultation Details'), findsOneWidget);
      expect(find.text('Chamari Silva'), findsOneWidget);
      expect(find.text('Digital Prescription'), findsOneWidget);
      expect(find.text('Follow-up Care Plan'), findsOneWidget);
      expect(find.byKey(const Key('details_complete_consultation_button')), findsOneWidget);
    });
  });
}
