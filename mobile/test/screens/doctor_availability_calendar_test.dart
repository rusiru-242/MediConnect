import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_availability.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/doctor/manage_availability_screen.dart';
import 'package:mediconnect/services/doctor_service.dart';
import 'package:provider/provider.dart';

class MockDoctorAvailabilityService extends DoctorService {
  DoctorWeeklySchedule weeklySchedule = DoctorWeeklySchedule(
    id: 'WS-1',
    doctorUserId: 'USER-DOC-1',
    doctorProfileId: 'PROF-1',
    timezone: 'Asia/Colombo',
    slotDurationMinutes: 30,
    weekdays: [
      WeekdaySchedule(day: 'monday', isEnabled: true, sessions: [
        WorkingSession(startTime: '09:00', endTime: '12:00'),
        WorkingSession(startTime: '14:00', endTime: '17:00'),
      ]),
      WeekdaySchedule(day: 'tuesday', isEnabled: true, sessions: [
        WorkingSession(startTime: '09:00', endTime: '13:00'),
      ]),
      WeekdaySchedule(day: 'wednesday', isEnabled: false, sessions: []),
      WeekdaySchedule(day: 'thursday', isEnabled: true, sessions: [
        WorkingSession(startTime: '09:00', endTime: '17:00'),
      ]),
      WeekdaySchedule(day: 'friday', isEnabled: true, sessions: [
        WorkingSession(startTime: '09:00', endTime: '12:00'),
      ]),
      WeekdaySchedule(day: 'saturday', isEnabled: false, sessions: []),
      WeekdaySchedule(day: 'sunday', isEnabled: false, sessions: []),
    ],
  );

  List<DoctorLeave> leaves = [
    DoctorLeave(
      id: 'LEAVE-1',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      leaveType: 'VACATION',
      startDate: '2026-11-20',
      endDate: '2026-11-22',
      reason: 'Annual family holiday',
      status: 'ACTIVE',
    ),
  ];

  List<DoctorBlockedTime> blockedTimes = [
    DoctorBlockedTime(
      id: 'BLOCK-1',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      date: '2026-11-18',
      startTime: '10:00',
      endTime: '11:00',
      reason: 'Department meeting',
    ),
  ];

  List<DoctorAvailability> availabilities = [
    DoctorAvailability(
      id: 'AVAIL-1',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      date: '2026-11-16',
      startTime: '09:00',
      endTime: '12:00',
      slotDurationMinutes: 30,
      isActive: true,
    ),
  ];

  @override
  Future<List<DoctorAvailability>> getMyAvailabilities() async {
    return availabilities;
  }

  @override
  Future<DoctorWeeklySchedule> getWeeklySchedule() async {
    return weeklySchedule;
  }

  @override
  Future<DoctorWeeklySchedule> updateWeeklySchedule({
    required List<WeekdaySchedule> weekdays,
    String timezone = 'Asia/Colombo',
    int slotDurationMinutes = 30,
  }) async {
    weeklySchedule = DoctorWeeklySchedule(
      id: weeklySchedule.id,
      doctorUserId: weeklySchedule.doctorUserId,
      doctorProfileId: weeklySchedule.doctorProfileId,
      timezone: timezone,
      slotDurationMinutes: slotDurationMinutes,
      weekdays: weekdays,
    );
    return weeklySchedule;
  }

  @override
  Future<List<DoctorLeave>> getMyLeaves({String? status}) async {
    if (status != null) {
      return leaves.where((l) => l.status == status).toList();
    }
    return leaves;
  }

  @override
  Future<DoctorLeave> createLeave({
    required String leaveType,
    required String startDate,
    required String endDate,
    String? startTime,
    String? endTime,
    String? reason,
    bool resolveConflicts = false,
  }) async {
    final newLeave = DoctorLeave(
      id: 'LEAVE-${leaves.length + 1}',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      leaveType: leaveType,
      startDate: startDate,
      endDate: endDate,
      startTime: startTime,
      endTime: endTime,
      reason: reason,
      status: 'ACTIVE',
    );
    leaves.add(newLeave);
    return newLeave;
  }

  @override
  Future<void> cancelLeave(String leaveId) async {
    leaves.removeWhere((l) => l.id == leaveId);
  }

  @override
  Future<List<DoctorBlockedTime>> getMyBlockedTimes({String? date}) async {
    if (date != null) {
      return blockedTimes.where((b) => b.date == date).toList();
    }
    return blockedTimes;
  }

  @override
  Future<DoctorBlockedTime> createBlockedTime({
    required String date,
    required String startTime,
    required String endTime,
    String? reason,
  }) async {
    final newBlock = DoctorBlockedTime(
      id: 'BLOCK-${blockedTimes.length + 1}',
      doctorUserId: 'USER-DOC-1',
      doctorProfileId: 'PROF-1',
      date: date,
      startTime: startTime,
      endTime: endTime,
      reason: reason,
    );
    blockedTimes.add(newBlock);
    return newBlock;
  }

