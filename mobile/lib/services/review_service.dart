import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/doctor_review.dart';

/// Service interfacing with the MediConnect Doctor Reviews & Ratings API (Phase 23).
class ReviewService {
  final ApiClient _apiClient;

  ReviewService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Fetch rating summary for a verified doctor.
  Future<DoctorRatingSummary> getDoctorRatingSummary(String doctorId) async {
    final endpoint = ApiConstants.doctorRatingSummaryEndpoint(doctorId);
    final response = await _apiClient.get(endpoint, includeAuth: false);

    if (response is Map<String, dynamic>) {
      return DoctorRatingSummary.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching doctor rating summary.');
  }

  /// Fetch paginated verified reviews for a doctor.
  Future<DoctorReviewsPage> getDoctorReviews(
    String doctorId, {
    int page = 1,
    int pageSize = 10,
  }) async {
    final endpoint = '${ApiConstants.doctorReviewsEndpoint(doctorId)}?page=$page&page_size=$pageSize';
    final response = await _apiClient.get(endpoint, includeAuth: false);

    if (response is Map<String, dynamic>) {
      return DoctorReviewsPage.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching doctor reviews.');
  }

  /// Fetch reviews submitted by the authenticated patient.
  Future<DoctorReviewsPage> getMyReviews({
    int page = 1,
    int pageSize = 20,
  }) async {
    final endpoint = '${ApiConstants.myReviewsEndpoint}?page=$page&page_size=$pageSize';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return DoctorReviewsPage.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching patient reviews.');
  }

  /// Submit a new verified review for a completed appointment.
  Future<DoctorReview> submitReview({
    required String appointmentId,
    required int rating,
    String? reviewText,
  }) async {
    final payload = {
      'appointmentId': appointmentId,
      'rating': rating,
      if (reviewText != null && reviewText.trim().isNotEmpty) 'reviewText': reviewText.trim(),
    };

    final response = await _apiClient.post(
      ApiConstants.reviewsEndpoint,
      body: payload,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DoctorReview.fromJson(response);
    }
    throw Exception('Unexpected response format when submitting review.');
  }

  /// Update an existing review rating or text by author.
  Future<DoctorReview> updateReview({
    required String reviewId,
    int? rating,
    String? reviewText,
  }) async {
    final payload = <String, dynamic>{};
    if (rating != null) payload['rating'] = rating;
    if (reviewText != null) payload['reviewText'] = reviewText.trim();

    final response = await _apiClient.patch(
      ApiConstants.reviewDetailEndpoint(reviewId),
      body: payload,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DoctorReview.fromJson(response);
    }
    throw Exception('Unexpected response format when updating review.');
  }

  /// Delete an authored review.
  Future<bool> deleteReview(String reviewId) async {
    final response = await _apiClient.delete(
      ApiConstants.reviewDetailEndpoint(reviewId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return true;
  }

  /// Flag an inappropriate review for moderation.
  Future<bool> reportReview({
    required String reviewId,
    required String reason,
  }) async {
    final payload = {'reason': reason.trim()};
    final response = await _apiClient.post(
      ApiConstants.reportReviewEndpoint(reviewId),
      body: payload,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return true;
  }
}
