// Data models for Doctor Reviews and Verified Ratings (Phase 23).

class DoctorRatingSummary {
  final String doctorId;
  final String? doctorUserId;
  final String? doctorProfileId;
  final double? averageRating;
  final int totalReviews;
  final Map<String, int> ratingDistribution;
  final bool hasReviews;

  const DoctorRatingSummary({
    required this.doctorId,
    this.doctorUserId,
    this.doctorProfileId,
    this.averageRating,
    this.totalReviews = 0,
    this.ratingDistribution = const {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0},
    this.hasReviews = false,
  });

  factory DoctorRatingSummary.fromJson(Map<String, dynamic> json) {
    final rawDist = json['ratingDistribution'];
    final dist = <String, int>{'1': 0, '2': 0, '3': 0, '4': 0, '5': 0};
    if (rawDist is Map) {
      rawDist.forEach((key, val) {
        dist[key.toString()] = (val is num) ? val.toInt() : 0;
      });
    }

    double? avg;
    if (json['averageRating'] != null) {
      avg = (json['averageRating'] as num).toDouble();
    }

    return DoctorRatingSummary(
      doctorId: (json['doctorId'] ?? '').toString(),
      doctorUserId: json['doctorUserId']?.toString(),
      doctorProfileId: json['doctorProfileId']?.toString(),
      averageRating: avg,
      totalReviews: (json['totalReviews'] as num?)?.toInt() ?? 0,
      ratingDistribution: dist,
      hasReviews: json['hasReviews'] == true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorId': doctorId,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'averageRating': averageRating,
      'totalReviews': totalReviews,
      'ratingDistribution': ratingDistribution,
      'hasReviews': hasReviews,
    };
  }

  /// Calculates percentage for a given star (1-5) for distribution progress bars.
  double getStarPercentage(int star) {
    if (totalReviews == 0) return 0.0;
    final count = ratingDistribution[star.toString()] ?? 0;
    return (count / totalReviews).clamp(0.0, 1.0);
  }
}

class DoctorReview {
  final String? id;
  final String reviewId;
  final String doctorUserId;
  final String? doctorProfileId;
  final String? doctorName;
  final String? doctorSpecialty;
  final String? doctorHospital;
  final String? patientUserId;
  final String patientDisplayName;
  final String appointmentId;
  final int rating;
  final String? reviewText;
  final String status;
  final bool verifiedAppointment;
  final DateTime createdAt;
  final DateTime? updatedAt;

  const DoctorReview({
    this.id,
    required this.reviewId,
    required this.doctorUserId,
    this.doctorProfileId,
    this.doctorName,
    this.doctorSpecialty,
    this.doctorHospital,
    this.patientUserId,
    required this.patientDisplayName,
    required this.appointmentId,
    required this.rating,
    this.reviewText,
    required this.status,
    this.verifiedAppointment = true,
    required this.createdAt,
    this.updatedAt,
  });

  factory DoctorReview.fromJson(Map<String, dynamic> json) {
    DateTime parsedCreated;
    try {
      parsedCreated = json['createdAt'] != null
          ? DateTime.parse(json['createdAt'].toString()).toLocal()
          : DateTime.now();
    } catch (_) {
      parsedCreated = DateTime.now();
    }

    DateTime? parsedUpdated;
    if (json['updatedAt'] != null) {
      try {
        parsedUpdated = DateTime.parse(json['updatedAt'].toString()).toLocal();
      } catch (_) {
        parsedUpdated = null;
      }
    }

    return DoctorReview(
      id: json['_id']?.toString() ?? json['id']?.toString(),
      reviewId: (json['reviewId'] ?? '').toString(),
      doctorUserId: (json['doctorUserId'] ?? '').toString(),
      doctorProfileId: json['doctorProfileId']?.toString(),
      doctorName: json['doctorName']?.toString(),
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      doctorHospital: json['doctorHospital']?.toString(),
      patientUserId: json['patientUserId']?.toString(),
      patientDisplayName: (json['patientDisplayName'] ?? 'Verified Patient').toString(),
      appointmentId: (json['appointmentId'] ?? '').toString(),
      rating: (json['rating'] as num?)?.toInt() ?? 5,
      reviewText: json['reviewText']?.toString(),
      status: (json['status'] ?? 'PUBLISHED').toString(),
      verifiedAppointment: json['verifiedAppointment'] != false,
      createdAt: parsedCreated,
      updatedAt: parsedUpdated,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'reviewId': reviewId,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'doctorName': doctorName,
      'doctorSpecialty': doctorSpecialty,
      'doctorHospital': doctorHospital,
      'patientUserId': patientUserId,
      'patientDisplayName': patientDisplayName,
      'appointmentId': appointmentId,
      'rating': rating,
      'reviewText': reviewText,
      'status': status,
      'verifiedAppointment': verifiedAppointment,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt?.toIso8601String(),
    };
  }
}

class DoctorReviewsPage {
  final List<DoctorReview> items;
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
  final DoctorRatingSummary? summary;

  const DoctorReviewsPage({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    this.summary,
  });

  factory DoctorReviewsPage.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'];
    final itemsList = <DoctorReview>[];
    if (rawItems is List) {
      for (final it in rawItems) {
        if (it is Map<String, dynamic>) {
          itemsList.add(DoctorReview.fromJson(it));
        }
      }
    }

    DoctorRatingSummary? parsedSummary;
    if (json['summary'] is Map<String, dynamic>) {
      parsedSummary = DoctorRatingSummary.fromJson(json['summary'] as Map<String, dynamic>);
    }

    return DoctorReviewsPage(
      items: itemsList,
      total: (json['total'] as num?)?.toInt() ?? itemsList.length,
      page: (json['page'] as num?)?.toInt() ?? 1,
      pageSize: (json['pageSize'] as num?)?.toInt() ?? 10,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 1,
      summary: parsedSummary,
    );
  }
}
