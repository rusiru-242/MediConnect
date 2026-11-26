// A02-BUG-016: device-local medication reminders are exact occurrences inside the prescribed dates.
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medication_reminder.dart';
import 'package:mediconnect/services/medication_reminder_service.dart';

MedicationReminder reminder({
  required List<String> times,
  required DateTime start,
  required DateTime end,
}) =>
    MedicationReminder.fromJson({
      '_id': 'rem-a02',
      'reminderId': 'REM-A02',
      'scheduledTimes': times,
      'startDate': start.toIso8601String(),
      'endDate': end.toIso8601String(),
      'enabled': true,
      'status': 'ACTIVE',
    });

void main() {
  // 2042-06-03 06:00 UTC = 11:30 Asia/Colombo.
  final now = DateTime.utc(2042, 6, 3, 6, 0);

  test('nothing is scheduled after the prescribed end date', () {
    final r = reminder(
      times: ['08:00', '20:00'],
      start: DateTime.utc(2042, 6, 1),
      end: DateTime.utc(2042, 6, 4, 18, 30), // 5 June 00:00 Colombo
    );
    final plan = MedicationReminderService.planOccurrences(r, now);
    // Today 20:00, 4 June 08:00 and 20:00 (Colombo); today's 08:00 has passed; nothing from 5 June.
    expect(plan.map((e) => e.value).toList(), [
      DateTime.utc(2042, 6, 3, 14, 30),
      DateTime.utc(2042, 6, 4, 2, 30),
      DateTime.utc(2042, 6, 4, 14, 30),
    ]);
    expect(plan.map((e) => e.key).toSet().length, 3); // distinct notification ids
  });

  test('a course that has not started yet is not scheduled early, and a finished one not at all', () {
    final future = reminder(
        times: ['09:00'], start: DateTime.utc(2042, 6, 8, 18, 30), end: DateTime.utc(2042, 6, 20));
    // The course starts 9 June 00:00 Colombo; the horizon ends 10 June: only 9 and 10 June 09:00.
    expect(MedicationReminderService.planOccurrences(future, now).map((e) => e.value).toList(),
        [DateTime.utc(2042, 6, 9, 3, 30), DateTime.utc(2042, 6, 10, 3, 30)]);
    final finished = reminder(
        times: ['09:00'], start: DateTime.utc(2042, 5, 1), end: DateTime.utc(2042, 5, 10));
    expect(MedicationReminderService.planOccurrences(finished, now), isEmpty);
  });

  test('an unparsable time is skipped, never replaced by an invented time', () {
    final r = reminder(times: ['8 am', '21:00'], start: DateTime.utc(2042, 6, 1), end: DateTime.utc(2042, 6, 3, 18, 30));
    final plan = MedicationReminderService.planOccurrences(r, now);
    expect(plan.map((e) => e.value).toList(), [DateTime.utc(2042, 6, 3, 15, 30)]);
  });

  test('scheduling is bounded to the planning horizon', () {
    final r = reminder(times: ['07:00', '13:00', '19:00'], start: DateTime.utc(2042, 1, 1), end: DateTime.utc(2043, 1, 1));
    expect(MedicationReminderService.planOccurrences(r, now).length, lessThanOrEqualTo(3 * 8));
  });
}
