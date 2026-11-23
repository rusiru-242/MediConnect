// Data models for Smart Medication Reminder System and Tracking (Phase 22).

class MedicationReminder {
  final String id;
  final String reminderId;
  final String patientUserId;
  final String prescriptionId;
  final String prescriptionDbId;
  final int prescriptionMedicationIndex;

  final String medicationName;
  final String strength;
  final String dose;
  final String route;
  final String frequency;
  final String duration;

  final List<String> scheduledTimes;
  final String patientTimezone;
  final DateTime startDate;
  final DateTime endDate;
  final bool enabled;
  final String status;

  final String? additionalInstructions;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const MedicationReminder({
    required this.id,
    required this.reminderId,
    required this.patientUserId,
    required this.prescriptionId,
    required this.prescriptionDbId,
    required this.prescriptionMedicationIndex,
    required this.medicationName,
    required this.strength,
    required this.dose,
    required this.route,
    required this.frequency,
    required this.duration,
    required this.scheduledTimes,
    required this.patientTimezone,
    required this.startDate,
    required this.endDate,
    required this.enabled,
    required this.status,
    this.additionalInstructions,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MedicationReminder.fromJson(Map<String, dynamic> json) {
    return MedicationReminder(
      id: json['_id']?.toString() ?? json['id']?.toString() ?? '',
      reminderId: json['reminderId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      prescriptionId: json['prescriptionId']?.toString() ?? '',
      prescriptionDbId: json['prescriptionDbId']?.toString() ?? '',
      prescriptionMedicationIndex: (json['prescriptionMedicationIndex'] as num?)?.toInt() ?? 0,
      medicationName: json['medicationName']?.toString() ?? '',
      strength: json['strength']?.toString() ?? '',
      dose: json['dose']?.toString() ?? '',
      route: json['route']?.toString() ?? 'Oral',
      frequency: json['frequency']?.toString() ?? '',
      duration: json['duration']?.toString() ?? '',
      scheduledTimes: (json['scheduledTimes'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      patientTimezone: json['patientTimezone']?.toString() ?? 'Asia/Colombo',
      startDate: DateTime.tryParse(json['startDate']?.toString() ?? '') ?? DateTime.now(),
      endDate: DateTime.tryParse(json['endDate']?.toString() ?? '') ??
          DateTime.now().add(const Duration(days: 7)),
      enabled: json['enabled'] == true,
      status: json['status']?.toString() ?? 'ACTIVE',
      additionalInstructions: json['additionalInstructions']?.toString(),
      notes: json['notes']?.toString(),
      createdAt: DateTime.tryParse(json['createdAt']?.toString() ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updatedAt']?.toString() ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      '_id': id,
      'reminderId': reminderId,
      'patientUserId': patientUserId,
      'prescriptionId': prescriptionId,
      'prescriptionDbId': prescriptionDbId,
      'prescriptionMedicationIndex': prescriptionMedicationIndex,
      'medicationName': medicationName,
      'strength': strength,
      'dose': dose,
      'route': route,
      'frequency': frequency,
      'duration': duration,
      'scheduledTimes': scheduledTimes,
      'patientTimezone': patientTimezone,
      'startDate': startDate.toIso8601String(),
      'endDate': endDate.toIso8601String(),
      'enabled': enabled,
      'status': status,
      if (additionalInstructions != null) 'additionalInstructions': additionalInstructions,
      if (notes != null) 'notes': notes,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
    };
  }
}

class MedicationEvent {
  final String id;
  final String eventId;
  final String reminderId;
  final String reminderDbId;
  final String patientUserId;
  final DateTime scheduledOccurrenceTime;
  final String status; // TAKEN, SKIPPED, SNOOZED
  final DateTime recordedAt;
  final int? snoozeMinutes;
  final String? notes;
  final String? medicationName;
  final String? dose;

  const MedicationEvent({
    required this.id,
    required this.eventId,
    required this.reminderId,
    required this.reminderDbId,
    required this.patientUserId,
    required this.scheduledOccurrenceTime,
    required this.status,
    required this.recordedAt,
    this.snoozeMinutes,
    this.notes,
    this.medicationName,
    this.dose,
  });

  factory MedicationEvent.fromJson(Map<String, dynamic> json) {
    return MedicationEvent(
      id: json['_id']?.toString() ?? json['id']?.toString() ?? '',
      eventId: json['eventId']?.toString() ?? '',
      reminderId: json['reminderId']?.toString() ?? '',
      reminderDbId: json['reminderDbId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      scheduledOccurrenceTime: DateTime.tryParse(json['scheduledOccurrenceTime']?.toString() ?? '') ??
          DateTime.now(),
      status: json['status']?.toString() ?? 'TAKEN',
      recordedAt: DateTime.tryParse(json['recordedAt']?.toString() ?? '') ?? DateTime.now(),
      snoozeMinutes: (json['snoozeMinutes'] as num?)?.toInt(),
      notes: json['notes']?.toString(),
      medicationName: json['medicationName']?.toString(),
      dose: json['dose']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      '_id': id,
      'eventId': eventId,
      'reminderId': reminderId,
      'reminderDbId': reminderDbId,
      'patientUserId': patientUserId,
      'scheduledOccurrenceTime': scheduledOccurrenceTime.toIso8601String(),
      'status': status,
      'recordedAt': recordedAt.toIso8601String(),
      if (snoozeMinutes != null) 'snoozeMinutes': snoozeMinutes,
      if (notes != null) 'notes': notes,
      if (medicationName != null) 'medicationName': medicationName,
      if (dose != null) 'dose': dose,
    };
  }
}

class TodayScheduleItem {
  final String reminderId;
  final String reminderDbId;
  final String medicationName;
  final String strength;
  final String dose;
  final String route;
  final String timeStr;
  final DateTime scheduledOccurrenceTime;
  final String status; // PENDING, TAKEN, SKIPPED, SNOOZED
  final DateTime? recordedAt;
  final int? snoozeMinutes;
  final String? additionalInstructions;

  const TodayScheduleItem({
    required this.reminderId,
    required this.reminderDbId,
    required this.medicationName,
    required this.strength,
    required this.dose,
    required this.route,
    required this.timeStr,
    required this.scheduledOccurrenceTime,
    required this.status,
    this.recordedAt,
    this.snoozeMinutes,
    this.additionalInstructions,
  });

  factory TodayScheduleItem.fromJson(Map<String, dynamic> json) {
    return TodayScheduleItem(
      reminderId: json['reminderId']?.toString() ?? '',
      reminderDbId: json['reminderDbId']?.toString() ?? '',
      medicationName: json['medicationName']?.toString() ?? '',
      strength: json['strength']?.toString() ?? '',
      dose: json['dose']?.toString() ?? '',
      route: json['route']?.toString() ?? 'Oral',
      timeStr: json['timeStr']?.toString() ?? '',
      scheduledOccurrenceTime:
          DateTime.tryParse(json['scheduledOccurrenceTime']?.toString() ?? '') ?? DateTime.now(),
      status: json['status']?.toString() ?? 'PENDING',
      recordedAt: json['recordedAt'] != null
          ? DateTime.tryParse(json['recordedAt'].toString())
          : null,
      snoozeMinutes: (json['snoozeMinutes'] as num?)?.toInt(),
      additionalInstructions: json['additionalInstructions']?.toString(),
    );
  }
}

class TodayScheduleResponse {
  final String date;
  final String patientTimezone;
  final int totalScheduled;
  final int takenCount;
  final int skippedCount;
  final int pendingCount;
  final List<TodayScheduleItem> items;

  const TodayScheduleResponse({
    required this.date,
    required this.patientTimezone,
    required this.totalScheduled,
    required this.takenCount,
    required this.skippedCount,
    required this.pendingCount,
    required this.items,
  });

  factory TodayScheduleResponse.fromJson(Map<String, dynamic> json) {
    final list = (json['items'] as List<dynamic>?)
            ?.map((e) => TodayScheduleItem.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    return TodayScheduleResponse(
      date: json['date']?.toString() ?? '',
      patientTimezone: json['patientTimezone']?.toString() ?? 'Asia/Colombo',
      totalScheduled: (json['totalScheduled'] as num?)?.toInt() ?? list.length,
      takenCount: (json['takenCount'] as num?)?.toInt() ?? 0,
      skippedCount: (json['skippedCount'] as num?)?.toInt() ?? 0,
      pendingCount: (json['pendingCount'] as num?)?.toInt() ?? 0,
      items: list,
    );
  }
}

class AdherenceSummary {
  final int totalTrackedDays;
  final int totalScheduledDoses;
  final int takenDoses;
  final int skippedDoses;
  final double adherenceRatePercent;
  final int activeRemindersCount;

  const AdherenceSummary({
    required this.totalTrackedDays,
    required this.totalScheduledDoses,
    required this.takenDoses,
    required this.skippedDoses,
    required this.adherenceRatePercent,
    required this.activeRemindersCount,
  });

  factory AdherenceSummary.fromJson(Map<String, dynamic> json) {
    return AdherenceSummary(
      totalTrackedDays: (json['totalTrackedDays'] as num?)?.toInt() ?? 30,
      totalScheduledDoses: (json['totalScheduledDoses'] as num?)?.toInt() ?? 0,
      takenDoses: (json['takenDoses'] as num?)?.toInt() ?? 0,
      skippedDoses: (json['skippedDoses'] as num?)?.toInt() ?? 0,
      adherenceRatePercent: (json['adherenceRatePercent'] as num?)?.toDouble() ?? 100.0,
      activeRemindersCount: (json['activeRemindersCount'] as num?)?.toInt() ?? 0,
    );
  }
}

class MedicationReminderListResponse {
  final List<MedicationReminder> items;
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;

  const MedicationReminderListResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
  });

  factory MedicationReminderListResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return MedicationReminderListResponse(
      items: rawItems.map((e) => MedicationReminder.fromJson(e as Map<String, dynamic>)).toList(),
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      pageSize: (json['pageSize'] as num?)?.toInt() ?? 20,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 1,
    );
  }
}

class MedicationEventListResponse {
  final List<MedicationEvent> items;
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;

  const MedicationEventListResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
  });

  factory MedicationEventListResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return MedicationEventListResponse(
      items: rawItems.map((e) => MedicationEvent.fromJson(e as Map<String, dynamic>)).toList(),
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      pageSize: (json['pageSize'] as num?)?.toInt() ?? 20,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 1,
    );
  }
}
