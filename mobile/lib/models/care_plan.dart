/// Data models for Smart Follow-up Care Plans (Phase 56).
library;

class CareTask {
  final String taskId;
  final String title;
  final String? description;
  final bool isCompleted;
  final DateTime? completedAt;

  const CareTask({
    required this.taskId,
    required this.title,
    this.description,
    this.isCompleted = false,
    this.completedAt,
  });

  factory CareTask.fromJson(Map<String, dynamic> json) {
    return CareTask(
      taskId: json['taskId']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      description: json['description']?.toString(),
      isCompleted: json['isCompleted'] == true,
      completedAt: json['completedAt'] != null
          ? DateTime.tryParse(json['completedAt'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'taskId': taskId,
      'title': title,
      if (description != null) 'description': description,
      'isCompleted': isCompleted,
      if (completedAt != null) 'completedAt': completedAt?.toIso8601String(),
    };
  }

  CareTask copyWith({
    String? taskId,
    String? title,
    String? description,
    bool? isCompleted,
    DateTime? completedAt,
  }) {
    return CareTask(
      taskId: taskId ?? this.taskId,
      title: title ?? this.title,
      description: description ?? this.description,
      isCompleted: isCompleted ?? this.isCompleted,
      completedAt: completedAt ?? this.completedAt,
    );
  }
}

class CarePlanAuditEntry {
  final String action;
  final String performedBy;
  final String performedByRole;
  final DateTime timestamp;
  final String? note;

  const CarePlanAuditEntry({
    required this.action,
    required this.performedBy,
    required this.performedByRole,
    required this.timestamp,
    this.note,
  });

  factory CarePlanAuditEntry.fromJson(Map<String, dynamic> json) {
    return CarePlanAuditEntry(
      action: json['action']?.toString() ?? '',
      performedBy: json['performedBy']?.toString() ?? '',
      performedByRole: json['performedByRole']?.toString() ?? 'SYSTEM',
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now()
          : DateTime.now(),
      note: json['note']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'action': action,
      'performedBy': performedBy,
      'performedByRole': performedByRole,
      'timestamp': timestamp.toIso8601String(),
      if (note != null) 'note': note,
    };
  }
}

class CarePlan {
  final String id;
  final String patientUserId;
  final String patientName;
  final String doctorUserId;
  final String doctorProfileId;
  final String doctorName;
  final String? doctorSpecialty;
  final String? doctorHospital;
  final String appointmentId;
  final String? consultationDate;
  final String followUpDate;
  final String? followUpDateEnd;
  final String reason;
  final String instructions;
  final String recommendedConsultationType;
  final List<CareTask> tasks;
  final List<String> linkedPrescriptionIds;
  final List<String> linkedMedicalRecordIds;
  final String? bookedAppointmentId;
  final String status;
  final int version;
  final String createdBy;
  final String updatedBy;
  final List<CarePlanAuditEntry> auditLog;
  final List<String> remindersSent;
  final DateTime createdAt;
  final DateTime updatedAt;

  const CarePlan({
    required this.id,
    required this.patientUserId,
    this.patientName = 'Patient',
    required this.doctorUserId,
    required this.doctorProfileId,
    this.doctorName = 'Doctor',
    this.doctorSpecialty,
    this.doctorHospital,
    required this.appointmentId,
    this.consultationDate,
    required this.followUpDate,
    this.followUpDateEnd,
    required this.reason,
    required this.instructions,
    this.recommendedConsultationType = 'IN_PERSON',
    this.tasks = const [],
    this.linkedPrescriptionIds = const [],
    this.linkedMedicalRecordIds = const [],
    this.bookedAppointmentId,
    this.status = 'ACTIVE',
    this.version = 1,
    required this.createdBy,
    required this.updatedBy,
    this.auditLog = const [],
    this.remindersSent = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  bool get isActive => status.toUpperCase() == 'ACTIVE';
  bool get isFollowUpBooked => status.toUpperCase() == 'FOLLOW_UP_BOOKED';
  bool get isCompleted => status.toUpperCase() == 'COMPLETED';
  bool get isCancelled => status.toUpperCase() == 'CANCELLED';
  bool get isOverdue => status.toUpperCase() == 'OVERDUE';

  int get totalTaskCount => tasks.length;
  int get completedTaskCount => tasks.where((t) => t.isCompleted).length;
  double get progressPercentage =>
      totalTaskCount == 0 ? 1.0 : completedTaskCount / totalTaskCount;

  factory CarePlan.fromJson(Map<String, dynamic> json) {
    return CarePlan(
      id: json['id']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      patientName: json['patientName']?.toString() ?? 'Patient',
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorProfileId: json['doctorProfileId']?.toString() ?? '',
      doctorName: json['doctorName']?.toString() ?? 'Doctor',
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      doctorHospital: json['doctorHospital']?.toString(),
      appointmentId: json['appointmentId']?.toString() ?? '',
      consultationDate: json['consultationDate']?.toString(),
      followUpDate: json['followUpDate']?.toString() ?? '',
      followUpDateEnd: json['followUpDateEnd']?.toString(),
      reason: json['reason']?.toString() ?? '',
      instructions: json['instructions']?.toString() ?? '',
      recommendedConsultationType:
          json['recommendedConsultationType']?.toString() ?? 'IN_PERSON',
      tasks: (json['tasks'] as List<dynamic>?)
              ?.map((t) => CareTask.fromJson(t as Map<String, dynamic>))
              .toList() ??
          [],
      linkedPrescriptionIds: (json['linkedPrescriptionIds'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      linkedMedicalRecordIds: (json['linkedMedicalRecordIds'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      bookedAppointmentId: json['bookedAppointmentId']?.toString(),
      status: json['status']?.toString() ?? 'ACTIVE',
      version: json['version'] is int ? json['version'] as int : 1,
      createdBy: json['createdBy']?.toString() ?? '',
      updatedBy: json['updatedBy']?.toString() ?? '',
      auditLog: (json['auditLog'] as List<dynamic>?)
              ?.map((a) => CarePlanAuditEntry.fromJson(a as Map<String, dynamic>))
              .toList() ??
          [],
      remindersSent: (json['remindersSent'] as List<dynamic>?)
              ?.map((r) => r.toString())
              .toList() ??
          [],
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'patientUserId': patientUserId,
      'patientName': patientName,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'doctorName': doctorName,
      if (doctorSpecialty != null) 'doctorSpecialty': doctorSpecialty,
      if (doctorHospital != null) 'doctorHospital': doctorHospital,
      'appointmentId': appointmentId,
      if (consultationDate != null) 'consultationDate': consultationDate,
      'followUpDate': followUpDate,
      if (followUpDateEnd != null) 'followUpDateEnd': followUpDateEnd,
      'reason': reason,
      'instructions': instructions,
      'recommendedConsultationType': recommendedConsultationType,
      'tasks': tasks.map((t) => t.toJson()).toList(),
      'linkedPrescriptionIds': linkedPrescriptionIds,
      'linkedMedicalRecordIds': linkedMedicalRecordIds,
      if (bookedAppointmentId != null) 'bookedAppointmentId': bookedAppointmentId,
      'status': status,
      'version': version,
      'createdBy': createdBy,
      'updatedBy': updatedBy,
      'auditLog': auditLog.map((a) => a.toJson()).toList(),
      'remindersSent': remindersSent,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
    };
  }

  CarePlan copyWith({
    String? id,
    String? patientUserId,
    String? patientName,
    String? doctorUserId,
    String? doctorProfileId,
    String? doctorName,
    String? doctorSpecialty,
    String? doctorHospital,
    String? appointmentId,
    String? consultationDate,
    String? followUpDate,
    String? followUpDateEnd,
    String? reason,
    String? instructions,
    String? recommendedConsultationType,
    List<CareTask>? tasks,
    List<String>? linkedPrescriptionIds,
    List<String>? linkedMedicalRecordIds,
    String? bookedAppointmentId,
    String? status,
    int? version,
    String? createdBy,
    String? updatedBy,
    List<CarePlanAuditEntry>? auditLog,
    List<String>? remindersSent,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return CarePlan(
      id: id ?? this.id,
      patientUserId: patientUserId ?? this.patientUserId,
      patientName: patientName ?? this.patientName,
      doctorUserId: doctorUserId ?? this.doctorUserId,
      doctorProfileId: doctorProfileId ?? this.doctorProfileId,
      doctorName: doctorName ?? this.doctorName,
      doctorSpecialty: doctorSpecialty ?? this.doctorSpecialty,
      doctorHospital: doctorHospital ?? this.doctorHospital,
      appointmentId: appointmentId ?? this.appointmentId,
      consultationDate: consultationDate ?? this.consultationDate,
      followUpDate: followUpDate ?? this.followUpDate,
      followUpDateEnd: followUpDateEnd ?? this.followUpDateEnd,
      reason: reason ?? this.reason,
      instructions: instructions ?? this.instructions,
      recommendedConsultationType:
          recommendedConsultationType ?? this.recommendedConsultationType,
      tasks: tasks ?? this.tasks,
      linkedPrescriptionIds: linkedPrescriptionIds ?? this.linkedPrescriptionIds,
      linkedMedicalRecordIds: linkedMedicalRecordIds ?? this.linkedMedicalRecordIds,
      bookedAppointmentId: bookedAppointmentId ?? this.bookedAppointmentId,
      status: status ?? this.status,
      version: version ?? this.version,
      createdBy: createdBy ?? this.createdBy,
      updatedBy: updatedBy ?? this.updatedBy,
      auditLog: auditLog ?? this.auditLog,
      remindersSent: remindersSent ?? this.remindersSent,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
