import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_review.dart';
import 'package:mediconnect/screens/admin/admin_reviews_screen.dart';
import 'package:mediconnect/services/review_service.dart';

class MockModerationReviewService extends Fake implements ReviewService {
  List<AdminReportedReviewItem> items = [
    AdminReportedReviewItem(
      reviewId: 'REV-REP-1',
      appointmentId: 'APPT-303',
      doctorUserId: 'DOC-101',
      doctorName: 'Dr. John Doe',
      patientUserId: 'PAT-202',
      patientDisplayName: 'Kasun P.',
      rating: 1,
      reviewText: 'Inappropriate language in comment test.',
      status: 'REPORTED',
      reportReason: 'Inappropriate content',
      createdAt: DateTime.now().subtract(const Duration(days: 1)),
    ),
    AdminReportedReviewItem(
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
      createdAt: DateTime.now().subtract(const Duration(days: 2)),
    ),
  ];

  String? lastModeratedId;
  String? lastAction;
  String? lastReason;

  @override
  Future<List<AdminReportedReviewItem>> getReportedReviews({
    int page = 1,
    int pageSize = 20,
  }) async {
    return items;
  }

  @override
  Future<bool> moderateReview({
    required String reviewId,
    required String action,
    String? reason,
  }) async {
    lastModeratedId = reviewId;
    lastAction = action;
    lastReason = reason;

    final index = items.indexWhere((r) => r.reviewId == reviewId);
    if (index != -1) {
      final existing = items[index];
      items[index] = AdminReportedReviewItem(
        reviewId: existing.reviewId,
        appointmentId: existing.appointmentId,
        doctorUserId: existing.doctorUserId,
        doctorName: existing.doctorName,
        patientUserId: existing.patientUserId,
        patientDisplayName: existing.patientDisplayName,
        rating: existing.rating,
        reviewText: existing.reviewText,
        status: action == 'HIDE' ? 'HIDDEN' : 'PUBLISHED',
        reportReason: existing.reportReason,
        createdAt: existing.createdAt,
      );
    }
    return true;
  }
}

void main() {
  testWidgets('AdminReviewsScreen renders reported reviews and allows moderation', (tester) async {
    final mockService = MockModerationReviewService();

    await tester.pumpWidget(
      MaterialApp(
        home: AdminReviewsScreen(reviewService: mockService),
      ),
    );

    await tester.pumpAndSettle();

    // Verify header and review texts
    expect(find.text('Review Moderation'), findsOneWidget);
    expect(find.text('"Inappropriate language in comment test."'), findsOneWidget);
    expect(find.text('"Spam review advertisement."'), findsOneWidget);

    // Verify doctor names and report reasons
    expect(find.text('Dr. John Doe'), findsOneWidget);
    expect(find.text('Dr. Jane Smith'), findsOneWidget);
    expect(find.text('Report reason: Inappropriate content'), findsOneWidget);

    // Verify action buttons
    final hideButton = find.byKey(const Key('hide_review_button_REV-REP-1'));
    expect(hideButton, findsOneWidget);

    final restoreButton = find.byKey(const Key('restore_review_button_REV-REP-2'));
    expect(restoreButton, findsOneWidget);

    // Tap "Hide Review" on first review
    await tester.tap(hideButton);
    await tester.pumpAndSettle();

    expect(mockService.lastModeratedId, 'REV-REP-1');
    expect(mockService.lastAction, 'HIDE');
    expect(find.text('Review hidden from public view.'), findsOneWidget);

    // Dismiss first SnackBar before interacting with second item
    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();

    // Ensure restore button is visible and tap
    await tester.ensureVisible(restoreButton);
    await tester.tap(restoreButton);
    await tester.pumpAndSettle();

    expect(mockService.lastModeratedId, 'REV-REP-2');
    expect(mockService.lastAction, 'RESTORE');
    expect(find.text('Review restored.'), findsOneWidget);
  });
}
