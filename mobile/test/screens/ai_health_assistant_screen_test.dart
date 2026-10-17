import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/health_chat.dart';
import 'package:mediconnect/screens/patient/ai_health_assistant_screen.dart';
import 'package:mediconnect/services/health_chat_service.dart';


class MockAiHealthChatService extends AiHealthChatService {
  late HealthChatSession session;
  bool deleteCalled = false;

  MockAiHealthChatService() {
    session = HealthChatSession(
      id: 'mock-sess-1',
      patientUserId: 'pat-1',
      language: 'en',
      consentGiven: true,
      triageLevel: 'general_info',
      messages: [
        HealthChatMessage(
          id: 'm-welcome',
          sender: 'assistant',
          content: 'Hello! I am your MediConnect AI Health Assistant.',
          timestamp: DateTime.now(),
          disclaimer: 'MediConnect provides general health guidance only.',
        ),
      ],
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
      expiresAt: DateTime.now().add(const Duration(hours: 48)),
    );
  }

  @override
  Future<HealthChatSession> createSession({
    String language = 'en',
    bool consentGiven = true,
    String? initialMessage,
  }) async {
    return session;
  }

  @override
  Future<HealthChatSession> getSession(String sessionId) async {
    return session;
  }

  @override
  Future<HealthChatSession> sendMessage(
    String sessionId,
    String message, {
    String? language,
  }) async {
    final userMsg = HealthChatMessage(
      id: 'm-user-${DateTime.now().millisecondsSinceEpoch}',
      sender: 'user',
      content: message,
      timestamp: DateTime.now(),
    );

    HealthChatMessage assistantMsg;
    if (message.toLowerCase().contains('chest pain') || message.contains('පපුවේ කැක්කුම')) {
      assistantMsg = HealthChatMessage(
        id: 'm-emg-${DateTime.now().millisecondsSinceEpoch}',
        sender: 'assistant',
        content: 'POTENTIAL MEDICAL EMERGENCY: Call 1990 immediately or proceed to ETU.',
        timestamp: DateTime.now(),
        triageLevel: 'emergency',
        isUrgent: true,
        emergencyNumber: '1990',
        disclaimer: 'MediConnect emergency disclaimer.',
      );
    } else if (message.toLowerCase().contains('headache') || message.contains('doctor')) {
      assistantMsg = HealthChatMessage(
        id: 'm-doc-${DateTime.now().millisecondsSinceEpoch}',
        sender: 'assistant',
        content: 'Your symptoms suggest scheduling a clinical consultation.',
        timestamp: DateTime.now(),
        triageLevel: 'routine_care',
        isUrgent: false,
        doctorReferrals: [
          const DoctorReferralCard(
            doctorId: 'DOC-999',
            fullName: 'Dr. Kasun Fernando',
            specialty: 'General Physician',
            consultationFee: 2000.0,
            city: 'Colombo',
            nextAvailableSlot: 'Tomorrow at 10:00',
          ),
        ],
      );
    } else {
      assistantMsg = HealthChatMessage(
        id: 'm-asst-${DateTime.now().millisecondsSinceEpoch}',
        sender: 'assistant',
        content: 'This is educational guidance regarding health and wellness.',
        timestamp: DateTime.now(),
        triageLevel: 'general_info',
        disclaimer: 'Educational disclaimer.',
      );
    }

    session = HealthChatSession(
      id: session.id,
      patientUserId: session.patientUserId,
      language: language ?? session.language,
      consentGiven: session.consentGiven,
      triageLevel: assistantMsg.triageLevel,
      messages: [...session.messages, userMsg, assistantMsg],
      createdAt: session.createdAt,
      updatedAt: DateTime.now(),
      expiresAt: session.expiresAt,
    );

    return session;
  }

  @override
  Future<bool> deleteSession(String sessionId) async {
    deleteCalled = true;
    return true;
  }
}