  @override
  Future<void> deleteBlockedTime(String blockId) async {
    blockedTimes.removeWhere((b) => b.id == blockId);
  }

  @override
  Future<DoctorCalendarOverview> getCalendarOverview({String? month}) async {
    return DoctorCalendarOverview(
      month: month ?? '2026-11',
      days: [
        CalendarDayOverview(
          date: '2026-11-16',
          weekday: 'monday',
          status: 'AVAILABLE',
          availableSlotsCount: 6,
          bookedAppointmentsCount: 1,
          appointments: [
            CalendarDayAppointment(
              appointmentId: 'APPT-101',
              patientName: 'Sunil Wickrama',
              startTime: '09:00',
              endTime: '09:30',
              status: 'CONFIRMED',
            ),
          ],
          slots: [
            TimeSlot(startTime: '09:30', endTime: '10:00'),
            TimeSlot(startTime: '10:00', endTime: '10:30'),
            TimeSlot(startTime: '10:30', endTime: '11:00'),
            TimeSlot(startTime: '11:00', endTime: '11:30'),
            TimeSlot(startTime: '11:30', endTime: '12:00'),
          ],
        ),
        CalendarDayOverview(
          date: '2026-11-20',
          weekday: 'friday',
          status: 'LEAVE',
          availableSlotsCount: 0,
          bookedAppointmentsCount: 0,
          leave: leaves.first,
        ),
      ],
    );
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

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

  group('Doctor Availability & Leave Calendar Tests (Phase 54)', () {
    testWidgets('1. Doctor calendar renders with month header, day grid, and legend', (tester) async {
      final mock = MockDoctorAvailabilityService();
      await tester.pumpWidget(createTestApp(
        child: ManageAvailabilityScreen(doctorService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Availability & Calendar'), findsOneWidget);
      expect(find.text('Calendar'), findsOneWidget);
      expect(find.text('Weekly'), findsOneWidget);
      expect(find.text('Leave & Dates'), findsOneWidget);

      // Legend items
      expect(find.text('Available'), findsWidgets);
      expect(find.text('Leave'), findsWidgets);
      expect(find.text('Booked'), findsOneWidget);
      expect(find.text('Unavailable'), findsWidgets);
    });

    testWidgets('2. Weekly Schedule tab allows toggling days and editing working hours', (tester) async {
      final mock = MockDoctorAvailabilityService();
      await tester.pumpWidget(createTestApp(
        child: ManageAvailabilityScreen(doctorService: mock),
      ));
      await tester.pumpAndSettle();

      // Switch to Weekly tab
      await tester.tap(find.text('Weekly'));
      await tester.pumpAndSettle();

      // Verify weekdays rendered
      expect(find.text('Monday'), findsOneWidget);
      expect(find.text('Tuesday'), findsOneWidget);
      expect(find.text('Wednesday'), findsOneWidget);
      expect(find.text('Timezone: Asia/Colombo'), findsOneWidget);
      expect(find.text('Slot Duration:'), findsOneWidget);
      expect(find.byKey(const Key('save_weekly_schedule_button')), findsOneWidget);

      // Save weekly schedule
      await tester.drag(find.byType(SingleChildScrollView).last, const Offset(0, -1200));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('save_weekly_schedule_button')));
      await tester.pumpAndSettle();

      expect(find.text('Weekly schedule saved successfully!'), findsOneWidget);
    });

    testWidgets('3. Leave & Dates tab displays active leaves, blocks, and allows cancellation', (tester) async {
      final mock = MockDoctorAvailabilityService();
      await tester.pumpWidget(createTestApp(
        child: ManageAvailabilityScreen(doctorService: mock),
      ));
      await tester.pumpAndSettle();

      // Switch to Leave & Dates tab
      await tester.tap(find.text('Leave & Dates'));
      await tester.pumpAndSettle();

      expect(find.text('Schedule Leave'), findsOneWidget);
      expect(find.text('Block Time'), findsOneWidget);
      expect(find.text('Scheduled Leave Records'), findsOneWidget);
      expect(find.text('VACATION (2026-11-20 to 2026-11-22)'), findsOneWidget);
      expect(find.text('Annual family holiday'), findsOneWidget);
      expect(find.text('Blocked Time Windows'), findsOneWidget);
      expect(find.text('2026-11-18 (10:00 - 11:00)'), findsOneWidget);

      // Cancel leave
      await tester.tap(find.byIcon(Icons.cancel_outlined));
      await tester.pumpAndSettle();

      expect(find.text('Cancel Scheduled Leave'), findsOneWidget);
      await tester.tap(find.text('Cancel Leave'));
      await tester.pumpAndSettle();

      expect(mock.leaves.isEmpty, true);
    });

    testWidgets('4. Responsive layout does not overflow on small screens', (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final mock = MockDoctorAvailabilityService();
      await tester.pumpWidget(createTestApp(
        child: ManageAvailabilityScreen(doctorService: mock),
      ));
      await tester.pumpAndSettle();

      expect(find.byType(ManageAvailabilityScreen), findsOneWidget);
    });
  });
}
