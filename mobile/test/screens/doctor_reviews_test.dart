import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor.dart';
import 'package:mediconnect/models/doctor_availability.dart';
import 'package:mediconnect/models/doctor_review.dart';
import 'package:mediconnect/screens/patient/doctor_detail_screen.dart';
import 'package:mediconnect/screens/patient/my_reviews_screen.dart';
import 'package:mediconnect/screens/patient/submit_review_dialog.dart';
import 'package:mediconnect/services/doctor_service.dart';
import 'package:mediconnect/services/review_service.dart';

class MockReviewService extends Fake implements ReviewService {
  DoctorRatingSummary mockSummary = const DoctorRatingSummary(
    doctorId: 'DOC-1',
    averageRating: 4.8,
    totalReviews: 5,
    ratingDistribution: {'1': 0, '2': 0, '3': 0, '4': 1, '5': 4},
    hasReviews: true,
  );

  List<DoctorReview> mockDoctorReviews = [
    DoctorReview(
      reviewId: 'REV-1',
      doctorUserId: 'doc_1',
      patientDisplayName: 'Alice P.',
      appointmentId: 'appt_1',
      rating: 5,
      reviewText: 'Great doctor, very helpful.',
      status: 'PUBLISHED',
      verifiedAppointment: true,
      createdAt: DateTime.now(),
    ),
  ];

  List<DoctorReview> mockMyReviews = [
    DoctorReview(
      reviewId: 'REV-MY-1',
      doctorUserId: 'doc_1',
      doctorName: 'Dr. Sarath Perera',
      doctorSpecialty: 'Cardiologist',
      patientDisplayName: 'Alice P.',
      appointmentId: 'appt_1',
      rating: 5,
      reviewText: 'Excellent care and diagnosis.',
      status: 'PUBLISHED',
      verifiedAppointment: true,
      createdAt: DateTime.now(),
    ),
  ];

  bool submitCalled = false;
  int? submittedRating;
  String? submittedText;

  @override
  Future<DoctorRatingSummary> getDoctorRatingSummary(String doctorId) async {
    return mockSummary;
  }

  @override
  Future<DoctorReviewsPage> getDoctorReviews(String doctorId, {int page = 1, int pageSize = 10}) async {
    return DoctorReviewsPage(
      items: mockDoctorReviews,
      total: mockDoctorReviews.length,
      page: page,
      pageSize: pageSize,
      totalPages: 1,
      summary: mockSummary,
    );
  }

  @override
  Future<DoctorReviewsPage> getMyReviews({int page = 1, int pageSize = 20}) async {
    return DoctorReviewsPage(
      items: mockMyReviews,
      total: mockMyReviews.length,
      page: page,
      pageSize: pageSize,
      totalPages: 1,
    );
  }

  @override
  Future<DoctorReview> submitReview({
    required String appointmentId,
    required int rating,
    String? reviewText,
  }) async {
    submitCalled = true;
    submittedRating = rating;
    submittedText = reviewText;
    return DoctorReview(
      reviewId: 'REV-NEW-1',
      doctorUserId: 'doc_1',
      patientDisplayName: 'Me P.',
      appointmentId: appointmentId,
      rating: rating,
      reviewText: reviewText,
      status: 'PUBLISHED',
      verifiedAppointment: true,
      createdAt: DateTime.now(),
    );
  }

  @override
  Future<bool> deleteReview(String reviewId) async {
    mockMyReviews.removeWhere((r) => r.reviewId == reviewId);
    return true;
  }
}

class MockDoctorService extends Fake implements DoctorService {
  @override
  Future<List<DayAvailabilitySlots>> getDoctorAvailability(String doctorId, {String? date}) async {
    return [];
  }
}