void main() {
  Widget createTestWidget({required MockAiHealthChatService mockService}) {
    return MaterialApp(
      home: AiHealthAssistantScreen(chatService: mockService),
      routes: {
        '/patient/doctor-detail': (ctx) => const Scaffold(body: Text('Doctor Detail Screen')),
        '/patient/ai-booking': (ctx) => const Scaffold(body: Text('AI Booking Screen')),
      },
    );
  }

  group('AiHealthAssistantScreen Widget Tests', () {
    testWidgets('renders disclaimer banner, welcome message, and starter chips', (tester) async {
      final mock = MockAiHealthChatService();
      await tester.pumpWidget(createTestWidget(mockService: mock));
      await tester.pumpAndSettle();

      expect(find.text('AI Health Assistant'), findsOneWidget);
      expect(find.byKey(const Key('health_chat_disclaimer_banner')), findsOneWidget);
      expect(find.text('Hello! I am your MediConnect AI Health Assistant.'), findsOneWidget);
      expect(find.byKey(const Key('health_chat_starter_chips')), findsOneWidget);
      expect(find.byKey(const Key('health_chat_input_field')), findsOneWidget);
      expect(find.byKey(const Key('health_chat_send_button')), findsOneWidget);
    });

    testWidgets('sends general inquiry message and renders assistant reply', (tester) async {
      final mock = MockAiHealthChatService();
      await tester.pumpWidget(createTestWidget(mockService: mock));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('health_chat_input_field')), 'How to stay hydrated?');
      await tester.tap(find.byKey(const Key('health_chat_send_button')));
      await tester.pumpAndSettle();

      expect(find.text('How to stay hydrated?'), findsOneWidget);
      expect(find.text('This is educational guidance regarding health and wellness.'), findsOneWidget);
    });

    testWidgets('triggers emergency escalation with 1990 ambulance banner and button', (tester) async {
      final mock = MockAiHealthChatService();
      await tester.pumpWidget(createTestWidget(mockService: mock));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('health_chat_input_field')), 'Severe chest pain');
      await tester.tap(find.byKey(const Key('health_chat_send_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('health_chat_emergency_banner')), findsOneWidget);
      expect(find.byKey(const Key('health_chat_emergency_call_1990_button')), findsOneWidget);
      expect(find.text('CALL 1990 AMBULANCE NOW'), findsOneWidget);
    });

    testWidgets('renders doctor referral card with profile and booking actions', (tester) async {
      final mock = MockAiHealthChatService();
      await tester.pumpWidget(createTestWidget(mockService: mock));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('health_chat_input_field')), 'I have a persistent headache, need doctor');
      await tester.tap(find.byKey(const Key('health_chat_send_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('doctor_referral_card_DOC-999')), findsOneWidget);
      expect(find.text('Dr. Kasun Fernando'), findsOneWidget);
      expect(find.text('Fee: LKR 2000 • Colombo'), findsOneWidget);
      expect(find.byKey(const Key('doctor_referral_view_button_DOC-999')), findsOneWidget);
      expect(find.byKey(const Key('doctor_referral_book_button_DOC-999')), findsOneWidget);
    });

    testWidgets('toggles language between English and Sinhala', (tester) async {
      final mock = MockAiHealthChatService();
      await tester.pumpWidget(createTestWidget(mockService: mock));
      await tester.pumpAndSettle();

      expect(find.text('EN'), findsOneWidget);
      await tester.tap(find.byKey(const Key('health_chat_language_toggle')));
      await tester.pumpAndSettle();

      expect(find.text('SI'), findsOneWidget);
    });

    testWidgets('opens delete conversation confirmation dialog', (tester) async {
      final mock = MockAiHealthChatService();
      await tester.pumpWidget(createTestWidget(mockService: mock));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('health_chat_delete_button')));
      await tester.pumpAndSettle();

      expect(find.text('Delete Conversation?'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Delete & Start Fresh'), findsOneWidget);

      await tester.tap(find.text('Delete & Start Fresh'));
      await tester.pumpAndSettle();

      expect(mock.deleteCalled, isTrue);
    });
  });
}
