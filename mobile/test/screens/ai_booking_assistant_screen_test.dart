import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/patient/ai_booking_assistant_screen.dart';
import 'package:mediconnect/services/ai_booking_service.dart';

class FakeAiBookingService implements AiBookingService {
  BookingSession currentSession;

  FakeAiBookingService({BookingSession? initialSession})
      : currentSession = initialSession ??
            BookingSession(
              id: 'test_session_1',
              patientUserId: 'patient_1',
              state: 'COLLECTING_PREFERENCES',
              preferences: const BookingPreferences(language: 'en'),
              messages: [
                ChatMessage(
                  id: 'msg_1',
                  sender: 'assistant',
                  content: "Hello! I'm your MediConnect AI Booking Assistant.",
                  timestamp: DateTime.now(),
                ),
              ],
              createdAt: DateTime.now(),
              updatedAt: DateTime.now(),
              expiresAt: DateTime.now().add(const Duration(minutes: 30)),
            );

  @override
  Future<BookingSession> createSession({String? initialMessage}) async {
    return currentSession;
  }

  @override
  Future<BookingSession> getSession(String sessionId) async {
    return currentSession;
  }

  @override
  Future<BookingSession> sendMessage(String sessionId, String message) async {
    final updatedMessages = List<ChatMessage>.from(currentSession.messages)
      ..add(ChatMessage(
        id: 'msg_user',
        sender: 'user',
        content: message,
        timestamp: DateTime.now(),
      ))
      ..add(ChatMessage(
        id: 'msg_reply',
        sender: 'assistant',
        content: 'I found 1 approved Cardiologist in Colombo:',
        timestamp: DateTime.now(),
      ));

    currentSession = BookingSession(
      id: sessionId,
      patientUserId: currentSession.patientUserId,
      state: 'AWAITING_DOCTOR_SELECTION',
      preferences: const BookingPreferences(
        specialty: 'Cardiologist',
        city: 'Colombo',
        language: 'en',
      ),
      candidateDoctors: const [
        DoctorCardSummary(
          doctorId: 'DOC-TEST-1',
          doctorProfileId: 'prof_1',
          doctorUserId: 'usr_1',
          fullName: 'Dr. Nihal Perera',
          specialty: 'Cardiologist',
          hospitalOrClinic: 'Asiri Central Hospital',
          consultationFee: 2500.0,
        ),
      ],
      messages: updatedMessages,
      createdAt: currentSession.createdAt,
      updatedAt: DateTime.now(),
      expiresAt: currentSession.expiresAt,
    );
    return currentSession;
  }

  @override
  Future<BookingSession> selectDoctor(String sessionId, String doctorId) async {
    final updatedMessages = List<ChatMessage>.from(currentSession.messages)
      ..add(ChatMessage(
        id: 'msg_slots',
        sender: 'assistant',
        content: 'Here are the available appointment slots for Dr. Nihal Perera:',
        timestamp: DateTime.now(),
      ));

    currentSession = BookingSession(
      id: sessionId,
      patientUserId: currentSession.patientUserId,
      state: 'AWAITING_SLOT_SELECTION',
      preferences: currentSession.preferences,
      selectedDoctor: const DoctorCardSummary(
        doctorId: 'DOC-TEST-1',
        doctorProfileId: 'prof_1',
        doctorUserId: 'usr_1',
        fullName: 'Dr. Nihal Perera',
        specialty: 'Cardiologist',
        hospitalOrClinic: 'Asiri Central Hospital',
        consultationFee: 2500.0,
      ),
      candidateSlots: const [
        SlotCardSummary(
          availabilityId: 'avail_1',
          date: '2026-10-15',
          startTime: '09:00',
          endTime: '09:30',
        ),
        SlotCardSummary(
          availabilityId: 'avail_1',
          date: '2026-10-15',
          startTime: '10:00',
          endTime: '10:30',
        ),
      ],
      messages: updatedMessages,
      createdAt: currentSession.createdAt,
      updatedAt: DateTime.now(),
      expiresAt: currentSession.expiresAt,
    );
    return currentSession;
  }

  @override
  Future<BookingSession> selectSlot(
    String sessionId, {
    required String availabilityId,
    required String date,
    required String startTime,
    String? endTime,
  }) async {
    final updatedMessages = List<ChatMessage>.from(currentSession.messages)
      ..add(ChatMessage(
        id: 'msg_summary',
        sender: 'assistant',
        content: 'Great choice! Here is your booking summary:',
        timestamp: DateTime.now(),
      ));

    currentSession = BookingSession(
      id: sessionId,
      patientUserId: currentSession.patientUserId,
      state: 'AWAITING_BOOKING_CONFIRMATION',
      preferences: currentSession.preferences,
      selectedDoctor: currentSession.selectedDoctor,
      selectedSlot: SlotCardSummary(
        availabilityId: availabilityId,
        date: date,
        startTime: startTime,
        endTime: endTime ?? '09:30',
      ),
      bookingSummary: const BookingSummary(
        doctorName: 'Dr. Nihal Perera',
        specialty: 'Cardiologist',
        hospitalOrClinic: 'Asiri Central Hospital',
        appointmentDate: '2026-10-15',
        startTime: '09:00',
        endTime: '09:30',
        consultationFee: 2500.0,
        serviceFee: 0.0,
        totalAmount: 2500.0,
        currency: 'lkr',
      ),
      messages: updatedMessages,
      createdAt: currentSession.createdAt,
      updatedAt: DateTime.now(),
      expiresAt: currentSession.expiresAt,
    );
    return currentSession;
  }

