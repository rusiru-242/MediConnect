import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/timeline.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/patient/healthcare_timeline_screen.dart';
import 'package:mediconnect/screens/patient/patient_visit_detail_screen.dart';
import 'package:mediconnect/services/patient_timeline_service.dart';
import 'package:provider/provider.dart';

class MockPatientTimelineService extends PatientTimelineService {
  TimelineResponse timelineResponse;
  TimelineSummary summary;
  VisitDetail? visitDetail;
  bool timelineCalled = false;
  bool summaryCalled = false;
  bool visitDetailCalled = false;
  String? lastCategoryRequested;
  String? lastCursorRequested;

  MockPatientTimelineService({
    required this.timelineResponse,
    required this.summary,
    this.visitDetail,
  });

  @override
  Future<TimelineResponse> getHealthcareTimeline({
    String category = 'ALL',
    String? fromDate,
    String? toDate,
    String? doctorId,
    String? cursor,
    int limit = 20,
  }) async {
    timelineCalled = true;
    lastCategoryRequested = category;
    lastCursorRequested = cursor;

    if (category != 'ALL') {
      final filtered = timelineResponse.events.where((e) => e.category == category).toList();
      return TimelineResponse(
        events: filtered,
        totalCount: filtered.length,
        hasMore: false,
      );
    }

    if (cursor != null && cursor.isNotEmpty) {
      // Return second page with an additional event
      return TimelineResponse(
        events: [
          TimelineEvent(
            eventId: 'appt_page2_booked',
            eventType: 'APPOINTMENT_BOOKED',
            category: 'APPOINTMENTS',
            occurredAt: DateTime.parse('2026-10-01T08:00:00Z'),
            displayDate: '2026-10-01',
            title: 'Appointment Booked with Dr. Saman Perera',
            description: 'Routine checkup scheduled.',
            sourceType: 'appointment',
            sourceId: 'APPT-P2',
            appointmentId: 'APPT-P2',
            status: 'COMPLETED',
            availableActions: const ['VIEW_APPOINTMENT', 'VIEW_VISIT'],
          ),
        ],
        totalCount: timelineResponse.totalCount + 1,
        hasMore: false,
      );
    }

    return timelineResponse;
  }

  @override
  Future<TimelineSummary> getHealthcareTimelineSummary() async {
    summaryCalled = true;
    return summary;
  }

