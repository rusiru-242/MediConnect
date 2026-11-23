/// Data models for Doctor Daily Schedule and Consultation Management (Phase 57).
library;

class ConsultationSession {
  final String id;
  final String appointmentId;
  final String doctorUserId;
  final String doctorProfileId;
  final String patientUserId;
  final String status; // NOT_STARTED | IN_PROGRESS | COMPLETED
  final DateTime? startedAt;
  final DateTime? completedAt;
  final String? startedBy;
  final String? completedBy;
  final String? notes;
  final int version;

  const ConsultationSession({
    required this.id,
    required this.appointmentId,
    required this.doctorUserId,
    required this.doctorProfileId,
    required this.patientUserId,
    required this.status,
    this.startedAt,
    this.completedAt,
    this.startedBy,
    this.completedBy,
    this.notes,
    this.version = 1,
  });

  bool get isInProgress => status.toUpperCase() == 'IN_PROGRESS';
  bool get isCompleted => status.toUpperCase() == 'COMPLETED';
  bool get isNotStarted => status.toUpperCase() == 'NOT_STARTED';

  ConsultationSession copyWith({
    String? id,
    String? appointmentId,
    String? doctorUserId,
    String? doctorProfileId,
    String? patientUserId,
    String? status,
    DateTime? startedAt,
    DateTime? completedAt,
    String? startedBy,
    String? completedBy,
    String? notes,
    int? version,
  }) {
    return ConsultationSession(
      id: id ?? this.id,
      appointmentId: appointmentId ?? this.appointmentId,
      doctorUserId: doctorUserId ?? this.doctorUserId,
      doctorProfileId: doctorProfileId ?? this.doctorProfileId,
      patientUserId: patientUserId ?? this.patientUserId,
      status: status ?? this.status,
      startedAt: startedAt ?? this.startedAt,
      completedAt: completedAt ?? this.completedAt,
      startedBy: startedBy ?? this.startedBy,
      completedBy: completedBy ?? this.completedBy,
      notes: notes ?? this.notes,
      version: version ?? this.version,
    );
  }

  factory ConsultationSession.fromJson(Map<String, dynamic> json) {
    return ConsultationSession(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      appointmentId: json['appointmentId']?.toString() ?? '',
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorProfileId: json['doctorProfileId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      status: json['status']?.toString() ?? 'NOT_STARTED',
      startedAt: json['startedAt'] != null ? DateTime.tryParse(json['startedAt'].toString()) : null,
      completedAt: json['completedAt'] != null ? DateTime.tryParse(json['completedAt'].toString()) : null,
      startedBy: json['startedBy']?.toString(),
      completedBy: json['completedBy']?.toString(),
      notes: json['notes']?.toString(),
      version: json['version'] is int ? json['version'] as int : 1,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'appointmentId': appointmentId,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'patientUserId': patientUserId,
      'status': status,
      if (startedAt != null) 'startedAt': startedAt!.toIso8601String(),
      if (completedAt != null) 'completedAt': completedAt!.toIso8601String(),
      if (startedBy != null) 'startedBy': startedBy,
      if (completedBy != null) 'completedBy': completedBy,
      if (notes != null) 'notes': notes,
      'version': version,
    };
  }
}

class DailyScheduleStats {
  final String date;
  final String timezone;
  final int totalScheduled;
  final int upcoming;
  final int waiting;
  final int inProgress;
  final int completed;
  final int cancelled;

  const DailyScheduleStats({
    required this.date,
    this.timezone = 'Asia/Colombo',
    this.totalScheduled = 0,
    this.upcoming = 0,
    this.waiting = 0,
    this.inProgress = 0,
    this.completed = 0,
    this.cancelled = 0,
  });

  DailyScheduleStats copyWith({
    String? date,
    String? timezone,
    int? totalScheduled,
    int? upcoming,
    int? waiting,
    int? inProgress,
    int? completed,
    int? cancelled,
  }) {
    return DailyScheduleStats(
      date: date ?? this.date,
      timezone: timezone ?? this.timezone,
      totalScheduled: totalScheduled ?? this.totalScheduled,
      upcoming: upcoming ?? this.upcoming,
      waiting: waiting ?? this.waiting,
      inProgress: inProgress ?? this.inProgress,
      completed: completed ?? this.completed,
      cancelled: cancelled ?? this.cancelled,
    );
  }

  factory DailyScheduleStats.fromJson(Map<String, dynamic> json) {
    return DailyScheduleStats(
      date: json['date']?.toString() ?? '',
      timezone: json['timezone']?.toString() ?? 'Asia/Colombo',
      totalScheduled: json['totalScheduled'] is int ? json['totalScheduled'] as int : 0,
      upcoming: json['upcoming'] is int ? json['upcoming'] as int : 0,
      waiting: json['waiting'] is int ? json['waiting'] as int : 0,
      inProgress: json['inProgress'] is int ? json['inProgress'] as int : 0,
      completed: json['completed'] is int ? json['completed'] as int : 0,
      cancelled: json['cancelled'] is int ? json['cancelled'] as int : 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'timezone': timezone,
      'totalScheduled': totalScheduled,
      'upcoming': upcoming,
      'waiting': waiting,
      'inProgress': inProgress,
      'completed': completed,
      'cancelled': cancelled,
    };
  }
}

class ScheduleAppointmentItem {
  final String appointmentId;
  final String appointmentDate;
  final String startTime;
  final String endTime;
  final String bookingStatus;
  final String consultationStatus;
  final double consultationFee;

