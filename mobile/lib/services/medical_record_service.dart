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
  /// A04-BUG-011: the endpoint returns a page object ({items, page, totalPages}); only a bare list was read, so
  /// the documentation screen was always empty and the prescription form could not be reached. Each status is
  /// read page by page (at most 5 pages of 50).
  Future<List<Map<String, dynamic>>> getDoctorCompletedAppointments() async {
    final results = <Map<String, dynamic>>[];
    for (final status in const ['COMPLETED', 'CONFIRMED']) {
      for (var page = 1; page <= 5; page++) {
        final response = await _apiClient.get(
          '${ApiConstants.doctorMyAppointmentsEndpoint}?status=$status&limit=50&page=$page',
          includeAuth: true,
        );
        final rows = response is Map<String, dynamic> ? response['items'] : response;
        if (rows is! List) break;
        results.addAll(rows.whereType<Map<String, dynamic>>().where(
            (appt) => appt['status']?.toString().toUpperCase() == status));
        final totalPages = response is Map<String, dynamic> ? (response['totalPages'] as num?)?.toInt() ?? 1 : 1;
        if (page >= totalPages) break;
      }
    }
    return results;
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

  /// A04: structural check of a draft before signing (missing fields, repeated medicines, documented allergies and
  /// active prescriptions). Nothing is stored or signed; the backend returns the items exactly as entered.
  Future<Map<String, dynamic>> reviewPrescriptionDraft({
    required String patientUserId,
    required List<MedicationItem> medicationItems,
  }) async {
    final response = await _apiClient.post(
      '/clinical/prescriptions/assistant-review/draft',
      body: {
        'patientUserId': patientUserId,
        'medicationItems': medicationItems.map((e) => e.toJson()).toList(),
      },
      includeAuth: true,
    );
    if (response is Map<String, dynamic>) {
      return response;
    }
    throw Exception('Prescription check unavailable.');
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
