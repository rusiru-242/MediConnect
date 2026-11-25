// Regression tests for the AI Assistant stabilization (BUG-014, BUG-015, BUG-016, BUG-024,
// BUG-025, BUG-026). Device-dependent behaviour (real keyboard, real gallery, Android back
// gesture) still requires the manual UAT steps in docs/MANUAL_UAT_TEST_PLAN.md.
import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/core/network/api_error_mapper.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';
import 'package:mediconnect/models/booking_session.dart';
import 'package:mediconnect/screens/patient/ai_care_assistant_screen.dart';
import 'package:mediconnect/utils/assistant_navigation.dart';
import 'package:mediconnect/widgets/safe_markdown_text.dart';

import 'ai_care_assistant_screen_test.dart' show FakeAiBookingService;

final Uint8List _png = Uint8List.fromList([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0]);

class _ImageFake extends FakeAiBookingService {
  Completer<BookingSession>? pending;
  bool failImage = false;
  int imageCalls = 0;

  @override
  Future<BookingSession> sendImageMessage(String sessionId, List<int> bytes, String filename, {String? message}) {
    imageCalls++;
    if (failImage) {
      failImage = false;
      return Future.error(const ApiException(message: 'Server unavailable', statusCode: 503));
    }
    pending = Completer<BookingSession>();
    return pending!.future;
  }
}

BookingSession _withAssistantReply(BookingSession base, String text) {
  return BookingSession.fromJson({
    ...base.toJson(),
    'messages': [
      ...base.messages.map((m) => m.toJson()),
      {
        'id': 'server_user_1',
        'sender': 'user',
        'content': 'Medicine photo',
        'timestamp': DateTime.now().toIso8601String(),
        'metadata': {'attachment': {'type': 'image', 'name': 'label.png'}},
      },
      {
        'id': 'server_reply_1',
        'sender': 'assistant',
        'content': text,
        'timestamp': DateTime.now().toIso8601String(),
        'metadata': {'type': 'medicine_image_analysis', 'status': 'provider_unavailable'},
      },
    ],
  });
}

Widget _app(FakeAiBookingService service, {Future<({Uint8List bytes, String name})?> Function()? picker}) {
  return MaterialApp(theme: AppTheme.lightTheme, 
    home: AiCareAssistantScreen(bookingService: service, imagePicker: picker),
  );
}

