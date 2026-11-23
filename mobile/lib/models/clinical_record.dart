// Models for Advanced Healthcare AI, Medical Records & Clinical Automation (Phase 6).

class PatientMedicalRecord {
  final String id;
  final String recordId;
  final String patientUserId;
  final String recordType;
  final String sourceType;
  final String authorId;
  final String authorRole;
  final String? authorName;
  final String title;
  final String? description;
  final String clinicalDate;
  final Map<String, dynamic> clinicalData;
  final bool hasAttachment;
  final String? attachmentName;
  final int? attachmentSize;
  final String? attachmentMimeType;
  final String status;
  final int version;
  final bool isAiGenerated;
  final DateTime createdAt;

  PatientMedicalRecord({
    required this.id,
    required this.recordId,
    required this.patientUserId,
    required this.recordType,
    required this.sourceType,
    required this.authorId,
    required this.authorRole,
    this.authorName,
    required this.title,
    this.description,
    required this.clinicalDate,
    required this.clinicalData,
    this.hasAttachment = false,
    this.attachmentName,
    this.attachmentSize,
    this.attachmentMimeType,
    required this.status,
    required this.version,
    this.isAiGenerated = false,
    required this.createdAt,
  });

  factory PatientMedicalRecord.fromJson(Map<String, dynamic> json) {
    return PatientMedicalRecord(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      recordId: json['recordId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      recordType: json['recordType']?.toString() ?? 'medical_document',
      sourceType: json['sourceType']?.toString() ?? 'patient_uploaded',
      authorId: json['authorId']?.toString() ?? '',
      authorRole: json['authorRole']?.toString() ?? 'PATIENT',
      authorName: json['authorName']?.toString(),
      title: json['title']?.toString() ?? 'Clinical Record',
      description: json['description']?.toString(),
      clinicalDate: json['clinicalDate']?.toString() ?? '',
      clinicalData: json['clinicalData'] is Map ? Map<String, dynamic>.from(json['clinicalData']) : {},
      hasAttachment: json['hasAttachment'] == true,
      attachmentName: json['attachmentName']?.toString(),
      attachmentSize: json['attachmentSize'] is int ? json['attachmentSize'] : null,
      attachmentMimeType: json['attachmentMimeType']?.toString(),
      status: json['status']?.toString() ?? 'active',
      version: json['version'] is int ? json['version'] : 1,
      isAiGenerated: json['isAiGenerated'] == true,
      createdAt: json['createdAt'] != null ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now() : DateTime.now(),
    );
  }
}

class MedicalRecordSummary {
  final String patientUserId;
  final int recordsAnalyzed;
  final String summary;
  final List<String> diagnoses;
  final List<String> activeMedications;
  final List<String> documentedAllergies;
  final List<String> keyClinicalFindings;
  final String? missingInformationNotice;
  final String aiDisclaimer;

  MedicalRecordSummary({
    required this.patientUserId,
    required this.recordsAnalyzed,
    required this.summary,
    required this.diagnoses,
    required this.activeMedications,
    required this.documentedAllergies,
    required this.keyClinicalFindings,
    this.missingInformationNotice,
    required this.aiDisclaimer,
  });

  factory MedicalRecordSummary.fromJson(Map<String, dynamic> json) {
    return MedicalRecordSummary(
      patientUserId: json['patientUserId']?.toString() ?? '',
      recordsAnalyzed: json['recordsAnalyzed'] is int ? json['recordsAnalyzed'] : 0,
      summary: json['summary']?.toString() ?? '',
      diagnoses: (json['diagnoses'] as List?)?.map((e) => e.toString()).toList() ?? [],
      activeMedications: (json['activeMedications'] as List?)?.map((e) => e.toString()).toList() ?? [],
      documentedAllergies: (json['documentedAllergies'] as List?)?.map((e) => e.toString()).toList() ?? [],
      keyClinicalFindings: (json['keyClinicalFindings'] as List?)?.map((e) => e.toString()).toList() ?? [],
      missingInformationNotice: json['missingInformationNotice']?.toString(),
      aiDisclaimer: json['aiDisclaimer']?.toString() ?? '',
    );
  }
}

class SoapContent {
  final String chiefComplaint;
  final String historyOfPresentIllness;
  final String? pastMedicalHistory;
  final String examinationFindings;
  final String assessment;
  final String plan;
  final String? followUpInstructions;

