/// Models representing AI doctor recommendation request interpretations and ranked matches.
library;

import 'doctor.dart';
import 'doctor_availability.dart';

class InterpretedPreferences {
  final String? specialty;
  final String? city;
  final String? date;
  final String? timeRange;
  final double? maxFee;
  final String? consultationType;
  final String languageDetected;

  InterpretedPreferences({
    this.specialty,
    this.city,
    this.date,
    this.timeRange,
    this.maxFee,
    this.consultationType,
    this.languageDetected = 'en',
  });

  factory InterpretedPreferences.fromJson(Map<String, dynamic> json) {
    return InterpretedPreferences(
      specialty: json['specialty']?.toString(),
      city: json['city']?.toString(),
      date: json['date']?.toString(),
      timeRange: json['timeRange']?.toString(),
      maxFee: json['maxFee'] is num ? (json['maxFee'] as num).toDouble() : null,
      consultationType: json['consultationType']?.toString(),
      languageDetected: (json['languageDetected'] ?? 'en').toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (specialty != null) 'specialty': specialty,
      if (city != null) 'city': city,
      if (date != null) 'date': date,
      if (timeRange != null) 'timeRange': timeRange,
      if (maxFee != null) 'maxFee': maxFee,
      if (consultationType != null) 'consultationType': consultationType,
      'languageDetected': languageDetected,
    };
  }
}

class RecommendedSlot {
  final String date;
  final String startTime;
  final String endTime;
  final String? availabilityId;

  RecommendedSlot({
    required this.date,
    required this.startTime,
    required this.endTime,
    this.availabilityId,
  });

  factory RecommendedSlot.fromJson(Map<String, dynamic> json) {
    return RecommendedSlot(
      date: (json['date'] ?? '').toString(),
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
      availabilityId: json['availabilityId']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'startTime': startTime,
      'endTime': endTime,
      if (availabilityId != null) 'availabilityId': availabilityId,
    };
  }

  /// Converts to standard TimeSlot for appointment booking screens
  TimeSlot toTimeSlot() {
    return TimeSlot(
      startTime: startTime,
      endTime: endTime,
      availabilityId: availabilityId,
    );
  }
}

class DoctorRecommendation {
  final String doctorId;
  final String fullName;
  final String specialty;
  final String hospitalOrClinic;
  final int experienceYears;
  final double consultationFee;
  final String? bio;
  final String? profileImage;
  final double score;
  final List<String> matchReasons;
  final List<RecommendedSlot> availableSlots;

  DoctorRecommendation({
    required this.doctorId,
    required this.fullName,
    required this.specialty,
    required this.hospitalOrClinic,
    required this.experienceYears,
    required this.consultationFee,
    this.bio,
    this.profileImage,
    required this.score,
    required this.matchReasons,
    required this.availableSlots,
  });

  factory DoctorRecommendation.fromJson(Map<String, dynamic> json) {
    final rawReasons = json['matchReasons'] as List<dynamic>? ?? [];
    final rawSlots = json['availableSlots'] as List<dynamic>? ?? [];

    return DoctorRecommendation(
      doctorId: (json['doctorId'] ?? '').toString(),
      fullName: (json['fullName'] ?? '').toString(),
      specialty: (json['specialty'] ?? '').toString(),
      hospitalOrClinic: (json['hospitalOrClinic'] ?? '').toString(),
      experienceYears: json['experienceYears'] is num ? (json['experienceYears'] as num).toInt() : 0,
      consultationFee: json['consultationFee'] is num ? (json['consultationFee'] as num).toDouble() : 2500.0,
      bio: json['bio']?.toString(),
      profileImage: json['profileImage']?.toString(),
      score: json['score'] is num ? (json['score'] as num).toDouble() : 0.0,
      matchReasons: rawReasons.map((e) => e.toString()).toList(),
      availableSlots: rawSlots.map((e) => RecommendedSlot.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorId': doctorId,
      'fullName': fullName,
      'specialty': specialty,
      'hospitalOrClinic': hospitalOrClinic,
      'experienceYears': experienceYears,
      'consultationFee': consultationFee,
      if (bio != null) 'bio': bio,
      if (profileImage != null) 'profileImage': profileImage,
      'score': score,
      'matchReasons': matchReasons,
      'availableSlots': availableSlots.map((s) => s.toJson()).toList(),
    };
  }

  /// Converts to Doctor model for seamless navigation to DoctorDetailScreen
  Doctor toDoctor() {
    return Doctor(
      doctorId: doctorId,
      fullName: fullName,
      specialty: specialty,
      hospitalOrClinic: hospitalOrClinic,
      experienceYears: experienceYears,
      bio: bio,
      profileImage: profileImage,
      verificationStatus: 'APPROVED',
      consultationFee: consultationFee,
    );
  }
}

class DoctorRecommendationResponse {
  final InterpretedPreferences interpretedPreferences;
  final List<DoctorRecommendation> recommendations;
  final int totalMatches;
  final bool isUrgent;
  final String? safetyGuidance;
  final String disclaimer;
  final String? clarificationQuestion;
  final String aiProviderUsed;

  DoctorRecommendationResponse({
    required this.interpretedPreferences,
    required this.recommendations,
    required this.totalMatches,
    this.isUrgent = false,
    this.safetyGuidance,
    required this.disclaimer,
    this.clarificationQuestion,
    this.aiProviderUsed = 'deterministic_fallback',
  });

  factory DoctorRecommendationResponse.fromJson(Map<String, dynamic> json) {
    final rawRecs = json['recommendations'] as List<dynamic>? ?? [];

    return DoctorRecommendationResponse(
      interpretedPreferences: json['interpretedPreferences'] != null
          ? InterpretedPreferences.fromJson(json['interpretedPreferences'] as Map<String, dynamic>)
          : InterpretedPreferences(),
      recommendations: rawRecs.map((e) => DoctorRecommendation.fromJson(e as Map<String, dynamic>)).toList(),
      totalMatches: json['totalMatches'] is num ? (json['totalMatches'] as num).toInt() : rawRecs.length,
      isUrgent: json['isUrgent'] is bool ? json['isUrgent'] as bool : false,
      safetyGuidance: json['safetyGuidance']?.toString(),
      disclaimer: (json['disclaimer'] ?? '').toString(),
      clarificationQuestion: json['clarificationQuestion']?.toString(),
      aiProviderUsed: (json['aiProviderUsed'] ?? 'deterministic_fallback').toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'interpretedPreferences': interpretedPreferences.toJson(),
      'recommendations': recommendations.map((r) => r.toJson()).toList(),
      'totalMatches': totalMatches,
      'isUrgent': isUrgent,
      if (safetyGuidance != null) 'safetyGuidance': safetyGuidance,
      'disclaimer': disclaimer,
      if (clarificationQuestion != null) 'clarificationQuestion': clarificationQuestion,
      'aiProviderUsed': aiProviderUsed,
    };
  }
}
