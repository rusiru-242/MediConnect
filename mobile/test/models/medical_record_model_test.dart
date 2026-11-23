import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/medical_record.dart';
import 'package:mediconnect/models/prescription.dart';

void main() {
  group('Phase 21 Medical Records & Prescription Models Tests', () {
    test('MedicationItem deserializes and serializes accurately', () {
      final json = {
        'medicationName': 'Atorvastatin',
        'strength': '20mg',
        'dose': '1 tablet',
        'route': 'Oral',
        'frequency': 'Once daily at bedtime',
        'duration': '30 days',
        'quantity': '30 tablets',
        'additionalInstructions': 'Avoid grapefruit juice.',
      };

      final item = MedicationItem.fromJson(json);
      expect(item.medicationName, 'Atorvastatin');
      expect(item.strength, '20mg');
      expect(item.dose, '1 tablet');
      expect(item.route, 'Oral');
      expect(item.frequency, 'Once daily at bedtime');
      expect(item.duration, '30 days');
      expect(item.quantity, '30 tablets');
      expect(item.additionalInstructions, 'Avoid grapefruit juice.');

      final roundtrip = item.toJson();
      expect(roundtrip['medicationName'], 'Atorvastatin');
      expect(roundtrip['strength'], '20mg');
      expect(roundtrip['additionalInstructions'], 'Avoid grapefruit juice.');
    });

    test('Prescription deserializes correctly with medication items and amendments', () {
      final json = {
        'id': '670000000000000000000001',
        'prescriptionId': 'RX-20261018-ABC123',
        'medicalRecordId': 'REC-20261018-REC999',
        'appointmentId': 'APPT-100',
        'patientUserId': 'PAT-USER-1',
        'patientName': 'Sunil Perera',
        'doctorUserId': 'DOC-USER-1',
        'doctorName': 'Dr. Kithsiri Silva',
        'doctorSpecialty': 'Cardiologist',
        'slmcRegistrationNumber': 'SLMC-44556',
        'hospitalOrClinic': 'National Hospital',
        'issuedAt': '2026-10-18T10:00:00.000Z',
        'status': 'AMENDED',
        'medicationItems': [
          {
            'medicationName': 'Metformin',
            'strength': '500mg',
            'dose': '1 tablet',
            'route': 'Oral',
            'frequency': 'Twice daily',
            'duration': '1 month',
            'quantity': '60 tablets',
            'additionalInstructions': 'Take with meals.',
          }
        ],
        'instructions': 'Monitor fasting blood sugar weekly.',
        'amendmentHistory': [
          {
            'amendedAt': '2026-10-18T12:00:00.000Z',
            'reason': 'Adjusted dose for better glycemic control.',
          }
        ],
      };

      final presc = Prescription.fromJson(json);
      expect(presc.prescriptionId, 'RX-20261018-ABC123');
      expect(presc.patientName, 'Sunil Perera');
      expect(presc.doctorName, 'Dr. Kithsiri Silva');
      expect(presc.status, 'AMENDED');
      expect(presc.medicationItems.length, 1);
      expect(presc.medicationItems.first.medicationName, 'Metformin');
      expect(presc.amendmentHistory.length, 1);
      expect(presc.amendmentHistory.first['reason'], 'Adjusted dose for better glycemic control.');

      final map = presc.toJson();
      expect(map['prescriptionId'], 'RX-20261018-ABC123');
      expect((map['medicationItems'] as List).length, 1);
    });

    test('MedicalRecord deserializes correctly with attached prescription', () {
      final json = {
        'id': '670000000000000000000002',
        'recordId': 'REC-20261018-XYZ789',
        'patientUserId': 'PAT-USER-1',
        'patientName': 'Sunil Perera',
        'doctorUserId': 'DOC-USER-1',
        'doctorName': 'Dr. Kithsiri Silva',
        'doctorSpecialty': 'Cardiologist',
        'slmcRegistrationNumber': 'SLMC-44556',
        'hospitalOrClinic': 'National Hospital',
        'appointmentId': 'APPT-100',
        'consultationDate': '2026-10-18',
        'clinicalNotes': 'Patient presents with stable angina symptoms on severe exertion.',
        'assessment': 'Coronary artery disease, stable angina. Well-controlled.',
        'treatmentPlan': 'Continue medical therapy. Moderate aerobic exercise.',
        'followUpInstructions': 'Review in 3 months with fasting lipid profile.',
        'status': 'ACTIVE',
        'prescription': {
          'id': '670000000000000000000001',
          'prescriptionId': 'RX-20261018-ABC123',
          'medicalRecordId': '670000000000000000000002',
          'appointmentId': 'APPT-100',
          'patientUserId': 'PAT-USER-1',
          'doctorUserId': 'DOC-USER-1',
          'issuedAt': '2026-10-18T10:00:00.000Z',
          'status': 'ISSUED',
          'medicationItems': [
            {
              'medicationName': 'Aspirin',
              'strength': '75mg',
              'dose': '1 tablet',
              'route': 'Oral',
              'frequency': 'Once daily',
              'duration': '30 days',
              'quantity': '30 tablets',
            }
          ],
        },
        'amendmentHistory': [],
        'createdAt': '2026-10-18T10:00:00.000Z',
        'updatedAt': '2026-10-18T10:00:00.000Z',
      };

      final rec = MedicalRecord.fromJson(json);
      expect(rec.recordId, 'REC-20261018-XYZ789');
      expect(rec.doctorName, 'Dr. Kithsiri Silva');
      expect(rec.consultationDate, '2026-10-18');
      expect(rec.clinicalNotes, contains('stable angina'));
      expect(rec.prescription, isNotNull);
      expect(rec.prescription!.prescriptionId, 'RX-20261018-ABC123');
      expect(rec.prescription!.medicationItems.first.medicationName, 'Aspirin');
    });
  });
}