  SoapContent({
    required this.chiefComplaint,
    required this.historyOfPresentIllness,
    this.pastMedicalHistory,
    required this.examinationFindings,
    required this.assessment,
    required this.plan,
    this.followUpInstructions,
  });

  factory SoapContent.fromJson(Map<String, dynamic> json) {
    return SoapContent(
      chiefComplaint: json['chiefComplaint']?.toString() ?? '',
      historyOfPresentIllness: json['historyOfPresentIllness']?.toString() ?? '',
      pastMedicalHistory: json['pastMedicalHistory']?.toString(),
      examinationFindings: json['examinationFindings']?.toString() ?? '',
      assessment: json['assessment']?.toString() ?? '',
      plan: json['plan']?.toString() ?? '',
      followUpInstructions: json['followUpInstructions']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'chiefComplaint': chiefComplaint,
    'historyOfPresentIllness': historyOfPresentIllness,
    if (pastMedicalHistory != null) 'pastMedicalHistory': pastMedicalHistory,
    'examinationFindings': examinationFindings,
    'assessment': assessment,
    'plan': plan,
    if (followUpInstructions != null) 'followUpInstructions': followUpInstructions,
  };
}

class ClinicalNote {
  final String id;
  final String noteId;
  final String patientUserId;
  final String? patientName;
  final String doctorUserId;
  final String? doctorName;
  final String? doctorSpecialty;
  final String? slmcRegistrationNumber;
  final String? appointmentId;
  final SoapContent content;
  final String status;
  final bool isAiDraft;
  final int version;
  final DateTime? signedAt;
  final DateTime createdAt;

  ClinicalNote({
    required this.id,
    required this.noteId,
    required this.patientUserId,
    this.patientName,
    required this.doctorUserId,
    this.doctorName,
    this.doctorSpecialty,
    this.slmcRegistrationNumber,
    this.appointmentId,
    required this.content,
    required this.status,
    required this.isAiDraft,
    required this.version,
    this.signedAt,
    required this.createdAt,
  });

  factory ClinicalNote.fromJson(Map<String, dynamic> json) {
    return ClinicalNote(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      noteId: json['noteId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      patientName: json['patientName']?.toString(),
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorName: json['doctorName']?.toString(),
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      slmcRegistrationNumber: json['slmcRegistrationNumber']?.toString(),
      appointmentId: json['appointmentId']?.toString(),
      content: SoapContent.fromJson(json['content'] is Map ? Map<String, dynamic>.from(json['content']) : {}),
      status: json['status']?.toString() ?? 'draft',
      isAiDraft: json['isAiDraft'] == true,
      version: json['version'] is int ? json['version'] : 1,
      signedAt: json['signedAt'] != null ? DateTime.tryParse(json['signedAt'].toString()) : null,
      createdAt: json['createdAt'] != null ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now() : DateTime.now(),
    );
  }
}

class PrescriptionRenewal {
  final String id;
  final String renewalId;
  final String patientUserId;
  final String? patientName;
  final String originalPrescriptionId;
  final String medicationName;
  final Map<String, dynamic> medicationDetails;
  final String doctorUserId;
  final String? doctorName;
  final String status;
  final String? patientReason;
  final String? doctorDecisionReason;
  final String? consultationDetails;
  final String? resultingPrescriptionId;
  final DateTime requestedAt;
  final DateTime? reviewedAt;

  PrescriptionRenewal({
    required this.id,
    required this.renewalId,
    required this.patientUserId,
    this.patientName,
    required this.originalPrescriptionId,
    required this.medicationName,
    required this.medicationDetails,
    required this.doctorUserId,
    this.doctorName,
    required this.status,
    this.patientReason,
    this.doctorDecisionReason,
    this.consultationDetails,
    this.resultingPrescriptionId,
    required this.requestedAt,
    this.reviewedAt,
  });

  factory PrescriptionRenewal.fromJson(Map<String, dynamic> json) {
    return PrescriptionRenewal(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      renewalId: json['renewalId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      patientName: json['patientName']?.toString(),
      originalPrescriptionId: json['originalPrescriptionId']?.toString() ?? '',
      medicationName: json['medicationName']?.toString() ?? '',
      medicationDetails: json['medicationDetails'] is Map ? Map<String, dynamic>.from(json['medicationDetails']) : {},
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorName: json['doctorName']?.toString(),
      status: json['status']?.toString() ?? 'requested',
      patientReason: json['patientReason']?.toString(),
      doctorDecisionReason: json['doctorDecisionReason']?.toString(),
      consultationDetails: json['consultationDetails']?.toString(),
      resultingPrescriptionId: json['resultingPrescriptionId']?.toString(),
      requestedAt: json['requestedAt'] != null ? DateTime.tryParse(json['requestedAt'].toString()) ?? DateTime.now() : DateTime.now(),
      reviewedAt: json['reviewedAt'] != null ? DateTime.tryParse(json['reviewedAt'].toString()) : null,
    );
  }
}

class HealthMeasurement {
  final String id;
  final String measurementId;
  final String patientUserId;
  final String metric;
  final double value;
  final double? secondary;
  final String unit;
  final String source;
  final String verificationStatus;
  final String? notes;
  final String? criticalAlert;
  final DateTime measuredAt;