void main() {
  setUp(AssistantNavigation.reset);

  group('BUG-024 Markdown rendering', () {
    testWidgets('bold, headings and bullets render without raw markers', (tester) async {
      await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, 
        home: Scaffold(body: SafeMarkdownText('**Medicine Packaging Analysis**\n\n## Next steps\n- Ask a **pharmacist**\n1. Keep the box')),
      ));
      final rendered = tester.widgetList<RichText>(find.byType(RichText)).map((w) => w.text.toPlainText()).join('\n');
      expect(rendered.contains('**'), isFalse);
      expect(rendered.contains('##'), isFalse);
      expect(rendered, contains('Medicine Packaging Analysis'));
      expect(rendered, contains('Ask a pharmacist'));
      expect(find.text('•'), findsOneWidget);
      expect(find.text('1.'), findsOneWidget);
    });

    test('no HTML or link handling: tags are shown as plain text', () {
      expect(SafeMarkdownText.toPlainText('<script>alert(1)</script> **ok**'), '<script>alert(1)</script> ok');
    });

    testWidgets('assistant bubble renders Markdown instead of raw asterisks', (tester) async {
      final service = FakeAiBookingService(
        initialSession: BookingSession.fromJson({
          ...FakeAiBookingService().currentSession.toJson(),
          'messages': [
            {
              'id': 'a1',
              'sender': 'assistant',
              'content': '**This may be a medical emergency.**\n- Call **1990** now',
              'timestamp': DateTime.now().toIso8601String(),
            },
          ],
        }),
      );
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      final texts = tester.widgetList<RichText>(find.byType(RichText)).map((w) => w.text.toPlainText()).join('\n');
      expect(texts, contains('This may be a medical emergency.'));
      expect(texts.contains('**This may'), isFalse);
    });
  });

  group('BUG-014 / BUG-015 composer and navigation lifecycle', () {
    testWidgets('exactly one composer after New Chat and after sending', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      expect(find.byType(TextField), findsOneWidget);

      await tester.tap(find.text('New Chat'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ai_care_assistant_input')), findsOneWidget);
      expect(find.byKey(const Key('ai_care_assistant_send')), findsOneWidget);

      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'Cardiologist in Colombo');
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ai_care_assistant_input')), findsOneWidget);
      expect(find.byKey(const Key('ai_care_assistant_send')), findsOneWidget);
    });

    testWidgets('composer stays single when the keyboard inset changes', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(_app(service));
      await tester.pumpAndSettle();
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      addTearDown(tester.view.resetViewInsets);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ai_care_assistant_input')), findsOneWidget);
    });

    testWidgets('pressing Back with a focused input and pending reply does not throw', (tester) async {
      final service = FakeAiBookingService();
      await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, 
        initialRoute: '/',
        routes: {
          '/': (context) => Scaffold(
                body: Center(
                  child: ElevatedButton(
                    onPressed: () => AssistantNavigation.open(context),
                    child: const Text('Open assistant'),
                  ),
                ),
              ),
          AssistantNavigation.routeName: (context) => AiCareAssistantScreen(bookingService: service),
        },
      ));
      await tester.tap(find.text('Open assistant'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_input')));
      await tester.enterText(find.byKey(const Key('ai_care_assistant_input')), 'Dermatologist tomorrow');
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      // Pop while the send result and the post-frame scroll are still pending.
      final NavigatorState navigator = tester.state(find.byType(Navigator));
      navigator.maybePop();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Open assistant'), findsOneWidget);
      expect(find.byType(AiCareAssistantScreen), findsNothing);
    });

    testWidgets('double tap opens the assistant only once and forwards the prompt', (tester) async {
      final service = FakeAiBookingService();
      String? receivedPrompt;
      await tester.pumpWidget(MaterialApp(theme: AppTheme.lightTheme, 
        routes: {
          '/': (context) => Scaffold(
                body: ElevatedButton(
                  onPressed: () => AssistantNavigation.open(context, initialPrompt: 'Headache for 3 days'),
                  child: const Text('Ask AI'),
                ),
              ),
          AssistantNavigation.routeName: (context) {
            receivedPrompt = AssistantNavigation.initialPromptFrom(context);
            return AiCareAssistantScreen(bookingService: service, initialQuery: receivedPrompt);
          },
        },
      ));
      await tester.tap(find.text('Ask AI'));
      await tester.tap(find.text('Ask AI'), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byType(AiCareAssistantScreen), findsOneWidget);
      expect(find.byKey(const Key('ai_care_assistant_input')), findsOneWidget);
      expect(receivedPrompt, 'Headache for 3 days');
    });
  });

  group('BUG-026 image upload feedback', () {
    testWidgets('shows preview, progress, then the analysis reply', (tester) async {
      final service = _ImageFake();
      await tester.pumpWidget(_app(service, picker: () async => (bytes: _png, name: 'label.png')));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('ai_care_assistant_attach_image')));
      await tester.pumpAndSettle();
      expect(find.text('label.png'), findsOneWidget);

      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pump();
      expect(find.byKey(const Key('ai_care_assistant_upload_progress')), findsOneWidget);
      expect(find.text('Photo attached'), findsOneWidget);

      service.pending!.complete(_withAssistantReply(service.currentSession, '**Image received, but it could not be analysed right now.**'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('ai_care_assistant_upload_progress')), findsNothing);
      final texts = tester.widgetList<RichText>(find.byType(RichText)).map((w) => w.text.toPlainText()).join('\n');
      expect(texts, contains('could not be analysed'));
      expect(texts.contains('Generic Medicine Label'), isFalse);
    });

    testWidgets('failed upload offers retry with the same photo', (tester) async {
      final service = _ImageFake()..failImage = true;
      await tester.pumpWidget(_app(service, picker: () async => (bytes: _png, name: 'label.png')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_attach_image')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Your photo was not analysed'), findsOneWidget);
      expect(find.byKey(const Key('ai_care_assistant_retry_upload')), findsOneWidget);

      await tester.tap(find.byKey(const Key('ai_care_assistant_retry_upload')));
      await tester.pump();
      expect(service.imageCalls, 2);
      expect(find.byKey(const Key('ai_care_assistant_upload_progress')), findsOneWidget);
      service.pending!.complete(_withAssistantReply(service.currentSession, 'Done'));
      await tester.pumpAndSettle();
    });

    testWidgets('cancel stops waiting and ignores the late result', (tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 2.6;
      addTearDown(tester.view.reset);
      final service = _ImageFake();
      await tester.pumpWidget(_app(service, picker: () async => (bytes: _png, name: 'label.png')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_attach_image')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ai_care_assistant_send')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400)); // let the auto-scroll animation finish
      await tester.ensureVisible(find.byKey(const Key('ai_care_assistant_cancel_upload')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('ai_care_assistant_cancel_upload')));
      await tester.pump();
      expect(find.byKey(const Key('ai_care_assistant_upload_progress')), findsNothing);
      expect(find.textContaining('Upload cancelled'), findsOneWidget);

      service.pending!.complete(_withAssistantReply(service.currentSession, 'Late reply'));
      await tester.pumpAndSettle();
      final texts = tester.widgetList<RichText>(find.byType(RichText)).map((w) => w.text.toPlainText()).join('\n');
      expect(texts.contains('Late reply'), isFalse);
    });
  });

  group('BUG-025 authentication error messages', () {
    test('a generic 401 is reported as an expired session, not a wrong password', () {
      const tokenExpired = ApiException(message: 'Authentication credentials were not provided.', statusCode: 401);
      expect(ApiErrorMapper.mapException(tokenExpired), ApiErrorMapper.sessionExpiredMessage);
      expect(ApiErrorMapper.fromResponseBody({'detail': 'Could not validate token.'}, 401),
          ApiErrorMapper.sessionExpiredMessage);
    });

    test('real login rejections still say incorrect email or password', () {
      expect(ApiErrorMapper.fromResponseBody({'detail': 'Invalid email or password.'}, 401),
          ApiErrorMapper.incorrectCredentialsMessage);
    });
  });

  group('BUG-016 medicine formulations', () {
    test('formulations are parsed with their dosage form', () {
      final card = MedicineCardSummary.fromJson({
        'medicineName': 'Paracetamol',
        'formulations': [
          {'form': 'Tablet', 'strength': '500 mg per tablet'},
          {'form': 'Oral liquid (syrup/suspension)', 'strength': '120 mg in each 5 mL'},
        ],
      });
      expect(card.formulations.first, {'form': 'Tablet', 'strength': '500 mg per tablet'});
      expect(card.formulations, hasLength(2));
    });
  });
}
