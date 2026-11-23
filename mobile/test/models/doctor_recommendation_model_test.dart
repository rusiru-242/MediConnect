import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/doctor_recommendation.dart';

void main() {
  group('DoctorRecommendation Models Test', () {
    test('InterpretedPreferences parses from and serializes to JSON', () {
      final json = {
        'specialty': 'Cardiologist',
        'city': 'Colombo',
        'date': '2026-10-15',
        'timeRange': 'evening',
        'maxFee': 3000.0,
        'consultationType': 'in-person',
        'languageDetected': 'en',
      };

      final prefs = InterpretedPreferences.fromJson(json);
      expect(prefs.specialty, 'Cardiologist');
      expect(prefs.city, 'Colombo');
      expect(prefs.date, '2026-10-15');
      expect(prefs.timeRange, 'evening');
      expect(prefs.maxFee, 3000.0);
      expect(prefs.consultationType, 'in-person');
      expect(prefs.languageDetected, 'en');

      final serialized = prefs.toJson();
      expect(serialized['specialty'], 'Cardiologist');
      expect(serialized['maxFee'], 3000.0);
    });

    test('RecommendedSlot parses and converts to TimeSlot', () {
      final json = {
        'date': '2026-10-15',
        'startTime': '18:00',
        'endTime': '18:30',
        'availabilityId': 'avail_123',
      };

      final slot = RecommendedSlot.fromJson(json);
      expect(slot.date, '2026-10-15');
      expect(slot.startTime, '18:00');
      expect(slot.endTime, '18:30');
      expect(slot.availabilityId, 'avail_123');

      final timeSlot = slot.toTimeSlot();
      expect(timeSlot.startTime, '18:00');
      expect(timeSlot.endTime, '18:30');
      expect(timeSlot.availabilityId, 'avail_123');
    });

    test('DoctorRecommendation parses and converts to Doctor model', () {
      final json = {
        'doctorId': 'DOC-101',
        'fullName': 'Dr. Kamal Perera',
        'specialty': 'Cardiologist',
        'hospitalOrClinic': 'Asiri Central Hospital, Colombo',
        'experienceYears': 12,
        'consultationFee': 2500.0,
        'bio': 'Cardiology specialist',
        'profileImage': null,
        'score': 92.5,
        'matchReasons': ['Matches requested specialty: Cardiologist', 'Located in Colombo'],
        'availableSlots': [
          {
            'date': '2026-10-15',
            'startTime': '18:00',
            'endTime': '18:30',
            'availabilityId': 'avail_101',
          }
        ],
      };

      final rec = DoctorRecommendation.fromJson(json);
      expect(rec.doctorId, 'DOC-101');
      expect(rec.fullName, 'Dr. Kamal Perera');
      expect(rec.score, 92.5);
      expect(rec.matchReasons.length, 2);
      expect(rec.availableSlots.length, 1);

      final doctor = rec.toDoctor();
      expect(doctor.doctorId, 'DOC-101');
      expect(doctor.fullName, 'Dr. Kamal Perera');
      expect(doctor.specialty, 'Cardiologist');
      expect(doctor.consultationFee, 2500.0);
      expect(doctor.verificationStatus, 'APPROVED');
    });

    test('DoctorRecommendationResponse parses complete response with urgency', () {
      final json = {
        'interpretedPreferences': {
          'specialty': 'Cardiologist',
          'city': 'Colombo',
          'languageDetected': 'en',
        },
        'recommendations': [
          {
            'doctorId': 'DOC-101',
            'fullName': 'Dr. Kamal Perera',
            'specialty': 'Cardiologist',
            'hospitalOrClinic': 'Asiri Central Hospital',
            'experienceYears': 12,
            'consultationFee': 2500.0,
            'score': 95.0,
            'matchReasons': ['Matches specialty'],
            'availableSlots': [],
          }
        ],
        'totalMatches': 1,
        'isUrgent': true,
        'safetyGuidance': 'Emergency care recommended. Call 1990.',
        'disclaimer': 'Informational discovery tool only.',
        'clarificationQuestion': null,
        'aiProviderUsed': 'deterministic_fallback',
      };

      final response = DoctorRecommendationResponse.fromJson(json);
      expect(response.totalMatches, 1);
      expect(response.isUrgent, true);
      expect(response.safetyGuidance, 'Emergency care recommended. Call 1990.');
      expect(response.disclaimer, 'Informational discovery tool only.');
      expect(response.recommendations.first.doctorId, 'DOC-101');
      expect(response.aiProviderUsed, 'deterministic_fallback');
    });
  });
}
