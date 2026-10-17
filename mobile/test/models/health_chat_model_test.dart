import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/health_chat.dart';


void main() {
  group('HealthChat Models Test', () {
    test('DoctorReferralCard deserializes correctly from JSON', () {
      final json = {
        'doctorId': 'DOC-123',
        'fullName': 'Dr. Sunimal Silva',
        'specialty': 'Cardiologist',
        'qualifications': 'MBBS, MD',
        'hospitalOrClinic': 'Asiri Surgical Hospital',
        'experienceYears': 15,
        'consultationFee': 3500.0,
        'rating': 4.9,
        'city': 'Colombo',
        'nextAvailableSlot': '2026-10-15 at 16:30',
        'matchReason': 'Verified Cardiologist with 15 years experience',
      };

      final card = DoctorReferralCard.fromJson(json);

      expect(card.doctorId, 'DOC-123');
      expect(card.fullName, 'Dr. Sunimal Silva');
      expect(card.specialty, 'Cardiologist');
      expect(card.experienceYears, 15);
      expect(card.consultationFee, 3500.0);
      expect(card.nextAvailableSlot, '2026-10-15 at 16:30');
    });

    test('HealthChatMessage deserializes emergency message and flags correctly', () {
      final json = {
        'id': 'msg-001',
        'sender': 'assistant',
        'content': 'POTENTIAL MEDICAL EMERGENCY DETECTED: Call 1990 immediately.',
        'timestamp': '2026-10-13T10:00:00.000Z',
        'triageLevel': 'emergency',
        'isUrgent': true,
        'emergencyNumber': '1990',
        'disclaimer': 'MediConnect general disclaimer.',
        'clarifyingQuestions': <String>[],
        'doctorReferrals': <dynamic>[],
      };

      final msg = HealthChatMessage.fromJson(json);

      expect(msg.id, 'msg-001');
      expect(msg.isAssistant, isTrue);
      expect(msg.isEmergency, isTrue);
      expect(msg.triageLevel, 'emergency');
      expect(msg.emergencyNumber, '1990');
    });

    test('HealthChatMessage deserializes doctor referrals and clarifying questions', () {
      final json = {
        'id': 'msg-002',
        'sender': 'assistant',
        'content': 'Based on your symptoms, a routine medical review is recommended.',
        'timestamp': '2026-10-13T10:05:00.000Z',
        'triageLevel': 'routine_care',
        'isUrgent': false,
        'clarifyingQuestions': ['How long have you had this?'],
        'doctorReferrals': [
          {
            'doctorId': 'DOC-456',
            'fullName': 'Dr. Nimali Perera',
            'specialty': 'Dermatologist',
            'consultationFee': 2500.0,
          }
        ],
      };

      final msg = HealthChatMessage.fromJson(json);

      expect(msg.isEmergency, isFalse);
      expect(msg.clarifyingQuestions.length, 1);
      expect(msg.doctorReferrals.length, 1);
      expect(msg.doctorReferrals.first.fullName, 'Dr. Nimali Perera');
    });

    test('HealthChatSession deserializes and roundtrips correctly', () {
      final sessionJson = {
        'id': 'sess-789',
        'patientUserId': 'user-101',
        'language': 'en',
        'consentGiven': true,
        'triageLevel': 'general_info',
        'recommendedSpecialty': 'General Physician',
        'messages': [
          {
            'id': 'm1',
            'sender': 'user',
            'content': 'Hello, what causes headaches?',
            'timestamp': '2026-10-13T10:00:00.000Z',
          }
        ],
        'createdAt': '2026-10-13T10:00:00.000Z',
        'updatedAt': '2026-10-13T10:01:00.000Z',
        'expiresAt': '2026-10-15T10:00:00.000Z',
      };

      final session = HealthChatSession.fromJson(sessionJson);

      expect(session.id, 'sess-789');
      expect(session.patientUserId, 'user-101');
      expect(session.messages.length, 1);
      expect(session.messages.first.content, 'Hello, what causes headaches?');

      final serialized = session.toJson();
      expect(serialized['id'], 'sess-789');
      expect((serialized['messages'] as List).length, 1);
    });
  });
}
