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
