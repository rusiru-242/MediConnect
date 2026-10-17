import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medical_record.dart';
import 'package:mediconnect/models/prescription.dart';
import 'package:mediconnect/screens/patient/medical_records_screen.dart';
import 'package:mediconnect/services/medical_record_service.dart';

class FakeMedicalRecordService extends MedicalRecordService {
  final List<MedicalRecord> fakeRecords;
  final List<Prescription> fakePrescriptions;
  bool downloadPdfCalled = false;

  FakeMedicalRecordService({
    this.fakeRecords = const [],
    this.fakePrescriptions = const [],
  });

  @override
  Future<List<MedicalRecord>> getPatientMedicalRecords({int page = 1, int pageSize = 20}) async {
    return fakeRecords;
  }

  @override
  Future<List<Prescription>> getPatientPrescriptions({int page = 1, int pageSize = 20}) async {
    return fakePrescriptions;
  }

  @override
  Future<List<int>> downloadPrescriptionPdf(String prescriptionId) async {
    downloadPdfCalled = true;
    return [37, 80, 68, 70, 45, 49, 46, 52]; // %PDF-1.4
  }
}

void main() {
  group('MedicalRecordsScreen Widget Tests', () {
    testWidgets('renders empty state when no consultation records or prescriptions exist', (tester) async {
      final fakeService = FakeMedicalRecordService(fakeRecords: [], fakePrescriptions: []);

      await tester.pumpWidget(
        MaterialApp(
          home: MedicalRecordsScreen(service: fakeService),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Medical Records & Rx'), findsOneWidget);
      expect(find.text('Consultations'), findsOneWidget);
      expect(find.text('Prescriptions'), findsOneWidget);
      expect(find.text('No Consultation Records Yet'), findsOneWidget);

      // Switch to Prescriptions tab
      await tester.tap(find.text('Prescriptions'));
      await tester.pumpAndSettle();

      expect(find.text('No Prescriptions Issued'), findsOneWidget);
    });

    testWidgets('renders list of consultation records and prescription items', (tester) async {
      final sampleRecord = MedicalRecord(
        id: 'rec-1',
        recordId: 'REC-20261018-001',
        patientUserId: 'pat-1',
        doctorUserId: 'doc-1',
        doctorName: 'Dr. Kasun Fernando',
        doctorSpecialty: 'General Physician',
        appointmentId: 'appt-1',
        consultationDate: '2026-10-18',
        clinicalNotes: 'Mild sore throat and low-grade pyrexia.',
        assessment: 'Acute Viral Pharyngitis',
        treatmentPlan: 'Warm saline gargles, adequate oral hydration.',
        status: 'ACTIVE',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      final samplePresc = Prescription(
        id: 'presc-1',
        prescriptionId: 'RX-20261018-999',
        medicalRecordId: 'rec-1',
        appointmentId: 'appt-1',
        patientUserId: 'pat-1',
        doctorUserId: 'doc-1',
        doctorName: 'Dr. Kasun Fernando',
        doctorSpecialty: 'General Physician',
        slmcRegistrationNumber: 'SLMC-98765',
        issuedAt: DateTime.now(),
        status: 'ISSUED',
        medicationItems: [
          const MedicationItem(
            medicationName: 'Paracetamol',
            strength: '500mg',
            dose: '1 tablet',
            frequency: 'TDS (Every 8 hours)',
            duration: '3 days',
            quantity: '10 tablets',
          )
        ],
      );

      final fakeService = FakeMedicalRecordService(
        fakeRecords: [sampleRecord],
        fakePrescriptions: [samplePresc],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: MedicalRecordsScreen(service: fakeService),
        ),
      );
      await tester.pumpAndSettle();

      // Check record card
      expect(find.text('Dr. Kasun Fernando'), findsOneWidget);
      expect(find.text('Acute Viral Pharyngitis'), findsOneWidget);
      expect(find.text('2026-10-18'), findsOneWidget);

      // Switch to prescriptions tab
      await tester.tap(find.text('Prescriptions'));
      await tester.pumpAndSettle();

      expect(find.text('RX-20261018-999'), findsOneWidget);
      expect(find.text('1 Medications Prescribed'), findsOneWidget);

      // Tap PDF download icon button
      final pdfButton = find.byKey(const Key('prescription_item_pdf_button_presc-1'));
      expect(pdfButton, findsOneWidget);
      await tester.tap(pdfButton);
      await tester.pumpAndSettle();

      expect(fakeService.downloadPdfCalled, isTrue);
      expect(find.text('PDF Download Ready'), findsOneWidget);
    });
  });
}