void main() {
  testWidgets('SubmitReviewDialog allows star selection and written review submission', (tester) async {
    final mockService = MockReviewService();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () {
                SubmitReviewDialog.show(
                  context,
                  appointmentId: 'appt_test_1',
                  doctorName: 'Dr. Sarath Perera',
                  reviewService: mockService,
                );
              },
              child: const Text('Open Dialog'),
            ),
          ),
        ),
      ),
    );

    // Open dialog
    await tester.tap(find.text('Open Dialog'));
    await tester.pumpAndSettle();

    expect(find.text('Rate & Review Doctor'), findsOneWidget);
    expect(find.text('Excellent (5/5)'), findsOneWidget);
    expect(find.textContaining('Privacy Notice'), findsOneWidget);

    // Select star 4
    await tester.tap(find.byKey(const Key('rating_star_4')));
    await tester.pumpAndSettle();
    expect(find.text('Very Good (4/5)'), findsOneWidget);

    // Enter review text
    await tester.enterText(find.byKey(const Key('review_text_field')), 'Thorough and attentive.');
    await tester.pumpAndSettle();

    // Tap submit
    await tester.ensureVisible(find.byKey(const Key('submit_review_button')));
    await tester.tap(find.byKey(const Key('submit_review_button')));
    await tester.pumpAndSettle();

    expect(mockService.submitCalled, isTrue);
    expect(mockService.submittedRating, 4);
    expect(mockService.submittedText, 'Thorough and attentive.');
  });

  testWidgets('MyReviewsScreen displays patient reviews with edit and delete options', (tester) async {
    final mockService = MockReviewService();

    await tester.pumpWidget(
      MaterialApp(
        home: MyReviewsScreen(reviewService: mockService),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('My Doctor Reviews'), findsOneWidget);
    expect(find.text('Dr. Sarath Perera'), findsOneWidget);
    expect(find.text('Cardiologist'), findsOneWidget);
    expect(find.text('5.0'), findsOneWidget);
    expect(find.text('Excellent care and diagnosis.'), findsOneWidget);
    expect(find.text('Verified Consultation'), findsOneWidget);
    expect(find.text('Edit'), findsOneWidget);
    expect(find.byIcon(Icons.delete_outline), findsOneWidget);
  });

  testWidgets('DoctorDetailScreen renders rating summary and verified patient reviews', (tester) async {
    final mockReviewService = MockReviewService();
    final mockDoctorService = MockDoctorService();

    final sampleDoctor = Doctor(
      doctorId: 'DOC-1',
      fullName: 'Dr. Sarath Perera',
      specialty: 'Cardiologist',
      qualifications: 'MBBS, MD',
      hospitalOrClinic: 'Asiri Central',
      experienceYears: 12,
      consultationFee: 3500.0,
      verificationStatus: 'APPROVED',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: DoctorDetailScreen(
          doctor: sampleDoctor,
          doctorService: mockDoctorService,
          reviewService: mockReviewService,
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Patient Reviews & Ratings'), findsOneWidget);
    expect(find.text('4.8'), findsOneWidget);
    expect(find.text('5 verified reviews'), findsOneWidget);
    expect(find.text('Verified Patient Feedback'), findsOneWidget);
    expect(find.text('Alice P.'), findsOneWidget);
    expect(find.text('Great doctor, very helpful.'), findsOneWidget);
  });

  testWidgets('DoctorDetailScreen displays empty state when doctor has no reviews', (tester) async {
    final mockReviewService = MockReviewService();
    mockReviewService.mockSummary = const DoctorRatingSummary(
      doctorId: 'DOC-ZERO',
      averageRating: null,
      totalReviews: 0,
      hasReviews: false,
    );
    mockReviewService.mockDoctorReviews = [];

    final mockDoctorService = MockDoctorService();

    final sampleDoctor = Doctor(
      doctorId: 'DOC-ZERO',
      fullName: 'Dr. New Doctor',
      specialty: 'General Physician',
      qualifications: 'MBBS',
      hospitalOrClinic: 'General Hospital',
      experienceYears: 2,
      consultationFee: 2000.0,
      verificationStatus: 'APPROVED',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: DoctorDetailScreen(
          doctor: sampleDoctor,
          doctorService: mockDoctorService,
          reviewService: mockReviewService,
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Patient Reviews & Ratings'), findsOneWidget);
    expect(find.text('No reviews yet'), findsOneWidget);
  });
}
