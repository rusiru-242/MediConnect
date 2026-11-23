// Models for MediConnect Admin Analytics Dashboard (Phase 24).

class CurrencyRevenueData {
  final String currency;
  final double grossAmount;
  final double refundedAmount;
  final double netAmount;
  final int paymentCount;

  const CurrencyRevenueData({
    required this.currency,
    required this.grossAmount,
    required this.refundedAmount,
    required this.netAmount,
    required this.paymentCount,
  });

  factory CurrencyRevenueData.fromJson(Map<String, dynamic> json) {
    return CurrencyRevenueData(
      currency: (json['currency'] ?? 'lkr').toString().toUpperCase(),
      grossAmount: (json['grossAmount'] as num?)?.toDouble() ?? 0.0,
      refundedAmount: (json['refundedAmount'] as num?)?.toDouble() ?? 0.0,
      netAmount: (json['netAmount'] as num?)?.toDouble() ?? 0.0,
      paymentCount: (json['paymentCount'] as num?)?.toInt() ?? 0,
    );
  }
}

class TrendDataPoint {
  final String date;
  final int total;
  final int completed;
  final int confirmed;
  final int cancelled;

  const TrendDataPoint({
    required this.date,
    required this.total,
    required this.completed,
    required this.confirmed,
    required this.cancelled,
  });

  factory TrendDataPoint.fromJson(Map<String, dynamic> json) {
    return TrendDataPoint(
      date: (json['date'] ?? '').toString(),
      total: (json['total'] as num?)?.toInt() ?? 0,
      completed: (json['completed'] as num?)?.toInt() ?? 0,
      confirmed: (json['confirmed'] as num?)?.toInt() ?? 0,
      cancelled: (json['cancelled'] as num?)?.toInt() ?? 0,
    );
  }
}

class SpecialtyCountData {
  final String specialty;
  final int count;

  const SpecialtyCountData({
    required this.specialty,
    required this.count,
  });

  factory SpecialtyCountData.fromJson(Map<String, dynamic> json) {
    return SpecialtyCountData(
      specialty: (json['specialty'] ?? 'General Practice').toString(),
      count: (json['count'] as num?)?.toInt() ?? 0,
    );
  }
}

class CategoryAnalyticsData {
  final String category;
  final int count;
  final int publishedCount;

  const CategoryAnalyticsData({
    required this.category,
    required this.count,
    this.publishedCount = 0,
  });

  factory CategoryAnalyticsData.fromJson(Map<String, dynamic> json) {
    return CategoryAnalyticsData(
      category: (json['category'] ?? '').toString(),
      count: (json['count'] as num?)?.toInt() ?? 0,
      publishedCount: (json['publishedCount'] as num?)?.toInt() ?? 0,
    );
  }
}

class TopContentData {
  final String contentId;
  final String title;
  final String category;
  final int bookmarksCount;

  const TopContentData({
    required this.contentId,
    required this.title,
    required this.category,
    required this.bookmarksCount,
  });

