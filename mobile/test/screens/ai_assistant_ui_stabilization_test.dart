// Regression tests for the UAT AI Assistant UI blockers (BUG-014, BUG-015, BUG-042, BUG-043,
// BUG-045). See docs/UAT_UI_STABILIZATION_REPORT.md.
//
// Confirmed root cause (reproduced on the Android emulator): the app theme gives every
// ElevatedButton `minimumSize: Size(double.infinity, 52)`. The emergency banner placed its 1990
// ElevatedButton directly in a Row, so layout received `BoxConstraints(w=Infinity)` and threw in
// the middle of a frame. Older tests never used the app theme or an urgent session, so they could
// not see it. Every test here pumps the real `AppTheme.lightTheme` and the real backend emergency
// contract (`isUrgent`, `urgencyReason`, `activeIntent: EMERGENCY_GUIDANCE`, metadata type
// `emergency`, state still `COLLECTING_PREFERENCES`).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';
import 'package:mediconnect/utils/assistant_navigation.dart';

import 'ai_care_assistant_screen_test.dart' show FakeAiBookingService;

const _emergencyReason = 'Possible heart-related emergency (chest pain or pressure)';

/// Mirrors the UAT backend response captured on 2026-11-25 for
/// "I have severe chest pain and cannot breathe".
BookingSession _emergencySession(BookingSession base, String userText,
    {String language = 'en', String? replyContent}) {
  final json = base.toJson();
  return BookingSession.fromJson({
    ...json,
    'state': 'COLLECTING_PREFERENCES',
    'isUrgent': true,
    'urgencyReason': _emergencyReason,
    'activeIntent': 'EMERGENCY_GUIDANCE',
    'preferences': <String, dynamic>{...(json['preferences'] as Map<String, dynamic>), 'language': language},
    'candidateDoctors': [],
    'messages': [
      ...base.messages.where((m) => !m.id.startsWith('temp_')).map((m) => m.toJson()),
      {
        'id': 'u_${base.messages.length}',
        'sender': 'user',
        'content': userText,
        'timestamp': DateTime.now().toIso8601String(),
      },
      {
        'id': 'a_${base.messages.length}',
        'sender': 'assistant',
        'content': replyContent ?? '**This may be a medical emergency.**\n\n- Call **1990** (Suwa Seriya ambulance) now.',
        'timestamp': DateTime.now().toIso8601String(),
        'metadata': {
          'type': 'emergency',
          'isUrgent': true,
          'ambulanceCall': '1990',
          'reason': _emergencyReason,
          'category': 'cardiac',
          'fromContext': false,
        },
      },
    ],
  });
}

bool _isEmergencyText(String text) =>
    text.contains('chest pain') || text.contains('papuwa') || text.contains('පපුව');

/// Fake that answers emergency messages with the real backend contract, can hold a reply
/// pending, and can start in an existing emergency conversation.
class _UiFake extends FakeAiBookingService {
  _UiFake({super.initialSession});

  Completer<BookingSession>? pending;
  bool holdNext = false;
  String language = 'en';
  String? replyContent;
  int sends = 0;

  @override
  Future<BookingSession> sendConversationMessage(String sessionId, String message, String requestId) async {
    sends++;
    if (holdNext) {
      holdNext = false;
      pending = Completer<BookingSession>();
      return pending!.future;
    }
    if (_isEmergencyText(message)) {
      currentSession = _emergencySession(currentSession, message, language: language, replyContent: replyContent);
      return currentSession;
    }
    return super.sendConversationMessage(sessionId, message, requestId);
  }
}

Widget _themedApp(FakeAiBookingService service, {Future<bool> Function(String)? dialer}) {
  return MaterialApp(
    theme: AppTheme.lightTheme,
    home: AiCareAssistantScreen(bookingService: service, emergencyDialer: dialer),
  );
}

/// Counts text-input render objects that are actually attached to the render tree. A corrupted
/// tree ("ghost" composer) shows up here even when widget finders report a single TextField.
int _attachedEditables(WidgetTester tester) {
  var count = 0;
  void visit(RenderObject node) {
    if (node is RenderEditable && node.attached) count++;
    node.visitChildren(visit);
  }

  visit(tester.binding.renderView);
  return count;
}

