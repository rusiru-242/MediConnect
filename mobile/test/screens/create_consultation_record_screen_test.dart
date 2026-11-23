import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medical_record.dart';
import 'package:mediconnect/models/prescription.dart';
import 'package:mediconnect/screens/doctor/create_consultation_record_screen.dart';
import 'package:mediconnect/services/medical_record_service.dart';

class FakeDoctorRecordService extends MedicalRecordService {
  bool createRecordCalled = false;
  bool createPrescriptionCalled = false;

  @override
  Future<MedicalRecord> createMedicalRecord({
    required String appointmentId,
    required String clinicalNotes,
    required String assessment,
    required String treatmentPlan,
    String? followUpInstructions,
  }) async {
    createRecordCalled = true;
    return MedicalRecord(
      id: 'rec-test-1',
      recordId: 'REC-TEST-1',
      patientUserId: 'pat-1',
      doctorUserId: 'doc-1',
      appointmentId: appointmentId,
      consultationDate: '2026-10-18',
      clinicalNotes: clinicalNotes,
      assessment: assessment,
      treatmentPlan: treatmentPlan,
      followUpInstructions: followUpInstructions,
      status: 'ACTIVE',
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
  }

  @override
  Future<Prescription> createPrescription({
    required String medicalRecordId,
    required String appointmentId,
    required List<MedicationItem> medicationItems,
    String? instructions,
  }) async {
    createPrescriptionCalled = true;
    return Prescription(
      id: 'presc-test-1',
      prescriptionId: 'RX-TEST-1',
      medicalRecordId: medicalRecordId,
      appointmentId: appointmentId,
      patientUserId: 'pat-1',
      doctorUserId: 'doc-1',
      issuedAt: DateTime.now(),
      status: 'ISSUED',
      medicationItems: medicationItems,
    );
  }
}

void main() {
  group('CreateConsultationRecordScreen Widget Tests', () {
    testWidgets('validates required fields and confirms submission with prescription', (tester) async {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      final fakeService = FakeDoctorRecordService();
      final sampleAppt = {
        'id': 'appt-test-1',
        'patientName': 'Kamal Gunaratne',
        'appointmentDate': '2026-10-18',
        'startTime': '10:00',
        'endTime': '10:30',
        'status': 'COMPLETED',
      };

      await tester.pumpWidget(
        MaterialApp(
          home: CreateConsultationRecordScreen(
            appointment: sampleAppt,
            service: fakeService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Document Consultation'), findsOneWidget);
      expect(find.text('Kamal Gunaratne'), findsOneWidget);
      expect(find.text('Issue Structured Digital Prescription (Rx)'), findsOneWidget);

      // Attempt submit without filling fields
      final submitButton = find.byKey(const Key('create_consultation_submit_button'));
      await tester.tap(submitButton);
      await tester.pumpAndSettle();

      expect(find.text('Clinical notes are required.'), findsOneWidget);
      expect(find.text('Assessment is required.'), findsOneWidget);
      expect(find.text('Treatment plan is required.'), findsOneWidget);
      expect(fakeService.createRecordCalled, isFalse);

      // Fill in fields
      await tester.enterText(
        find.byKey(const Key('consultation_clinical_notes_field')),
        'Patient presents with typical migraine symptoms without aura.',
      );
      await tester.enterText(
        find.byKey(const Key('consultation_assessment_field')),
        'Migraine headache without aura',
      );
      await tester.enterText(
        find.byKey(const Key('consultation_treatment_plan_field')),
        'Avoid trigger foods, maintain sleep hygiene.',
      );

      // Fill in medication item
      await tester.enterText(find.byKey(const Key('med_name_0')), 'Sumatriptan');
      await tester.enterText(find.byKey(const Key('med_strength_0')), '50mg');

      // Tap submit button
      await tester.tap(submitButton);
      await tester.pumpAndSettle();

      // Verify confirmation dialog appears
      expect(find.text('Confirm Record & Prescription'), findsOneWidget);

      // Confirm dialog
      await tester.tap(find.text('Confirm & Issue'));
      await tester.pumpAndSettle();

      expect(fakeService.createRecordCalled, isTrue);
      expect(fakeService.createPrescriptionCalled, isTrue);
    });
  });
}
