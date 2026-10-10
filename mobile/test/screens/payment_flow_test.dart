import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/doctor.dart';
import 'package:mediconnect/models/doctor_availability.dart';
import 'package:mediconnect/models/payment.dart';
import 'package:mediconnect/screens/patient/booking_confirmation_screen.dart';
import 'package:mediconnect/screens/patient/doctor_detail_screen.dart';
import 'package:mediconnect/screens/patient/payment_history_screen.dart';
import 'package:mediconnect/screens/patient/payment_success_screen.dart';
import 'package:mediconnect/services/appointment_service.dart';
import 'package:mediconnect/services/doctor_service.dart';
import 'package:mediconnect/services/payment_service.dart';

// ---------------------------------------------------------------------------
// TEST MOCKS
// ---------------------------------------------------------------------------

class MockDoctorService extends DoctorService {
  final Doctor sampleDoctor = Doctor(
    doctorId: 'DR-TEST-100',
    fullName: 'Dr. Sarah Perera',
    specialty: 'Cardiology',
    hospitalOrClinic: 'Asiri Central Hospital',
    experienceYears: 12,
    consultationFee: 2500.0,
    bio: 'Senior cardiologist.',
    verificationStatus: 'APPROVED',
  );

  @override
  Future<Doctor> getDoctorDetail(String doctorId) async {
    return sampleDoctor;
  }

  @override
  Future<List<DayAvailabilitySlots>> getDoctorAvailability(
    String doctorId, {
    String? date,
  }) async {
    return [
      DayAvailabilitySlots(
        date: '2026-10-20',
        slots: [
          TimeSlot(
            startTime: '10:00',
            endTime: '10:30',
            availabilityId: 'AVAIL-TEST-100',
          ),
        ],
      ),
    ];
  }
}

class MockAppointmentService extends AppointmentService {
  int createCallCount = 0;

  @override
  Future<Appointment> createAppointment({
    required String doctorId,
    String? availabilityId,
    required String date,
    required String startTime,
    String? patientNote,
  }) async {
    createCallCount++;
    return Appointment(
      id: 'APPT-TEST-200',
      patientUserId: 'PATIENT-001',
      doctorUserId: 'DOC-USER-001',
      doctorProfileId: 'PROF-001',
      availabilityId: availabilityId ?? 'AVAIL-TEST-100',
      appointmentDate: date,
      startTime: startTime,
      endTime: '10:30',
      status: 'PENDING',
      paymentStatus: 'UNPAID',
      consultationFee: 2500.0,
      doctorName: 'Dr. Sarah Perera',
      specialty: 'Cardiology',
      hospitalOrClinic: 'Asiri Central Hospital',
      createdAt: DateTime.now(),
    );
  }
}

class MockPaymentService extends PaymentService {
  int createIntentCallCount = 0;
  int getStatusCallCount = 0;
  bool simulateCancel = false;
  bool simulateFailed = false;

  @override
  Future<CreatePaymentIntentResponse> createPaymentIntent(
      String appointmentId) async {
    createIntentCallCount++;
    if (simulateCancel) {
      throw const StripeException(
        error: LocalizedErrorMessage(
          code: FailureCode.Canceled,
          message: 'Payment was cancelled',
          localizedMessage: 'Payment was cancelled',
        ),
      );
    }
    return CreatePaymentIntentResponse(
      paymentIntentClientSecret: 'pi_test_secret_abc123',
      paymentId: 'PAY-TEST-300',
      amount: 250000,
      currency: 'lkr',
    );
  }

  @override
  Future<PaymentStatusResult> getPaymentStatus(String paymentId) async {
    getStatusCallCount++;
    if (simulateFailed) {
      return PaymentStatusResult(
        paymentId: paymentId,
        appointmentId: 'APPT-TEST-200',
        paymentStatus: 'FAILED',
        appointmentStatus: 'PENDING',
        amount: 2500.0,
        currency: 'lkr',
      );
    }
    return PaymentStatusResult(
      paymentId: paymentId,
      appointmentId: 'APPT-TEST-200',
      paymentStatus: 'SUCCEEDED',
      appointmentStatus: 'CONFIRMED',
      amount: 2500.0,
      currency: 'lkr',
      paidAt: DateTime.now(),
    );
  }

