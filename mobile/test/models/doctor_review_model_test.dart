import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_review.dart';

void main() {
  group('DoctorRatingSummary model tests', () {
    test('parses active doctor rating summary correctly', () {
      final json = {
        'doctorId': 'DOC-123',
        'doctorUserId': 'usr_doc_123',
        'doctorProfileId': 'prof_123',
        'averageRating': 4.6,
        'totalReviews': 10,
        'ratingDistribution': {
          '1': 0,
          '2': 1,
          '3': 1,
          '4': 2,
          '5': 6,
        },
        'hasReviews': true,
      };

      final summary = DoctorRatingSummary.fromJson(json);
      expect(summary.doctorId, 'DOC-123');
      expect(summary.averageRating, 4.6);
      expect(summary.totalReviews, 10);
      expect(summary.hasReviews, isTrue);
      expect(summary.getStarPercentage(5), 0.6);
      expect(summary.getStarPercentage(1), 0.0);
    });

    test('parses zero-review doctor summary without fabricated ratings', () {
      final json = {
        'doctorId': 'DOC-NEW',
        'averageRating': null,
        'totalReviews': 0,
        'ratingDistribution': {
          '1': 0,
          '2': 0,
          '3': 0,
          '4': 0,
          '5': 0,
        },
        'hasReviews': false,
      };

      final summary = DoctorRatingSummary.fromJson(json);
      expect(summary.doctorId, 'DOC-NEW');
      expect(summary.averageRating, isNull);
      expect(summary.totalReviews, 0);
      expect(summary.hasReviews, isFalse);
      expect(summary.getStarPercentage(5), 0.0);
    });
  });

  group('DoctorReview model tests', () {
    test('parses verified review item correctly', () {
      final json = {
        '_id': 'mongo_rev_1',
        'reviewId': 'REV-20261018-ABC123',
        'doctorUserId': 'usr_doc_1',
        'patientDisplayName': 'Kamal S.',
        'appointmentId': 'appt_999',
        'rating': 5,
        'reviewText': 'Excellent care and diagnostic attention.',
        'status': 'PUBLISHED',
        'verifiedAppointment': true,
        'createdAt': '2026-10-18T00:00:00.000Z',
      };

      final review = DoctorReview.fromJson(json);
      expect(review.reviewId, 'REV-20261018-ABC123');
      expect(review.rating, 5);
      expect(review.patientDisplayName, 'Kamal S.');
      expect(review.appointmentId, 'appt_999');
      expect(review.reviewText, 'Excellent care and diagnostic attention.');
      expect(review.verifiedAppointment, isTrue);
      expect(review.status, 'PUBLISHED');
    });

    test('parses paginated reviews page response', () {
      final json = {
        'items': [
          {
            'reviewId': 'REV-1',
            'doctorUserId': 'doc_1',
            'patientDisplayName': 'Alice P.',
            'appointmentId': 'appt_1',
            'rating': 4,
            'reviewText': 'Very good consultation',
            'status': 'PUBLISHED',
            'createdAt': '2026-10-18T01:00:00.000Z',
          }
        ],
        'total': 1,
        'page': 1,
        'pageSize': 10,
        'totalPages': 1,
        'summary': {
          'doctorId': 'DOC-1',
          'averageRating': 4.0,
          'totalReviews': 1,
          'hasReviews': true,
        },
      };

      final page = DoctorReviewsPage.fromJson(json);
      expect(page.total, 1);
      expect(page.items.length, 1);
      expect(page.items.first.reviewId, 'REV-1');
      expect(page.summary, isNotNull);
      expect(page.summary!.averageRating, 4.0);
    });
  });
}
