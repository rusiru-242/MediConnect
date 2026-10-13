import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/doctor_recommendation.dart';

/// Service communicating with the MediConnect backend AI Doctor Recommendation Agent.
class AiRecommendationService {
  final ApiClient _apiClient;

  AiRecommendationService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Request personalized, ranked doctor recommendations based on natural-language query and optional explicit filters.
  Future<DoctorRecommendationResponse> getDoctorRecommendations({
    required String query,
    String? specialty,
    String? city,
    String? date,
    String? timeRange,
    double? maxFee,
    String? consultationType,
  }) async {
    final payload = <String, dynamic>{
      'query': query.trim(),
    };

    if (specialty != null && specialty.trim().isNotEmpty && specialty.trim().toLowerCase() != 'all') {
      payload['specialty'] = specialty.trim();
    }
    if (city != null && city.trim().isNotEmpty) {
      payload['city'] = city.trim();
    }
    if (date != null && date.trim().isNotEmpty) {
      payload['date'] = date.trim();
    }
    if (timeRange != null && timeRange.trim().isNotEmpty && timeRange.trim().toLowerCase() != 'any') {
      payload['timeRange'] = timeRange.trim().toLowerCase();
    }
    if (maxFee != null && maxFee > 0) {
      payload['maxFee'] = maxFee;
    }
    if (consultationType != null && consultationType.trim().isNotEmpty) {
      payload['consultationType'] = consultationType.trim();
    }

    final response = await _apiClient.post(
      ApiConstants.aiDoctorRecommendationsEndpoint,
      body: payload,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DoctorRecommendationResponse.fromJson(response);
    }

    throw Exception('Unexpected response format received from AI recommendation service.');
  }
}
