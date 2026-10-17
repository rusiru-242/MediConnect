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
    _cancelLocalNotificationsForId(reminderId);

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

  /// Synchronize local scheduled notifications across all active reminders.
  Future<void> syncLocalReminders(List<MedicationReminder> reminders) async {
    try {
      for (final r in reminders) {
        if (r.enabled && r.status == 'ACTIVE') {
          await _scheduleLocalNotificationsForReminder(r);
        } else {
          await _cancelLocalNotificationsForReminder(r);
        }
      }
    } catch (e) {
      debugPrint('[MedicationReminderService] syncLocalReminders error: $e');
    }
  }

  /// Schedule notifications for each daily time of a reminder.
  Future<void> _scheduleLocalNotificationsForReminder(MedicationReminder reminder) async {
    for (int i = 0; i < reminder.scheduledTimes.length; i++) {
      final timeStr = reminder.scheduledTimes[i];
      final parts = timeStr.split(':');
      if (parts.length == 2) {
        final hour = int.tryParse(parts[0]) ?? 8;
        final minute = int.tryParse(parts[1]) ?? 0;
        final notifId = _generateNotificationId(reminder.id, i);

        await _notificationService.scheduleDailyMedicationReminder(
          notificationId: notifId,
          hour: hour,
          minute: minute,
          payload: reminder.id,
        );
      }
    }
  }

  /// Cancel all notifications associated with a reminder.
  Future<void> _cancelLocalNotificationsForReminder(MedicationReminder reminder) async {
    _cancelLocalNotificationsForId(reminder.id);
  }

  Future<void> _cancelLocalNotificationsForId(String reminderId) async {
    for (int i = 0; i < 6; i++) {
      final notifId = _generateNotificationId(reminderId, i);
      await _notificationService.cancelReminder(notifId);
    }
  }

  /// Generate a deterministic 31-bit positive integer notification ID.
  int _generateNotificationId(String reminderId, int slotIndex) {
    var hash = 0;
    final key = '$reminderId:$slotIndex';
    for (var i = 0; i < key.length; i++) {
      hash = (31 * hash + key.codeUnitAt(i)) & 0x7FFFFFFF;
    }
    return hash;
  }
}
