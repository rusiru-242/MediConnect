import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/screens/doctor/doctor_workflow_screen.dart';

class ClinicClient extends ApiClient {
  Map<String, dynamic>? approved;

  @override
  Future<dynamic> get(
    String endpoint, {
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    expect(includeAuth, isTrue);
    return {'appointments': []};
  }

  @override
  Future<dynamic> post(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    bool includeAuth = true,
  }) async {
    expect(includeAuth, isTrue);
    if (endpoint.endsWith('/assistant')) {
      return {
        'message': 'Draft ready',
        'reminder': {
          'title': 'Appointment reminder',
          'date': '2026-11-25',
          'body': 'Open MediConnect to review your appointment.',
          'count': 1,
          'token': 'fixture-token',
        },
      };
    }
    expect(endpoint, '/doctor/workflow/reminders/2026-11-25');
    approved = body;
    return {
      'statuses': {'pending': 1},
    };
  }
}

void main() {
  testWidgets('Shows the reminder draft and only queues after confirmation', (
    tester,
  ) async {
    final client = ClinicClient();
    await tester.pumpWidget(
      MaterialApp(home: DoctorWorkflowScreen(apiClient: client)),
    );
    await tester.pumpAndSettle();
    expect(find.text('No appointments in this period.'), findsOneWidget);
    await tester.tap(find.text('Tomorrow’s reminders'));
    await tester.pumpAndSettle();
    expect(find.text('Appointment reminder'), findsOneWidget);
    expect(client.approved, isNull);
    await tester.tap(find.text('Approve reminder'));
    await tester.pumpAndSettle();
    expect(client.approved, isNull);
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(client.approved, {'confirm': true, 'token': 'fixture-token'});
    // Expectation changed in Phase 05 (P3-B7): fields are shown with readable labels, not raw API keys.
    expect(find.text('Pending: 1'), findsOneWidget);
  });
}
