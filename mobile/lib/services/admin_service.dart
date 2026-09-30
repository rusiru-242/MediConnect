import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/admin_doctor_application.dart';

/// Service handling administrator operations for doctor verification.
class AdminService {
  final ApiClient _apiClient;

  AdminService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Retrieve doctor applications, optionally filtered by status (PENDING, APPROVED, REJECTED, ALL).
  Future<List<AdminDoctorApplicationSummary>> getDoctorApplications({
    String? status,
  }) async {
    final query = status != null && status.isNotEmpty ? '?status=$status' : '';
    final endpoint = '${ApiConstants.adminDoctorApplicationsEndpoint}$query';

    final response = await _apiClient.get(endpoint, includeAuth: true);
    if (response is List) {
      return response
          .map((item) => AdminDoctorApplicationSummary.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  /// Retrieve full doctor application detail by doctorProfileId.
  Future<AdminDoctorApplicationDetail> getDoctorApplicationDetail(
    String doctorProfileId,
  ) async {
    final endpoint = ApiConstants.adminDoctorApplicationDetailEndpoint(doctorProfileId);
    final response = await _apiClient.get(endpoint, includeAuth: true);
    return AdminDoctorApplicationDetail.fromJson(response as Map<String, dynamic>);
  }

  /// Securely retrieve raw document bytes for admin preview.
  Future<List<int>> getDoctorDocumentBytes(
    String doctorProfileId,
    String documentKey,
  ) async {
    final endpoint = ApiConstants.adminDoctorDocumentEndpoint(doctorProfileId, documentKey);
    return await _apiClient.getBytes(endpoint, includeAuth: true);
  }

  /// Approve a pending doctor application.
  Future<String> approveDoctor(String doctorProfileId) async {
    final endpoint = ApiConstants.adminDoctorApproveEndpoint(doctorProfileId);
    final response = await _apiClient.post(endpoint, includeAuth: true);
    if (response is Map<String, dynamic> && response.containsKey('message')) {
      return response['message'].toString();
    }
    return 'Doctor application approved successfully.';
  }

  /// Reject a pending doctor application with reason.
  Future<String> rejectDoctor(String doctorProfileId, String reason) async {
    final endpoint = ApiConstants.adminDoctorRejectEndpoint(doctorProfileId);
    final response = await _apiClient.post(
      endpoint,
      body: {'reason': reason.trim()},
      includeAuth: true,
    );
    if (response is Map<String, dynamic> && response.containsKey('message')) {
      return response['message'].toString();
    }
    return 'Doctor application rejected.';
  }
}
