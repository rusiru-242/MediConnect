// A05 (Agent 26): patient Help & Support — create a ticket, read support's reply, answer it; deep link from a
// notification; truthful loading, empty, error and closed states. The service is a fake; no network.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/theme/app_theme.dart';
import 'package:mediconnect/models/notification_model.dart';
import 'package:mediconnect/models/support_ticket.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/providers/notification_provider.dart';
import 'package:mediconnect/screens/notifications/notifications_screen.dart';
import 'package:mediconnect/screens/patient/patient_profile_screen.dart';
import 'package:mediconnect/screens/patient/support_screens.dart';
import 'package:mediconnect/services/support_service.dart';
import 'package:provider/provider.dart';

import '../helpers/fake_profile_service.dart';
import 'notification_screen_test.dart' show MockNotificationService;

Map<String, dynamic> _ticketJson(String id, {String status = 'open', List<Map<String, dynamic>>? messages,
    String? safety, String? awaiting = 'support'}) => {
      'ticketId': id,
      'subject': 'Payment shows pending',
      'category': 'payment_issue',
      'status': status,
      'safetyNotice': safety,
      'awaitingReplyFrom': awaiting,
      'updatedAt': '2026-11-27T10:00:00Z',
      'messages': messages ??
          [
            {'messageId': 'm1', 'senderRole': 'PATIENT', 'senderName': 'A05 Patient',
             'message': 'I paid but it shows pending.', 'sentAt': '2026-11-27T09:00:00Z'},
          ],
    };

class FakeSupportService extends SupportService {
  final Map<String, Map<String, dynamic>> tickets = {};
  final created = <Map<String, String>>[];
  final replies = <String>[];
  bool failList = false;

  @override
  Future<List<SupportTicket>> myTickets() async {
    if (failList) throw Exception('offline');
    return tickets.values.map(SupportTicket.fromJson).toList();
  }

  @override
  Future<SupportTicket> ticket(String ticketId) async => SupportTicket.fromJson(tickets[ticketId]!);

  @override
  Future<SupportTicket> create({required String category, required String subject, required String message}) async {
    created.add({'category': category, 'subject': subject, 'message': message});
    final json = _ticketJson('TCK-A05NEW01', messages: [
      {'messageId': 'm9', 'senderRole': 'PATIENT', 'senderName': 'A05 Patient', 'message': message,
       'sentAt': '2026-11-27T11:00:00Z'},
    ]);
    json['subject'] = subject;
    json['category'] = category;
    tickets[json['ticketId'] as String] = json;
    return SupportTicket.fromJson(json);
  }

  @override
  Future<SupportTicket> reply(String ticketId, String message) async {
    replies.add('$ticketId:$message');
    final json = tickets[ticketId]!;
    (json['messages'] as List).add({'messageId': 'm${replies.length + 20}', 'senderRole': 'PATIENT',
        'senderName': 'A05 Patient', 'message': message, 'sentAt': '2026-11-27T12:00:00Z'});
    json['status'] = 'open';
    return SupportTicket.fromJson(json);
  }
}

Widget _app(Widget home) => MaterialApp(theme: AppTheme.lightTheme, home: home);

