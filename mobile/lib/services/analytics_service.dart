import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/analytics_data.dart';

/// Service interfacing with the MediConnect Admin Analytics API (Phase 24).
class AnalyticsService {
  final ApiClient _apiClient;

  AnalyticsService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Retrieve high-level platform health overview metrics with optional date range.
  Future<AnalyticsOverviewData> fetchOverview({
    String? startDate,
    String? endDate,
  }) async {
    final queryParams = <String>[];
    if (startDate != null && startDate.trim().isNotEmpty) {
      queryParams.add('startDate=${Uri.encodeComponent(startDate.trim())}');
    }
    if (endDate != null && endDate.trim().isNotEmpty) {
      queryParams.add('endDate=${Uri.encodeComponent(endDate.trim())}');
    }

    final endpoint = queryParams.isEmpty
        ? ApiConstants.adminAnalyticsOverviewEndpoint
        : '${ApiConstants.adminAnalyticsOverviewEndpoint}?${queryParams.join('&')}';

    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return AnalyticsOverviewData.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching analytics overview.');
  }

  /// Retrieve appointment metrics and daily volume trends.
  Future<AppointmentAnalyticsData> fetchAppointmentAnalytics({
    String? startDate,
    String? endDate,
  }) async {
    final queryParams = <String>[];
    if (startDate != null && startDate.trim().isNotEmpty) {
      queryParams.add('startDate=${Uri.encodeComponent(startDate.trim())}');
    }
    if (endDate != null && endDate.trim().isNotEmpty) {
      queryParams.add('endDate=${Uri.encodeComponent(endDate.trim())}');
    }

    final endpoint = queryParams.isEmpty
        ? ApiConstants.adminAnalyticsAppointmentsEndpoint
        : '${ApiConstants.adminAnalyticsAppointmentsEndpoint}?${queryParams.join('&')}';

    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return AppointmentAnalyticsData.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching appointment analytics.');
  }

  /// Retrieve payment and revenue statistics by currency, distinguishing Stripe test mode.
  Future<PaymentAnalyticsData> fetchPaymentAnalytics({
    String? startDate,
    String? endDate,
  }) async {
    final queryParams = <String>[];
    if (startDate != null && startDate.trim().isNotEmpty) {
      queryParams.add('startDate=${Uri.encodeComponent(startDate.trim())}');
    }
    if (endDate != null && endDate.trim().isNotEmpty) {
      queryParams.add('endDate=${Uri.encodeComponent(endDate.trim())}');
    }

    final endpoint = queryParams.isEmpty
        ? ApiConstants.adminAnalyticsPaymentsEndpoint
        : '${ApiConstants.adminAnalyticsPaymentsEndpoint}?${queryParams.join('&')}';

    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return PaymentAnalyticsData.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching payment analytics.');
  }

  /// Retrieve doctor verification pipeline metrics and medical specialty distribution.
  Future<DoctorAnalyticsData> fetchDoctorAnalytics() async {
    final response = await _apiClient.get(
      ApiConstants.adminAnalyticsDoctorsEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DoctorAnalyticsData.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching doctor analytics.');
  }

  /// Retrieve health content catalog and bookmark engagement statistics.
  Future<ContentAnalyticsData> fetchContentAnalytics() async {
    final response = await _apiClient.get(
      ApiConstants.adminAnalyticsContentEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return ContentAnalyticsData.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching content analytics.');
  }
}
