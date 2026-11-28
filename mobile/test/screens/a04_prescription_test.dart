// A04 (Agent 17): doctor prescription entry and patient prescription view.
// A04-BUG-009 (no pre-filled dosing, quantity field), A04-BUG-010 (retry does not recreate the record),
// draft check shown before issuing, "not stated" for absent values, renewal names the exact medicine.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_client.dart';
import 'package:mediconnect/models/clinical_record.dart';
import 'package:mediconnect/models/medical_record.dart';
import 'package:mediconnect/models/prescription.dart';
import 'package:mediconnect/screens/doctor/create_consultation_record_screen.dart';
import 'package:mediconnect/screens/patient/prescription_detail_screen.dart';
import 'package:mediconnect/services/clinical_api_service.dart';
import 'package:mediconnect/services/medical_record_service.dart';

class FakeRecordService extends MedicalRecordService {
  int records = 0;
  int prescriptionAttempts = 0;
  bool failFirstPrescription = false;
  bool reviewFails = false;
  List<MedicationItem>? issued;
  List<MedicationItem>? reviewed;

  @override
  Future<MedicalRecord> createMedicalRecord({
    required String appointmentId,
    required String clinicalNotes,
    required String assessment,
    required String treatmentPlan,
    String? followUpInstructions,
  }) async {
    records++;
    return MedicalRecord(
      id: 'rec-a04', recordId: 'REC-A04', patientUserId: 'pat-a04', doctorUserId: 'doc-a04',
      appointmentId: appointmentId, consultationDate: '2026-11-27', clinicalNotes: clinicalNotes,
      assessment: assessment, treatmentPlan: treatmentPlan, followUpInstructions: followUpInstructions,
      status: 'ACTIVE', createdAt: DateTime(2026, 11, 27), updatedAt: DateTime(2026, 11, 27),
    );
  }

  @override
  Future<Map<String, dynamic>> reviewPrescriptionDraft({
    required String patientUserId,
    required List<MedicationItem> medicationItems,
  }) async {
    reviewed = medicationItems;
    if (reviewFails) throw Exception('offline');
    return {
      'allergyWarnings': ["POSSIBLE ALLERGY CONTRAINDICATION: Patient has documented allergy to 'synthocillin'."],
      'potentialDuplicates': <String>[],
      'repeatedMedicines': <String>[],
      'missingFieldsWarnings': <String>[],
      'items': [
        {'index': 0, 'medicationName': 'Synthocillin', 'missingFields': <String>[], 'notes': <String>[]}
      ],
      'interactionCheck': 'unavailable',
      'interactionCheckNotice': 'Drug-interaction checking is not available: no validated source.',
      'approved': false,
      'status': 'unapproved_draft',
    };
  }

  @override
  Future<Prescription> createPrescription({
    required String medicalRecordId,
    required String appointmentId,
    required List<MedicationItem> medicationItems,
    String? instructions,
  }) async {
    prescriptionAttempts++;
    if (failFirstPrescription && prescriptionAttempts == 1) {
      throw Exception('quantity is required');
    }
    issued = medicationItems;
    return Prescription(
      id: 'rx-a04', prescriptionId: 'RX-20261127-A04A04', medicalRecordId: medicalRecordId,
      appointmentId: appointmentId, patientUserId: 'pat-a04', doctorUserId: 'doc-a04',
      issuedAt: DateTime(2026, 11, 27), status: 'ISSUED', medicationItems: medicationItems,
    );
  }
}

class FakeClinicalApi extends ClinicalApiService {
  String? prescriptionId;
  String? medicationName;

  @override
  Future<PrescriptionRenewal> requestPrescriptionRenewal({
    required String originalPrescriptionId,
    required String medicationName,
    String? patientReason,
  }) async {
    prescriptionId = originalPrescriptionId;
    this.medicationName = medicationName;
    return PrescriptionRenewal.fromJson({
      'id': 'r1', 'renewalId': 'REN-1', 'patientUserId': 'pat-a04', 'originalPrescriptionId': originalPrescriptionId,
      'medicationName': medicationName, 'doctorUserId': 'doc-a04', 'status': 'requested',
      'requestedAt': '2026-11-27T10:00:00Z', 'createdAt': '2026-11-27T10:00:00Z', 'updatedAt': '2026-11-27T10:00:00Z',
    });
  }
}

