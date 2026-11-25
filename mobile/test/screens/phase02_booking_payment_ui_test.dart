// Phase 02 regression tests: appointment details (BUG-058/059/060), reservation release (BUG-063),
// truthful doctor overview and money formatting. See docs/uat/phase-02/PHASE_02_BUG_FIX_REPORT.md.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/doctor/doctor_appointment_detail_screen.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';
import 'package:mediconnect/screens/patient/appointment_detail_screen.dart';
import 'package:mediconnect/services/appointment_service.dart';
import 'package:mediconnect/widgets/appointment_payment_summary.dart';
import 'package:mediconnect/widgets/doctor_today_overview.dart';

import 'ai_care_assistant_screen_test.dart' show FakeAiBookingService;

const _ref = '6b06825ccc345d412f2d7898';

Appointment _appt({String status = 'CONFIRMED', String payment = 'PAID', double? fee = 3000, double? paid = 3000,
    String? refund, String id = _ref}) {
  return Appointment.fromJson({
    'id': id, 'patientUserId': 'P1', 'doctorUserId': 'D1', 'doctorProfileId': 'DP1', 'availabilityId': 'A1',
    'appointmentDate': '2026-12-02', 'startTime': '09:00', 'endTime': '09:30', 'status': status,
    'paymentStatus': payment, 'consultationFee': fee, 'consultationFeeAtBooking': fee, 'amountPaid': paid,
    'paidAt': paid == null ? null : '2026-11-25T09:30:00Z', 'currency': 'lkr', 'bookingReference': id,
    'visitType': 'IN_PERSON', 'doctorName': 'Dr. P02 Ortho', 'specialty': 'Orthopedic Surgeon',
    'hospitalOrClinic': 'UAT Kandy Bone Clinic', 'patientName': 'P02 Patient A', 'refundStatus': refund,
  });
}

class _FakeAppointments extends AppointmentService {
  _FakeAppointments(this.current);
  Appointment current;
  final requested = <String>[];
  int releases = 0;
  Map<String, dynamic> preview = {'refund': null};

  @override
  Future<Appointment> getAppointmentDetail(String appointmentId) async {
    requested.add(appointmentId);
    return current;
  }

  @override
  Future<Appointment> releaseHold(String appointmentId) async {
    releases++;
    current = _appt(status: 'CANCELLED', payment: 'PENDING', paid: null, id: appointmentId);
    return current;
  }

  @override
  Future<Map<String, dynamic>> getCancellationPreview(String appointmentId) async => preview;
}

Widget _routed(String route, Widget screen, Object args) => MaterialApp(
      theme: AppTheme.lightTheme,
      onGenerateRoute: (settings) => MaterialPageRoute(builder: (_) => screen, settings: settings),
      initialRoute: '/',
      routes: {
        '/': (context) => Scaffold(
              body: Center(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(minimumSize: const Size(80, 40)),
                  onPressed: () => Navigator.pushNamed(context, route, arguments: args),
                  child: const Text('open'),
                ),
              ),
            ),
      },
    );