void _expectSingleComposer(WidgetTester tester) {
  expect(find.byKey(const Key('ai_care_assistant_input')), findsOneWidget);
  expect(find.byKey(const Key('ai_care_assistant_send')), findsOneWidget);
  expect(find.byKey(const Key('ai_care_assistant_attach_image')), findsOneWidget);
  expect(_attachedEditables(tester), 1, reason: 'exactly one attached composer render object');
}

Future<void> _send(WidgetTester tester, String text) async {
  await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), text);
  await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
  await tester.pumpAndSettle();
}

void main() {
  setUp(AssistantNavigation.reset);

  group('Root cause: emergency banner layout under the real app theme', () {
    testWidgets('opening an existing emergency conversation lays out without any exception', (tester) async {
      final base = FakeAiBookingService().currentSession;
      final service = _UiFake(initialSession: _emergencySession(base, 'I have severe chest pain'));
      service.history = [
        {'id': service.currentSession.id, 'title': 'Chest pain'},
      ];
      service.storedSessions[service.currentSession.id] = service.currentSession;

      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('ai_emergency_banner')), findsOneWidget);
      final button = tester.getSize(find.byKey(const Key('ai_emergency_call_1990')));
      expect(button.width.isFinite, isTrue);
      expect(button.width, lessThan(200));
      _expectSingleComposer(tester);
    });

    testWidgets('the composer stays laid out and single after an emergency reply', (tester) async {
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      await _send(tester, 'I have severe chest pain and cannot breathe');

      expect(tester.takeException(), isNull);
      _expectSingleComposer(tester);
      final composer = tester.renderObject<RenderBox>(find.byKey(const Key('ai_care_assistant_input')));
      expect(composer.hasSize, isTrue);
      expect(composer.debugNeedsLayout, isFalse);
    });
  });

  group('BUG-042 emergency UI', () {
    testWidgets('emergency reply shows banner, dedicated 1990 action and hides routine chips', (tester) async {
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      expect(find.text('Find Doctor'), findsOneWidget, reason: 'routine chips before the emergency');

      await _send(tester, 'I have severe chest pain and cannot breathe');

      expect(find.byKey(const Key('ai_emergency_banner')), findsOneWidget);
      expect(find.text('Possible medical emergency'), findsOneWidget);
      expect(find.textContaining(_emergencyReason), findsOneWidget);
      expect(find.byKey(const Key('ai_emergency_call_1990')), findsOneWidget);
      expect(find.byKey(const Key('ai_emergency_message_call')), findsOneWidget);
      expect(find.text('Find Doctor'), findsNothing);
      expect(find.text('Book Slot'), findsNothing);
      expect(find.text('Cardiologist in Colombo'), findsNothing);
    });

    testWidgets('normal reply shows no emergency UI and keeps routine chips', (tester) async {
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      await _send(tester, 'Healthy Sri Lankan breakfast ideas');

      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('ai_emergency_banner')), findsNothing);
      expect(find.byKey(const Key('ai_emergency_message_call')), findsNothing);
      _expectSingleComposer(tester);
    });

    testWidgets('1990 asks for confirmation and never dials on cancel', (tester) async {
      final dialed = <String>[];
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service, dialer: (n) async {
        dialed.add(n);
        return true;
      }));
      await tester.pumpAndSettle();
      await _send(tester, 'I have severe chest pain');

      await tester.tap(find.byKey(const Key('ai_emergency_call_1990')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ai_emergency_call_dialog')), findsOneWidget);
      expect(dialed, isEmpty, reason: 'nothing is dialled before confirmation');

      await tester.tap(find.byKey(const Key('ai_emergency_call_cancel')));
      await tester.pumpAndSettle();
      expect(dialed, isEmpty);

      await tester.tap(find.byKey(const Key('ai_emergency_message_call')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_emergency_call_confirm')));
      await tester.pumpAndSettle();
      expect(dialed, ['1990']);
      expect(tester.takeException(), isNull);
    });

    testWidgets('a dialer failure tells the patient to dial 1990 manually', (tester) async {
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service, dialer: (_) async => false));
      await tester.pumpAndSettle();
      await _send(tester, 'I have severe chest pain');
      await tester.tap(find.byKey(const Key('ai_emergency_call_1990')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_emergency_call_confirm')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Dial 1990 on your phone now'), findsOneWidget);
    });

    testWidgets('Sinhala conversations get Sinhala emergency guidance', (tester) async {
      final service = _UiFake()..language = 'si';
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      await _send(tester, 'මට පපුව රිදෙනවා');

      expect(tester.takeException(), isNull);
      expect(find.text('හදිසි වෛද්‍ය තත්ත්වයක් විය හැක'), findsOneWidget);
      expect(find.text('1990 අමතන්න'), findsOneWidget);
    });
    testWidgets('Romanized Sinhala emergency answered in Sinhala gets a Sinhala banner', (tester) async {
      // Observed on the emulator: the backend replies in Sinhala but keeps preferences.language "en"
      // and an English urgencyReason.
      final service = _UiFake()
        ..replyContent = '**මෙය හදිසි වෛද්‍ය තත්ත්වයක් විය හැකියි.**\n\n- දැන්ම **1990** අමතන්න.';
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      await _send(tester, 'mata papuwa godak ridenawa');

      expect(tester.takeException(), isNull);
      expect(find.text('හදිසි වෛද්‍ය තත්ත්වයක් විය හැක'), findsOneWidget);
      expect(find.textContaining(_emergencyReason), findsNothing, reason: 'English-only reason hidden');
      expect(find.text('1990 අමතන්න'), findsOneWidget);
    });
  });

  group('BUG-014 composer always fits (found on the emulator 2026-11-25)', () {
    // Pixel 7 Pro emulator in landscape: about 891 x 411 logical px; the keyboard takes about
    // 265 px, which leaves about 64 px for the body. Before the fix the disclaimer and emergency
    // banner overflowed by 106 px and pushed the composer off-screen.
    Future<void> pumpLandscape(WidgetTester tester, {required double keyboard}) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(891, 411);
      tester.view.viewInsets = FakeViewPadding(bottom: keyboard);
      addTearDown(tester.view.reset);
      await tester.pumpAndSettle();
    }

    for (final keyboard in [0.0, 265.0]) {
      testWidgets('landscape emergency chat, keyboard ${keyboard == 0 ? 'closed' : 'open'}: no overflow, composer visible',
          (tester) async {
        final service = _UiFake();
        await tester.pumpWidget(_themedApp(service));
        await tester.pumpAndSettle();
        await _send(tester, 'I have severe chest pain');

        await pumpLandscape(tester, keyboard: keyboard);
        expect(tester.takeException(), isNull, reason: 'no RenderFlex overflow');
        _expectSingleComposer(tester);
        final composer = tester.getRect(find.byKey(const Key('ai_care_assistant_input')));
        expect(composer.bottom, lessThanOrEqualTo(411 - keyboard), reason: 'composer above the keyboard');
        expect(composer.height, greaterThan(30));
        if (keyboard == 0) {
          expect(find.byKey(const Key('ai_emergency_call_1990')), findsOneWidget);
        }

        // Close the keyboard again: the emergency banner comes back.
        tester.view.viewInsets = FakeViewPadding.zero;
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(find.byKey(const Key('ai_emergency_banner')), findsOneWidget);
      });
    }

    testWidgets('portrait with keyboard keeps banner, chips and composer without overflow', (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(411, 891);
      tester.view.viewInsets = const FakeViewPadding(bottom: 336);
      addTearDown(tester.view.reset);
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      expect(find.text('Find Doctor'), findsOneWidget);
      await _send(tester, 'I have severe chest pain');
      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('ai_emergency_banner')), findsOneWidget);
      _expectSingleComposer(tester);
    });
  });

  group('BUG-014 / BUG-015 / BUG-043 lifecycle under the real theme', () {
    testWidgets('keyboard open/close repeatedly keeps one composer', (tester) async {
      final service = _UiFake();
      await tester.pumpWidget(_themedApp(service));
      await tester.pumpAndSettle();
      await _send(tester, 'I have severe chest pain');
      addTearDown(tester.view.resetViewInsets);
      for (var i = 0; i < 20; i++) {
        await tester.showKeyboard(find.byKey(const Key('ai_care_assistant_input')));
        tester.view.viewInsets = const FakeViewPadding(bottom: 900);
        await tester.pumpAndSettle();
        _expectSingleComposer(tester);
        tester.view.viewInsets = FakeViewPadding.zero;
        FocusManager.instance.primaryFocus?.unfocus();
        await tester.pumpAndSettle();
        _expectSingleComposer(tester);
      }
      expect(tester.takeException(), isNull);
    });

    testWidgets('20 cycles of open, emergency, New Chat, history, Back with pending reply', (tester) async {
      final service = _UiFake();
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.lightTheme,
        routes: {
          '/': (context) => Scaffold(
                body: Center(
                  child: TextButton(
                    onPressed: () => AssistantNavigation.open(context),
                    child: const Text('Open assistant'),
                  ),
                ),
              ),
          AssistantNavigation.routeName: (context) =>
              AiCareAssistantScreen(bookingService: service, emergencyDialer: (_) async => true),
        },
      ));
      addTearDown(tester.view.resetViewInsets);

      for (var cycle = 0; cycle < 20; cycle++) {
        await tester.tap(find.text('Open assistant'));
        await tester.pumpAndSettle();
        _expectSingleComposer(tester);

        await _send(tester, 'I have severe chest pain');
        expect(find.byKey(const Key('ai_emergency_banner')), findsOneWidget);
        _expectSingleComposer(tester);

        await tester.tap(find.text('New Chat'));
        await tester.pumpAndSettle();
        _expectSingleComposer(tester);

        await tester.tap(find.byTooltip('Chat History'));
        await tester.pumpAndSettle();
        await tester.tapAt(const Offset(10, 10)); // dismiss the sheet
        await tester.pumpAndSettle();
        _expectSingleComposer(tester);

        // Back while the keyboard is open and a reply is still pending.
        service.holdNext = true;
        await tester.showKeyboard(find.byKey(const Key('ai_care_assistant_input')));
        tester.view.viewInsets = const FakeViewPadding(bottom: 900);
        await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'Dermatologist tomorrow');
        await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
        await tester.pump();
        final NavigatorState navigator = tester.state(find.byType(Navigator));
        navigator.maybePop();
        await tester.pump();
        // The reply arrives after the route started closing: it must be ignored safely.
        service.pending!.complete(service.currentSession);
        tester.view.viewInsets = FakeViewPadding.zero;
        await tester.pumpAndSettle();

        expect(tester.takeException(), isNull, reason: 'cycle $cycle');
        expect(find.byType(AiCareAssistantScreen), findsNothing);
        expect(_attachedEditables(tester), 0, reason: 'no composer left behind after Back');
      }
    });

    testWidgets('a late emergency reply after Back does not touch the disposed screen', (tester) async {
      final service = _UiFake()..holdNext = true;
      await tester.pumpWidget(MaterialApp(
        theme: AppTheme.lightTheme,
        routes: {
          '/': (context) => Scaffold(
                body: TextButton(
                  onPressed: () => AssistantNavigation.open(context),
                  child: const Text('Open assistant'),
                ),
              ),
          AssistantNavigation.routeName: (context) => AiCareAssistantScreen(bookingService: service),
        },
      ));
      await tester.tap(find.text('Open assistant'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'I have severe chest pain');
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pump();
      tester.state<NavigatorState>(find.byType(Navigator)).maybePop();
      await tester.pumpAndSettle();
      service.pending!.complete(_emergencySession(service.currentSession, 'I have severe chest pain'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('ai_emergency_banner')), findsNothing);
    });
  });
}
