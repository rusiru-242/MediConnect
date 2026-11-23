import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/timeline.dart';

/// Client API Service for Patient Healthcare Timeline & Visit History (Phase 58).
class PatientTimelineService {
  final ApiClient _apiClient;

  PatientTimelineService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Retrieve patient-safe chronological healthcare timeline events.
  Future<TimelineResponse> getHealthcareTimeline({
    String category = 'ALL',
    String? fromDate,
    String? toDate,
    String? doctorId,
    String? cursor,
    int limit = 20,
  }) async {
    final queryParams = <String, String>{
      if (category.isNotEmpty && category != 'ALL') 'category': category,
      if (fromDate != null && fromDate.isNotEmpty) 'fromDate': fromDate,
      if (toDate != null && toDate.isNotEmpty) 'toDate': toDate,
      if (doctorId != null && doctorId.isNotEmpty) 'doctorId': doctorId,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
      'limit': limit.toString(),
    };

    final queryString = Uri(queryParameters: queryParams).query;
    final endpoint = queryString.isNotEmpty
        ? '${ApiConstants.patientHealthcareTimelineEndpoint}?$queryString'
        : ApiConstants.patientHealthcareTimelineEndpoint;

    final response = await _apiClient.get(
      endpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return TimelineResponse.fromJson(response);
    }
    throw Exception('Failed to load healthcare timeline.');
  }

  /// Retrieve summary statistics for patient healthcare dashboard.
  Future<TimelineSummary> getHealthcareTimelineSummary() async {
    final response = await _apiClient.get(
      ApiConstants.patientHealthcareTimelineSummaryEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return TimelineSummary.fromJson(response);
    }
    throw Exception('Failed to load healthcare timeline summary.');
  }

  /// Retrieve consolidated visit details for a specific appointment.
  Future<VisitDetail> getVisitDetail(String appointmentId) async {
    final response = await _apiClient.get(
      ApiConstants.patientVisitDetailEndpoint(appointmentId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return VisitDetail.fromJson(response);
    }
    throw Exception('Failed to load visit details.');
  }
}