void main() {
  testWidgets('BUG-060: a notification link {appointmentId} opens the patient appointment', (tester) async {
    final service = _FakeAppointments(_appt());
    await tester.pumpWidget(_routed('/patient/appointment-detail', AppointmentDetailScreen(appointmentService: service),
        {'appointmentId': _ref}));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(service.requested, [_ref]);
    expect(find.text('Appointment not found.'), findsNothing);
    expect(find.text('Dr. P02 Ortho'), findsOneWidget);
  });

  testWidgets('BUG-060: the doctor notification link opens the doctor view', (tester) async {
    final service = _FakeAppointments(_appt());
    await tester.pumpWidget(_routed('/doctor/appointment-detail',
        DoctorAppointmentDetailScreen(appointmentService: service), {'appointmentId': _ref}));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(service.requested, [_ref]);
    expect(find.text('Appointment not found.'), findsNothing);
  });

  testWidgets('BUG-059: doctor sees the booked fee, amount paid and payment status', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme,
        home: DoctorAppointmentDetailScreen(appointment: _appt())));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const Key('doctor_appt_fee'))).data, 'LKR 3,000');
    expect(tester.widget<Text>(find.byKey(const Key('doctor_appt_amount_paid'))).data, 'LKR 3,000');
    expect(tester.widget<Text>(find.byKey(const Key('doctor_appt_payment_status'))).data, 'Paid');
    expect(find.text('LKR '), findsNothing);
  });

  testWidgets('BUG-059: a missing fee is "Not available", never a default amount', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme,
        home: DoctorAppointmentDetailScreen(appointment: _appt(fee: null, paid: null, payment: 'UNPAID'))));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const Key('doctor_appt_fee'))).data, 'Not available');
    expect(find.byKey(const Key('doctor_appt_amount_paid')), findsNothing);
    expect(find.textContaining('2500'), findsNothing);
  });

  testWidgets('BUG-058: patient sees payment facts and the full booking reference with copy', (tester) async {
    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') copied = (call.arguments as Map)['text'] as String?;
      return null;
    });
    addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme,
        home: AppointmentDetailScreen(appointment: _appt(refund: 'requested'))));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const Key('appt_fee'))).data, 'LKR 3,000');
    expect(tester.widget<Text>(find.byKey(const Key('appt_amount_paid'))).data, 'LKR 3,000');
    expect(tester.widget<Text>(find.byKey(const Key('appt_payment_status'))).data, 'Paid');
    expect(tester.widget<Text>(find.byKey(const Key('appt_visit_type'))).data, 'In-person visit');
    expect(tester.widget<SelectableText>(find.byKey(const Key('appt_booking_reference'))).data, _ref);
    expect(tester.widget<Text>(find.byKey(const Key('appt_refund_status'))).data, 'Requested - awaiting review');
    await tester.ensureVisible(find.byKey(const Key('appt_copy_reference')));
    await tester.tap(find.byKey(const Key('appt_copy_reference')));
    await tester.pump();
    expect(find.text('Booking reference copied.'), findsOneWidget);
    expect(copied, _ref);
  });

  testWidgets('BUG-063: an unpaid reservation is released only after confirmation', (tester) async {
    final service = _FakeAppointments(_appt(status: 'PENDING', payment: 'PENDING', paid: null));
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme,
        home: AppointmentDetailScreen(appointment: service.current, appointmentService: service)));
    await tester.pumpAndSettle();
    final button = find.byKey(const Key('cancel_appointment_button'));
    await tester.ensureVisible(button);
    expect(find.text('Release Reservation'), findsOneWidget);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('release_reservation_dialog')), findsOneWidget);
    await tester.tap(find.text('Keep Reservation'));
    await tester.pumpAndSettle();
    expect(service.releases, 0);
    await tester.tap(button);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('release_reservation_confirm')));
    await tester.pumpAndSettle();
    expect(service.releases, 1);
    expect(find.text('Reservation released. No payment was taken.'), findsOneWidget);
  });

  testWidgets('P-05o: cancelling a paid booking shows the policy refund before confirming', (tester) async {
    final service = _FakeAppointments(_appt())
      ..preview = {'refund': {'eligible': true, 'eligibleAmount': 3000, 'penaltyAmount': 0, 'currency': 'lkr',
                               'ruleApplied': 'Cancelled with more than 24 hours notice; 100% full refund eligible.'}};
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme,
        home: AppointmentDetailScreen(appointment: service.current, appointmentService: service)));
    await tester.pumpAndSettle();
    final button = find.byKey(const Key('cancel_appointment_button'));
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pumpAndSettle();
    final text = tester.widget<Text>(find.byKey(const Key('cancel_refund_implication'))).data!;
    expect(text, contains('LKR 3,000'));
    expect(text, contains('reviewed and approved by MediConnect'));
    await tester.tap(find.text('Keep Appointment'));
    await tester.pumpAndSettle();
  });

  testWidgets('BUG-063: the AI hold card offers Release Reservation with confirmation', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(800, 1400);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final service = FakeAiBookingService();
    service.currentSession = BookingSession.fromJson({
      ...service.currentSession.toJson(),
      'state': 'AWAITING_PAYMENT', 'appointmentId': _ref,
      'holdExpiresAt': DateTime.now().add(const Duration(minutes: 9)).toIso8601String(),
    });
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, home: AiCareAssistantScreen(bookingService: service)));
    await tester.pump(const Duration(milliseconds: 500));
    final release = find.byKey(const Key('ai_release_reservation'));
    expect(release, findsOneWidget);
    // The hold card sits in a height-capped panel; trigger the enabled button directly (the device tap is
    // covered by the emulator run).
    final button = tester.widget<TextButton>(release);
    expect(button.onPressed, isNotNull);
    button.onPressed!();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.byKey(const Key('ai_release_reservation_dialog')), findsOneWidget);
    await tester.tap(find.byKey(const Key('ai_release_reservation_confirm')));
    await tester.pump(const Duration(milliseconds: 500));
    expect(service.currentSession.state, 'CANCELLED');
    expect(release, findsNothing);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('Doctor overview uses real appointments only (no fabricated or video figures)', (tester) async {
    String? askedDate;
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, home: Scaffold(body: DoctorTodayOverview(
      loader: (date) async {
        askedDate = date;
        return [_appt(), _appt(id: 'B', payment: 'UNPAID', paid: null), _appt(id: 'C', status: 'CANCELLED')];
      },
    ))));
    await tester.pumpAndSettle();
    expect(askedDate, DoctorTodayOverview.colomboToday());
    expect(tester.widget<Text>(find.byKey(const Key('doctor_today_appointments'))).data, '2');
    expect(tester.widget<Text>(find.byKey(const Key('doctor_today_paid_total'))).data, 'LKR 3,000');
    for (final fabricated in ['12 Patients', 'video', 'LKR 18,500', '3 In Queue', 'LIVE STREAM']) {
      expect(find.textContaining(fabricated), findsNothing);
    }
  });

  test('Money formatting and models never invent amounts', () {
    expect(formatMoney(2500), 'LKR 2,500');
    expect(formatMoney(1234567.5, currency: 'lkr'), 'LKR 1,234,567.50');
    expect(formatMoney(null), 'Not available');
    final bare = Appointment.fromJson({'id': 'x', 'status': 'PENDING'});
    expect(bare.consultationFee, isNull);
    expect(bare.bookedFee, isNull);
    expect(bare.visitType, 'IN_PERSON');
    expect(DoctorTodayOverview.colomboToday(DateTime.utc(2026, 11, 25, 19, 0)), '2026-11-26');
  });
}
