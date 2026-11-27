// Agent Completion A03 (A03-BUG-012): a cancel / reschedule request in the chat lists the patient's appointments and
// links to My Appointments; the chat itself never cancels or moves a booking.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';

import 'ai_care_assistant_screen_test.dart' show FakeAiBookingService;

void main() {
  testWidgets('A03-BUG-012: appointment management reply offers My Appointments, nothing else', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(800, 1200);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final service = FakeAiBookingService();
    service.currentSession = BookingSession.fromJson({
      ...service.currentSession.toJson(),
      'messages': [
        {'id': 'u1', 'sender': 'user', 'content': 'I want to cancel my appointment.', 'timestamp': '2026-11-27T10:00:00Z'},
        {
          'id': 'a1', 'sender': 'assistant', 'timestamp': '2026-11-27T10:00:01Z',
          'content': "I can't cancel an appointment from the chat. Your upcoming appointments:\n"
              '• 2026-12-03 at 09:00 with Dr. P02 Ortho (confirmed)',
          'metadata': {
            'type': 'appointment_management', 'action': 'cancel',
            'appointments': [
              {'appointmentId': 'a'.padRight(24, '0'), 'date': '2026-12-03', 'startTime': '09:00',
               'status': 'CONFIRMED', 'doctorName': 'Dr. P02 Ortho'},
            ],
          },
        },
      ],
    });
    final opened = <String>[];
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: AiCareAssistantScreen(bookingService: service),
      onGenerateRoute: (settings) {
        opened.add(settings.name ?? '');
        return MaterialPageRoute(builder: (_) => const Scaffold(body: Text('My Appointments page')));
      },
    ));
    await tester.pump(const Duration(milliseconds: 500));
    final action = find.byKey(const ValueKey('manage_appointments_action'));
    expect(action, findsOneWidget);
    expect(find.text('Choose the appointment, then Cancel Appointment'), findsOneWidget);
    await tester.ensureVisible(action);
    await tester.pumpAndSettle();
    // Invoke the tile's own handler (the composer can overlap the list in a test viewport).
    tester.widget<ListTile>(find.descendant(of: action, matching: find.byType(ListTile))).onTap!();
    await tester.pumpAndSettle();
    expect(opened, ['/patient/my-appointments']);
  });

  test('A03-BUG-017: a summary without the server fee is not shown (no invented LKR 2,500)', () {
    final base = {'doctorName': 'Dr. X', 'specialty': 'Cardiology', 'appointmentDate': '2026-12-01',
        'startTime': '09:00', 'endTime': '09:30'};
    expect(BookingSummary.tryFromJson(base), isNull);
    final ok = BookingSummary.tryFromJson({...base, 'consultationFee': 3500, 'totalAmount': 3500});
    expect(ok!.totalAmount, 3500);
    expect(ok.visitType, 'IN_PERSON');
  });

  testWidgets('A03-BUG-015: the booking summary states an in-person clinic visit', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(800, 2400);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final service = FakeAiBookingService();
    service.currentSession = BookingSession.fromJson({
      ...service.currentSession.toJson(),
      'state': 'AWAITING_BOOKING_CONFIRMATION',
      'bookingSummary': {
        'proposalId': 'p1', 'doctorName': 'Dr. A03', 'specialty': 'Cardiology', 'appointmentDate': '2026-12-01',
        'startTime': '10:30', 'endTime': '11:00', 'consultationFee': 3500, 'totalAmount': 3500, 'visitType': 'IN_PERSON',
      },
    });
    await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, home: AiCareAssistantScreen(bookingService: service)));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Visit type'), findsOneWidget);
    expect(find.text('In-person at the clinic'), findsOneWidget);
    expect(find.textContaining('Video'), findsNothing);
  });
}
