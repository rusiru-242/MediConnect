// Data models for Patient Consultation Medical Records (Phase 21).

import 'prescription.dart';

class MedicalRecord {
  final String id;
  final String recordId;
  final String patientUserId;
  final String? patientName;
  final String doctorUserId;
  final String? doctorName;
  final String? doctorSpecialty;
  final String? slmcRegistrationNumber;
  final String? hospitalOrClinic;
  final String appointmentId;
  final String consultationDate;
  final String clinicalNotes;
  final String assessment;
  final String treatmentPlan;
  final String? followUpInstructions;
  final String status;
  final Prescription? prescription;
  final List<Map<String, dynamic>> amendmentHistory;
  final DateTime createdAt;
  final DateTime updatedAt;

  const MedicalRecord({
    required this.id,
    required this.recordId,
    required this.patientUserId,
    this.patientName,
    required this.doctorUserId,
    this.doctorName,
    this.doctorSpecialty,
    this.slmcRegistrationNumber,
    this.hospitalOrClinic,
    required this.appointmentId,
    required this.consultationDate,
    required this.clinicalNotes,
    required this.assessment,
    required this.treatmentPlan,
    this.followUpInstructions,
    required this.status,
    this.prescription,
    this.amendmentHistory = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  factory MedicalRecord.fromJson(Map<String, dynamic> json) {
    Prescription? parsedPrescription;
    if (json['prescription'] != null && json['prescription'] is Map<String, dynamic>) {
      parsedPrescription = Prescription.fromJson(json['prescription'] as Map<String, dynamic>);
    }

    final rawAmendments = json['amendmentHistory'];
    final amendmentsList = <Map<String, dynamic>>[];
    if (rawAmendments is List) {
      for (final a in rawAmendments) {
        if (a is Map<String, dynamic>) {
          amendmentsList.add(a);
        }
      }
    }

    DateTime parsedCreated = DateTime.now();
    if (json['createdAt'] != null) {
      parsedCreated = DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now();
    }
    DateTime parsedUpdated = parsedCreated;
    if (json['updatedAt'] != null) {
      parsedUpdated = DateTime.tryParse(json['updatedAt'].toString()) ?? parsedCreated;
    }

    return MedicalRecord(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      recordId: json['recordId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      patientName: json['patientName']?.toString(),
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorName: json['doctorName']?.toString(),
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      slmcRegistrationNumber: json['slmcRegistrationNumber']?.toString(),
      hospitalOrClinic: json['hospitalOrClinic']?.toString(),
      appointmentId: json['appointmentId']?.toString() ?? '',
      consultationDate: json['consultationDate']?.toString() ?? '',
      clinicalNotes: json['clinicalNotes']?.toString() ?? '',
      assessment: json['assessment']?.toString() ?? '',
      treatmentPlan: json['treatmentPlan']?.toString() ?? '',
      followUpInstructions: json['followUpInstructions']?.toString(),
      status: json['status']?.toString() ?? 'ACTIVE',
      prescription: parsedPrescription,
      amendmentHistory: amendmentsList,
      createdAt: parsedCreated,
      updatedAt: parsedUpdated,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'recordId': recordId,
      'patientUserId': patientUserId,
      'patientName': patientName,
      'doctorUserId': doctorUserId,
      'doctorName': doctorName,
      'doctorSpecialty': doctorSpecialty,
      'slmcRegistrationNumber': slmcRegistrationNumber,
      'hospitalOrClinic': hospitalOrClinic,
      'appointmentId': appointmentId,
      'consultationDate': consultationDate,
      'clinicalNotes': clinicalNotes,
      'assessment': assessment,
      'treatmentPlan': treatmentPlan,
      'followUpInstructions': followUpInstructions,
      'status': status,
      if (prescription != null) 'prescription': prescription!.toJson(),
      'amendmentHistory': amendmentHistory,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
    };
  }
}
