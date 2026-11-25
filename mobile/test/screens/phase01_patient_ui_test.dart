// Phase 01 regression tests: mental-health crisis UI, keyboard UX, duplicate-send protection, reply scrolling,
// and the truthful patient dashboard. See docs/uat/phase-01/PHASE_01_BUG_FIX_REPORT.md.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/appointment.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/models/user_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';
import 'package:mediconnect/screens/patient/patient_home_screen.dart';

import 'ai_care_assistant_screen_test.dart' show FakeAiBookingService;
import 'doctor_discovery_availability_test.dart' show MockAuthApiService, createTestApp;

BookingSession _withReply(BookingSession base, String user, String reply, Map<String, dynamic> metadata,
    {bool urgent = false, String? intent}) {
  final json = base.toJson();
  return BookingSession.fromJson({
    ...json,
    'isUrgent': urgent,
    'activeIntent': intent,
    'urgencyReason': urgent ? 'Risk of suicide or self-harm' : null,
    'messages': [
      ...base.messages.where((m) => !m.id.startsWith('temp_')).map((m) => m.toJson()),
      {'id': 'u${base.messages.length}', 'sender': 'user', 'content': user, 'timestamp': DateTime.now().toIso8601String()},
      {'id': 'a${base.messages.length}', 'sender': 'assistant', 'content': reply,
       'timestamp': DateTime.now().toIso8601String(), 'metadata': metadata},
    ],
  });
}

class _Phase01Fake extends FakeAiBookingService {
  int sends = 0;
  Completer<BookingSession>? pending;
  bool hold = false;
  String longReply = '';

  @override
  Future<BookingSession> sendConversationMessage(String sessionId, String message, String requestId) async {
    sends++;
    BookingSession next;
    if (message.contains('kill myself')) {
      next = _withReply(currentSession, message, '**I am really glad you told me.** Call 1926.',
          {'type': 'emergency', 'isUrgent': true, 'category': 'self_harm', 'crisisType': 'mental_health',
           'ambulanceCall': '1990', 'supportLines': [{'number': '1926'}, {'number': '1333'}]},
          urgent: true, intent: 'EMERGENCY_GUIDANCE');
    } else if (message.contains('symptoms of a heart attack')) {
      next = _withReply(currentSession, message, 'Common warning signs... If you or someone near you has these symptoms now, call 1990.',
          {'type': 'emergency_information', 'category': 'cardiac', 'conditionalEmergency': true}, intent: 'HEALTH_INFORMATION');
    } else if (message.contains('long')) {
      next = _withReply(currentSession, message, longReply, {'type': 'health_guidance'}, intent: 'HEALTH_GUIDANCE');
    } else {
      next = _withReply(currentSession, message, 'Here is some general guidance.', {'type': 'health_guidance'},
          intent: 'HEALTH_GUIDANCE');
    }
    currentSession = next;
    if (hold) {
      pending = Completer<BookingSession>();
      return pending!.future;
    }
    return next;
  }
}

Widget _app(FakeAiBookingService service, {Future<bool> Function(String)? dialer}) => MaterialApp(
      theme: AppTheme.lightTheme,
      home: AiCareAssistantScreen(bookingService: service, emergencyDialer: dialer),
    );

Future<void> _send(WidgetTester tester, String text) async {
  await tester.tap(find.byKey(const Key('ai_care_assistant_input')));
  await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), text);
  await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
  await tester.pumpAndSettle();
}

EditableText _editable(WidgetTester tester) =>
    tester.widget<EditableText>(find.descendant(of: find.byKey(const Key('ai_care_assistant_input')), matching: find.byType(EditableText)));