  @override
  Future<BookingSession> confirmBooking(String sessionId, {String? patientNote}) async {
    final updatedMessages = List<ChatMessage>.from(currentSession.messages)
      ..add(ChatMessage(
        id: 'msg_hold',
        sender: 'assistant',
        content: 'Your appointment hold has been reserved for 10 minutes.',
        timestamp: DateTime.now(),
      ));

    currentSession = BookingSession(
      id: sessionId,
      patientUserId: currentSession.patientUserId,
      state: 'AWAITING_PAYMENT',
      preferences: currentSession.preferences,
      selectedDoctor: currentSession.selectedDoctor,
      selectedSlot: currentSession.selectedSlot,
      bookingSummary: currentSession.bookingSummary,
      appointmentId: 'appt_mock_123',
      holdExpiresAt: DateTime.now().add(const Duration(minutes: 10)),
      messages: updatedMessages,
      createdAt: currentSession.createdAt,
      updatedAt: DateTime.now(),
      expiresAt: currentSession.expiresAt,
    );
    return currentSession;
  }

  @override
  Future<BookingSession> cancelSession(String sessionId) async {
    currentSession = BookingSession(
      id: sessionId,
      patientUserId: currentSession.patientUserId,
      state: 'CANCELLED',
      preferences: currentSession.preferences,
      createdAt: currentSession.createdAt,
      updatedAt: DateTime.now(),
      expiresAt: currentSession.expiresAt,
    );
    return currentSession;
  }

  @override
  Future<BookingSession> syncPaymentStatus(String sessionId) async {
    return currentSession;
  }
}

void main() {
  Widget createTestWidget({required AiBookingService service}) {
    return MaterialApp(
      home: AiBookingAssistantScreen(
        bookingService: service,
      ),
    );
  }

  group('AiBookingAssistantScreen Widget Tests', () {
    testWidgets('1. Renders title and welcoming introduction', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.text('AI Booking Assistant'), findsOneWidget);
      expect(find.text("Hello! I'm your MediConnect AI Booking Assistant."), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('2. Displays quick suggestion prompt chips', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.text('Cardiologist in Colombo'), findsOneWidget);
      expect(find.text('Dermatologist tomorrow morning'), findsOneWidget);
    });

    testWidgets('3. Sending message shows user bubble and doctor candidate card', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'I need a cardiologist in Colombo');
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pumpAndSettle();

      expect(find.text('I need a cardiologist in Colombo'), findsOneWidget);
      expect(find.text('Dr. Nihal Perera'), findsOneWidget);
      expect(find.text('Select'), findsOneWidget);
    });

    testWidgets('4. Selecting doctor presents slot options', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      // Send search query first
      await tester.enterText(find.byType(TextField), 'Cardiologist in Colombo');
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pumpAndSettle();

      // Tap "Select" on candidate doctor
      await tester.tap(find.text('Select'));
      await tester.pumpAndSettle();

      expect(find.text('09:00 - 09:30'), findsOneWidget);
      expect(find.text('10:00 - 10:30'), findsOneWidget);
    });

    testWidgets('5. Selecting slot presents Booking Summary card with Confirm button', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'Cardiologist in Colombo');
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Select'));
      await tester.pumpAndSettle();

      // Select first slot
      await tester.tap(find.text('09:00 - 09:30'));
      await tester.pumpAndSettle();

      expect(find.text('Booking Summary'), findsOneWidget);
      expect(find.text('Confirm Booking'), findsOneWidget);
      expect(find.text('LKR 2500'), findsWidgets);
    });

    testWidgets('6. Displays emergency warning banner when isUrgent is true', (tester) async {
      final urgentSession = BookingSession(
        id: 'urgent_sess',
        patientUserId: 'pat_1',
        state: 'COLLECTING_PREFERENCES',
        preferences: const BookingPreferences(),
        isUrgent: true,
        urgencyReason: 'Potential acute cardiac symptom detected.',
        messages: [
          ChatMessage(
            id: 'u1',
            sender: 'assistant',
            content: 'Emergency guidance: call 1990 immediately.',
            timestamp: DateTime.now(),
          ),
        ],
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        expiresAt: DateTime.now().add(const Duration(minutes: 30)),
      );

      final service = FakeAiBookingService(initialSession: urgentSession);
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.text('Potential Emergency Detected'), findsOneWidget);
      expect(find.text('1990'), findsWidgets);
    });
  });
}