const _appointment = {
  'id': 'appt-a04', 'patientUserId': 'pat-a04', 'patientName': 'A04 Synthetic Patient',
  'appointmentDate': '2026-11-27', 'startTime': '10:00', 'endTime': '10:30', 'status': 'COMPLETED',
};

Future<void> _pumpDoctor(WidgetTester tester, FakeRecordService service) async {
  tester.view.physicalSize = const Size(900, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() => tester.view.resetPhysicalSize());
  await tester.pumpWidget(MaterialApp(home: CreateConsultationRecordScreen(appointment: _appointment, service: service)));
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(const Key('consultation_clinical_notes_field')), 'Synthetic notes');
  await tester.enterText(find.byKey(const Key('consultation_assessment_field')), 'Synthetic assessment');
  await tester.enterText(find.byKey(const Key('consultation_treatment_plan_field')), 'Synthetic plan');
}

Future<void> _fillItem(WidgetTester tester) async {
  for (final entry in {
    'med_name_0': 'Synthocillin', 'med_strength_0': '250 mg', 'med_dose_0': '2 capsules',
    'med_frequency_0': 'Three times daily', 'med_duration_0': '7 days', 'med_quantity_0': '42 capsules',
  }.entries) {
    await tester.enterText(find.byKey(Key(entry.key)), entry.value);
  }
}

String _fieldText(WidgetTester tester, String key) =>
    tester.widget<EditableText>(find.descendant(of: find.byKey(Key(key)), matching: find.byType(EditableText)))
        .controller
        .text;

