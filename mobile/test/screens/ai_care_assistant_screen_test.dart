import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';
import 'package:mediconnect/services/ai_booking_service.dart';

class FakeAiBookingService implements AiBookingService {
  BookingSession currentSession;
  String? acceptedProposal;
  bool acceptedSms = false;
  List<Map<String, dynamic>> history = [];
  final Map<String, BookingSession> storedSessions = {};
  final List<String> sentRequestIds = [];
  bool failNextSend = false;
  int created = 0;

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
  Future<List<Map<String, dynamic>>> listConversations({int offset = 0}) async => history;

  @override
  Future<BookingSession> createConversation() async {
    if (storedSessions.isEmpty) return createSession();
    created++;
    return BookingSession.fromJson({
      ...currentSession.toJson(),
      'id': 'new_conversation',
      'state': 'COLLECTING_PREFERENCES',
      'candidateDoctors': [],
      'messages': [currentSession.messages.first.toJson()],
    });
  }

  @override
  Future<BookingSession> sendConversationMessage(String sessionId, String message, String requestId) async {
    sentRequestIds.add(requestId);
    if (failNextSend) {
      failNextSend = false;
      throw StateError('Simulated network interruption');
    }
    return sendMessage(sessionId, message);
  }

  @override
  Future<void> renameConversation(String id, String title) async {}

  @override
  Future<void> deleteConversation(String id) async {}

  @override
  Future<BookingSession> viewSlots(String sessionId, String doctorId, String date) =>
      selectDoctor(sessionId, doctorId);

  @override
  Future<BookingSession> createSession({String? initialMessage}) async {
    return currentSession;
  }

