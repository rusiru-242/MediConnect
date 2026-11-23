import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/screens/patient/care_agenda_screen.dart';
import 'package:mediconnect/services/fcm_service.dart';

class CareTestClient extends ApiClient {
  final Completer<dynamic> loading = Completer<dynamic>();
  Map<String, dynamic>? recorded;
  final event = <String, dynamic>{
    'id': 'fixture-event',
    'title': 'Fixture medication',
    'kind': 'medication',
    'source': 'clinician',
    'instructions': 'Clinician-entered instruction',
    'scheduledAt': DateTime.now().subtract(const Duration(minutes: 5)).toIso8601String(),
  };

  @override
  Future<dynamic> get(String endpoint, {Map<String, String>? headers, bool includeAuth = true}) {
    if (endpoint.contains('/agenda')) return loading.future;
    expect(includeAuth, isTrue);
    return Future.value(event);
  }

  @override
  Future<dynamic> post(String endpoint, {Map<String, dynamic>? body, Map<String, String>? headers, bool includeAuth = true}) async {
    expect(endpoint, '/care-automation/events/fixture-event/actions');
    expect(includeAuth, isTrue);
    recorded = body;
    return {...event, 'action': body!['action']};
  }
}

void main() {
  testWidgets('Loads Today and records a patient-reported medication action', (tester) async {
    final client = CareTestClient();
    await tester.pumpWidget(MaterialApp(home: CareAgendaScreen(apiClient: client)));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    client.loading.complete({'items': [client.event]});
    await tester.pumpAndSettle();
    expect(find.text('Today'), findsOneWidget);
    await tester.tap(find.text('Fixture medication'));
    await tester.pumpAndSettle();
    expect(find.text('Clinician-entered instruction'), findsOneWidget);
    await tester.tap(find.text('Mark as Taken'));
    await tester.pumpAndSettle();
    expect(client.recorded?['action'], 'taken');
    expect(client.recorded?['requestId'], isNotEmpty);
    expect(find.text('Status: taken (patient-reported)'), findsOneWidget);
  });

  testWidgets('Queues a care notification tap until the patient home is ready', (tester) async {
    final service = FcmService();
    await service.removeTokenOnLogout();
    final eventId = List.filled(64, 'a').join();
    await tester.pumpWidget(MaterialApp(
      navigatorKey: service.navigatorKey,
      home: const Scaffold(body: Text('Patient home')),
      routes: {
        '/patient/care-agenda': (context) => Scaffold(
          body: Text(ModalRoute.of(context)!.settings.arguments as String),
        ),
      },
    ));
    service.routeFromMessage(RemoteMessage(data: {'type': 'CARE_REMINDER', 'careEventId': eventId}));
    await tester.pumpAndSettle();
    expect(find.text('Patient home'), findsOneWidget);
    service.openPendingCareReminder();
    await tester.pumpAndSettle();
    expect(find.text(eventId), findsOneWidget);
    await service.removeTokenOnLogout();
  });
}