  HealthMeasurement({
    required this.id,
    required this.measurementId,
    required this.patientUserId,
    required this.metric,
    required this.value,
    this.secondary,
    required this.unit,
    required this.source,
    required this.verificationStatus,
    this.notes,
    this.criticalAlert,
    required this.measuredAt,
  });

  factory HealthMeasurement.fromJson(Map<String, dynamic> json) {
    return HealthMeasurement(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      measurementId: json['measurementId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      metric: json['metric']?.toString() ?? '',
      value: (json['value'] is num) ? (json['value'] as num).toDouble() : 0.0,
      secondary: (json['secondary'] is num) ? (json['secondary'] as num).toDouble() : null,
      unit: json['unit']?.toString() ?? '',
      source: json['source']?.toString() ?? 'patient_reported',
      verificationStatus: json['verificationStatus']?.toString() ?? 'unverified',
      notes: json['notes']?.toString(),
      criticalAlert: json['criticalAlert']?.toString(),
      measuredAt: json['measuredAt'] != null ? DateTime.tryParse(json['measuredAt'].toString()) ?? DateTime.now() : DateTime.now(),
    );
  }
}

class MetricTrendSummary {
  final String metric;
  final String unit;
  final int count;
  final double? latestValue;
  final double? latestSecondary;
  final DateTime? latestDate;
  final double? sevenDayAverage;
  final double? thirtyDayAverage;
  final double? minValue;
  final double? maxValue;
  final String trendDirection;
  final String? clinicalNotice;

  MetricTrendSummary({
    required this.metric,
    required this.unit,
    required this.count,
    this.latestValue,
    this.latestSecondary,
    this.latestDate,
    this.sevenDayAverage,
    this.thirtyDayAverage,
    this.minValue,
    this.maxValue,
    required this.trendDirection,
    this.clinicalNotice,
  });

  factory MetricTrendSummary.fromJson(Map<String, dynamic> json) {
    return MetricTrendSummary(
      metric: json['metric']?.toString() ?? '',
      unit: json['unit']?.toString() ?? '',
      count: json['count'] is int ? json['count'] : 0,
      latestValue: (json['latestValue'] is num) ? (json['latestValue'] as num).toDouble() : null,
      latestSecondary: (json['latestSecondary'] is num) ? (json['latestSecondary'] as num).toDouble() : null,
      latestDate: json['latestDate'] != null ? DateTime.tryParse(json['latestDate'].toString()) : null,
      sevenDayAverage: (json['sevenDayAverage'] is num) ? (json['sevenDayAverage'] as num).toDouble() : null,
      thirtyDayAverage: (json['thirtyDayAverage'] is num) ? (json['thirtyDayAverage'] as num).toDouble() : null,
      minValue: (json['minValue'] is num) ? (json['minValue'] as num).toDouble() : null,
      maxValue: (json['maxValue'] is num) ? (json['maxValue'] as num).toDouble() : null,
      trendDirection: json['trendDirection']?.toString() ?? 'INSUFFICIENT_DATA',
      clinicalNotice: json['clinicalNotice']?.toString(),
    );
  }
}

class HealthTrends {
  final String patientUserId;
  final List<MetricTrendSummary> trends;
  final List<String> criticalAlerts;

  HealthTrends({
    required this.patientUserId,
    required this.trends,
    required this.criticalAlerts,
  });

  factory HealthTrends.fromJson(Map<String, dynamic> json) {
    final trendsList = (json['trends'] as List?)
            ?.map((e) => MetricTrendSummary.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList() ??
        [];
    final alertsList = (json['criticalAlerts'] as List?)?.map((e) => e.toString()).toList() ?? [];

    return HealthTrends(
      patientUserId: json['patientUserId']?.toString() ?? '',
      trends: trendsList,
      criticalAlerts: alertsList,
    );
  }
}