  @override
  Future<BookingSession> getSession(String sessionId) async {
    return storedSessions[sessionId] ?? currentSession;
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
    bool prepareProposal = false,
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
  Future<BookingSession> confirmBooking(String sessionId, {String? patientNote, String? proposalId, bool smsConsent = false}) async {
    acceptedProposal = proposalId;
    acceptedSms = smsConsent;
    if (proposalId != null && currentSession.bookingSummary?.totalAmount == 0) {
      currentSession = BookingSession.fromJson({
        ...currentSession.toJson(),
        'state': 'BOOKING_CONFIRMED',
        'appointmentId': 'booking-reference',
        'bookingResult': {
          'status': 'CONFIRMED', 'reference': 'booking-reference',
          'doctor': 'Dr. Test', 'date': '2026-12-05', 'time': '16:00',
          'clinic': 'Test Clinic', 'paymentStatus': 'NOT_REQUIRED',
          'notifications': {'email': 'sent', 'sms': 'accepted'},
        },
      });
      return currentSession;
    }
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
    return MaterialApp(theme: AppTheme.lightTheme, 
      home: AiCareAssistantScreen(
        bookingService: service,
      ),
    );
  }

  group('AiCareAssistantScreen Widget Tests (Phase 39)', () {
    testWidgets('Accepts the exact proposal and shows verified booking status', (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(800, 1000);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final service = FakeAiBookingService();
      service.currentSession = BookingSession.fromJson({
        ...service.currentSession.toJson(),
        'state': 'AWAITING_BOOKING_CONFIRMATION',
        'bookingSummary': {
          'proposalId': 'proposal-for-current-slot',
          'doctorName': 'Dr. Test', 'specialty': 'Neurology',
          'appointmentDate': '2026-12-05', 'startTime': '16:00', 'endTime': '16:30',
          'consultationFee': 0, 'totalAmount': 0, 'maskedPhone': '***4567',
        },
      });
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();
      final sms = find.text('Send confirmation SMS to ***4567');
      await tester.ensureVisible(sms);
      await tester.tap(sms);
      await tester.pumpAndSettle();
      final button = find.text('Accept & Continue');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(service.acceptedProposal, 'proposal-for-current-slot');
      expect(service.acceptedSms, isTrue);
      expect(find.text('Appointment Confirmed'), findsOneWidget);
      expect(find.text('SMS: accepted by provider'), findsOneWidget); // Phase 02: truthful delivery wording
    });

    testWidgets('Restores a conversation, starts a new one, and reopens history', (tester) async {
      final service = FakeAiBookingService();
      final original = await service.sendMessage(service.currentSession.id, 'Find a doctor in Colombo');
      service.storedSessions[original.id] = original;
      service.history = [
        {'id': original.id, 'title': 'Colombo doctors', 'preview': 'Earlier search'},
      ];
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();
      expect(find.text('Dr. Nihal Perera'), findsWidgets);
      expect(service.created, 0);

      await tester.tap(find.text('New Chat'));
      await tester.pumpAndSettle();
      expect(service.created, 1);
      expect(find.text('Dr. Nihal Perera'), findsNothing);
      await tester.tap(find.byTooltip('Chat History'));
      await tester.pumpAndSettle();
      expect(find.text('Earlier search'), findsOneWidget);
      await tester.tap(find.text('Colombo doctors'));
      await tester.pumpAndSettle();
      expect(find.text('Dr. Nihal Perera'), findsWidgets);

      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();
      expect(find.text('Dr. Nihal Perera'), findsWidgets);
    });

    testWidgets('Failed submission restores input and retries the same request', (tester) async {
      final service = FakeAiBookingService()..failNextSend = true;
      await tester.pumpWidget(createTestWidget(service: service));
      await tester.pumpAndSettle();
      final input = find.byKey(const Key('ai_care_assistant_input'));
      final send = find.byKey(const Key('ai_care_assistant_send'));
      await tester.enterText(input, 'Find a doctor in Colombo');
      await tester.tap(send);
      await tester.pumpAndSettle();
      expect(tester.widget<TextField>(input).controller!.text, 'Find a doctor in Colombo');
      await tester.tap(send);
      await tester.pumpAndSettle();
      expect(service.sentRequestIds, hasLength(2));
      expect(service.sentRequestIds.toSet(), hasLength(1));
      expect(service.currentSession.messages.where((message) => message.isUser), hasLength(1));
    });

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
      expect(find.text('View Available Slots'), findsWidgets);
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

      await tester.ensureVisible(find.text('View Available Slots').first);
      await tester.tap(find.text('View Available Slots').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('OK'));
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

      await tester.ensureVisible(find.text('View Available Slots').first);
      await tester.tap(find.text('View Available Slots').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('OK'));
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

      await tester.ensureVisible(find.text('View Available Slots').first);
      await tester.tap(find.text('View Available Slots').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('OK'));
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

      // Runs under the real app theme: before the BUG-042/043 fix this layout threw
      // "BoxConstraints forces an infinite width" for the 1990 button.
      expect(tester.takeException(), isNull);
      expect(find.text('Possible medical emergency'), findsOneWidget);
      expect(find.byKey(const Key('ai_emergency_call_1990')), findsOneWidget);
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
      // A01 changed expectation: the card no longer claims "High Confidence" (the backend never sends it and a
      // photo cannot establish a medicine's identity), and it no longer repeats the text already in the reply.
      expect(find.text('High Confidence'), findsNothing);
      expect(find.text('Label read — verify with pharmacist'), findsOneWidget);
      expect(find.text('PANADOL 500mg Tablets Paracetamol'), findsNothing);
      expect(find.byKey(const Key('ai_image_library_match')), findsOneWidget);
    });

    testWidgets('12. A01 image card: several packages, unreadable fields, ignored text, reader shown', (tester) async {
      final session = BookingSession(
        id: 'image_session_a01',
        patientUserId: 'patient_img',
        state: 'COLLECTING_PREFERENCES',
        preferences: const BookingPreferences(),
        activeIntent: 'MEDICINE_IMAGE_ANALYSIS',
        activeImageAnalysis: ImageAnalysisSummary.fromJson(const {
          'status': 'multiple_packages',
          'detectedText': 'Brand name: Synthopar 500, Synthocet 10',
          'identifiedMedicine': null,
          'confidenceLevel': 'low',
          'uncertaintyExplanation': 'Printed label text was read from the image.',
          'safetyAdvice': 'Confirm with a pharmacist.',
          'provider': 'gemini',
          'model': 'gemini-3.8-flash',
          'packageCount': 2,
          'embeddedTextIgnored': true,
          'extracted': {'unreadableFields': ['expiry date']},
        }),
        messages: [
          ChatMessage(id: 'i1', sender: 'assistant', content: 'Text read from your photo', timestamp: DateTime.now()),
        ],
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        expiresAt: DateTime.now().add(const Duration(minutes: 30)),
      );
      await tester.pumpWidget(createTestWidget(service: FakeAiBookingService(initialSession: session)));
      await tester.pumpAndSettle();

      expect(find.text('Several packages'), findsOneWidget);
      expect(find.byKey(const Key('ai_image_library_match')), findsNothing);
      expect(find.text('Not readable in this photo: expiry date'), findsOneWidget);
      expect(find.byKey(const Key('ai_image_embedded_text_ignored')), findsOneWidget);
      expect(find.text('Read by Google Gemini (gemini-3.8-flash) — automated reading, not verified'), findsOneWidget);
    });
  });
}