  factory TopContentData.fromJson(Map<String, dynamic> json) {
    return TopContentData(
      contentId: (json['contentId'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      category: (json['category'] ?? '').toString(),
      bookmarksCount: (json['bookmarksCount'] as num?)?.toInt() ?? 0,
    );
  }
}

class PaymentTransactionData {
  final String id;
  final String appointmentId;
  final double amount;
  final String currency;
  final String status;
  final bool isTestPayment;
  final DateTime? paidAt;
  final DateTime createdAt;

  const PaymentTransactionData({
    required this.id,
    required this.appointmentId,
    required this.amount,
    required this.currency,
    required this.status,
    required this.isTestPayment,
    this.paidAt,
    required this.createdAt,
  });

  factory PaymentTransactionData.fromJson(Map<String, dynamic> json) {
    return PaymentTransactionData(
      id: (json['id'] ?? '').toString(),
      appointmentId: (json['appointmentId'] ?? '').toString(),
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
      currency: (json['currency'] ?? 'lkr').toString().toUpperCase(),
      status: (json['status'] ?? 'PENDING').toString().toUpperCase(),
      isTestPayment: json['isTestPayment'] == true,
      paidAt: json['paidAt'] != null ? DateTime.tryParse(json['paidAt'].toString()) : null,
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class AnalyticsOverviewData {
  final int totalPatients;
  final int totalVerifiedDoctors;
  final int pendingDoctorApprovals;
  final int rejectedDoctorApplications;

  final int totalAppointments;
  final int confirmedAppointments;
  final int completedAppointments;
  final int cancelledAppointments;
  final int pendingAppointments;

  final List<CurrencyRevenueData> totalRevenueByCurrency;
  final int successfulPaymentsCount;
  final int testPaymentsCount;
  final int livePaymentsCount;

  final int totalArticles;
  final int publishedArticles;
  final int draftArticles;
  final int totalBookmarks;

  final String? startDate;
  final String? endDate;

  const AnalyticsOverviewData({
    required this.totalPatients,
    required this.totalVerifiedDoctors,
    required this.pendingDoctorApprovals,
    required this.rejectedDoctorApplications,
    required this.totalAppointments,
    required this.confirmedAppointments,
    required this.completedAppointments,
    required this.cancelledAppointments,
    required this.pendingAppointments,
    required this.totalRevenueByCurrency,
    required this.successfulPaymentsCount,
    required this.testPaymentsCount,
    required this.livePaymentsCount,
    required this.totalArticles,
    required this.publishedArticles,
    required this.draftArticles,
    required this.totalBookmarks,
    this.startDate,
    this.endDate,
  });

  factory AnalyticsOverviewData.fromJson(Map<String, dynamic> json) {
    return AnalyticsOverviewData(
      totalPatients: (json['totalPatients'] as num?)?.toInt() ?? 0,
      totalVerifiedDoctors: (json['totalVerifiedDoctors'] as num?)?.toInt() ?? 0,
      pendingDoctorApprovals: (json['pendingDoctorApprovals'] as num?)?.toInt() ?? 0,
      rejectedDoctorApplications: (json['rejectedDoctorApplications'] as num?)?.toInt() ?? 0,
      totalAppointments: (json['totalAppointments'] as num?)?.toInt() ?? 0,
      confirmedAppointments: (json['confirmedAppointments'] as num?)?.toInt() ?? 0,
      completedAppointments: (json['completedAppointments'] as num?)?.toInt() ?? 0,
      cancelledAppointments: (json['cancelledAppointments'] as num?)?.toInt() ?? 0,
      pendingAppointments: (json['pendingAppointments'] as num?)?.toInt() ?? 0,
      totalRevenueByCurrency: (json['totalRevenueByCurrency'] as List<dynamic>?)
              ?.map((r) => CurrencyRevenueData.fromJson(r as Map<String, dynamic>))
              .toList() ??
          const [],
      successfulPaymentsCount: (json['successfulPaymentsCount'] as num?)?.toInt() ?? 0,
      testPaymentsCount: (json['testPaymentsCount'] as num?)?.toInt() ?? 0,
      livePaymentsCount: (json['livePaymentsCount'] as num?)?.toInt() ?? 0,
      totalArticles: (json['totalArticles'] as num?)?.toInt() ?? 0,
      publishedArticles: (json['publishedArticles'] as num?)?.toInt() ?? 0,
      draftArticles: (json['draftArticles'] as num?)?.toInt() ?? 0,
      totalBookmarks: (json['totalBookmarks'] as num?)?.toInt() ?? 0,
      startDate: json['startDate']?.toString(),
      endDate: json['endDate']?.toString(),
    );
  }
}

class AppointmentAnalyticsData {
  final int totalAppointments;
  final Map<String, int> statusBreakdown;
  final List<TrendDataPoint> trends;
  final double completionRate;
  final double cancellationRate;

  const AppointmentAnalyticsData({
    required this.totalAppointments,
    required this.statusBreakdown,
    required this.trends,
    required this.completionRate,
    required this.cancellationRate,
  });

  factory AppointmentAnalyticsData.fromJson(Map<String, dynamic> json) {
    final rawMap = json['statusBreakdown'] as Map<String, dynamic>? ?? {};
    final statusMap = rawMap.map((k, v) => MapEntry(k, (v as num?)?.toInt() ?? 0));

    return AppointmentAnalyticsData(
      totalAppointments: (json['totalAppointments'] as num?)?.toInt() ?? 0,
      statusBreakdown: statusMap,
      trends: (json['trends'] as List<dynamic>?)
              ?.map((t) => TrendDataPoint.fromJson(t as Map<String, dynamic>))
              .toList() ??
          const [],
      completionRate: (json['completionRate'] as num?)?.toDouble() ?? 0.0,
      cancellationRate: (json['cancellationRate'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class PaymentAnalyticsData {
  final int successfulPaymentsCount;
  final int testPaymentsCount;
  final int livePaymentsCount;
  final int failedPaymentsCount;
  final int refundedPaymentsCount;
  final List<CurrencyRevenueData> revenueByCurrency;
  final bool isStripeTestMode;
  final List<PaymentTransactionData> recentTransactions;

  const PaymentAnalyticsData({
    required this.successfulPaymentsCount,
    required this.testPaymentsCount,
    required this.livePaymentsCount,
    required this.failedPaymentsCount,
    required this.refundedPaymentsCount,
    required this.revenueByCurrency,
    required this.isStripeTestMode,
    required this.recentTransactions,
  });

  factory PaymentAnalyticsData.fromJson(Map<String, dynamic> json) {
    return PaymentAnalyticsData(
      successfulPaymentsCount: (json['successfulPaymentsCount'] as num?)?.toInt() ?? 0,
      testPaymentsCount: (json['testPaymentsCount'] as num?)?.toInt() ?? 0,
      livePaymentsCount: (json['livePaymentsCount'] as num?)?.toInt() ?? 0,
      failedPaymentsCount: (json['failedPaymentsCount'] as num?)?.toInt() ?? 0,
      refundedPaymentsCount: (json['refundedPaymentsCount'] as num?)?.toInt() ?? 0,
      revenueByCurrency: (json['revenueByCurrency'] as List<dynamic>?)
              ?.map((r) => CurrencyRevenueData.fromJson(r as Map<String, dynamic>))
              .toList() ??
          const [],
      isStripeTestMode: json['isStripeTestMode'] == true,
      recentTransactions: (json['recentTransactions'] as List<dynamic>?)
              ?.map((tx) => PaymentTransactionData.fromJson(tx as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

class DoctorAnalyticsData {
  final int totalDoctors;
  final int approvedDoctors;
  final int pendingDoctors;
  final int rejectedDoctors;
  final List<SpecialtyCountData> specialtyDistribution;
  final double averageExperienceYears;
  final double averageConsultationFee;

  const DoctorAnalyticsData({
    required this.totalDoctors,
    required this.approvedDoctors,
    required this.pendingDoctors,
    required this.rejectedDoctors,
    required this.specialtyDistribution,
    required this.averageExperienceYears,
    required this.averageConsultationFee,
  });

  factory DoctorAnalyticsData.fromJson(Map<String, dynamic> json) {
    return DoctorAnalyticsData(
      totalDoctors: (json['totalDoctors'] as num?)?.toInt() ?? 0,
      approvedDoctors: (json['approvedDoctors'] as num?)?.toInt() ?? 0,
      pendingDoctors: (json['pendingDoctors'] as num?)?.toInt() ?? 0,
      rejectedDoctors: (json['rejectedDoctors'] as num?)?.toInt() ?? 0,
      specialtyDistribution: (json['specialtyDistribution'] as List<dynamic>?)
              ?.map((s) => SpecialtyCountData.fromJson(s as Map<String, dynamic>))
              .toList() ??
          const [],
      averageExperienceYears: (json['averageExperienceYears'] as num?)?.toDouble() ?? 0.0,
      averageConsultationFee: (json['averageConsultationFee'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class ContentAnalyticsData {
  final int totalArticles;
  final int publishedArticles;
  final int draftArticles;
  final int archivedArticles;
  final List<CategoryAnalyticsData> categoryDistribution;
  final int totalBookmarks;
  final List<TopContentData> topBookmarkedArticles;

  const ContentAnalyticsData({
    required this.totalArticles,
    required this.publishedArticles,
    required this.draftArticles,
    required this.archivedArticles,
    required this.categoryDistribution,
    required this.totalBookmarks,
    required this.topBookmarkedArticles,
  });

  factory ContentAnalyticsData.fromJson(Map<String, dynamic> json) {
    return ContentAnalyticsData(
      totalArticles: (json['totalArticles'] as num?)?.toInt() ?? 0,
      publishedArticles: (json['publishedArticles'] as num?)?.toInt() ?? 0,
      draftArticles: (json['draftArticles'] as num?)?.toInt() ?? 0,
      archivedArticles: (json['archivedArticles'] as num?)?.toInt() ?? 0,
      categoryDistribution: (json['categoryDistribution'] as List<dynamic>?)
              ?.map((c) => CategoryAnalyticsData.fromJson(c as Map<String, dynamic>))
              .toList() ??
          const [],
      totalBookmarks: (json['totalBookmarks'] as num?)?.toInt() ?? 0,
      topBookmarkedArticles: (json['topBookmarkedArticles'] as List<dynamic>?)
              ?.map((t) => TopContentData.fromJson(t as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}