  @override
  Future<List<PaymentHistoryItem>> getPaymentHistory() async {
    return [
      PaymentHistoryItem(
        paymentId: 'PAY-HIST-001',
        appointmentId: 'APPT-001',
        doctorName: 'Dr. Sarah Perera',
        amount: 2500.0,
        currency: 'lkr',
        status: 'SUCCEEDED',
        paidAt: DateTime(2026, 10, 1),
        createdAt: DateTime(2026, 10, 1),
      ),
      PaymentHistoryItem(
        paymentId: 'PAY-HIST-002',
        appointmentId: 'APPT-002',
        doctorName: 'Dr. Anne Silva',
        amount: 3000.0,
        currency: 'lkr',
        status: 'PENDING',
        createdAt: DateTime(2026, 10, 2),
      ),
    ];
  }
}

Widget createTestApp({required Widget child}) {
  return MaterialApp(
    home: child,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('flutter.stripe/payments', JSONMethodCodec()),
      (MethodCall methodCall) async {
        if (methodCall.method == 'initPaymentSheet') {
          return {};
        }
        if (methodCall.method == 'presentPaymentSheet') {
          return {};
        }
        return {};
      },
    );
    Stripe.publishableKey =
        'pk_test_mock_${DateTime.now().microsecondsSinceEpoch}_${UniqueKey().toString()}';
  });

  // TEST 14: Doctor detail shows consultation fee
  testWidgets('TEST 14: Doctor detail shows consultation fee', (tester) async {
    final mockDoctorService = MockDoctorService();

    await tester.pumpWidget(createTestApp(
      child: DoctorDetailScreen(
        doctorId: 'DR-TEST-100',
        doctorService: mockDoctorService,
      ),
    ));
    await tester.pumpAndSettle();

    // Verify consultation fee is rendered
    expect(find.text('Consultation Fee'), findsOneWidget);
    expect(find.text('LKR 2500.00'), findsOneWidget);
  });

  // TEST 15: Patient selects slot -> booking summary
  testWidgets(
      'TEST 15: Patient selects slot -> booking summary shows fee and details',
      (tester) async {
    final mockDoctorService = MockDoctorService();
    final mockApptService = MockAppointmentService();
    final mockPaymentService = MockPaymentService();

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-20',
        slot: TimeSlot(
          startTime: '10:00',
          endTime: '10:30',
          availabilityId: 'AVAIL-TEST-100',
        ),
        appointmentService: mockApptService,
        paymentService: mockPaymentService,
      ),
    ));
    await tester.pumpAndSettle();

    // Verify summary displays Doctor, Date, Time, and Consultation Fee
    expect(find.text('Confirm Booking'), findsOneWidget);
    expect(find.text('Dr. Sarah Perera'), findsOneWidget);
    expect(find.text('Cardiology'), findsOneWidget);
    expect(find.text('2026-10-20'), findsOneWidget);
    expect(find.text('10:00 - 10:30'), findsOneWidget);
    expect(find.text('Consultation Fee:'), findsOneWidget);
    expect(find.byKey(const Key('consultation_fee_text')), findsOneWidget);
    expect(find.text('LKR 2500.00'), findsOneWidget);
    expect(find.byKey(const Key('continue_to_payment_button')), findsOneWidget);
  });

  // TEST 16 & TEST 18: Continue to Payment calls createPaymentIntent and checks backend status
  testWidgets(
      'TEST 16 & TEST 18: Continue to Payment calls payment intent and verifies backend status',
      (tester) async {
    final mockDoctorService = MockDoctorService();
    final mockApptService = MockAppointmentService();
    final mockPaymentService = MockPaymentService();

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-20',
        slot: TimeSlot(
          startTime: '10:00',
          endTime: '10:30',
          availabilityId: 'AVAIL-TEST-100',
        ),
        appointmentService: mockApptService,
        paymentService: mockPaymentService,
      ),
    ));
    await tester.pumpAndSettle();

    // Tap Continue to Payment
    await tester.tap(find.byKey(const Key('continue_to_payment_button')));
    for (int i = 0; i < 15; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    // Verify appointment was created
    expect(mockApptService.createCallCount, 1);
    // Verify PaymentIntent was created
    expect(mockPaymentService.createIntentCallCount, 1);
    // Verify backend status was queried (Rule 19)
    expect(mockPaymentService.getStatusCallCount, 1);
  });

  // TEST 17: Cancel PaymentSheet -> clean cancellation message
  testWidgets('TEST 17: Cancel PaymentSheet shows clean cancellation message',
      (tester) async {
    final mockDoctorService = MockDoctorService();
    final mockApptService = MockAppointmentService();
    final cancellingService = MockPaymentService()..simulateCancel = true;

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-20',
        slot: TimeSlot(
          startTime: '10:00',
          endTime: '10:30',
          availabilityId: 'AVAIL-TEST-100',
        ),
        appointmentService: mockApptService,
        paymentService: cancellingService,
      ),
    ));
    await tester.pumpAndSettle();

    // Tap Continue to Payment (triggers cancellation simulation)
    await tester.tap(find.byKey(const Key('continue_to_payment_button')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('Payment was cancelled.'), findsOneWidget);
    // Must NOT navigate to confirmation screen
    expect(find.byType(PaymentSuccessScreen), findsNothing);
  });

  // TEST 19: Webhook/Backend confirms payment -> Appointment Confirmed screen
  testWidgets(
      'TEST 19: Backend confirms payment -> Payment Success and Appointment Confirmed screen',
      (tester) async {
    await tester.pumpWidget(createTestApp(
      child: const PaymentSuccessScreen(
        appointmentId: 'APPT-TEST-200',
        paymentId: 'PAY-TEST-300',
        doctorName: 'Dr. Sarah Perera',
        specialty: 'Cardiology',
        date: '2026-10-20',
        time: '10:00 - 10:30',
        amount: 2500.0,
        currency: 'lkr',
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Payment Successful'), findsOneWidget);
    expect(find.text('Appointment Confirmed'), findsOneWidget);
    expect(find.text('Dr. Sarah Perera'), findsOneWidget);
    expect(find.text('2026-10-20 at 10:00 - 10:30'), findsOneWidget);
    expect(find.text('LKR 2500.00'), findsOneWidget);
    expect(find.text('View My Appointments'), findsOneWidget);
  });

  // TEST 20: Failed payment -> appointment not confirmed
  testWidgets('TEST 20: Failed payment does not confirm appointment',
      (tester) async {
    final mockDoctorService = MockDoctorService();
    final mockApptService = MockAppointmentService();
    final mockPaymentService = MockPaymentService()..simulateFailed = true;

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-20',
        slot: TimeSlot(
          startTime: '10:00',
          endTime: '10:30',
          availabilityId: 'AVAIL-TEST-100',
        ),
        appointmentService: mockApptService,
        paymentService: mockPaymentService,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('continue_to_payment_button')));
    for (int i = 0; i < 40; i++) {
      await tester.pump(const Duration(milliseconds: 50));
      if (mockPaymentService.getStatusCallCount > 0) break;
    }
    await tester.pump(const Duration(milliseconds: 100));

    expect(mockPaymentService.createIntentCallCount, 1);
    expect(mockPaymentService.getStatusCallCount, 1);

    // Verify error message displayed and no confirmation screen shown
    expect(
      find.text('Payment could not be completed. Please try again.'),
      findsOneWidget,
    );
    expect(find.byType(PaymentSuccessScreen), findsNothing);
  });

  // TEST 21: Repeated button tap -> no accidental duplicate payment intents
  testWidgets(
      'TEST 21: Repeated button tap disables button while request in progress',
      (tester) async {
    final mockDoctorService = MockDoctorService();
    final mockApptService = MockAppointmentService();
    final mockPaymentService = MockPaymentService();

    await tester.pumpWidget(createTestApp(
      child: BookingConfirmationScreen(
        doctor: mockDoctorService.sampleDoctor,
        date: '2026-10-20',
        slot: TimeSlot(
          startTime: '10:00',
          endTime: '10:30',
          availabilityId: 'AVAIL-TEST-100',
        ),
        appointmentService: mockApptService,
        paymentService: mockPaymentService,
      ),
    ));
    await tester.pumpAndSettle();

    // Tap once
    await tester.tap(find.byKey(const Key('continue_to_payment_button')));
    // Immediately attempt second tap before settlement
    await tester.tap(find.byKey(const Key('continue_to_payment_button')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    // Only one payment intent was created
    expect(mockPaymentService.createIntentCallCount, 1);
  });

  // TEST 22: Payment history -> correct safe information displayed
  testWidgets('TEST 22: Payment history displays safe payment items',
      (tester) async {
    final mockPaymentService = MockPaymentService();

    await tester.pumpWidget(createTestApp(
      child: PaymentHistoryScreen(
        paymentService: mockPaymentService,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Payment History'), findsOneWidget);
    expect(find.text('Dr. Sarah Perera'), findsOneWidget);
    expect(find.text('LKR 2500.00'), findsOneWidget);
    expect(find.text('SUCCEEDED'), findsOneWidget);

    expect(find.text('Dr. Anne Silva'), findsOneWidget);
    expect(find.text('LKR 3000.00'), findsOneWidget);
    expect(find.text('PENDING'), findsOneWidget);
  });
}
