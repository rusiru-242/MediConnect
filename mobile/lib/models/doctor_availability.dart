/// Models representing doctor availability schedules and patient-visible time slots.
library;

class DoctorAvailability {
  final String id;
  final String doctorUserId;
  final String doctorProfileId;
  final String date;
  final String startTime;
  final String endTime;
  final int slotDurationMinutes;
  final bool isActive;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  DoctorAvailability({
    required this.id,
    required this.doctorUserId,
    required this.doctorProfileId,
    required this.date,
    required this.startTime,
    required this.endTime,
    required this.slotDurationMinutes,
    required this.isActive,
    this.createdAt,
    this.updatedAt,
  });

  factory DoctorAvailability.fromJson(Map<String, dynamic> json) {
    return DoctorAvailability(
      id: (json['id'] ?? json['_id'] ?? '').toString(),
      doctorUserId: (json['doctorUserId'] ?? '').toString(),
      doctorProfileId: (json['doctorProfileId'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
      slotDurationMinutes:
          json['slotDurationMinutes'] is num ? (json['slotDurationMinutes'] as num).toInt() : 30,
      isActive: json['isActive'] is bool ? json['isActive'] as bool : true,
      createdAt: json['createdAt'] != null ? DateTime.tryParse(json['createdAt'].toString()) : null,
      updatedAt: json['updatedAt'] != null ? DateTime.tryParse(json['updatedAt'].toString()) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'date': date,
      'startTime': startTime,
      'endTime': endTime,
      'slotDurationMinutes': slotDurationMinutes,
      'isActive': isActive,
      'createdAt': createdAt?.toIso8601String(),
      'updatedAt': updatedAt?.toIso8601String(),
    };
  }
}

class TimeSlot {
  final String startTime;
  final String endTime;
  final String? availabilityId;

  TimeSlot({
    required this.startTime,
    required this.endTime,
    this.availabilityId,
  });

  factory TimeSlot.fromJson(Map<String, dynamic> json) {
    return TimeSlot(
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
      availabilityId: json['availabilityId']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'startTime': startTime,
      'endTime': endTime,
      if (availabilityId != null) 'availabilityId': availabilityId,
    };
  }
}

class DayAvailabilitySlots {
  final String date;
  final List<TimeSlot> slots;

  DayAvailabilitySlots({
    required this.date,
    required this.slots,
  });

  factory DayAvailabilitySlots.fromJson(Map<String, dynamic> json) {
    final rawSlots = json['slots'] as List<dynamic>? ?? [];
    return DayAvailabilitySlots(
      date: (json['date'] ?? '').toString(),
      slots: rawSlots.map((e) => TimeSlot.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'slots': slots.map((s) => s.toJson()).toList(),
    };
  }
}

// ---------------------------------------------------------------------------
// Phase 54 Models: Weekly Schedule, Leave, Blocked Time & Calendar Overview
// ---------------------------------------------------------------------------

class WorkingSession {
  final String startTime;
  final String endTime;

  WorkingSession({
    required this.startTime,
    required this.endTime,
  });

  factory WorkingSession.fromJson(Map<String, dynamic> json) {
    return WorkingSession(
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'startTime': startTime,
      'endTime': endTime,
    };
  }
}

class WeekdaySchedule {
  final String day;
  final bool isEnabled;
  final List<WorkingSession> sessions;

  WeekdaySchedule({
    required this.day,
    required this.isEnabled,
    required this.sessions,
  });

  factory WeekdaySchedule.fromJson(Map<String, dynamic> json) {
    final rawSessions = json['sessions'] as List<dynamic>? ?? [];
    return WeekdaySchedule(
      day: (json['day'] ?? '').toString().toLowerCase(),
      isEnabled: json['isEnabled'] is bool ? json['isEnabled'] as bool : true,
      sessions: rawSessions
          .map((s) => WorkingSession.fromJson(s as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'day': day,
      'isEnabled': isEnabled,
      'sessions': sessions.map((s) => s.toJson()).toList(),
    };
  }

  WeekdaySchedule copyWith({
    String? day,
    bool? isEnabled,
    List<WorkingSession>? sessions,
  }) {
    return WeekdaySchedule(
      day: day ?? this.day,
      isEnabled: isEnabled ?? this.isEnabled,
      sessions: sessions ?? this.sessions,
    );
  }
}

class DoctorWeeklySchedule {
  final String? id;
  final String doctorUserId;
  final String doctorProfileId;
  final String timezone;
  final int slotDurationMinutes;
  final List<WeekdaySchedule> weekdays;
  final DateTime? updatedAt;

  DoctorWeeklySchedule({
    this.id,
    required this.doctorUserId,
    required this.doctorProfileId,
    this.timezone = 'Asia/Colombo',
    this.slotDurationMinutes = 30,
    required this.weekdays,
    this.updatedAt,
  });

  factory DoctorWeeklySchedule.fromJson(Map<String, dynamic> json) {
    final rawWeekdays = json['weekdays'] as List<dynamic>? ?? [];
    return DoctorWeeklySchedule(
      id: json['id']?.toString(),
      doctorUserId: (json['doctorUserId'] ?? '').toString(),
      doctorProfileId: (json['doctorProfileId'] ?? '').toString(),
      timezone: (json['timezone'] ?? 'Asia/Colombo').toString(),
      slotDurationMinutes: json['slotDurationMinutes'] is num
          ? (json['slotDurationMinutes'] as num).toInt()
          : 30,
      weekdays: rawWeekdays
          .map((w) => WeekdaySchedule.fromJson(w as Map<String, dynamic>))
          .toList(),
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (id != null) 'id': id,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'timezone': timezone,
      'slotDurationMinutes': slotDurationMinutes,
      'weekdays': weekdays.map((w) => w.toJson()).toList(),
      if (updatedAt != null) 'updatedAt': updatedAt?.toIso8601String(),
    };
  }
}

class DoctorLeave {
  final String id;
  final String doctorUserId;
  final String doctorProfileId;
  final String leaveType;
  final String startDate;
  final String endDate;
  final String? startTime;
  final String? endTime;
  final String? reason;
  final String status;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  DoctorLeave({
    required this.id,
    required this.doctorUserId,
    required this.doctorProfileId,
    required this.leaveType,
    required this.startDate,
    required this.endDate,
    this.startTime,
    this.endTime,
    this.reason,
    this.status = 'ACTIVE',
    this.createdAt,
    this.updatedAt,
  });

  factory DoctorLeave.fromJson(Map<String, dynamic> json) {
    return DoctorLeave(
      id: (json['id'] ?? json['_id'] ?? '').toString(),
      doctorUserId: (json['doctorUserId'] ?? '').toString(),
      doctorProfileId: (json['doctorProfileId'] ?? '').toString(),
      leaveType: (json['leaveType'] ?? 'PERSONAL').toString(),
      startDate: (json['startDate'] ?? '').toString(),
      endDate: (json['endDate'] ?? '').toString(),
      startTime: json['startTime']?.toString(),
      endTime: json['endTime']?.toString(),
      reason: json['reason']?.toString(),
      status: (json['status'] ?? 'ACTIVE').toString(),
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString())
          : null,
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'leaveType': leaveType,
      'startDate': startDate,
      'endDate': endDate,
      if (startTime != null) 'startTime': startTime,
      if (endTime != null) 'endTime': endTime,
      if (reason != null) 'reason': reason,
      'status': status,
    };
  }
}

class DoctorBlockedTime {
  final String id;
  final String doctorUserId;
  final String doctorProfileId;
  final String date;
  final String startTime;
  final String endTime;
  final String? reason;
  final DateTime? createdAt;

  DoctorBlockedTime({
    required this.id,
    required this.doctorUserId,
    required this.doctorProfileId,
    required this.date,
    required this.startTime,
    required this.endTime,
    this.reason,
    this.createdAt,
  });

  factory DoctorBlockedTime.fromJson(Map<String, dynamic> json) {
    return DoctorBlockedTime(
      id: (json['id'] ?? json['_id'] ?? '').toString(),
      doctorUserId: (json['doctorUserId'] ?? '').toString(),
      doctorProfileId: (json['doctorProfileId'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
      reason: json['reason']?.toString(),
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'date': date,
      'startTime': startTime,
      'endTime': endTime,
      if (reason != null) 'reason': reason,
    };
  }
}

class CalendarDayAppointment {
  final String appointmentId;
  final String patientName;
  final String startTime;
  final String endTime;
  final String status;

  CalendarDayAppointment({
    required this.appointmentId,
    required this.patientName,
    required this.startTime,
    required this.endTime,
    required this.status,
  });

  factory CalendarDayAppointment.fromJson(Map<String, dynamic> json) {
    return CalendarDayAppointment(
      appointmentId: (json['appointmentId'] ?? '').toString(),
      patientName: (json['patientName'] ?? 'Patient').toString(),
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
      status: (json['status'] ?? '').toString(),
    );
  }
}

class CalendarDayOverview {
  final String date;
  final String weekday;
  final String status; // AVAILABLE | UNAVAILABLE | LEAVE | BLOCKED
  final int availableSlotsCount;
  final int bookedAppointmentsCount;
  final DoctorLeave? leave;
  final List<DoctorBlockedTime> blockedTimes;
  final List<CalendarDayAppointment> appointments;
  final List<TimeSlot> slots;

  CalendarDayOverview({
    required this.date,
    required this.weekday,
    required this.status,
    required this.availableSlotsCount,
    required this.bookedAppointmentsCount,
    this.leave,
    this.blockedTimes = const [],
    this.appointments = const [],
    this.slots = const [],
  });

  factory CalendarDayOverview.fromJson(Map<String, dynamic> json) {
    final rawBlocks = json['blockedTimes'] as List<dynamic>? ?? [];
    final rawAppts = json['appointments'] as List<dynamic>? ?? [];
    final rawSlots = json['slots'] as List<dynamic>? ?? [];

    return CalendarDayOverview(
      date: (json['date'] ?? '').toString(),
      weekday: (json['weekday'] ?? '').toString(),
      status: (json['status'] ?? 'UNAVAILABLE').toString(),
      availableSlotsCount: json['availableSlotsCount'] is num
          ? (json['availableSlotsCount'] as num).toInt()
          : 0,
      bookedAppointmentsCount: json['bookedAppointmentsCount'] is num
          ? (json['bookedAppointmentsCount'] as num).toInt()
          : 0,
      leave: json['leave'] is Map<String, dynamic>
          ? DoctorLeave.fromJson(json['leave'] as Map<String, dynamic>)
          : null,
      blockedTimes: rawBlocks
          .map((b) => DoctorBlockedTime.fromJson(b as Map<String, dynamic>))
          .toList(),
      appointments: rawAppts
          .map((a) => CalendarDayAppointment.fromJson(a as Map<String, dynamic>))
          .toList(),
      slots: rawSlots
          .map((s) => TimeSlot.fromJson(s as Map<String, dynamic>))
          .toList(),
    );
  }
}

class DoctorCalendarOverview {
  final String month;
  final List<CalendarDayOverview> days;

  DoctorCalendarOverview({
    required this.month,
    required this.days,
  });

  factory DoctorCalendarOverview.fromJson(Map<String, dynamic> json) {
    final rawDays = json['days'] as List<dynamic>? ?? [];
    return DoctorCalendarOverview(
      month: (json['month'] ?? '').toString(),
      days: rawDays
          .map((d) => CalendarDayOverview.fromJson(d as Map<String, dynamic>))
          .toList(),
    );
  }
}
