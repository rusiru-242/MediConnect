import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medication_reminder.dart';

void main() {
  group('Phase 22 Medication Reminder & Event Model Tests', () {
    test('MedicationReminder deserializes and serializes accurately', () {
      final json = {
        '_id': '670000000000000000000001',
        'reminderId': 'REM-20261018-A1B2C3',
        'patientUserId': 'PAT-USER-1',
        'prescriptionId': 'RX-20261018-1234',
        'prescriptionDbId': '670000000000000000000099',
        'prescriptionMedicationIndex': 0,
        'medicationName': 'Amoxicillin',
        'strength': '500mg',
        'dose': '1 capsule',
        'route': 'Oral',
        'frequency': 'Twice daily',
        'duration': '5 days',
        'scheduledTimes': ['08:00', '20:00'],
        'patientTimezone': 'Asia/Colombo',
        'startDate': '2026-10-18T00:00:00.000Z',
        'endDate': '2026-10-23T00:00:00.000Z',
        'enabled': true,
        'status': 'ACTIVE',
        'additionalInstructions': 'Take after meals',
        'notes': 'Keep in backpack',
        'createdAt': '2026-10-18T00:00:00.000Z',
        'updatedAt': '2026-10-18T00:00:00.000Z',
      };

      final reminder = MedicationReminder.fromJson(json);
      expect(reminder.id, '670000000000000000000001');
      expect(reminder.reminderId, 'REM-20261018-A1B2C3');
      expect(reminder.medicationName, 'Amoxicillin');
      expect(reminder.strength, '500mg');
      expect(reminder.scheduledTimes, ['08:00', '20:00']);
      expect(reminder.enabled, isTrue);
      expect(reminder.status, 'ACTIVE');
      expect(reminder.notes, 'Keep in backpack');

      final roundtrip = reminder.toJson();
      expect(roundtrip['medicationName'], 'Amoxicillin');
      expect(roundtrip['scheduledTimes'], ['08:00', '20:00']);
      expect(roundtrip['notes'], 'Keep in backpack');
    });

    test('MedicationEvent deserializes and serializes accurately', () {
      final json = {
        '_id': '670000000000000000000002',
        'eventId': 'EVT-20261018-E1F2G3',
        'reminderId': 'REM-20261018-A1B2C3',
        'reminderDbId': '670000000000000000000001',
        'patientUserId': 'PAT-USER-1',
        'scheduledOccurrenceTime': '2026-10-18T08:00:00.000Z',
        'status': 'TAKEN',
        'recordedAt': '2026-10-18T08:05:00.000Z',
        'snoozeMinutes': null,
        'notes': 'Taken with warm water',
        'medicationName': 'Amoxicillin',
        'dose': '1 capsule',
      };

      final event = MedicationEvent.fromJson(json);
      expect(event.eventId, 'EVT-20261018-E1F2G3');
      expect(event.status, 'TAKEN');
      expect(event.medicationName, 'Amoxicillin');
      expect(event.notes, 'Taken with warm water');

      final roundtrip = event.toJson();
      expect(roundtrip['eventId'], 'EVT-20261018-E1F2G3');
      expect(roundtrip['status'], 'TAKEN');
    });

    test('TodayScheduleResponse and AdherenceSummary parse correctly', () {
      final scheduleJson = {
        'date': '2026-10-18',
        'patientTimezone': 'Asia/Colombo',
        'totalScheduled': 2,
        'takenCount': 1,
        'skippedCount': 0,
        'pendingCount': 1,
        'items': [
          {
            'reminderId': 'REM-1',
            'reminderDbId': '670000000000000000000001',
            'medicationName': 'Amoxicillin',
            'strength': '500mg',
            'dose': '1 capsule',
            'route': 'Oral',
            'timeStr': '08:00',
            'scheduledOccurrenceTime': '2026-10-18T02:30:00.000Z',
            'status': 'TAKEN',
            'recordedAt': '2026-10-18T02:35:00.000Z',
          },
          {
            'reminderId': 'REM-1',
            'reminderDbId': '670000000000000000000001',
            'medicationName': 'Amoxicillin',
            'strength': '500mg',
            'dose': '1 capsule',
            'route': 'Oral',
            'timeStr': '20:00',
            'scheduledOccurrenceTime': '2026-10-18T14:30:00.000Z',
            'status': 'PENDING',
          },
        ],
      };

      final schedule = TodayScheduleResponse.fromJson(scheduleJson);
      expect(schedule.date, '2026-10-18');
      expect(schedule.totalScheduled, 2);
      expect(schedule.takenCount, 1);
      expect(schedule.items.length, 2);
      expect(schedule.items[0].status, 'TAKEN');
      expect(schedule.items[1].status, 'PENDING');

      final adherenceJson = {
        'totalTrackedDays': 30,
        'totalScheduledDoses': 20,
        'takenDoses': 18,
        'skippedDoses': 2,
        'adherenceRatePercent': 90.0,
        'activeRemindersCount': 2,
      };

      final adherence = AdherenceSummary.fromJson(adherenceJson);
      expect(adherence.totalTrackedDays, 30);
      expect(adherence.takenDoses, 18);
      expect(adherence.skippedDoses, 2);
      expect(adherence.adherenceRatePercent, 90.0);
      expect(adherence.activeRemindersCount, 2);
    });
  });
}
