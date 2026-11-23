import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';
import 'package:mediconnect/services/ai_booking_service.dart';

class FakeAiBookingService implements AiBookingService {
  BookingSession currentSession;

  FakeAiBookingService({BookingSession? initialSession})
      : currentSession = initialSession ??
            BookingSession(
              id: 'care_session_1',
              patientUserId: 'patient_1',
              state: 'COLLECTING_PREFERENCES',
              preferences: const BookingPreferences(language: 'en'),
              messages: [
                ChatMessage(
                  id: 'msg_1',
                  sender: 'assistant',
                  content: "Hello! I'm your MediConnect AI Care Assistant. How can I assist you with your health today?",
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
  Future<BookingSession> sendMessage(String sessionId, String message, {String? imageUrl}) async {
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
        content: 'I found 2 approved Cardiologists matching your criteria:',
        timestamp: DateTime.now(),
      ));

    currentSession = BookingSession(
      id: sessionId,
      patientUserId: currentSession.patientUserId,
      state: 'AWAITING_DOCTOR_SELECTION',
      preferences: const BookingPreferences(
        specialty: 'Cardiologist',
        city: 'Colombo',
        maxFee: 3000.0,
        symptoms: 'headache and chest tightness',
        language: 'en',
      ),
      candidateDoctors: const [
        DoctorCardSummary(
          doctorId: 'DOC-101',
          doctorProfileId: 'prof_1',
          doctorUserId: 'usr_1',
          fullName: 'Dr. Nihal Perera',
          specialty: 'Cardiologist',
          qualifications: 'MBBS, MD (Cardiology)',
          hospitalOrClinic: 'Asiri Central Hospital, Colombo',
          consultationFee: 2500.0,
          matchScore: 95.0,
          matchReasons: [
            'Direct specialty match: Cardiologist',
            'Within requested budget of LKR 3,000',
          ],
        ),
        DoctorCardSummary(
          doctorId: 'DOC-102',
          doctorProfileId: 'prof_2',
          doctorUserId: 'usr_2',
          fullName: 'Dr. Anoma Silva',
          specialty: 'Cardiologist',
          qualifications: 'MBBS, MRCP (UK)',
          hospitalOrClinic: 'Durdans Hospital, Colombo',
          consultationFee: 2800.0,
          matchScore: 92.0,
          matchReasons: [
            'Direct specialty match: Cardiologist',
            'Located in Colombo',
          ],
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
        doctorId: 'DOC-101',
        doctorProfileId: 'prof_1',
        doctorUserId: 'usr_1',
        fullName: 'Dr. Nihal Perera',
        specialty: 'Cardiologist',
        hospitalOrClinic: 'Asiri Central Hospital, Colombo',
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
          availabilityId: 'avail_2',
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
        content: 'I have prepared your appointment summary. Please review and confirm your hold.',
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
        hospitalOrClinic: 'Asiri Central Hospital, Colombo',
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
        content: 'Your appointment hold has been reserved for 10 minutes. Please complete payment to confirm.',
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
      appointmentId: 'appt_hold_phase39_test',
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

  @override
  Future<Map<String, dynamic>> uploadMedicineImage(List<int> bytes, String filename) async {
    return {'imageUrl': 'https://storage.mediconnect.local/test.jpg'};
  }

  @override
  Future<BookingSession> sendImageMessage(String sessionId, List<int> bytes, String filename, {String? message}) async {
    return currentSession;
  }
}

void main() {
  Widget createTestWidget({required AiBookingService service}) {
    return MaterialApp(
      home: AiCareAssistantScreen(
        bookingService: service,
      ),
    );
  }

  group('AiCareAssistantScreen Widget Tests (Phase 39)', () {
    testWidgets('1. Renders title and welcoming introduction', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.text('MediConnect AI Assistant'), findsOneWidget);
      expect(
        find.text("Hello! I'm your MediConnect AI Care Assistant. How can I assist you with your health today?"),
        findsOneWidget,
      );
      expect(find.byKey(const Key('ai_care_assistant_input')), findsOneWidget);
      expect(find.byKey(const Key('ai_care_assistant_attach_image')), findsOneWidget);
      expect(find.byKey(const Key('ai_care_assistant_send')), findsOneWidget);
    });

    testWidgets('2. Displays quick suggestion prompt chips', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.text('Headache for 3 days'), findsOneWidget);
      expect(find.text('Cardiologist in Colombo'), findsOneWidget);
      expect(find.text('Budget under LKR 3000'), findsOneWidget);
    });

    testWidgets('3. Sending message shows candidate doctors, match scores & reasons', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_care_assistant_input')),
        'Cardiologist in Colombo',
      );
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();

      expect(find.text('Dr. Nihal Perera'), findsOneWidget);
      expect(find.text('95% Match'), findsOneWidget);
      expect(find.text('Dr. Anoma Silva'), findsOneWidget);
      expect(find.text('92% Match'), findsOneWidget);
      expect(find.text('Compare'), findsOneWidget);
      expect(find.text('Select Doctor'), findsWidgets);
    });

    testWidgets('4. Tapping Compare opens candidate doctor comparison sheet', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_care_assistant_input')),
        'Cardiologist in Colombo',
      );
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();

      await tester.drag(find.byType(ListView).first, const Offset(0, 300));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Compare'));
      await tester.pumpAndSettle();

      expect(find.text('Compare Candidate Doctors'), findsOneWidget);
      expect(find.text('MBBS, MD (Cardiology)'), findsWidgets);
      expect(find.text('MBBS, MRCP (UK)'), findsWidgets);
    });

    testWidgets('5. Selecting doctor presents slot options', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_care_assistant_input')),
        'Cardiologist in Colombo',
      );
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Select Doctor').first);
      await tester.pumpAndSettle();

      expect(find.text('09:00 - 09:30'), findsOneWidget);
      expect(find.text('10:00 - 10:30'), findsOneWidget);
    });

    testWidgets('6. Selecting slot presents Booking Summary card with Confirm button', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_care_assistant_input')),
        'Cardiologist in Colombo',
      );
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Select Doctor').first);
      await tester.pumpAndSettle();

      await tester.tap(find.text('09:00 - 09:30'));
      await tester.pumpAndSettle();

      expect(find.text('Booking Summary'), findsOneWidget);
      expect(find.text('Confirm Booking'), findsOneWidget);
      expect(find.text('LKR 2500.00'), findsWidgets);
    });

    testWidgets('7. Explicitly confirming booking activates 10-minute hold reservation', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('ai_care_assistant_input')),
        'Cardiologist in Colombo',
      );
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Select Doctor').first);
      await tester.pumpAndSettle();

      await tester.tap(find.text('09:00 - 09:30'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Confirm Booking'));
      await tester.pumpAndSettle();

      expect(find.text('10-Minute Hold Active'), findsOneWidget);
      expect(find.text('Ref: appt_hold_phase39_test'), findsOneWidget);
      expect(find.text('Proceed to Payment (Stripe)'), findsOneWidget);
    });

    testWidgets('8. Displays emergency warning banner and 1990 triage button when isUrgent is true', (tester) async {
      final urgentSession = BookingSession(
        id: 'urgent_session_phase39',
        patientUserId: 'patient_urgent',
        state: 'COLLECTING_PREFERENCES',
        preferences: const BookingPreferences(),
        isUrgent: true,
        urgencyReason: 'Potential acute cardiac symptom detected.',
        messages: [
          ChatMessage(
            id: 'u1',
            sender: 'assistant',
            content: 'Emergency guidance: If you have crushing chest pain, call 1990 immediately.',
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

    testWidgets('9. Displays educational medicine card when activeMedicineCard is present', (tester) async {
      final medicineSession = BookingSession(
        id: 'med_session_phase40',
        patientUserId: 'patient_med',
        state: 'COLLECTING_PREFERENCES',
        preferences: const BookingPreferences(),
        activeIntent: 'MEDICINE_INFORMATION',
        activeMedicineCard: const MedicineCardSummary(
          medicineName: 'Paracetamol',
          activeIngredient: 'Acetaminophen (Paracetamol)',
          commonUses: ['Relief of mild-to-moderate pain', 'Fever reduction'],
          precautions: ['Do not exceed recommended maximum daily dose'],
          sideEffects: ['Rare at therapeutic doses; nausea occasionally'],
          warnings: ['Avoid alcohol while taking paracetamol'],
          consultPharmacistWhen: ['Fever lasts more than 3 days'],
          isPrescriptionRequired: false,
        ),
        messages: [
          ChatMessage(
            id: 'm1',
            sender: 'assistant',
            content: 'Here is educational information about Paracetamol:',
            timestamp: DateTime.now(),
          ),
        ],
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        expiresAt: DateTime.now().add(const Duration(minutes: 30)),
      );

      final service = FakeAiBookingService(initialSession: medicineSession);
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ai_medicine_card')), findsOneWidget);
      expect(find.text('Paracetamol'), findsOneWidget);
      expect(find.text('Active Ingredient: Acetaminophen (Paracetamol)'), findsOneWidget);
      expect(find.text('Common Uses'), findsOneWidget);
    });

    testWidgets('10. Displays educational wellness card when activeWellnessCard is present', (tester) async {
      final wellnessSession = BookingSession(
        id: 'wellness_session_phase40',
        patientUserId: 'patient_well',
        state: 'COLLECTING_PREFERENCES',
        preferences: const BookingPreferences(),
        activeIntent: 'HEALTHY_FOOD',
        activeWellnessCard: const WellnessCardSummary(
          category: 'FOOD',
          title: 'Healthy Sri Lankan Breakfast Options',
          summary: 'Start your day with balanced complex carbohydrates and fiber.',
          tips: ['Replace white bread with red rice or kurakkan pittu'],
          sriLankanOptions: ['Kola Kenda (herbal porridge)', 'Gotu Kola Sambol'],
          safetyNote: 'If diabetic, consult your doctor for personalized glycemic targets.',
        ),
        messages: [
          ChatMessage(
            id: 'w1',
            sender: 'assistant',
            content: 'Here are healthy Sri Lankan breakfast ideas:',
            timestamp: DateTime.now(),
          ),
        ],
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        expiresAt: DateTime.now().add(const Duration(minutes: 30)),
      );

      final service = FakeAiBookingService(initialSession: wellnessSession);
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ai_wellness_card')), findsOneWidget);
      expect(find.text('Healthy Sri Lankan Breakfast Options'), findsOneWidget);
    });

    testWidgets('11. Displays image analysis card when activeImageAnalysis is present', (tester) async {
      final imageSession = BookingSession(
        id: 'image_session_phase40',
        patientUserId: 'patient_img',
        state: 'COLLECTING_PREFERENCES',
        preferences: const BookingPreferences(),
        activeIntent: 'MEDICINE_IMAGE_ANALYSIS',
        activeImageAnalysis: const ImageAnalysisSummary(
          detectedText: 'PANADOL 500mg Tablets Paracetamol',
          identifiedMedicine: 'Paracetamol',
          activeIngredient: 'Acetaminophen (Paracetamol)',
          confidenceLevel: 'HIGH',
          safetyAdvice: 'Always verify with the packaging leaflet before use.',
          requiresClearerPhoto: false,
        ),
        messages: [
          ChatMessage(
            id: 'i1',
            sender: 'assistant',
            content: 'Analysis of your medicine label:',
            timestamp: DateTime.now(),
          ),
        ],
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        expiresAt: DateTime.now().add(const Duration(minutes: 30)),
      );

      final service = FakeAiBookingService(initialSession: imageSession);
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('ai_image_analysis_card')), findsOneWidget);
      expect(find.text('Label & Packaging Analysis'), findsOneWidget);
      expect(find.text('High Confidence'), findsOneWidget);
    });
  });
}