  final String patientUserId;
  final String patientName;
  final String? patientEmail;
  final String? patientPhone;
  final String? patientNote;

  final String? consultationSessionId;
  final DateTime? startedAt;
  final DateTime? completedAt;

  final bool hasPrescription;
  final bool hasMedicalRecord;
  final bool hasCarePlan;

  final String? prescriptionId;
  final String? medicalRecordId;
  final String? carePlanId;

  const ScheduleAppointmentItem({
    required this.appointmentId,
    required this.appointmentDate,
    required this.startTime,
    required this.endTime,
    required this.bookingStatus,
    this.consultationStatus = 'NOT_STARTED',
    this.consultationFee = 2500.0,
    required this.patientUserId,
    required this.patientName,
    this.patientEmail,
    this.patientPhone,
    this.patientNote,
    this.consultationSessionId,
    this.startedAt,
    this.completedAt,
    this.hasPrescription = false,
    this.hasMedicalRecord = false,
    this.hasCarePlan = false,
    this.prescriptionId,
    this.medicalRecordId,
    this.carePlanId,
  });

  bool get isInProgress => consultationStatus.toUpperCase() == 'IN_PROGRESS';
  bool get isCompleted => consultationStatus.toUpperCase() == 'COMPLETED';
  bool get isNotStarted => consultationStatus.toUpperCase() == 'NOT_STARTED';
  bool get isCancelled => bookingStatus.toUpperCase() == 'CANCELLED';

  ScheduleAppointmentItem copyWith({
    String? appointmentId,
    String? appointmentDate,
    String? startTime,
    String? endTime,
    String? bookingStatus,
    String? consultationStatus,
    double? consultationFee,
    String? patientUserId,
    String? patientName,
    String? patientEmail,
    String? patientPhone,
    String? patientNote,
    String? consultationSessionId,
    DateTime? startedAt,
    DateTime? completedAt,
    bool? hasPrescription,
    bool? hasMedicalRecord,
    bool? hasCarePlan,
    String? prescriptionId,
    String? medicalRecordId,
    String? carePlanId,
  }) {
    return ScheduleAppointmentItem(
      appointmentId: appointmentId ?? this.appointmentId,
      appointmentDate: appointmentDate ?? this.appointmentDate,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      bookingStatus: bookingStatus ?? this.bookingStatus,
      consultationStatus: consultationStatus ?? this.consultationStatus,
      consultationFee: consultationFee ?? this.consultationFee,
      patientUserId: patientUserId ?? this.patientUserId,
      patientName: patientName ?? this.patientName,
      patientEmail: patientEmail ?? this.patientEmail,
      patientPhone: patientPhone ?? this.patientPhone,
      patientNote: patientNote ?? this.patientNote,
      consultationSessionId: consultationSessionId ?? this.consultationSessionId,
      startedAt: startedAt ?? this.startedAt,
      completedAt: completedAt ?? this.completedAt,
      hasPrescription: hasPrescription ?? this.hasPrescription,
      hasMedicalRecord: hasMedicalRecord ?? this.hasMedicalRecord,
      hasCarePlan: hasCarePlan ?? this.hasCarePlan,
      prescriptionId: prescriptionId ?? this.prescriptionId,
      medicalRecordId: medicalRecordId ?? this.medicalRecordId,
      carePlanId: carePlanId ?? this.carePlanId,
    );
  }

