// A04: the doctor's renewal queue shows pending requests and sends the doctor's explicit decision.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/clinical_record.dart';
import 'package:mediconnect/screens/doctor/doctor_prescription_renewal_queue_screen.dart';
import 'package:mediconnect/services/clinical_api_service.dart';

class FakeQueueApi extends ClinicalApiService {
  final decisions = <String>[];

  PrescriptionRenewal _renewal(String status) => PrescriptionRenewal.fromJson({
        'id': 'r1', 'renewalId': 'REN-20261127-A04AAA', 'patientUserId': 'pat-a04', 'patientName': 'A04 Patient',
        'originalPrescriptionId': 'RX-20261127-A04AAA', 'medicationName': 'Synthocillin-A04',
        'medicationDetails': {'strength': '250 mg', 'dose': '1 capsule', 'frequency': 'Twice daily', 'duration': '5 days'},
        'doctorUserId': 'doc-a04', 'status': status, 'patientReason': 'Course nearly finished.',
        'requestedAt': '2026-11-27T10:00:00Z',
      });

  @override
  Future<List<PrescriptionRenewal>> getPrescriptionRenewals({String? statusFilter}) async =>
      [_renewal(decisions.isEmpty ? 'requested' : 'approved')];

  @override
  Future<PrescriptionRenewal> reviewPrescriptionRenewal({
    required String renewalId,
    required String decision,
    required String reason,
    String? consultationDetails,
  }) async {
    decisions.add('$renewalId:$decision:$reason');
    return _renewal('approved');
  }
}

void main() {
  testWidgets('A04-R02: a pending renewal is listed on a phone-sized screen and approved only by the doctor',
      (tester) async {
    tester.view.physicalSize = const Size(1440, 3120);
    tester.view.devicePixelRatio = 3.5;
    addTearDown(() => tester.view.resetPhysicalSize());
    addTearDown(() => tester.view.resetDevicePixelRatio());
    final api = FakeQueueApi();
    await tester.pumpWidget(MaterialApp(home: DoctorPrescriptionRenewalQueueScreen(service: api)));
    await tester.pumpAndSettle();
    expect(find.text('Synthocillin-A04'), findsOneWidget);
    expect(find.text('Approve'), findsOneWidget);
    final error = tester.takeException();
    expect(error, isNull, reason: error.toString());
    await tester.tap(find.text('Approve'));
    await tester.pumpAndSettle();
    expect(find.text('Frequency: Twice daily'), findsOneWidget);
    expect(find.text('Quantity: not stated'), findsOneWidget); // absent in the source, not invented
    expect(api.decisions, isEmpty); // nothing sent before the doctor confirms
    await tester.tap(find.text('Approve & Issue Rx'));
    await tester.pumpAndSettle();
    expect(api.decisions.single, startsWith('REN-20261127-A04AAA:approve:'));
  });
}
