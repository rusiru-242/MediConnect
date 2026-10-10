/// Payment models for Stripe integration and history.
library;

class CreatePaymentIntentResponse {
  final String paymentIntentClientSecret;
  final String paymentId;
  final int amount; // in smallest unit (e.g. cents)
  final String currency;
  final String? publishableKey;

  CreatePaymentIntentResponse({
    required this.paymentIntentClientSecret,
    required this.paymentId,
    required this.amount,
    required this.currency,
    this.publishableKey,
  });

  factory CreatePaymentIntentResponse.fromJson(Map<String, dynamic> json) {
    return CreatePaymentIntentResponse(
      paymentIntentClientSecret:
          (json['paymentIntentClientSecret'] ?? '').toString(),
      paymentId: (json['paymentId'] ?? '').toString(),
      amount: json['amount'] is num ? (json['amount'] as num).toInt() : 0,
      currency: (json['currency'] ?? 'lkr').toString(),
      publishableKey: json['publishableKey']?.toString(),
    );
  }
}

class PaymentStatusResult {
  final String paymentId;
  final String appointmentId;
  final String paymentStatus;
  final String appointmentStatus;
  final double amount;
  final String currency;
  final DateTime? paidAt;

  PaymentStatusResult({
    required this.paymentId,
    required this.appointmentId,
    required this.paymentStatus,
    required this.appointmentStatus,
    required this.amount,
    required this.currency,
    this.paidAt,
  });

  factory PaymentStatusResult.fromJson(Map<String, dynamic> json) {
    return PaymentStatusResult(
      paymentId: (json['paymentId'] ?? '').toString(),
      appointmentId: (json['appointmentId'] ?? '').toString(),
      paymentStatus: (json['paymentStatus'] ?? 'PENDING').toString(),
      appointmentStatus: (json['appointmentStatus'] ?? 'UNKNOWN').toString(),
      amount: json['amount'] is num ? (json['amount'] as num).toDouble() : 0.0,
      currency: (json['currency'] ?? 'lkr').toString(),
      paidAt: json['paidAt'] != null
          ? DateTime.tryParse(json['paidAt'].toString())
          : null,
    );
  }

  bool get isSucceeded =>
      paymentStatus.toUpperCase() == 'SUCCEEDED' &&
      appointmentStatus.toUpperCase() == 'CONFIRMED';
}

class PaymentHistoryItem {
  final String paymentId;
  final String appointmentId;
  final String doctorName;
  final double amount;
  final String currency;
  final String status;
  final DateTime? paidAt;
  final DateTime? createdAt;

  PaymentHistoryItem({
    required this.paymentId,
    required this.appointmentId,
    required this.doctorName,
    required this.amount,
    required this.currency,
    required this.status,
    this.paidAt,
    this.createdAt,
  });

  factory PaymentHistoryItem.fromJson(Map<String, dynamic> json) {
    return PaymentHistoryItem(
      paymentId: (json['paymentId'] ?? '').toString(),
      appointmentId: (json['appointmentId'] ?? '').toString(),
      doctorName: (json['doctorName'] ?? 'Doctor').toString(),
      amount: json['amount'] is num ? (json['amount'] as num).toDouble() : 0.0,
      currency: (json['currency'] ?? 'lkr').toString(),
      status: (json['status'] ?? 'PENDING').toString(),
      paidAt: json['paidAt'] != null
          ? DateTime.tryParse(json['paidAt'].toString())
          : null,
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString())
          : null,
    );
  }
}