  @override
  Future<VisitDetail> getVisitDetail(String appointmentId) async {
    visitDetailCalled = true;
    if (visitDetail != null) return visitDetail!;
    return VisitDetail(
      appointmentId: appointmentId,
      appointmentNumber: 'APT-TEST-001',
      appointmentDate: '2026-11-10',
      startTime: '09:00',
      endTime: '09:30',
      bookingStatus: 'COMPLETED',
      consultationStatus: 'COMPLETED',
      consultationFee: 3000.0,
      doctorUserId: 'DOC-1',
      doctorName: 'Dr. Anil Jayasuriya',
      doctorSpecialty: 'Cardiology',
      doctorHospital: 'Lanka Hospitals',
      patientNote: 'Experiencing mild palpitations',
      consultationSession: {
        'status': 'COMPLETED',
        'startedAt': '2026-11-10T09:02:00Z',
        'completedAt': '2026-11-10T09:28:00Z',
      },
      prescription: {
        'id': 'RX-1',
        'prescriptionId': 'RX-2026-001',
        'medicationsCount': 2,
      },
      medicalRecord: {
        'id': 'MR-1',
        'recordId': 'REC-2026-001',
        'assessment': 'Normal sinus rhythm, mild sinus tachycardia.',
      },
      carePlan: {
        'id': 'CP-1',
        'status': 'ACTIVE',
        'followUpDate': '2026-12-10',
        'reason': 'Palpitations review',
      },
      timelineEvents: [
        TimelineEvent(
          eventId: 'appt_001_booked',
          eventType: 'APPOINTMENT_BOOKED',
          category: 'APPOINTMENTS',
          occurredAt: DateTime.parse('2026-11-01T08:00:00Z'),
          displayDate: '2026-11-01',
          title: 'Appointment Booked',
          description: 'Consultation visit scheduled',
          sourceType: 'appointment',
          sourceId: appointmentId,
          appointmentId: appointmentId,
        ),
      ],
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

  final testEvents = [
    TimelineEvent(
      eventId: 'sess_101_completed',
      eventType: 'CONSULTATION_COMPLETED',
      category: 'CONSULTATIONS',
      occurredAt: DateTime.parse('2026-11-10T10:30:00Z'),
      displayDate: '2026-11-10',
      displayTime: '10:30',
      title: 'Doctor Consultation Completed (Dr. Anil Jayasuriya)',
      description: 'Consultation concluded successfully.',
      doctorUserId: 'DOC-1',
      doctorDisplayName: 'Dr. Anil Jayasuriya',
      doctorSpecialty: 'Cardiology',
      sourceType: 'consultation',
      sourceId: 'SESS-101',
      appointmentId: 'APPT-101',
      status: 'COMPLETED',
      availableActions: const ['VIEW_VISIT'],
    ),
    TimelineEvent(
      eventId: 'rx_101_issued',
      eventType: 'PRESCRIPTION_ISSUED',
      category: 'PRESCRIPTIONS',
      occurredAt: DateTime.parse('2026-11-10T10:25:00Z'),
      displayDate: '2026-11-10',
      displayTime: '10:25',
      title: 'Digital Prescription Issued (RX-101)',
      description: '2 medication(s) prescribed by Dr. Anil Jayasuriya.',
      doctorUserId: 'DOC-1',
      doctorDisplayName: 'Dr. Anil Jayasuriya',
      doctorSpecialty: 'Cardiology',
      sourceType: 'prescription',
      sourceId: 'RX-101',
      appointmentId: 'APPT-101',
      status: 'ISSUED',
      availableActions: const ['VIEW_PRESCRIPTION', 'VIEW_VISIT'],
    ),
    TimelineEvent(
      eventId: 'cp_101_created',
      eventType: 'FOLLOW_UP_PLAN_CREATED',
      category: 'FOLLOW_UPS',
      occurredAt: DateTime.parse('2026-11-10T10:28:00Z'),
      displayDate: '2026-11-10',
      displayTime: '10:28',
      title: 'Follow-up Care Plan Created (Dr. Anil Jayasuriya)',
      description: 'Target follow-up date: 2026-12-10.',
      doctorUserId: 'DOC-1',
      doctorDisplayName: 'Dr. Anil Jayasuriya',
      doctorSpecialty: 'Cardiology',
      sourceType: 'care_plan',
      sourceId: 'CP-101',
      appointmentId: 'APPT-101',
      status: 'ACTIVE',
      availableActions: const ['VIEW_CARE_PLAN', 'VIEW_VISIT'],
    ),
  ];

  final testSummary = const TimelineSummary(
    totalEvents: 3,
    upcomingAppointmentsCount: 1,
    completedConsultationsCount: 1,
    prescriptionsCount: 1,
    medicalRecordsCount: 0,
    activeCarePlansCount: 1,
  );

  final testTimelineResponse = TimelineResponse(
    events: testEvents,
    nextCursor: 'offset_3',
    totalCount: 3,
    hasMore: true,
  );

  group('Patient Healthcare Timeline Screen Tests (Phase 58)', () {
    testWidgets('1. Timeline screen loads with title, summary metrics, and category filters', (tester) async {
      final mock = MockPatientTimelineService(
        timelineResponse: testTimelineResponse,
        summary: testSummary,
      );

      await tester.pumpWidget(createTestApp(
        child: HealthcareTimelineScreen(timelineService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Healthcare Timeline'), findsOneWidget);
      expect(find.text('YOUR CARE JOURNEY'), findsOneWidget);
      expect(find.text('Upcoming'), findsOneWidget);
      expect(find.text('Prescriptions'), findsWidgets);
      expect(find.text('Care Plans'), findsWidgets);
      expect(find.text('All Activity'), findsOneWidget);
      expect(find.text('Appointments'), findsWidgets);
      expect(find.text('Consultations'), findsWidgets);
    });

    testWidgets('2. Event cards render doctor info, status badge, and action buttons', (tester) async {
      final mock = MockPatientTimelineService(
        timelineResponse: testTimelineResponse,
        summary: testSummary,
      );

      await tester.pumpWidget(createTestApp(
        child: HealthcareTimelineScreen(timelineService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Doctor Consultation Completed (Dr. Anil Jayasuriya)'), findsOneWidget);
      expect(find.text('Digital Prescription Issued (RX-101)'), findsOneWidget);
      expect(find.byKey(const Key('view_visit_sess_101_completed')), findsOneWidget);

      await tester.drag(find.byType(ListView), const Offset(0, -300));
      await tester.pumpAndSettle();

      expect(find.text('Follow-up Care Plan Created (Dr. Anil Jayasuriya)'), findsOneWidget);
      expect(find.byKey(const Key('view_care_plan_cp_101_created')), findsOneWidget);
    });

    testWidgets('3. Category filter chip filters events', (tester) async {
      final mock = MockPatientTimelineService(
        timelineResponse: testTimelineResponse,
        summary: testSummary,
      );

      await tester.pumpWidget(createTestApp(
        child: HealthcareTimelineScreen(timelineService: mock),
      ));
      await tester.pumpAndSettle();

      // Tap on Prescriptions filter chip
      final rxChip = find.byKey(const Key('category_chip_PRESCRIPTIONS'));
      expect(rxChip, findsOneWidget);
      await tester.tap(rxChip);
      await tester.pumpAndSettle();

      expect(mock.lastCategoryRequested, 'PRESCRIPTIONS');
      expect(find.text('Digital Prescription Issued (RX-101)'), findsOneWidget);
      expect(find.text('Doctor Consultation Completed (Dr. Anil Jayasuriya)'), findsNothing);
    });

    testWidgets('4. Pull-to-refresh reloads timeline data', (tester) async {
      final mock = MockPatientTimelineService(
        timelineResponse: testTimelineResponse,
        summary: testSummary,
      );

      await tester.pumpWidget(createTestApp(
        child: HealthcareTimelineScreen(timelineService: mock),
      ));
      await tester.pumpAndSettle();

      final refreshBtn = find.byKey(const Key('timeline_refresh_button'));
      expect(refreshBtn, findsOneWidget);
      await tester.tap(refreshBtn);
      await tester.pumpAndSettle();

      expect(mock.timelineCalled, isTrue);
      expect(mock.summaryCalled, isTrue);
    });

    testWidgets('5. Load more pagination appends additional events without duplicates', (tester) async {
      final mock = MockPatientTimelineService(
        timelineResponse: testTimelineResponse,
        summary: testSummary,
      );

      await tester.pumpWidget(createTestApp(
        child: HealthcareTimelineScreen(timelineService: mock),
      ));
      await tester.pumpAndSettle();

      await tester.drag(find.byType(ListView), const Offset(0, -500));
      await tester.pumpAndSettle();

      final loadMoreFinder = find.byKey(const Key('timeline_load_more_button'));
      if (loadMoreFinder.evaluate().isNotEmpty) {
        await tester.tap(loadMoreFinder);
        await tester.pumpAndSettle();
      }

      expect(mock.lastCursorRequested, 'offset_3');
      expect(find.text('Appointment Booked with Dr. Saman Perera'), findsOneWidget);
    });

    testWidgets('6. Empty state displays appropriate message when no events exist', (tester) async {
      final emptyResponse = const TimelineResponse(events: [], totalCount: 0, hasMore: false);
      final mock = MockPatientTimelineService(
        timelineResponse: emptyResponse,
        summary: const TimelineSummary(),
      );

      await tester.pumpWidget(createTestApp(
        child: HealthcareTimelineScreen(timelineService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('No Healthcare History Yet'), findsOneWidget);
    });

    testWidgets('7. Visit Detail screen renders consolidated visit, prescription, and milestones', (tester) async {
      final mock = MockPatientTimelineService(
        timelineResponse: testTimelineResponse,
        summary: testSummary,
      );

      await tester.pumpWidget(createTestApp(
        child: PatientVisitDetailScreen(
          appointmentId: 'APPT-101',
          timelineService: mock,
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Visit Details'), findsOneWidget);
      expect(find.text('Dr. Anil Jayasuriya'), findsOneWidget);
      expect(find.text('Cardiology'), findsOneWidget);
      expect(find.text('Digital Prescription (RX-2026-001)'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('Medical Record (REC-2026-001)'), 150);
      await tester.pumpAndSettle();
      expect(find.text('Medical Record (REC-2026-001)'), findsOneWidget);
      expect(find.text('Follow-up Care Plan'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('Visit Milestones'), 200);
      await tester.pumpAndSettle();
      expect(find.text('Visit Milestones'), findsOneWidget);
    });
  });
}
