/// Data models for Patient Healthcare Timeline & Visit History (Phase 58).
library;

class TimelineEvent {
  final String eventId;
  final String eventType;
  final String category;
  final DateTime occurredAt;
  final String displayDate;
  final String? displayTime;
  final String title;
  final String description;
  final String? doctorUserId;
  final String? doctorDisplayName;
  final String? doctorSpecialty;
  final String? hospitalOrClinic;
  final String sourceType;
  final String sourceId;
  final String? appointmentId;
  final String? status;
  final List<String> availableActions;
  final Map<String, dynamic> metadata;

  const TimelineEvent({
    required this.eventId,
    required this.eventType,
    required this.category,
    required this.occurredAt,
    required this.displayDate,
    this.displayTime,
    required this.title,
    required this.description,
    this.doctorUserId,
    this.doctorDisplayName,
    this.doctorSpecialty,
    this.hospitalOrClinic,
    required this.sourceType,
    required this.sourceId,
    this.appointmentId,
    this.status,
    this.availableActions = const [],
    this.metadata = const {},
  });

  factory TimelineEvent.fromJson(Map<String, dynamic> json) {
    return TimelineEvent(
      eventId: json['eventId']?.toString() ?? '',
      eventType: json['eventType']?.toString() ?? '',
      category: json['category']?.toString() ?? 'ALL',
      occurredAt: json['occurredAt'] != null
          ? DateTime.tryParse(json['occurredAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      displayDate: json['displayDate']?.toString() ?? '',
      displayTime: json['displayTime']?.toString(),
      title: json['title']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      doctorUserId: json['doctorUserId']?.toString(),
      doctorDisplayName: json['doctorDisplayName']?.toString(),
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      hospitalOrClinic: json['hospitalOrClinic']?.toString(),
      sourceType: json['sourceType']?.toString() ?? '',
      sourceId: json['sourceId']?.toString() ?? '',
      appointmentId: json['appointmentId']?.toString(),
      status: json['status']?.toString(),
      availableActions: json['availableActions'] is List
          ? (json['availableActions'] as List).map((e) => e.toString()).toList()
          : const [],
      metadata: json['metadata'] is Map<String, dynamic>
          ? json['metadata'] as Map<String, dynamic>
          : const {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'eventId': eventId,
      'eventType': eventType,
      'category': category,
      'occurredAt': occurredAt.toIso8601String(),
      'displayDate': displayDate,
      if (displayTime != null) 'displayTime': displayTime,
      'title': title,
      'description': description,
      if (doctorUserId != null) 'doctorUserId': doctorUserId,
      if (doctorDisplayName != null) 'doctorDisplayName': doctorDisplayName,
      if (doctorSpecialty != null) 'doctorSpecialty': doctorSpecialty,
      if (hospitalOrClinic != null) 'hospitalOrClinic': hospitalOrClinic,
      'sourceType': sourceType,
      'sourceId': sourceId,
      if (appointmentId != null) 'appointmentId': appointmentId,
      if (status != null) 'status': status,
      'availableActions': availableActions,
      'metadata': metadata,
    };
  }
}

class TimelineResponse {
  final List<TimelineEvent> events;
  final String? nextCursor;
  final int totalCount;
  final bool hasMore;

  const TimelineResponse({
    this.events = const [],
    this.nextCursor,
    this.totalCount = 0,
    this.hasMore = false,
  });

  factory TimelineResponse.fromJson(Map<String, dynamic> json) {
    final list = json['events'];
    final parsedEvents = <TimelineEvent>[];
    if (list is List) {
      for (final item in list) {
        if (item is Map<String, dynamic>) {
          parsedEvents.add(TimelineEvent.fromJson(item));
        }
      }
    }
    return TimelineResponse(
      events: parsedEvents,
      nextCursor: json['nextCursor']?.toString(),
      totalCount: json['totalCount'] is int ? json['totalCount'] as int : parsedEvents.length,
      hasMore: json['hasMore'] == true,
    );
  }
}

class TimelineSummary {
  final int totalEvents;
  final int upcomingAppointmentsCount;
  final int completedConsultationsCount;
  final int prescriptionsCount;
  final int medicalRecordsCount;
  final int activeCarePlansCount;

  const TimelineSummary({
    this.totalEvents = 0,
    this.upcomingAppointmentsCount = 0,
    this.completedConsultationsCount = 0,
    this.prescriptionsCount = 0,
    this.medicalRecordsCount = 0,
    this.activeCarePlansCount = 0,
  });

  factory TimelineSummary.fromJson(Map<String, dynamic> json) {
    return TimelineSummary(
      totalEvents: json['totalEvents'] is int ? json['totalEvents'] as int : 0,
      upcomingAppointmentsCount: json['upcomingAppointmentsCount'] is int ? json['upcomingAppointmentsCount'] as int : 0,
      completedConsultationsCount: json['completedConsultationsCount'] is int ? json['completedConsultationsCount'] as int : 0,
      prescriptionsCount: json['prescriptionsCount'] is int ? json['prescriptionsCount'] as int : 0,
      medicalRecordsCount: json['medicalRecordsCount'] is int ? json['medicalRecordsCount'] as int : 0,
      activeCarePlansCount: json['activeCarePlansCount'] is int ? json['activeCarePlansCount'] as int : 0,
    );
  }
}

class VisitDetail {
  final String appointmentId;
  final String? appointmentNumber;
  final String appointmentDate;
  final String startTime;
  final String endTime;
  final String bookingStatus;
  final String consultationStatus;
  final double consultationFee;

  final String doctorUserId;
  final String doctorName;
  final String? doctorSpecialty;
  final String? doctorHospital;

  final String? patientNote;
  final String? cancelledBy;
  final String? cancellationReason;

  final Map<String, dynamic>? consultationSession;
  final Map<String, dynamic>? prescription;
  final Map<String, dynamic>? medicalRecord;
  final Map<String, dynamic>? carePlan;
  final List<TimelineEvent> timelineEvents;

  const VisitDetail({
    required this.appointmentId,
    this.appointmentNumber,
    required this.appointmentDate,
    required this.startTime,
    required this.endTime,
    required this.bookingStatus,
    required this.consultationStatus,
    this.consultationFee = 2500.0,
    required this.doctorUserId,
    required this.doctorName,
    this.doctorSpecialty,
    this.doctorHospital,
    this.patientNote,
    this.cancelledBy,
    this.cancellationReason,
    this.consultationSession,
    this.prescription,
    this.medicalRecord,
    this.carePlan,
    this.timelineEvents = const [],
  });

  factory VisitDetail.fromJson(Map<String, dynamic> json) {
    final list = json['timelineEvents'];
    final parsedEvents = <TimelineEvent>[];
    if (list is List) {
      for (final item in list) {
        if (item is Map<String, dynamic>) {
          parsedEvents.add(TimelineEvent.fromJson(item));
        }
      }
    }

    return VisitDetail(
      appointmentId: json['appointmentId']?.toString() ?? '',
      appointmentNumber: json['appointmentNumber']?.toString(),
      appointmentDate: json['appointmentDate']?.toString() ?? '',
      startTime: json['startTime']?.toString() ?? '',
      endTime: json['endTime']?.toString() ?? '',
      bookingStatus: json['bookingStatus']?.toString() ?? 'PENDING',
      consultationStatus: json['consultationStatus']?.toString() ?? 'NOT_STARTED',
      consultationFee: (json['consultationFee'] is num) ? (json['consultationFee'] as num).toDouble() : 2500.0,
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorName: json['doctorName']?.toString() ?? 'Doctor',
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      doctorHospital: json['doctorHospital']?.toString(),
      patientNote: json['patientNote']?.toString(),
      cancelledBy: json['cancelledBy']?.toString(),
      cancellationReason: json['cancellationReason']?.toString(),
      consultationSession: json['consultationSession'] is Map<String, dynamic> ? json['consultationSession'] as Map<String, dynamic> : null,
      prescription: json['prescription'] is Map<String, dynamic> ? json['prescription'] as Map<String, dynamic> : null,
      medicalRecord: json['medicalRecord'] is Map<String, dynamic> ? json['medicalRecord'] as Map<String, dynamic> : null,
      carePlan: json['carePlan'] is Map<String, dynamic> ? json['carePlan'] as Map<String, dynamic> : null,
      timelineEvents: parsedEvents,
    );
  }
}

