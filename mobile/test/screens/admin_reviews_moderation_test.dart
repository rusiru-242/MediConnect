import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_review.dart';

void main() {
  group('AdminReportedReviewItem model tests', () {
    test('parses reported review item from JSON correctly', () {
      final json = {
        'reviewId': 'REV-REP-1',
        'appointmentId': 'APPT-303',
        'doctorUserId': 'DOC-101',
        'doctorName': 'Dr. John Doe',
        'patientUserId': 'PAT-202',
        'patientDisplayName': 'Kasun P.',
        'rating': 1,
        'reviewText': 'Inappropriate language in comment test.',
        'status': 'REPORTED',
        'reportReason': 'Inappropriate content',
        'createdAt': '2026-10-17T10:00:00Z',
      };

      final item = AdminReportedReviewItem.fromJson(json);

      expect(item.reviewId, 'REV-REP-1');
      expect(item.appointmentId, 'APPT-303');
      expect(item.doctorUserId, 'DOC-101');
      expect(item.doctorName, 'Dr. John Doe');
      expect(item.patientUserId, 'PAT-202');
      expect(item.patientDisplayName, 'Kasun P.');
      expect(item.rating, 1);
      expect(item.reviewText, 'Inappropriate language in comment test.');
      expect(item.status, 'REPORTED');
      expect(item.reportReason, 'Inappropriate content');
    });

    test('serializes reported review item to JSON correctly', () {
      final item = AdminReportedReviewItem(
        reviewId: 'REV-REP-2',
        appointmentId: 'APPT-304',
        doctorUserId: 'DOC-102',
        doctorName: 'Dr. Jane Smith',
        patientUserId: 'PAT-203',
        patientDisplayName: 'Nuwan S.',
        rating: 2,
        reviewText: 'Spam review advertisement.',
        status: 'HIDDEN',
        reportReason: 'Spam / Advertisement',
        createdAt: DateTime.parse('2026-10-16T12:00:00Z'),
      );

      final json = item.toJson();

      expect(json['reviewId'], 'REV-REP-2');
      expect(json['status'], 'HIDDEN');
      expect(json['reportReason'], 'Spam / Advertisement');
      expect(json['rating'], 2);
    });
  });
}
