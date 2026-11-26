import 'package:flutter/foundation.dart';

import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/medication_reminder.dart';
import 'local_notification_service.dart';

/// Service interfacing with the MediConnect Medication Reminder API (Phase 22).
class MedicationReminderService {
  final ApiClient _apiClient;
  final LocalNotificationService _notificationService;

  MedicationReminderService({
    ApiClient? apiClient,
    LocalNotificationService? notificationService,
  })  : _apiClient = apiClient ?? ApiClient(),
        _notificationService = notificationService ?? LocalNotificationService();

  /// Retrieve list of reminders for the authenticated patient.
  Future<MedicationReminderListResponse> getReminders({
    bool activeOnly = false,
    int page = 1,
    int limit = 20,
  }) async {
    final endpoint =
        '${ApiConstants.medicationRemindersEndpoint}?active_only=$activeOnly&page=$page&page_size=$limit';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      final list = MedicationReminderListResponse.fromJson(response);
      // Synchronize local notifications in background
      if (activeOnly) {
        syncLocalReminders(list.items);
      }
      return list;
    }
    throw Exception('Unexpected response format when fetching medication reminders.');
  }

  /// Get details for a single medication reminder.
  Future<MedicationReminder> getReminder(String reminderId) async {
    final endpoint = ApiConstants.medicationReminderDetailEndpoint(reminderId);
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return MedicationReminder.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching medication reminder.');
  }

  /// Create a new medication reminder schedule linked to a prescription item.
  Future<MedicationReminder> createReminder({
    required String prescriptionId,
    required int prescriptionMedicationIndex,
    required List<String> scheduledTimes,
    String patientTimezone = 'Asia/Colombo',
    String? notes,
  }) async {
    final body = {
      'prescriptionId': prescriptionId,
      'prescriptionMedicationIndex': prescriptionMedicationIndex,
      'scheduledTimes': scheduledTimes,
      'patientTimezone': patientTimezone,
      if (notes != null && notes.trim().isNotEmpty) 'notes': notes.trim(),
    };

    final response = await _apiClient.post(
      ApiConstants.medicationRemindersEndpoint,
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      final reminder = MedicationReminder.fromJson(response);
      // Schedule local notification immediately
      _scheduleLocalNotificationsForReminder(reminder);
      return reminder;
    }
    throw Exception('Failed to create medication reminder.');
  }

  /// Update reminder times, active status, or patient notes.
  Future<MedicationReminder> updateReminder(
    String reminderId, {
    List<String>? scheduledTimes,
    bool? enabled,
    String? notes,
  }) async {
    final body = <String, dynamic>{};
    if (scheduledTimes != null) body['scheduledTimes'] = scheduledTimes;
    if (enabled != null) body['enabled'] = enabled;
    if (notes != null) body['notes'] = notes;

    final response = await _apiClient.patch(
      ApiConstants.medicationReminderDetailEndpoint(reminderId),
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      final updated = MedicationReminder.fromJson(response);
      if (updated.enabled) {
        _scheduleLocalNotificationsForReminder(updated);
      } else {
        _cancelLocalNotificationsForReminder(updated);
      }
      return updated;
    }
    throw Exception('Failed to update medication reminder.');
  }

  /// Delete or cancel a medication reminder.
  Future<bool> deleteReminder(String reminderId) async {
    final response = await _apiClient.delete(
      ApiConstants.medicationReminderDetailEndpoint(reminderId),
      includeAuth: true,
    );

    // Cancel local notifications
    await _cancelLocalNotificationsForId(reminderId);

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return true;
  }

  /// Fetch today's schedule with occurrence items and recorded statuses.
  Future<TodayScheduleResponse> getTodaySchedule({String? timezone}) async {
    final endpoint = timezone != null
        ? '${ApiConstants.todayMedicationScheduleEndpoint}?timezone=$timezone'
        : ApiConstants.todayMedicationScheduleEndpoint;

    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return TodayScheduleResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching today schedule.');
  }

  /// Record a medication intake action: TAKEN, SKIPPED, or SNOOZED.
  Future<MedicationEvent> recordEvent({
    required String reminderId,
    required DateTime scheduledOccurrenceTime,
    required String status,
    int? snoozeMinutes,
    String? notes,
  }) async {
    final body = <String, dynamic>{
      'scheduledOccurrenceTime': scheduledOccurrenceTime.toUtc().toIso8601String(),
      'status': status,
    };
    if (snoozeMinutes != null) {
      body['snoozeMinutes'] = snoozeMinutes;
    }
    if (notes != null && notes.trim().isNotEmpty) {
      body['notes'] = notes.trim();
    }

    final response = await _apiClient.post(
      ApiConstants.medicationReminderEventsEndpoint(reminderId),
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return MedicationEvent.fromJson(response);
    }
    throw Exception('Failed to record medication intake event.');
  }

  /// Get paginated history of recorded intake events.
  Future<MedicationEventListResponse> getHistory({
    int page = 1,
    int limit = 20,
  }) async {
    final endpoint =
        '${ApiConstants.medicationRemindersHistoryEndpoint}?page=$page&page_size=$limit';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return MedicationEventListResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching medication history.');
  }

  /// Get patient adherence summary over the past 30 days.
  Future<AdherenceSummary> getAdherenceSummary() async {
    final response = await _apiClient.get(
      ApiConstants.medicationRemindersAdherenceEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return AdherenceSummary.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching adherence summary.');
  }

  /// Payload prefix of every device-local medication reminder.
  static const String payloadPrefix = 'medrem:';

  /// Days of occurrences scheduled ahead on the device; re-planned whenever the reminders list is loaded.
  static const int horizonDays = 7;

  /// Synchronize device-local reminders with the server (A02-BUG-016).
  ///
  /// Before A02 only reminders still returned as active were (re)scheduled, as open-ended daily repeats: a
  /// reminder cancelled on the server, on another device or by a prescription change kept firing on this phone,
  /// and every reminder kept firing after its prescribed end date. Now every pending local medication reminder is
  /// cancelled and only occurrences of active reminders inside their start/end dates are scheduled again.
  Future<void> syncLocalReminders(List<MedicationReminder> reminders) async {
    try {
      await _notificationService.cancelPendingWithPayloadPrefix(payloadPrefix);
      for (final r in reminders) {
        if (r.enabled && r.status == 'ACTIVE') {
          await _scheduleLocalNotificationsForReminder(r);
        }
      }
    } catch (e) {
      debugPrint('[MedicationReminderService] syncLocalReminders error: $e');
    }
  }

  /// Exact occurrences of [reminder] in the next [days] days, inside its start and end dates.
  ///
  /// Reminder times are Asia/Colombo wall-clock times (UTC+05:30, no daylight saving), the only zone the backend
  /// schedules in. No time is invented: an unparsable time is skipped.
  static List<MapEntry<int, DateTime>> planOccurrences(MedicationReminder reminder, DateTime now,
      {int days = horizonDays}) {
    const offset = Duration(hours: 5, minutes: 30);
    final nowUtc = now.toUtc();
    final localToday = nowUtc.add(offset);
    final result = <MapEntry<int, DateTime>>[];
    for (var d = 0; d <= days; d++) {
      final day = DateTime.utc(localToday.year, localToday.month, localToday.day + d);
      for (var slot = 0; slot < reminder.scheduledTimes.length; slot++) {
        final match = RegExp(r'^([01][0-9]|2[0-3]):([0-5][0-9])$').firstMatch(reminder.scheduledTimes[slot]);
        if (match == null) continue;
        final whenUtc = DateTime.utc(day.year, day.month, day.day, int.parse(match.group(1)!),
                int.parse(match.group(2)!))
            .subtract(offset);
        if (!whenUtc.isAfter(nowUtc)) continue;
        if (whenUtc.isBefore(reminder.startDate.toUtc()) || !whenUtc.isBefore(reminder.endDate.toUtc())) continue;
        final key = '${reminder.id}:${day.toIso8601String().substring(0, 10)}:$slot';
        result.add(MapEntry(_hashId(key), whenUtc));
      }
    }
    return result;
  }

  Future<void> _scheduleLocalNotificationsForReminder(MedicationReminder reminder) async {
    await _cancelLocalNotificationsForId(reminder.id);
    for (final occurrence in planOccurrences(reminder, DateTime.now())) {
      await _notificationService.scheduleMedicationOccurrence(
        notificationId: occurrence.key,
        whenUtc: occurrence.value,
        payload: '$payloadPrefix${reminder.id}',
      );
    }
  }

  /// Cancel all notifications associated with a reminder.
  Future<void> _cancelLocalNotificationsForReminder(MedicationReminder reminder) async {
    await _cancelLocalNotificationsForId(reminder.id);
  }

  Future<void> _cancelLocalNotificationsForId(String reminderId) async {
    // Occurrences scheduled since A02, and the daily repeats created by earlier versions of the app.
    await _notificationService.cancelPendingWithPayloadPrefix('$payloadPrefix$reminderId');
    for (int i = 0; i < 6; i++) {
      await _notificationService.cancelReminder(_generateNotificationId(reminderId, i));
    }
  }

  /// Generate a deterministic 31-bit positive integer notification ID.
  int _generateNotificationId(String reminderId, int slotIndex) => _hashId('$reminderId:$slotIndex');

  static int _hashId(String key) {
    var hash = 0;
    for (var i = 0; i < key.length; i++) {
      hash = (31 * hash + key.codeUnitAt(i)) & 0x7FFFFFFF;
    }
    return hash;
  }
}
