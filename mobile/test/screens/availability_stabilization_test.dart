// Regression tests for doctor availability loading (BUG-005, BUG-006, new BUG-027).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_availability.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/doctor/manage_availability_screen.dart';
import 'package:provider/provider.dart';

import 'doctor_availability_calendar_test.dart' show MockDoctorAvailabilityService;

class _FailingWeeklyService extends MockDoctorAvailabilityService {
  int saves = 0;

  @override
  Future<DoctorWeeklySchedule> getWeeklySchedule() async => throw Exception('network');

  @override
  Future<DoctorWeeklySchedule> updateWeeklySchedule({
    required List<WeekdaySchedule> weekdays,
    String timezone = 'Asia/Colombo',
    int slotDurationMinutes = 30,
  }) async {
    saves++;
    throw StateError('must not save while the schedule failed to load');
  }
}

class _FailingCalendarService extends MockDoctorAvailabilityService {
  @override
  Future<DoctorCalendarOverview> getCalendarOverview({String? month}) async => throw Exception('timeout');
}

class _SlowMonthService extends MockDoctorAvailabilityService {
  final Map<String, Completer<DoctorCalendarOverview>> pending = {};

  @override
  Future<DoctorCalendarOverview> getCalendarOverview({String? month}) {
    final completer = Completer<DoctorCalendarOverview>();
    pending[month ?? ''] = completer;
    return completer.future;
  }
}

Widget _app(Widget child) => MultiProvider(
      providers: [ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider())],
      child: MaterialApp(home: child),
    );

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('BUG-027: failed weekly schedule load shows an error, not a placeholder schedule', (tester) async {
    final service = _FailingWeeklyService();
    await tester.pumpWidget(_app(ManageAvailabilityScreen(doctorService: service)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Weekly'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('availability_weekly_error')), findsOneWidget);
    // The old fallback invented Monday 09:00-12:00 / 14:00-17:00 sessions.
    expect(find.text('14:00'), findsNothing);
  });

  testWidgets('BUG-005: calendar failure is reported instead of an empty month', (tester) async {
    await tester.pumpWidget(_app(ManageAvailabilityScreen(doctorService: _FailingCalendarService())));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('availability_calendar_error')), findsOneWidget);
  });

  testWidgets('BUG-005: changing month loads that month from the server', (tester) async {
    final service = _SlowMonthService();
    await tester.pumpWidget(_app(ManageAvailabilityScreen(doctorService: service)));
    await tester.pump();
    final firstMonth = service.pending.keys.single;
    service.pending[firstMonth]!.complete(DoctorCalendarOverview(month: firstMonth, days: []));
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.chevron_right_rounded).first);
    await tester.pump();
    final secondMonth = service.pending.keys.firstWhere((m) => m != firstMonth);
    expect(secondMonth.compareTo(firstMonth), greaterThan(0));
    service.pending[secondMonth]!.complete(DoctorCalendarOverview(month: secondMonth, days: []));
    await tester.pumpAndSettle();

    final state = tester.state(find.byType(ManageAvailabilityScreen));
    // ignore: avoid_dynamic_calls
    expect((state as dynamic).debugCalendarMonth, secondMonth);
    expect(find.byKey(const Key('availability_calendar_error')), findsNothing);
  });
}
