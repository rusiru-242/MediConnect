import 'package:http/http.dart' as http;

import '../core/network/api_client.dart';
import '../models/clinical_record.dart';

/// Clinical API service covering Phase 6 Advanced Healthcare AI,
/// Medical Records, Health Tracking, Clinical Notes, and Prescription Renewals.
class ClinicalApiService {
  final ApiClient _client;

  ClinicalApiService({ApiClient? client}) : _client = client ?? ApiClient();

  // ---------------------------------------------------------------------------
  // 1. Longitudinal Medical Records & Documents
  // ---------------------------------------------------------------------------

  Future<List<PatientMedicalRecord>> getMedicalRecords({
    String? patientId,
    String? recordType,
    int page = 1,
    int pageSize = 20,
  }) async {
    final queryParams = <String>[
      'page=$page',
      'pageSize=$pageSize',
      if (patientId != null) 'patientId=$patientId',
      if (recordType != null) 'recordType=$recordType',
    ].join('&');

    final response = await _client.get('/clinical/records?$queryParams', includeAuth: true);
    if (response is Map<String, dynamic> && response['records'] is List) {
      final list = response['records'] as List;
      return list.map((e) => PatientMedicalRecord.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    }
    return [];
  }

  Future<PatientMedicalRecord> getMedicalRecordDetail(String recordId) async {
    final response = await _client.get('/clinical/records/$recordId', includeAuth: true);
    return PatientMedicalRecord.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<MedicalRecordSummary> getMedicalRecordSummary({String? patientId}) async {
    final query = patientId != null ? '?patientId=$patientId' : '';
    final response = await _client.get('/clinical/records/summary$query', includeAuth: true);
    return MedicalRecordSummary.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<List<int>> downloadDocumentFile(String recordId) async {
    return _client.getBytes('/clinical/records/$recordId/download', includeAuth: true);
  }

  Future<PatientMedicalRecord> uploadMedicalDocument({
    required List<int> fileBytes,
    required String filename,
    required String title,
    required String recordType,
    required String clinicalDate,
    String? description,
    String? targetPatientId,
  }) async {
    final multipartFile = http.MultipartFile.fromBytes(
      'file',
      fileBytes,
      filename: filename,
    );

    final fields = <String, String>{
      'title': title,
      'recordType': recordType,
      'clinicalDate': clinicalDate,
    };
    if (description != null) fields['description'] = description;
    if (targetPatientId != null) fields['targetPatientId'] = targetPatientId;

    final response = await _client.postMultipart(
      '/clinical/records/documents/upload',
      fields: fields,
      files: [multipartFile],
      includeAuth: true,
    );

    return PatientMedicalRecord.fromJson(Map<String, dynamic>.from(response as Map));
  }

  // ---------------------------------------------------------------------------
  // 2. Clinical Notes (SOAP Notes)
  // ---------------------------------------------------------------------------

  Future<List<ClinicalNote>> getClinicalNotes({String? patientId}) async {
    final query = patientId != null ? '?patientId=$patientId' : '';
    final response = await _client.get('/clinical/notes$query', includeAuth: true);
    if (response is Map<String, dynamic> && response['notes'] is List) {
      final list = response['notes'] as List;
      return list.map((e) => ClinicalNote.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    }
    return [];
  }

  Future<ClinicalNote> createClinicalNoteDraft({
    required String patientUserId,
    String? appointmentId,
    String? rawNotes,
    SoapContent? content,
  }) async {
    final body = <String, dynamic>{
      'patientUserId': patientUserId,
    };
    if (appointmentId != null) body['appointmentId'] = appointmentId;
    if (rawNotes != null) body['rawNotes'] = rawNotes;
    if (content != null) body['content'] = content.toJson();
    final response = await _client.post('/clinical/notes/draft', body: body, includeAuth: true);
    return ClinicalNote.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<ClinicalNote> updateClinicalNoteDraft({
    required String noteId,
    required SoapContent content,
  }) async {
    final response = await _client.put(
      '/clinical/notes/$noteId/draft',
      body: {'content': content.toJson()},
      includeAuth: true,
    );
    return ClinicalNote.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<ClinicalNote> signClinicalNote(String noteId) async {
    final response = await _client.post(
      '/clinical/notes/$noteId/sign',
      body: {'confirmSign': true},
      includeAuth: true,
    );
    return ClinicalNote.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<ClinicalNote> amendClinicalNote({
    required String noteId,
    required String justification,
    required String addendum,
  }) async {
    final response = await _client.post(
      '/clinical/notes/$noteId/amend',
      body: {'justification': justification, 'addendum': addendum},
      includeAuth: true,
    );
    return ClinicalNote.fromJson(Map<String, dynamic>.from(response as Map));
  }

  // ---------------------------------------------------------------------------
  // 3. Prescriptions & Renewals
  // ---------------------------------------------------------------------------

  Future<PrescriptionRenewal> requestPrescriptionRenewal({
    required String originalPrescriptionId,
    required String medicationName,
    String? patientReason,
  }) async {
    final body = <String, dynamic>{
      'originalPrescriptionId': originalPrescriptionId,
      'medicationName': medicationName,
    };
    if (patientReason != null) body['patientReason'] = patientReason;
    final response = await _client.post(
      '/clinical/prescriptions/renewals',
      body: body,
      includeAuth: true,
    );
    return PrescriptionRenewal.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<List<PrescriptionRenewal>> getPrescriptionRenewals({String? statusFilter}) async {
    final query = statusFilter != null ? '?statusFilter=$statusFilter' : '';
    final response = await _client.get('/clinical/prescriptions/renewals$query', includeAuth: true);
    if (response is Map<String, dynamic> && response['renewals'] is List) {
      final list = response['renewals'] as List;
      return list.map((e) => PrescriptionRenewal.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    }
    return [];
  }

  Future<PrescriptionRenewal> reviewPrescriptionRenewal({
    required String renewalId,
    required String decision,
    required String reason,
    String? consultationDetails,
  }) async {
    final body = <String, dynamic>{
      'decision': decision,
      'reason': reason,
    };
    if (consultationDetails != null) body['consultationDetails'] = consultationDetails;
    final response = await _client.post(
      '/clinical/prescriptions/renewals/$renewalId/review',
      body: body,
      includeAuth: true,
    );
    return PrescriptionRenewal.fromJson(Map<String, dynamic>.from(response as Map));
  }

  // ---------------------------------------------------------------------------
  // 4. Health Tracking & Trends
  // ---------------------------------------------------------------------------

  Future<HealthMeasurement> recordMeasurement({
    required String metric,
    required double value,
    double? secondary,
    String? unit,
    String? source,
    String? notes,
    String? targetPatientId,
  }) async {
    final query = targetPatientId != null ? '?targetPatientId=$targetPatientId' : '';
    final body = <String, dynamic>{
      'metric': metric,
      'value': value,
    };
    if (secondary != null) body['secondary'] = secondary;
    if (unit != null) body['unit'] = unit;
    if (source != null) body['source'] = source;
    if (notes != null) body['notes'] = notes;
    final response = await _client.post(
      '/clinical/measurements$query',
      body: body,
      includeAuth: true,
    );
    return HealthMeasurement.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<HealthMeasurement> correctMeasurement({
    required String measurementId,
    required double newValue,
    double? newSecondary,
    required String reason,
  }) async {
    final body = <String, dynamic>{
      'newValue': newValue,
      'reason': reason,
    };
    if (newSecondary != null) body['newSecondary'] = newSecondary;
    final response = await _client.patch(
      '/clinical/measurements/$measurementId/correct',
      body: body,
      includeAuth: true,
    );
    return HealthMeasurement.fromJson(Map<String, dynamic>.from(response as Map));
  }

  Future<List<HealthMeasurement>> getMeasurements({
    String? patientId,
    String? metric,
    int limit = 50,
  }) async {
    final queryParams = <String>[
      'limit=$limit',
      if (patientId != null) 'patientId=$patientId',
      if (metric != null) 'metric=$metric',
    ].join('&');

    final response = await _client.get('/clinical/measurements?$queryParams', includeAuth: true);
    if (response is Map<String, dynamic> && response['items'] is List) {
      final list = response['items'] as List;
      return list.map((e) => HealthMeasurement.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    }
    return [];
  }

  Future<HealthTrends> getHealthTrends({String? patientId}) async {
    final query = patientId != null ? '?patientId=$patientId' : '';
    final response = await _client.get('/clinical/measurements/trends$query', includeAuth: true);
    return HealthTrends.fromJson(Map<String, dynamic>.from(response as Map));
  }

  // ---------------------------------------------------------------------------
  // 5. AI Clinical Assistant Chat
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> chatClinicalAI({
    required String message,
    String? patientUserId,
  }) async {
    final body = <String, dynamic>{
      'message': message,
    };
    if (patientUserId != null) body['patientUserId'] = patientUserId;
    final response = await _client.post(
      '/clinical/ai-assistant/chat',
      body: body,
      includeAuth: true,
    );
    return Map<String, dynamic>.from(response as Map);
  }
}
