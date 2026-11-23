import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/booking_session.dart';

void main() {
  group('BookingSession Model Tests', () {
    test('1. Deserializes valid booking session JSON properly', () {
      final json = {
        'id': 'sess_123',
        'patientUserId': 'pat_456',
        'state': 'AWAITING_DOCTOR_SELECTION',
        'preferences': {
          'specialty': 'Cardiologist',
          'city': 'Colombo',
          'date': '2026-10-15',
          'timeRange': 'morning',
          'maxFee': 3500.0,
          'language': 'en',
          'patientNote': 'Routine check',
        },
        'selectedDoctor': null,
        'selectedSlot': null,
        'bookingSummary': null,
        'candidateDoctors': [
          {
            'doctorId': 'DOC-001',
            'doctorProfileId': 'prof_1',
            'doctorUserId': 'usr_doc_1',
            'fullName': 'Dr. Nihal Perera',
            'specialty': 'Cardiologist',
            'hospitalOrClinic': 'Asiri Hospital',
            'experienceYears': 12,
            'consultationFee': 2500.0,
            'rating': 4.9,
          }
        ],
        'candidateSlots': [],
        'messages': [
          {
            'id': 'm1',
            'sender': 'user',
            'content': 'I need a cardiologist in Colombo',
            'timestamp': '2026-10-14T08:00:00Z',
          },
          {
            'id': 'm2',
            'sender': 'assistant',
            'content': 'I found 1 approved Cardiologist in Colombo.',
            'timestamp': '2026-10-14T08:00:01Z',
          }
        ],
        'isUrgent': false,
        'urgencyReason': null,
        'createdAt': '2026-10-14T08:00:00Z',
        'updatedAt': '2026-10-14T08:00:01Z',
        'expiresAt': '2026-10-14T08:30:00Z',
      };

      final session = BookingSession.fromJson(json);

      expect(session.id, 'sess_123');
      expect(session.patientUserId, 'pat_456');
      expect(session.state, 'AWAITING_DOCTOR_SELECTION');
      expect(session.isAwaitingDoctor, isTrue);
      expect(session.preferences.specialty, 'Cardiologist');
      expect(session.preferences.city, 'Colombo');
      expect(session.preferences.maxFee, 3500.0);
      expect(session.candidateDoctors.length, 1);
      expect(session.candidateDoctors.first.fullName, 'Dr. Nihal Perera');
      expect(session.messages.length, 2);
      expect(session.messages.first.isUser, isTrue);
      expect(session.messages.last.isAssistant, isTrue);
    });

    test('2. Converts DoctorCardSummary to Doctor model safely', () {
      const summary = DoctorCardSummary(
        doctorId: 'DOC-002',
        doctorProfileId: 'prof_2',
        doctorUserId: 'usr_2',
        fullName: 'Dr. Sunethra Silva',
        specialty: 'Dermatologist',
        hospitalOrClinic: 'Nawaloka Negombo',
        experienceYears: 8,
        consultationFee: 3000.0,
        rating: 4.8,
      );

      final doctor = summary.toDoctor();

      expect(doctor.doctorId, 'DOC-002');
      expect(doctor.fullName, 'Dr. Sunethra Silva');
      expect(doctor.specialty, 'Dermatologist');
      expect(doctor.hospitalOrClinic, 'Nawaloka Negombo');
      expect(doctor.experienceYears, 8);
      expect(doctor.consultationFee, 3000.0);
    });

    test('3. Converts SlotCardSummary to TimeSlot model safely', () {
      const summary = SlotCardSummary(
        availabilityId: 'avail_999',
        date: '2026-10-16',
        startTime: '09:00',
        endTime: '09:30',
      );

      final slot = summary.toTimeSlot();

      expect(slot.availabilityId, 'avail_999');
      expect(slot.startTime, '09:00');
      expect(slot.endTime, '09:30');
    });

    test('4. BookingSummary deserializes and computes total correctly', () {
      final json = {
        'doctorName': 'Dr. Nihal Perera',
        'specialty': 'Cardiologist',
        'hospitalOrClinic': 'Asiri Central',
        'appointmentDate': '2026-10-15',
        'startTime': '10:00',
        'endTime': '10:30',
        'consultationFee': 2500.0,
        'serviceFee': 0.0,
        'totalAmount': 2500.0,
        'currency': 'lkr',
      };

      final summary = BookingSummary.fromJson(json);

      expect(summary.doctorName, 'Dr. Nihal Perera');
      expect(summary.consultationFee, 2500.0);
      expect(summary.serviceFee, 0.0);
      expect(summary.totalAmount, 2500.0);
      expect(summary.currency, 'lkr');
    });

    test('5. MedicineCardSummary deserializes string consultPharmacistWhen and list fields safely', () {
      final json = {
        'medicineName': 'Paracetamol',
        'activeIngredient': 'Acetaminophen 500mg',
        'commonUses': ['Relief of mild pain', 'Fever reduction'],
        'precautions': ['Do not exceed 4000mg/day'],
        'sideEffects': ['Rare nausea'],
        'warnings': ['Severe liver damage risk if overdosed'],
        'consultPharmacistWhen': 'Pain persists for more than 5 days, or fever over 3 days.',
        'isPrescriptionRequired': false,
      };

      final medCard = MedicineCardSummary.fromJson(json);
      expect(medCard.medicineName, 'Paracetamol');
      expect(medCard.activeIngredient, 'Acetaminophen 500mg');
      expect(medCard.commonUses.length, 2);
      expect(medCard.consultPharmacistWhen, [
        'Pain persists for more than 5 days, or fever over 3 days.'
      ]);
      expect(medCard.isPrescriptionRequired, isFalse);
    });

    test('6. WellnessCardSummary and ImageAnalysisSummary deserialize resiliently', () {
      final wellnessJson = {
        'category': 'FOOD',
        'title': 'Balanced Nutrition',
        'summary': 'Nutritious Sri Lankan diet advice',
        'tips': 'Drink plenty of water and eat greens',
        'sriLankanOptions': ['Gotukola sambol', 'Red rice'],
        'safetyNote': 'Consult nutritionist if diabetic',
      };

      final wellness = WellnessCardSummary.fromJson(wellnessJson);
      expect(wellness.category, 'FOOD');
      expect(wellness.tips, ['Drink plenty of water and eat greens']);
      expect(wellness.sriLankanOptions.length, 2);

      final imageJson = {
        'detectedText': 'AMOXICILLIN 500MG',
        'identifiedMedicine': 'Amoxicillin',
        'confidenceLevel': 'HIGH',
        'uncertaintyExplanation': 'Clear package view',
        'safetyAdvice': 'Prescription antibiotic',
        'requiresClearerPhoto': false,
      };

      final analysis = ImageAnalysisSummary.fromJson(imageJson);
      expect(analysis.detectedText, 'AMOXICILLIN 500MG');
      expect(analysis.identifiedMedicine, 'Amoxicillin');
      expect(analysis.confidenceLevel, 'HIGH');
    });
  });
}