void main() {
  testWidgets('A05-C01/C02/C03: empty state, validation, then a ticket is created with the chosen category',
      (tester) async {
    final service = FakeSupportService();
    await tester.pumpWidget(_app(SupportTicketsScreen(service: service)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('support_empty')), findsOneWidget);
    expect(find.textContaining('In an emergency call 1990'), findsOneWidget);

    await tester.tap(find.byKey(const Key('support_create_button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('support_submit')));
    await tester.pumpAndSettle();
    expect(find.text('Enter a subject of at least 3 characters.'), findsOneWidget);
    expect(service.created, isEmpty);

    await tester.tap(find.byKey(const Key('support_category')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Payment help').last);
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('support_subject')), 'Card charged twice');
    await tester.enterText(find.byKey(const Key('support_message')), 'My card shows two charges for one visit.');
    await tester.tap(find.byKey(const Key('support_submit')));
    await tester.pumpAndSettle();
    expect(service.created.single,
        {'category': 'payment_issue', 'subject': 'Card charged twice', 'message': 'My card shows two charges for one visit.'});
    // The new ticket opens with the patient's message.
    expect(find.text('TCK-A05NEW01'), findsOneWidget);
    expect(find.text('My card shows two charges for one visit.'), findsOneWidget);
  });

  testWidgets('A05-C04/C05/C10/C11: list shows support replied; detail shows the reply; patient answers',
      (tester) async {
    final service = FakeSupportService();
    service.tickets['TCK-A05AAA01'] = _ticketJson('TCK-A05AAA01', status: 'waiting_for_user', awaiting: 'requester',
        messages: [
          {'messageId': 'm1', 'senderRole': 'PATIENT', 'senderName': 'A05 Patient', 'message': 'It shows pending.',
           'sentAt': '2026-11-27T09:00:00Z'},
          {'messageId': 'm2', 'senderRole': 'ADMIN', 'senderName': 'Support', 'message': '<b>Please</b> refresh.',
           'sentAt': '2026-11-27T09:30:00Z'},
        ]);
    await tester.pumpWidget(_app(SupportTicketsScreen(service: service)));
    await tester.pumpAndSettle();
    expect(find.text('Support replied'), findsOneWidget);
    await tester.tap(find.byKey(const Key('support_ticket_TCK-A05AAA01')));
    await tester.pumpAndSettle();
    expect(find.text('MediConnect Support'), findsOneWidget);
    expect(find.text('<b>Please</b> refresh.'), findsOneWidget); // shown as text, not markup
    await tester.enterText(find.byKey(const Key('support_reply_field')), 'Still pending after refresh.');
    await tester.tap(find.byKey(const Key('support_reply_send')));
    await tester.pumpAndSettle();
    expect(service.replies, ['TCK-A05AAA01:Still pending after refresh.']);
    expect(find.text('Still pending after refresh.'), findsOneWidget);
    expect(find.textContaining('Open'), findsWidgets);
  });

  testWidgets('A05-C14: a closed ticket shows no composer; a safety notice is shown when present', (tester) async {
    final service = FakeSupportService();
    service.tickets['TCK-A05CLS01'] = _ticketJson('TCK-A05CLS01', status: 'closed', awaiting: null,
        safety: 'Your message may describe a medical emergency. … call 1990 …');
    await tester.pumpWidget(_app(SupportTicketDetailScreen(ticketId: 'TCK-A05CLS01', service: service)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('support_closed_notice')), findsOneWidget);
    expect(find.byKey(const Key('support_reply_field')), findsNothing);
    expect(find.byKey(const Key('support_safety_notice')), findsOneWidget);
  });

  testWidgets('A05: a failed load shows a truthful error with retry', (tester) async {
    final service = FakeSupportService()..failList = true;
    await tester.pumpWidget(_app(SupportTicketsScreen(service: service)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('support_error')), findsOneWidget);
    service.failList = false;
    await tester.tap(find.byKey(const Key('support_retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('support_empty')), findsOneWidget);
  });

  testWidgets('A05-C01: the patient profile has a Help & Support entry', (tester) async {
    await tester.pumpWidget(MultiProvider(
      providers: [ChangeNotifierProvider<AuthProvider>.value(value: AuthProvider())],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: PatientProfileScreen(service: FakeProfileService()),
        routes: {'/patient/support': (_) => const Scaffold(body: Text('support route'))},
      ),
    ));
    await tester.pumpAndSettle();
    final tile = find.byKey(const Key('profile_help_support'));
    await tester.scrollUntilVisible(tile, 300, scrollable: find.byType(Scrollable).first);
    await tester.tap(tile);
    await tester.pumpAndSettle();
    expect(find.text('support route'), findsOneWidget);
  });

  testWidgets('A05-C20: a support reply notification opens its ticket', (tester) async {
    final notifications = MockNotificationService()
      ..mockItems = [
        NotificationModel.fromJson({
          'id': 'n-a05', 'recipientUserId': 'u1', 'type': 'SYSTEM', 'title': 'Support ticket update',
          'body': 'MediConnect Support replied to your ticket TCK-A05AAA01.', 'relatedTicketId': 'TCK-A05AAA01',
          'isRead': false, 'createdAt': DateTime.now().toIso8601String(),
        }),
      ]
      ..mockUnreadCount = 1;
    String? opened;
    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<NotificationProvider>.value(
            value: NotificationProvider(notificationService: notifications)),
        ChangeNotifierProvider<AuthProvider>.value(value: AuthProvider()),
      ],
      child: MaterialApp(
        home: const NotificationsScreen(),
        onGenerateRoute: (settings) {
          opened = '${settings.name}:${settings.arguments}';
          return MaterialPageRoute(builder: (_) => const Scaffold(body: Text('ticket route')));
        },
      ),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Support ticket update'));
    await tester.pumpAndSettle();
    expect(opened, '/patient/support/ticket:TCK-A05AAA01');
  });
}
