import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_recommendation.dart';
import 'package:mediconnect/screens/patient/ai_doctor_recommendation_screen.dart';
import 'package:mediconnect/services/ai_recommendation_service.dart';

class MockAiRecommendationService extends AiRecommendationService {
  DoctorRecommendationResponse? mockResponse;
  bool shouldThrow = false;
  String? lastQuery;

  @override
  Future<DoctorRecommendationResponse> getDoctorRecommendations({
    required String query,
    String? specialty,
    String? city,
    String? date,
    String? timeRange,
    double? maxFee,
    String? consultationType,
  }) async {
    lastQuery = query;
    if (shouldThrow) {
      throw Exception('Simulated network failure');
    }
    return mockResponse ??
        DoctorRecommendationResponse(
          interpretedPreferences: InterpretedPreferences(
            specialty: 'Cardiologist',
            city: 'Colombo',
            languageDetected: 'en',
          ),
          recommendations: [
            DoctorRecommendation(
              doctorId: 'DOC-101',
              fullName: 'Dr. Kamal Perera',
              specialty: 'Cardiologist',
              hospitalOrClinic: 'Asiri Central Hospital, Colombo',
              experienceYears: 12,
              consultationFee: 2500.0,
              score: 95.0,
              matchReasons: [
                'Direct match for requested specialty: Cardiologist',
                'Located in Colombo',
              ],
              availableSlots: [
                RecommendedSlot(
                  date: '2026-10-15',
                  startTime: '18:00',
                  endTime: '18:30',
                  availabilityId: 'avail_101',
                ),
              ],
            ),
          ],
          totalMatches: 1,
          isUrgent: false,
          disclaimer: 'Informational discovery tool only.',
          aiProviderUsed: 'deterministic_fallback',
        );
  }
}

void main() {
  Widget createTestWidget(MockAiRecommendationService mockService) {
    return MaterialApp(
      home: AiDoctorRecommendationScreen(aiService: mockService),
    );
  }

  group('AiDoctorRecommendationScreen Tests', () {
    testWidgets('Renders header, input field, and sample prompts', (tester) async {
      final mockService = MockAiRecommendationService();
      await tester.pumpWidget(createTestWidget(mockService));
      await tester.pumpAndSettle();

      expect(find.text('AI Doctor Finder'), findsOneWidget);
      expect(find.byKey(const Key('ai_doctor_search_input')), findsOneWidget);
      expect(find.byKey(const Key('ai_doctor_search_submit_button')), findsOneWidget);
      expect(find.text('Example Inquiries:'), findsOneWidget);
      expect(find.text('Cardiologist in Colombo tomorrow'), findsOneWidget);
    });

    testWidgets('Submitting query displays recommendations with match score and available slots', (tester) async {
      final mockService = MockAiRecommendationService();
      await tester.pumpWidget(createTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_doctor_search_input')),
        'I need a heart specialist in Colombo',
      );
      await tester.tap(find.byKey(const Key('ai_doctor_search_submit_button')));
      await tester.pump(); // Start loading
      await tester.pumpAndSettle(); // Finish loading

      expect(mockService.lastQuery, 'I need a heart specialist in Colombo');
      expect(find.text('Dr. Kamal Perera'), findsOneWidget);
      expect(find.text('Cardiologist'), findsWidgets);
      expect(find.text('95% Match'), findsOneWidget);
      expect(find.text('Why Recommended:'), findsOneWidget);
      expect(find.text('Real Available Slots:'), findsOneWidget);
      expect(find.text('2026-10-15 18:00'), findsOneWidget);
      expect(find.text('View Profile'), findsOneWidget);
      expect(find.text('Book Slot'), findsOneWidget);
    });

    testWidgets('Urgent response displays emergency guidance banner', (tester) async {
      final mockService = MockAiRecommendationService()
        ..mockResponse = DoctorRecommendationResponse(
          interpretedPreferences: InterpretedPreferences(specialty: 'Cardiologist'),
          recommendations: [],
          totalMatches: 0,
          isUrgent: true,
          safetyGuidance: 'Acute chest pain detected. Seek immediate emergency evaluation.',
          disclaimer: 'Informational discovery tool only.',
          aiProviderUsed: 'deterministic_fallback',
        );

      await tester.pumpWidget(createTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_doctor_search_input')),
        'I have severe crushing chest pain',
      );
      await tester.tap(find.byKey(const Key('ai_doctor_search_submit_button')));
      await tester.pumpAndSettle();

      expect(find.text('Potential Emergency Caution'), findsOneWidget);
      expect(find.text('Call Ambulance (1990)'), findsOneWidget);
      expect(find.textContaining('Acute chest pain detected'), findsOneWidget);
    });

    testWidgets('Error during search displays error state with retry button', (tester) async {
      final mockService = MockAiRecommendationService()..shouldThrow = true;

      await tester.pumpWidget(createTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_doctor_search_input')),
        'Test query',
      );
      await tester.tap(find.byKey(const Key('ai_doctor_search_submit_button')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Unable to complete AI doctor search'), findsOneWidget);
      expect(find.text('Try Again'), findsOneWidget);
    });

    testWidgets('Tapping sample prompt populates input and triggers search', (tester) async {
      final mockService = MockAiRecommendationService();
      await tester.pumpWidget(createTestWidget(mockService));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cardiologist in Colombo tomorrow'));
      await tester.pumpAndSettle();

      expect(mockService.lastQuery, 'Cardiologist in Colombo tomorrow');
      expect(find.text('Dr. Kamal Perera'), findsOneWidget);
    });
  });
}
