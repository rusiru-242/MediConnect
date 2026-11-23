import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medication_reminder.dart';
import 'package:mediconnect/screens/patient/medication_reminders_screen.dart';
import 'package:mediconnect/services/medication_reminder_service.dart';

class FakeMedicationReminderService extends MedicationReminderService {
  TodayScheduleResponse fakeTodaySchedule;
  List<MedicationReminder> fakeReminders;
  List<MedicationEvent> fakeHistory;
  AdherenceSummary fakeAdherence;

  bool recordEventCalled = false;
  String? lastRecordedStatus;

  FakeMedicationReminderService({
    TodayScheduleResponse? todaySchedule,
    List<MedicationReminder>? reminders,
    List<MedicationEvent>? history,
    AdherenceSummary? adherence,
  })  : fakeTodaySchedule = todaySchedule ??
            const TodayScheduleResponse(
              date: '2026-10-18',
              patientTimezone: 'Asia/Colombo',
              totalScheduled: 0,
              takenCount: 0,
              skippedCount: 0,
              pendingCount: 0,
              items: [],
            ),
        fakeReminders = reminders ?? [],
        fakeHistory = history ?? [],
        fakeAdherence = adherence ??
            const AdherenceSummary(
              totalTrackedDays: 30,
              totalScheduledDoses: 0,
              takenDoses: 0,
              skippedDoses: 0,
              adherenceRatePercent: 100.0,
              activeRemindersCount: 0,
            );

  @override
  Future<TodayScheduleResponse> getTodaySchedule({String? timezone}) async {
    return fakeTodaySchedule;
  }

  @override
  Future<MedicationReminderListResponse> getReminders({
    bool activeOnly = false,
    int page = 1,
    int limit = 20,
  }) async {
    return MedicationReminderListResponse(
      items: fakeReminders,
      total: fakeReminders.length,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    );
  }

  @override
  Future<MedicationEventListResponse> getHistory({int page = 1, int limit = 20}) async {
    return MedicationEventListResponse(
      items: fakeHistory,
      total: fakeHistory.length,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    );
  }

  @override
  Future<AdherenceSummary> getAdherenceSummary() async {
    return fakeAdherence;
  }

  @override
  Future<MedicationEvent> recordEvent({
    required String reminderId,
    required DateTime scheduledOccurrenceTime,
    required String status,
    int? snoozeMinutes,
    String? notes,
  }) async {
    recordEventCalled = true;
    lastRecordedStatus = status;
    return MedicationEvent(
      id: 'EVT-1',
      eventId: 'EVT-TEST',
      reminderId: reminderId,
      reminderDbId: reminderId,
      patientUserId: 'USER-1',
      scheduledOccurrenceTime: scheduledOccurrenceTime,
      status: status,
      recordedAt: DateTime.now(),
      snoozeMinutes: snoozeMinutes,
    );
  }
}

void main() {
  group('MedicationRemindersScreen Widget Tests', () {
    testWidgets('renders empty state when no doses scheduled for today', (tester) async {
      final fakeService = FakeMedicationReminderService();

      await tester.pumpWidget(
        MaterialApp(
          home: MedicationRemindersScreen(service: fakeService),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Medication Reminders'), findsOneWidget);
      expect(find.text('Today'), findsOneWidget);
      expect(find.text('My Medications'), findsOneWidget);
      expect(find.text('History'), findsOneWidget);
      expect(find.text('All caught up for today!'), findsOneWidget);
    });

    testWidgets('renders today schedule items and triggers take/skip actions', (tester) async {
      final sampleItem = TodayScheduleItem(
        reminderId: 'REM-1',
        reminderDbId: '670000000000000000000001',
        medicationName: 'Amoxicillin',
        strength: '500mg',
        dose: '1 capsule',
        route: 'Oral',
        timeStr: '08:00',
        scheduledOccurrenceTime: DateTime.now(),
        status: 'PENDING',
        additionalInstructions: 'Take with full glass of water',
      );

      final fakeService = FakeMedicationReminderService(
        todaySchedule: TodayScheduleResponse(
          date: '2026-10-18',
          patientTimezone: 'Asia/Colombo',
          totalScheduled: 1,
          takenCount: 0,
          skippedCount: 0,
          pendingCount: 1,
          items: [sampleItem],
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: MedicationRemindersScreen(service: fakeService),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Amoxicillin'), findsOneWidget);
      expect(find.text('08:00'), findsOneWidget);
      expect(find.text('PENDING'), findsOneWidget);
      expect(find.text('Take'), findsOneWidget);
      expect(find.text('Skip'), findsOneWidget);

      // Tap Take
      await tester.tap(find.text('Take'));
      await tester.pumpAndSettle();

      expect(fakeService.recordEventCalled, isTrue);
      expect(fakeService.lastRecordedStatus, 'TAKEN');
    });

    testWidgets('switches to My Medications and History tabs accurately', (tester) async {
      tester.view.physicalSize = const Size(600, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final sampleReminder = MedicationReminder(
        id: '670000000000000000000001',
        reminderId: 'REM-TEST-001',
        patientUserId: 'USER-1',
        prescriptionId: 'RX-100',
        prescriptionDbId: 'RX-DB-1',
        prescriptionMedicationIndex: 0,
        medicationName: 'Metformin',
        strength: '500mg',
        dose: '1 tablet',
        route: 'Oral',
        frequency: 'Once daily',
        duration: '30 days',
        scheduledTimes: ['08:00'],
        patientTimezone: 'Asia/Colombo',
        startDate: DateTime.now(),
        endDate: DateTime.now().add(const Duration(days: 30)),
        enabled: true,
        status: 'ACTIVE',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      final fakeService = FakeMedicationReminderService(
        reminders: [sampleReminder],
        adherence: const AdherenceSummary(
          totalTrackedDays: 30,
          totalScheduledDoses: 30,
          takenDoses: 27,
          skippedDoses: 3,
          adherenceRatePercent: 90.0,
          activeRemindersCount: 1,
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: MedicationRemindersScreen(service: fakeService),
        ),
      );
      await tester.pumpAndSettle();

      // Switch to My Medications tab
      await tester.tap(find.text('My Medications'));
      await tester.pumpAndSettle();

      expect(find.text('Metformin'), findsOneWidget);
      expect(find.text('Settings'), findsOneWidget);

      // Switch to History tab
      await tester.tap(find.text('History'));
      await tester.pumpAndSettle();

      expect(find.text('30-Day Medication Adherence'), findsOneWidget);
      expect(find.text('90.0%'), findsOneWidget);
      expect(find.text('Taken'), findsOneWidget);
      expect(find.text('Skipped'), findsOneWidget);
    });
  });
}
