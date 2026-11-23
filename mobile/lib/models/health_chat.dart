// Data models for AI Health Symptom Guidance & Doctor Referral Chatbot (Phase 20).


class DoctorReferralCard {
  final String doctorId;
  final String fullName;
  final String specialty;
  final String? qualifications;
  final String? hospitalOrClinic;
  final int experienceYears;
  final double consultationFee;
  final double rating;
  final String? city;
  final String? nextAvailableSlot;
  final String? matchReason;

  const DoctorReferralCard({
    required this.doctorId,
    required this.fullName,
    required this.specialty,
    this.qualifications,
    this.hospitalOrClinic,
    this.experienceYears = 0,
    required this.consultationFee,
    this.rating = 0.0,
    this.city,
    this.nextAvailableSlot,
    this.matchReason,
  });

  factory DoctorReferralCard.fromJson(Map<String, dynamic> json) {
    return DoctorReferralCard(
      doctorId: json['doctorId']?.toString() ?? '',
      fullName: json['fullName']?.toString() ?? 'Doctor',
      specialty: json['specialty']?.toString() ?? 'General Physician',
      qualifications: json['qualifications']?.toString(),
      hospitalOrClinic: json['hospitalOrClinic']?.toString(),
      experienceYears: (json['experienceYears'] as num?)?.toInt() ?? 0,
      consultationFee: (json['consultationFee'] as num?)?.toDouble() ?? 2500.0,
      rating: (json['rating'] as num?)?.toDouble() ?? 4.8,
      city: json['city']?.toString(),
      nextAvailableSlot: json['nextAvailableSlot']?.toString(),
      matchReason: json['matchReason']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorId': doctorId,
      'fullName': fullName,
      'specialty': specialty,
      'qualifications': qualifications,
      'hospitalOrClinic': hospitalOrClinic,
      'experienceYears': experienceYears,
      'consultationFee': consultationFee,
      'rating': rating,
      'city': city,
      'nextAvailableSlot': nextAvailableSlot,
      'matchReason': matchReason,
    };
  }
}

class HealthChatMessage {
  final String id;
  final String sender; // 'user' | 'assistant' | 'system'
  final String content;
  final DateTime timestamp;
  final String? triageLevel;
  final bool isUrgent;
  final String? emergencyNumber;
  final String? disclaimer;
  final List<String> clarifyingQuestions;
  final String? recommendedSpecialty;
  final List<DoctorReferralCard> doctorReferrals;

  const HealthChatMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.triageLevel,
    this.isUrgent = false,
    this.emergencyNumber,
    this.disclaimer,
    this.clarifyingQuestions = const [],
    this.recommendedSpecialty,
    this.doctorReferrals = const [],
  });

  bool get isUser => sender == 'user';
  bool get isAssistant => sender == 'assistant';
  bool get isEmergency => triageLevel == 'emergency' || isUrgent;

  factory HealthChatMessage.fromJson(Map<String, dynamic> json) {
    final meta = (json['metadata'] as Map<String, dynamic>?) ?? {};

    final referralsList = (json['doctorReferrals'] as List<dynamic>?) ??
        (meta['doctorReferrals'] as List<dynamic>?) ??
        [];
    final referrals = referralsList
        .map((r) => DoctorReferralCard.fromJson(r as Map<String, dynamic>))
        .toList();

    final clarifyingList = (json['clarifyingQuestions'] as List<dynamic>?) ??
        (meta['clarifyingQuestions'] as List<dynamic>?) ??
        [];
    final questions = clarifyingList.map((q) => q.toString()).toList();

    return HealthChatMessage(
      id: json['id']?.toString() ?? '',
      sender: json['sender']?.toString() ?? 'assistant',
      content: json['content']?.toString() ?? '',
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now()
          : DateTime.now(),
      triageLevel: json['triageLevel']?.toString() ?? meta['triageLevel']?.toString(),
      isUrgent: json['isUrgent'] == true || meta['isUrgent'] == true,
      emergencyNumber: json['emergencyNumber']?.toString() ?? meta['emergencyNumber']?.toString(),
      disclaimer: json['disclaimer']?.toString() ?? meta['disclaimer']?.toString(),
      clarifyingQuestions: questions,
      recommendedSpecialty:
          json['recommendedSpecialty']?.toString() ?? meta['recommendedSpecialty']?.toString(),
      doctorReferrals: referrals,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'sender': sender,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'triageLevel': triageLevel,
      'isUrgent': isUrgent,
      'emergencyNumber': emergencyNumber,
      'disclaimer': disclaimer,
      'clarifyingQuestions': clarifyingQuestions,
      'recommendedSpecialty': recommendedSpecialty,
      'doctorReferrals': doctorReferrals.map((d) => d.toJson()).toList(),
    };
  }
}

class HealthChatSession {
  final String id;
  final String patientUserId;
  final String language;
  final bool consentGiven;
  final String? triageLevel;
  final String? recommendedSpecialty;
  final List<HealthChatMessage> messages;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime expiresAt;

  const HealthChatSession({
    required this.id,
    required this.patientUserId,
    this.language = 'en',
    this.consentGiven = true,
    this.triageLevel,
    this.recommendedSpecialty,
    this.messages = const [],
    required this.createdAt,
    required this.updatedAt,
    required this.expiresAt,
  });

  factory HealthChatSession.fromJson(Map<String, dynamic> json) {
    final msgList = (json['messages'] as List<dynamic>?) ?? [];
    final messages = msgList
        .map((m) => HealthChatMessage.fromJson(m as Map<String, dynamic>))
        .toList();

    return HealthChatSession(
      id: json['id']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      language: json['language']?.toString() ?? 'en',
      consentGiven: json['consentGiven'] != false,
      triageLevel: json['triageLevel']?.toString(),
      recommendedSpecialty: json['recommendedSpecialty']?.toString(),
      messages: messages,
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      expiresAt: json['expiresAt'] != null
          ? DateTime.tryParse(json['expiresAt'].toString()) ??
              DateTime.now().add(const Duration(hours: 48))
          : DateTime.now().add(const Duration(hours: 48)),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'patientUserId': patientUserId,
      'language': language,
      'consentGiven': consentGiven,
      'triageLevel': triageLevel,
      'recommendedSpecialty': recommendedSpecialty,
      'messages': messages.map((m) => m.toJson()).toList(),
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
      'expiresAt': expiresAt.toIso8601String(),
    };
  }
}