void main() {
  group('Mental-health crisis UI', () {
    testWidgets('self-harm shows the supportive UI, not the cardiac alarm', (tester) async {
      final service = _Phase01Fake();
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await _send(tester, 'I want to kill myself');

      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('ai_mental_health_banner')), findsOneWidget);
      expect(find.byKey(const Key('ai_emergency_banner')), findsNothing);
      expect(find.text("You don't have to face this alone"), findsOneWidget);
      expect(find.byKey(const Key('ai_mental_health_message_call_1926')), findsOneWidget);
      expect(find.byKey(const Key('ai_mental_health_call_1333')), findsOneWidget);
      expect(find.byKey(const Key('ai_mental_health_call_1990')), findsOneWidget, reason: 'escalation is kept');
      expect(find.text('Find Doctor'), findsNothing);
    });

    for (final number in ['1926', '1333', '1990']) {
      testWidgets('$number asks for confirmation and dials only $number after confirming', (tester) async {
        final dialed = <String>[];
        final service = _Phase01Fake();
        await tester.pumpWidget(_app(service, dialer: (n) async {
          dialed.add(n);
          return true;
        }));
        await tester.pumpAndSettle();
        await _send(tester, 'I want to kill myself');

        final key = number == '1926' ? 'ai_mental_health_message_call_1926' : 'ai_mental_health_call_$number';
        await tester.ensureVisible(find.byKey(Key(key)));
        await tester.tap(find.byKey(Key(key)));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('ai_emergency_call_dialog')), findsOneWidget);
        expect(dialed, isEmpty, reason: 'no call before confirmation');
        await tester.tap(find.byKey(const Key('ai_emergency_call_cancel')));
        await tester.pumpAndSettle();
        expect(dialed, isEmpty, reason: 'cancel never dials');

        await tester.tap(find.byKey(Key(key)));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('ai_emergency_call_confirm')));
        await tester.pumpAndSettle();
        expect(dialed, [number]);
      });
    }

    testWidgets('an informational heart-attack question shows no emergency banner', (tester) async {
      final service = _Phase01Fake();
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await _send(tester, 'What are the common symptoms of a heart attack?');
      expect(find.byKey(const Key('ai_emergency_banner')), findsNothing);
      expect(find.byKey(const Key('ai_mental_health_banner')), findsNothing);
      expect(find.textContaining('If you or someone near you has these symptoms now'), findsOneWidget);
    });
  });

  group('Keyboard and chat UX', () {
    testWidgets('sending dismisses the keyboard and the reply does not reopen it', (tester) async {
      final service = _Phase01Fake();
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_input')));
      await tester.pump();
      expect(_editable(tester).focusNode.hasFocus, isTrue);
      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'I have a headache');
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();
      expect(_editable(tester).focusNode.hasFocus, isFalse);
      expect(tester.testTextInput.isVisible, isFalse);
      expect(service.sends, 1);
    });

    testWidgets('tapping outside the composer dismisses the keyboard; it can be focused again', (tester) async {
      final service = _Phase01Fake();
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_input')));
      await tester.pump();
      expect(_editable(tester).focusNode.hasFocus, isTrue);
      await tester.tapAt(const Offset(200, 300)); // conversation area
      await tester.pump();
      expect(_editable(tester).focusNode.hasFocus, isFalse);
      await tester.tap(find.byKey(const Key('ai_care_assistant_input')));
      await tester.pump();
      expect(_editable(tester).focusNode.hasFocus, isTrue);
    });

    testWidgets('a reply arriving while the user types does not steal focus or clear the draft', (tester) async {
      final service = _Phase01Fake()..hold = true;
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'I have a headache');
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('ai_care_assistant_input')));
      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'my next question');
      await tester.pump();
      service.pending!.complete(service.currentSession);
      await tester.pumpAndSettle();
      expect(_editable(tester).focusNode.hasFocus, isTrue);
      expect(_editable(tester).controller.text, 'my next question');
    });

    testWidgets('rapid repeated taps send one request', (tester) async {
      final service = _Phase01Fake()..hold = true;
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'I have a headache');
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')), warnIfMissed: false);
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')), warnIfMissed: false);
      await tester.pump();
      expect(service.sends, 1);
      service.pending!.complete(service.currentSession);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });

    testWidgets('a long reply is shown from its beginning, not its end', (tester) async {
      final service = _Phase01Fake()
        ..longReply = 'START-OF-REPLY\n\n${List.generate(80, (i) => '- detail line $i').join('\n')}\n\nEND-OF-REPLY';
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      await _send(tester, 'give me a long answer');
      final viewport = tester.getRect(find.byType(ListView).first);
      final start = tester.getRect(find.textContaining('START-OF-REPLY'));
      expect(start.top, greaterThanOrEqualTo(viewport.top - 1));
      expect(start.top, lessThan(viewport.bottom));
    });
  });

  group('Patient dashboard', () {
    AuthProvider auth() {
      final provider = AuthProvider(authApiService: MockAuthApiService());
      provider.setSessionForTesting(AuthSession(
        message: 'ok', accessToken: 't', refreshToken: 'r', expiresIn: 3600,
        user: UserModel(id: 'PAT-1', fullName: 'Jane Doe', email: 'jane@example.com', role: 'PATIENT',
            emailVerified: true, accountStatus: 'ACTIVE', createdAt: DateTime.now()),
      ));
      return provider;
    }

    Appointment appointment(String date, String status) => Appointment.fromJson({
          'id': 'A1', 'patientUserId': 'PAT-1', 'doctorUserId': 'D1', 'doctorProfileId': 'DP1', 'availabilityId': 'AV1',
          'appointmentDate': date, 'startTime': '09:00', 'endTime': '09:30', 'status': status, 'paymentStatus': 'PAID',
          'consultationFee': 2000, 'doctorName': 'Dr. UAT Cardio', 'specialty': 'Cardiology',
          'hospitalOrClinic': 'Colombo Care Centre',
        });

    void expectNoFabricatedContent() {
      for (final text in ['Dr. Alexander Wright', 'Join Call', 'VITALS: NORMAL', 'Synced 12m ago',
                          'Encrypted Video Consultation']) {
        expect(find.text(text), findsNothing, reason: text);
      }
      expect(find.textContaining('Video'), findsNothing);
    }

    testWidgets('no upcoming appointments shows a truthful empty state', (tester) async {
      await tester.pumpWidget(createTestApp(
          child: PatientHomeScreen(appointmentsLoader: () async => <Appointment>[]), authProvider: auth()));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('upcoming_appointment_empty')));
      expect(find.text('You have no upcoming appointments.'), findsOneWidget);
      expectNoFabricatedContent();
      expect(find.text('Medicine Reminders'), findsOneWidget);
      expect(find.text('Prescriptions'), findsNothing);
    });

    testWidgets('a real upcoming appointment is shown as an in-person visit', (tester) async {
      final date = DateTime.now().add(const Duration(days: 3)).toIso8601String().split('T').first;
      final past = DateTime.now().subtract(const Duration(days: 3)).toIso8601String().split('T').first;
      await tester.pumpWidget(createTestApp(
          child: PatientHomeScreen(appointmentsLoader: () async => [
                appointment(past, 'CONFIRMED'),
                appointment(date, 'CANCELLED'),
                appointment(date, 'CONFIRMED'),
              ]),
          authProvider: auth()));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('upcoming_appointment_item')));
      expect(find.text('Dr. UAT Cardio'), findsOneWidget);
      expect(find.textContaining('In-person visit'), findsOneWidget);
      expect(find.textContaining(date), findsOneWidget);
      expectNoFabricatedContent();
    });

    testWidgets('a loading failure is reported, not replaced with placeholder data', (tester) async {
      await tester.pumpWidget(createTestApp(
          child: PatientHomeScreen(appointmentsLoader: () async => throw Exception('offline')), authProvider: auth()));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('upcoming_appointment_error')));
      expectNoFabricatedContent();
    });
  });
}