  factory ScheduleAppointmentItem.fromJson(Map<String, dynamic> json) {
    return ScheduleAppointmentItem(
      appointmentId: json['appointmentId']?.toString() ?? '',
      appointmentDate: json['appointmentDate']?.toString() ?? '',
      startTime: json['startTime']?.toString() ?? '',
      endTime: json['endTime']?.toString() ?? '',
      bookingStatus: json['bookingStatus']?.toString() ?? 'PENDING',
      consultationStatus: json['consultationStatus']?.toString() ?? 'NOT_STARTED',
      consultationFee: (json['consultationFee'] is num) ? (json['consultationFee'] as num).toDouble() : 2500.0,
      patientUserId: json['patientUserId']?.toString() ?? '',
      patientName: json['patientName']?.toString() ?? 'Patient',
      patientEmail: json['patientEmail']?.toString(),
      patientPhone: json['patientPhone']?.toString(),
      patientNote: json['patientNote']?.toString(),
      consultationSessionId: json['consultationSessionId']?.toString(),
      startedAt: json['startedAt'] != null ? DateTime.tryParse(json['startedAt'].toString()) : null,
      completedAt: json['completedAt'] != null ? DateTime.tryParse(json['completedAt'].toString()) : null,
      hasPrescription: json['hasPrescription'] == true,
      hasMedicalRecord: json['hasMedicalRecord'] == true,
      hasCarePlan: json['hasCarePlan'] == true,
      prescriptionId: json['prescriptionId']?.toString(),
      medicalRecordId: json['medicalRecordId']?.toString(),
      carePlanId: json['carePlanId']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'appointmentId': appointmentId,
      'appointmentDate': appointmentDate,
      'startTime': startTime,
      'endTime': endTime,
      'bookingStatus': bookingStatus,
      'consultationStatus': consultationStatus,
      'consultationFee': consultationFee,
      'patientUserId': patientUserId,
      'patientName': patientName,
      if (patientEmail != null) 'patientEmail': patientEmail,
      if (patientPhone != null) 'patientPhone': patientPhone,
      if (patientNote != null) 'patientNote': patientNote,
      if (consultationSessionId != null) 'consultationSessionId': consultationSessionId,
      if (startedAt != null) 'startedAt': startedAt!.toIso8601String(),
      if (completedAt != null) 'completedAt': completedAt!.toIso8601String(),
      'hasPrescription': hasPrescription,
      'hasMedicalRecord': hasMedicalRecord,
      'hasCarePlan': hasCarePlan,
      if (prescriptionId != null) 'prescriptionId': prescriptionId,
      if (medicalRecordId != null) 'medicalRecordId': medicalRecordId,
      if (carePlanId != null) 'carePlanId': carePlanId,
    };
  }
}

class DoctorDailySchedule {
  final String date;
  final String timezone;
  final DailyScheduleStats stats;
  final ScheduleAppointmentItem? nextPatient;
  final List<ScheduleAppointmentItem> appointments;

  const DoctorDailySchedule({
    required this.date,
    required this.timezone,
    required this.stats,
    this.nextPatient,
    this.appointments = const [],
  });

  DoctorDailySchedule copyWith({
    String? date,
    String? timezone,
    DailyScheduleStats? stats,
    ScheduleAppointmentItem? nextPatient,
    List<ScheduleAppointmentItem>? appointments,
  }) {
    return DoctorDailySchedule(
      date: date ?? this.date,
      timezone: timezone ?? this.timezone,
      stats: stats ?? this.stats,
      nextPatient: nextPatient,
      appointments: appointments ?? this.appointments,
    );
  }

  factory DoctorDailySchedule.fromJson(Map<String, dynamic> json) {
    return DoctorDailySchedule(
      date: json['date']?.toString() ?? '',
      timezone: json['timezone']?.toString() ?? 'Asia/Colombo',
      stats: json['stats'] is Map<String, dynamic>
          ? DailyScheduleStats.fromJson(json['stats'] as Map<String, dynamic>)
          : DailyScheduleStats(date: json['date']?.toString() ?? ''),
      nextPatient: json['nextPatient'] is Map<String, dynamic>
          ? ScheduleAppointmentItem.fromJson(json['nextPatient'] as Map<String, dynamic>)
          : null,
      appointments: json['appointments'] is List
          ? (json['appointments'] as List)
              .map((e) => ScheduleAppointmentItem.fromJson(e as Map<String, dynamic>))
              .toList()
          : [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'timezone': timezone,
      'stats': stats.toJson(),
      if (nextPatient != null) 'nextPatient': nextPatient!.toJson(),
      'appointments': appointments.map((e) => e.toJson()).toList(),
    };
  }
}

class ConsultationDetail {
  final ScheduleAppointmentItem appointment;
  final ConsultationSession? session;
  final Map<String, dynamic>? medicalRecord;
  final Map<String, dynamic>? prescription;
  final Map<String, dynamic>? carePlan;

  const ConsultationDetail({
    required this.appointment,
    this.session,
    this.medicalRecord,
    this.prescription,
    this.carePlan,
  });

  factory ConsultationDetail.fromJson(Map<String, dynamic> json) {
    return ConsultationDetail(
      appointment: json['appointment'] is Map<String, dynamic>
          ? ScheduleAppointmentItem.fromJson(json['appointment'] as Map<String, dynamic>)
          : ScheduleAppointmentItem(
              appointmentId: '',
              appointmentDate: '',
              startTime: '',
              endTime: '',
              bookingStatus: '',
              patientUserId: '',
              patientName: '',
            ),
      session: json['session'] is Map<String, dynamic>
          ? ConsultationSession.fromJson(json['session'] as Map<String, dynamic>)
          : null,
      medicalRecord: json['medicalRecord'] is Map<String, dynamic>
          ? json['medicalRecord'] as Map<String, dynamic>
          : null,
      prescription: json['prescription'] is Map<String, dynamic>
          ? json['prescription'] as Map<String, dynamic>
          : null,
      carePlan: json['carePlan'] is Map<String, dynamic>
          ? json['carePlan'] as Map<String, dynamic>
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'appointment': appointment.toJson(),
      if (session != null) 'session': session!.toJson(),
      if (medicalRecord != null) 'medicalRecord': medicalRecord,
      if (prescription != null) 'prescription': prescription,
      if (carePlan != null) 'carePlan': carePlan,
    };
  }
}