void main() {
  _pagedTests();
  testWidgets('A04-BUG-009: dosing fields start empty and are required; nothing is pre-filled', (tester) async {
    final service = FakeRecordService();
    await _pumpDoctor(tester, service);
    for (final key in ['med_dose_0', 'med_frequency_0', 'med_duration_0', 'med_quantity_0', 'med_instructions_0']) {
      expect(_fieldText(tester, key), isEmpty, reason: key);
    }
    await tester.enterText(find.byKey(const Key('med_name_0')), 'Synthocillin');
    await tester.enterText(find.byKey(const Key('med_strength_0')), '250 mg');
    await tester.tap(find.byKey(const Key('create_consultation_submit_button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rx_missing_fields_message')), findsOneWidget);
    expect(find.textContaining('dose, frequency, duration, quantity'), findsOneWidget);
    expect(service.records, 0);
    expect(service.prescriptionAttempts, 0);
  });

  testWidgets('A04-P07/A03: the doctor reviews exactly what was entered, with the allergy warning, before issuing',
      (tester) async {
    final service = FakeRecordService();
    await _pumpDoctor(tester, service);
    await _fillItem(tester);
    await tester.tap(find.byKey(const Key('create_consultation_submit_button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rx_review_dialog')), findsOneWidget);
    expect(find.textContaining('Synthocillin 250 mg — 2 capsules, Oral, Three times daily, 7 days, quantity 42 capsules'),
        findsOneWidget);
    expect(find.byKey(const Key('rx_review_allergy_warning')), findsOneWidget);
    expect(find.byKey(const Key('rx_review_interaction_notice')), findsOneWidget);
    expect(service.prescriptionAttempts, 0); // nothing issued before Confirm
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(service.records, 0);
    await tester.tap(find.byKey(const Key('create_consultation_submit_button')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm & Issue'));
    await tester.pumpAndSettle();
    expect(service.issued!.single.toJson(), {
      'medicationName': 'Synthocillin', 'strength': '250 mg', 'dose': '2 capsules', 'route': 'Oral',
      'frequency': 'Three times daily', 'duration': '7 days', 'quantity': '42 capsules',
    });
    expect(service.reviewed!.single.quantity, '42 capsules');
  });

  testWidgets('A04-BUG-010: a failed prescription can be retried without creating the record twice', (tester) async {
    final service = FakeRecordService()..failFirstPrescription = true;
    await _pumpDoctor(tester, service);
    await _fillItem(tester);
    await tester.tap(find.byKey(const Key('create_consultation_submit_button')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm & Issue'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rx_issue_failed_message')), findsOneWidget);
    expect(service.records, 1);
    await tester.pump(const Duration(seconds: 9));
    await tester.tap(find.byKey(const Key('create_consultation_submit_button')));
    await tester.pumpAndSettle();
    expect(find.text('Confirm Prescription'), findsOneWidget);
    await tester.tap(find.text('Confirm & Issue'));
    await tester.pumpAndSettle();
    expect(service.records, 1); // reused, not "already exists"
    expect(service.prescriptionAttempts, 2);
    expect(service.issued, isNotNull);
  });

  testWidgets('A04: when the check cannot run the dialog says so instead of implying no findings', (tester) async {
    final service = FakeRecordService()..reviewFails = true;
    await _pumpDoctor(tester, service);
    await _fillItem(tester);
    await tester.tap(find.byKey(const Key('create_consultation_submit_button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rx_review_unavailable')), findsOneWidget);
    expect(find.byKey(const Key('rx_review_no_match')), findsNothing);
  });

  Prescription rx(String status, List<MedicationItem> items) => Prescription(
        id: 'rx-db', prescriptionId: 'RX-20261127-A04B05', medicalRecordId: '', appointmentId: 'appt-a04',
        patientUserId: 'pat-a04', doctorUserId: 'doc-a04', doctorName: 'Dr. A04 Synthetic',
        issuedAt: DateTime(2026, 11, 27), status: status, medicationItems: items,
      );

  testWidgets('A04-U02: patient view shows absent values as not stated and renews the exact medicine', (tester) async {
    tester.view.physicalSize = const Size(900, 2000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());
    final api = FakeClinicalApi();
    final legacy = MedicationItem.fromJson({'medicationName': 'Synthozole', 'strength': '20 mg'});
    expect(legacy.route, isEmpty); // was 'Oral'
    await tester.pumpWidget(MaterialApp(
      home: PrescriptionDetailScreen(
        prescriptionId: 'RX-20261127-A04B05', initialPrescription: rx('ISSUED', [legacy]), renewalService: api),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Dose: not stated'), findsOneWidget);
    expect(find.text('Frequency not stated'), findsOneWidget);
    expect(find.text('Duration not stated'), findsOneWidget);
    expect(find.text('Route not stated'), findsOneWidget);
    await tester.tap(find.byKey(const Key('rx_request_renewal_0')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rx_renewal_dialog')), findsOneWidget);
    await tester.tap(find.text('Send request'));
    await tester.pumpAndSettle();
    expect(api.prescriptionId, 'RX-20261127-A04B05');
    expect(api.medicationName, 'Synthozole');
    expect(find.byKey(const Key('rx_renewal_sent')), findsOneWidget);
  });

  testWidgets('A04: a cancelled prescription offers no renewal', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: PrescriptionDetailScreen(
        prescriptionId: 'RX-20261127-A04B05',
        initialPrescription: rx('CANCELLED', [MedicationItem.fromJson({'medicationName': 'Synthozole'})]),
        renewalService: FakeClinicalApi()),
    ));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('rx_request_renewal_0')), findsNothing);
  });

  testWidgets('R03-BUG-004: the prescription claims no SLMC register check or tamper evidence', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: PrescriptionDetailScreen(
          prescriptionId: 'RX-20261127-A04B05',
          initialPrescription: rx('ISSUED', [MedicationItem.fromJson({'medicationName': 'Synthozole'})]),
          renewalService: FakeClinicalApi()),
    ));
    await tester.pumpAndSettle();
    expect(find.textContaining('Verified against'), findsNothing);
    expect(find.textContaining('Tamper-Evident'), findsNothing);
    expect(find.textContaining('not checked automatically against the SLMC register'), findsOneWidget);
  });
}

class PagedDoctorClient extends ApiClient {
  final requested = <String>[];

  @override
  Future<dynamic> get(String endpoint, {Map<String, String>? headers, bool includeAuth = true}) async {
    requested.add(endpoint);
    final status = endpoint.contains('status=COMPLETED') ? 'COMPLETED' : 'CONFIRMED';
    final page = endpoint.contains('page=2') ? 2 : 1;
    final pages = status == 'COMPLETED' ? 2 : 1;
    return {
      'items': [
        {'id': 'appt-$status-$page', 'status': status, 'patientUserId': 'pat-a04'}
      ],
      'page': page, 'limit': 50, 'total': pages, 'totalPages': pages,
    };
  }
}



void _pagedTests() {
  test('A04-BUG-011: the documentation list reads the paginated appointments response', () async {
    final client = PagedDoctorClient();
    final rows = await MedicalRecordService(apiClient: client).getDoctorCompletedAppointments();
    expect(rows.map((r) => r['id']), ['appt-COMPLETED-1', 'appt-COMPLETED-2', 'appt-CONFIRMED-1']); // was empty
    expect(client.requested.length, 3);
  });
}
