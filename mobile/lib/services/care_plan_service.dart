import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/care_plan.dart';

/// Client API Service for Smart Follow-up Care Plans (Phase 56).
class CarePlanService {
  final ApiClient _apiClient;

  CarePlanService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  // -------------------------------------------------------------------------
  // Doctor Operations
  // -------------------------------------------------------------------------

  /// Doctor creates a follow-up care plan for an eligible consultation.
  Future<CarePlan> createCarePlan({
    required String appointmentId,
    required String followUpDate,
    String? followUpDateEnd,
    required String reason,
    required String instructions,
    String recommendedConsultationType = 'IN_PERSON',
    List<Map<String, dynamic>> tasks = const [],
    List<String> linkedPrescriptionIds = const [],
    List<String> linkedMedicalRecordIds = const [],
  }) async {
    final response = await _apiClient.post(
      ApiConstants.carePlansEndpoint,
      body: {
        'appointmentId': appointmentId,
        'followUpDate': followUpDate,
        if (followUpDateEnd != null && followUpDateEnd.isNotEmpty)
          'followUpDateEnd': followUpDateEnd,
        'reason': reason.trim(),
        'instructions': instructions.trim(),
        'recommendedConsultationType': recommendedConsultationType,
        'tasks': tasks,
        'linkedPrescriptionIds': linkedPrescriptionIds,
        'linkedMedicalRecordIds': linkedMedicalRecordIds,
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CarePlan.fromJson(response);
    }
    throw Exception('Failed to create follow-up care plan.');
  }

  /// List care plans authored by the authenticated doctor.
  Future<List<CarePlan>> getDoctorCarePlans({
    String? status,
    String? appointmentId,
  }) async {
    final params = <String>[];
    if (status != null && status.isNotEmpty) {
      params.add('status=${Uri.encodeComponent(status)}');
    }
    if (appointmentId != null && appointmentId.isNotEmpty) {
      params.add('appointment_id=${Uri.encodeComponent(appointmentId)}');
    }
    final queryStr = params.isNotEmpty ? '?${params.join('&')}' : '';

    final response = await _apiClient.get(
      '${ApiConstants.carePlansDoctorEndpoint}$queryStr',
      includeAuth: true,
    );

    if (response is Map<String, dynamic> && response['plans'] is List) {
      final list = response['plans'] as List;
      return list.map((e) => CarePlan.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  /// Doctor updates an active care plan.
  Future<CarePlan> updateCarePlan(
    String planId, {
    String? followUpDate,
    String? followUpDateEnd,
    String? reason,
    String? instructions,
    String? recommendedConsultationType,
    List<Map<String, dynamic>>? tasks,
    List<String>? linkedPrescriptionIds,
    List<String>? linkedMedicalRecordIds,
  }) async {
    final body = <String, dynamic>{};
    if (followUpDate != null) body['followUpDate'] = followUpDate;
    if (followUpDateEnd != null) body['followUpDateEnd'] = followUpDateEnd;
    if (reason != null) body['reason'] = reason.trim();
    if (instructions != null) body['instructions'] = instructions.trim();
    if (recommendedConsultationType != null) {
      body['recommendedConsultationType'] = recommendedConsultationType;
    }
    if (tasks != null) body['tasks'] = tasks;
    if (linkedPrescriptionIds != null) {
      body['linkedPrescriptionIds'] = linkedPrescriptionIds;
    }
    if (linkedMedicalRecordIds != null) {
      body['linkedMedicalRecordIds'] = linkedMedicalRecordIds;
    }

    final response = await _apiClient.put(
      ApiConstants.carePlanDetailEndpoint(planId),
      body: body,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CarePlan.fromJson(response);
    }
    throw Exception('Failed to update follow-up care plan.');
  }

  /// Doctor cancels a care plan.
  Future<CarePlan> cancelCarePlan(String planId, {required String reason}) async {
    final response = await _apiClient.post(
      ApiConstants.carePlanCancelEndpoint(planId),
      body: {'reason': reason.trim()},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CarePlan.fromJson(response);
    }
    throw Exception('Failed to cancel follow-up care plan.');
  }

  // -------------------------------------------------------------------------
  // Patient Operations
  // -------------------------------------------------------------------------

  /// Fetch care plans assigned to the authenticated patient.
  Future<List<CarePlan>> getPatientCarePlans({String? status}) async {
    final queryStr = (status != null && status.isNotEmpty)
        ? '?status=${Uri.encodeComponent(status)}'
        : '';

    final response = await _apiClient.get(
      '${ApiConstants.carePlansPatientEndpoint}$queryStr',
      includeAuth: true,
    );

    if (response is Map<String, dynamic> && response['plans'] is List) {
      final list = response['plans'] as List;
      return list.map((e) => CarePlan.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  /// Patient toggles completion status of a non-medication task.
  Future<CarePlan> updateTaskStatus(
    String planId,
    String taskId, {
    required bool isCompleted,
  }) async {
    final response = await _apiClient.patch(
      ApiConstants.carePlanTaskStatusEndpoint(planId, taskId),
      body: {'isCompleted': isCompleted},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CarePlan.fromJson(response);
    }
    throw Exception('Failed to update care task completion status.');
  }

  /// Patient links newly confirmed follow-up appointment to the care plan.
  Future<CarePlan> linkBookedAppointment(
    String planId, {
    required String appointmentId,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.carePlanLinkAppointmentEndpoint(planId),
      body: {'appointmentId': appointmentId},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CarePlan.fromJson(response);
    }
    throw Exception('Failed to link follow-up appointment to care plan.');
  }

  // -------------------------------------------------------------------------
  // Shared Operations
  // -------------------------------------------------------------------------

  /// Fetch details of a specific care plan.
  Future<CarePlan> getCarePlanDetails(String planId) async {
    final response = await _apiClient.get(
      ApiConstants.carePlanDetailEndpoint(planId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CarePlan.fromJson(response);
    }
    throw Exception('Failed to load care plan details.');
  }
}
