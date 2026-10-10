import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/payment.dart';

/// Service handling patient payment operations via MediConnect FastAPI backend.
class PaymentService {
  final ApiClient _apiClient;

  PaymentService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  /// Create a Stripe PaymentIntent for a held appointment.
  /// Server determines authoritative amount from doctor's consultation fee.
  Future<CreatePaymentIntentResponse> createPaymentIntent(
      String appointmentId) async {
    final response = await _apiClient.post(
      ApiConstants.createPaymentIntentEndpoint,
      body: {'appointmentId': appointmentId},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return CreatePaymentIntentResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when creating payment intent.');
  }

  /// Authoritative backend payment and appointment status check.
  /// Used after Stripe PaymentSheet completes.
  Future<PaymentStatusResult> getPaymentStatus(String paymentId) async {
    final response = await _apiClient.get(
      ApiConstants.paymentStatusEndpoint(paymentId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return PaymentStatusResult.fromJson(response);
    }
    throw Exception('Unexpected response format when checking payment status.');
  }

  /// Retrieve patient's past payments.
  Future<List<PaymentHistoryItem>> getPaymentHistory() async {
    final response = await _apiClient.get(
      ApiConstants.paymentHistoryEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic> && response.containsKey('items')) {
      final items = response['items'] as List<dynamic>;
      return items
          .map((item) =>
              PaymentHistoryItem.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }
}
