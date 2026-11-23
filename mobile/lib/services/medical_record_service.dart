import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/medical_record.dart';
import '../models/prescription.dart';

/// Service communicating with the MediConnect backend for Medical Records & Prescriptions (Phase 21).
class MedicalRecordService {
  final ApiClient _apiClient;

  MedicalRecordService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  // -------------------------------------------------------------------------
  // Patient Operations
  // -------------------------------------------------------------------------

  /// Fetch authenticated patient's consultation records.
  Future<List<MedicalRecord>> getPatientMedicalRecords({int page = 1, int pageSize = 20}) async {
    final response = await _apiClient.get(
      '${ApiConstants.myMedicalRecordsEndpoint}?page=$page&page_size=$pageSize',
      includeAuth: true,
    );

    if (response is Map<String, dynamic> && response['items'] is List) {
      final items = response['items'] as List;
      return items.map((e) => MedicalRecord.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  /// Fetch specific consultation record details.
  Future<MedicalRecord> getMedicalRecordDetail(String recordId) async {
    final response = await _apiClient.get(
      ApiConstants.medicalRecordDetailEndpoint(recordId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return MedicalRecord.fromJson(response);
    }
    throw Exception('Failed to load consultation medical record details.');
  }

  /// Fetch authenticated patient's issued digital prescriptions.
  Future<List<Prescription>> getPatientPrescriptions({int page = 1, int pageSize = 20}) async {
    final response = await _apiClient.get(
      '${ApiConstants.myPrescriptionsEndpoint}?page=$page&page_size=$pageSize',
      includeAuth: true,
    );

    if (response is Map<String, dynamic> && response['items'] is List) {
      final items = response['items'] as List;
      return items.map((e) => Prescription.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  /// Fetch specific digital prescription details.
  Future<Prescription> getPrescriptionDetail(String prescriptionId) async {
    final response = await _apiClient.get(
      ApiConstants.prescriptionDetailEndpoint(prescriptionId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return Prescription.fromJson(response);
    }
    throw Exception('Failed to load digital prescription details.');
  }

  /// Securely download official PDF bytes for an issued prescription.
  Future<List<int>> downloadPrescriptionPdf(String prescriptionId) async {
    return _apiClient.getBytes(
      ApiConstants.prescriptionPdfEndpoint(prescriptionId),
      includeAuth: true,
    );
  }

  // -------------------------------------------------------------------------
  // Doctor Operations
  // -------------------------------------------------------------------------

  /// Retrieve completed appointments available for clinical documentation.
  Future<List<Map<String, dynamic>>> getDoctorCompletedAppointments() async {
    final response = await _apiClient.get(
      ApiConstants.doctorMyAppointmentsEndpoint,
      includeAuth: true,
    );

    if (response is List) {
      return response
          .whereType<Map<String, dynamic>>()
          .where((appt) {
            final status = appt['status']?.toString().toUpperCase();
            return status == 'COMPLETED' || status == 'CONFIRMED';
          })
          .toList();
    }
    return [];
  }

  /// Document a new consultation record for a completed appointment.
  Future<MedicalRecord> createMedicalRecord({
    required String appointmentId,
    required String clinicalNotes,
    required String assessment,
    required String treatmentPlan,
    String? followUpInstructions,
  }) async {
    final body = {
      'appointmentId': appointmentId,
      'clinicalNotes': clinicalNotes.trim(),
      'assessment': assessment.trim(),
      'treatmentPlan': treatmentPlan.trim(),
      if (followUpInstructions != null && followUpInstructions.trim().isNotEmpty)
        'followUpInstructions': followUpInstructions.trim(),
    };

    final response = await _apiClient.post(
      ApiConstants.medicalRecordsEndpoint,
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return MedicalRecord.fromJson(response);
    }
    throw Exception('Failed to create consultation medical record.');
  }

  /// Safely amend an existing consultation record with mandatory audit reason.
  Future<MedicalRecord> amendMedicalRecord({
    required String recordId,
    required String amendmentReason,
    required String clinicalNotes,
    required String assessment,
    required String treatmentPlan,
    String? followUpInstructions,
  }) async {
    final body = {
      'amendmentReason': amendmentReason.trim(),
      'clinicalNotes': clinicalNotes.trim(),
      'assessment': assessment.trim(),
      'treatmentPlan': treatmentPlan.trim(),
      if (followUpInstructions != null && followUpInstructions.trim().isNotEmpty)
        'followUpInstructions': followUpInstructions.trim(),
    };

    final response = await _apiClient.patch(
      ApiConstants.medicalRecordDetailEndpoint(recordId),
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return MedicalRecord.fromJson(response);
    }
    throw Exception('Failed to amend medical record.');
  }

  /// Issue a structured digital prescription.
  Future<Prescription> createPrescription({
    required String medicalRecordId,
    required String appointmentId,
    required List<MedicationItem> medicationItems,
    String? instructions,
  }) async {
    final body = {
      'medicalRecordId': medicalRecordId,
      'appointmentId': appointmentId,
      'medicationItems': medicationItems.map((e) => e.toJson()).toList(),
      if (instructions != null && instructions.trim().isNotEmpty)
        'instructions': instructions.trim(),
    };

    final response = await _apiClient.post(
      ApiConstants.prescriptionsEndpoint,
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return Prescription.fromJson(response);
    }
    throw Exception('Failed to issue digital prescription.');
  }

  /// Amend an issued prescription with mandatory audit reason.
  Future<Prescription> amendPrescription({
    required String prescriptionId,
    required String amendmentReason,
    required List<MedicationItem> medicationItems,
    String? instructions,
  }) async {
    final body = {
      'amendmentReason': amendmentReason.trim(),
      'medicationItems': medicationItems.map((e) => e.toJson()).toList(),
      if (instructions != null && instructions.trim().isNotEmpty)
        'instructions': instructions.trim(),
    };

    final response = await _apiClient.patch(
      ApiConstants.prescriptionDetailEndpoint(prescriptionId),
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return Prescription.fromJson(response);
    }
    throw Exception('Failed to amend digital prescription.');
  }
}
