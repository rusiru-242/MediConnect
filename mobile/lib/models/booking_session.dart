import 'doctor.dart';
import 'doctor_availability.dart';

/// Helper to safely parse strings or lists of strings from JSON without throwing TypeErrors.
List<String> _parseStringList(dynamic value) {
  if (value == null) return const [];
  if (value is List) {
    return value.map((e) => e.toString()).toList();
  }
  final str = value.toString().trim();
  return str.isNotEmpty ? [str] : const [];
}

/// Represents a single conversational message in an AI booking session.
class ChatMessage {
  final String id;
  final String sender; // 'user' | 'assistant' | 'system'
  final String content;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;
  final String? imageUrl;

  const ChatMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.metadata,
    this.imageUrl,
  });

  bool get isUser => sender == 'user';
  bool get isAssistant => sender == 'assistant';
  bool get isSystem => sender == 'system';

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as String? ?? '',
      sender: json['sender'] as String? ?? 'assistant',
      content: json['content'] as String? ?? '',
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'] as String) ?? DateTime.now()
          : DateTime.now(),
      metadata: json['metadata'] as Map<String, dynamic>?,
      imageUrl: json['imageUrl'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'sender': sender,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'metadata': metadata,
      if (imageUrl != null) 'imageUrl': imageUrl,
    };
  }
}

/// Accumulative structured booking preferences extracted by AI.
class BookingPreferences {
  final String? specialty;
  final String? city;
  final String? date;
  final String? timeRange;
  final double? maxFee;
  final String language;
  final String? patientNote;
  final String? preferredGender;
  final String? symptoms;
  final String? sortBy;

  const BookingPreferences({
    this.specialty,
    this.city,
    this.date,
    this.timeRange,
    this.maxFee,
    this.language = 'en',
    this.patientNote,
    this.preferredGender,
    this.symptoms,
    this.sortBy,
  });

  factory BookingPreferences.fromJson(Map<String, dynamic> json) {
    return BookingPreferences(
      specialty: json['specialty'] as String?,
      city: json['city'] as String?,
      date: json['date'] as String?,
      timeRange: json['timeRange'] as String?,
      maxFee: (json['maxFee'] as num?)?.toDouble(),
      language: json['language'] as String? ?? 'en',
      patientNote: json['patientNote'] as String?,
      preferredGender: json['preferredGender'] as String?,
      symptoms: json['symptoms'] as String?,
      sortBy: json['sortBy'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'specialty': specialty,
      'city': city,
      'date': date,
      'timeRange': timeRange,
      'maxFee': maxFee,
      'language': language,
      'patientNote': patientNote,
      'preferredGender': preferredGender,
      'symptoms': symptoms,
      'sortBy': sortBy,
    };
  }
}

/// Discrete slot option presented in conversational booking.
class SlotCardSummary {
  final String availabilityId;
  final String date;
  final String startTime;
  final String endTime;

  const SlotCardSummary({
    required this.availabilityId,
    required this.date,
    required this.startTime,
    required this.endTime,
  });

  factory SlotCardSummary.fromJson(Map<String, dynamic> json) {
    return SlotCardSummary(
      availabilityId: json['availabilityId'] as String? ?? '',
      date: json['date'] as String? ?? '',
      startTime: json['startTime'] as String? ?? '',
      endTime: json['endTime'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'availabilityId': availabilityId,
      'date': date,
      'startTime': startTime,
      'endTime': endTime,
    };
  }

  /// Converts to standard TimeSlot model for booking compatibility.
  TimeSlot toTimeSlot() {
    return TimeSlot(
      startTime: startTime,
      endTime: endTime,
      availabilityId: availabilityId,
    );
  }
}

/// Summary card for doctor candidates in conversational flow.
class DoctorCardSummary {
  final String doctorId;
  final String doctorProfileId;
  final String doctorUserId;
  final String fullName;
  final String specialty;
  final String? qualifications;
  final String? hospitalOrClinic;
  final int experienceYears;
  final double consultationFee;
  final double rating;
  final double? matchScore;
  final String? nextAvailableDate;
  final String? matchReason;
  final List<String> matchReasons;
  final List<SlotCardSummary> availableSlots;

  const DoctorCardSummary({
    required this.doctorId,
    required this.doctorProfileId,
    required this.doctorUserId,
    required this.fullName,
    required this.specialty,
    this.qualifications,
    this.hospitalOrClinic,
    this.experienceYears = 0,
    required this.consultationFee,
    this.rating = 4.8,
    this.matchScore,
    this.nextAvailableDate,
    this.matchReason,
    this.matchReasons = const [],
    this.availableSlots = const [],
  });

  factory DoctorCardSummary.fromJson(Map<String, dynamic> json) {
    return DoctorCardSummary(
      doctorId: json['doctorId'] as String? ?? '',
      doctorProfileId: json['doctorProfileId'] as String? ?? '',
      doctorUserId: json['doctorUserId'] as String? ?? '',
      fullName: json['fullName'] as String? ?? 'Doctor',
      specialty: json['specialty'] as String? ?? '',
      qualifications: json['qualifications'] as String?,
      hospitalOrClinic: json['hospitalOrClinic'] as String?,
      experienceYears: (json['experienceYears'] as num?)?.toInt() ?? 0,
      consultationFee: (json['consultationFee'] as num?)?.toDouble() ?? 2500.0,
      rating: (json['rating'] as num?)?.toDouble() ?? 4.8,
      matchScore: (json['matchScore'] as num?)?.toDouble(),
      nextAvailableDate: json['nextAvailableDate'] as String?,
      matchReason: json['matchReason'] as String?,
      matchReasons: _parseStringList(json['matchReasons']).isNotEmpty
          ? _parseStringList(json['matchReasons'])
          : (json['matchReason'] != null ? [json['matchReason'].toString()] : const []),
      availableSlots: (json['availableSlots'] is List)
          ? (json['availableSlots'] as List)
              .whereType<Map<String, dynamic>>()
              .map((e) => SlotCardSummary.fromJson(e))
              .toList()
          : const [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorId': doctorId,
      'doctorProfileId': doctorProfileId,
      'doctorUserId': doctorUserId,
      'fullName': fullName,
      'specialty': specialty,
      'qualifications': qualifications,
      'hospitalOrClinic': hospitalOrClinic,
      'experienceYears': experienceYears,
      'consultationFee': consultationFee,
      'rating': rating,
      'matchScore': matchScore,
      'nextAvailableDate': nextAvailableDate,
      'matchReason': matchReason,
      'matchReasons': matchReasons,
      'availableSlots': availableSlots.map((e) => e.toJson()).toList(),
    };
  }

  /// Converts to standard Doctor model for existing profile navigation.
  Doctor toDoctor() {
    return Doctor(
      doctorId: doctorId,
      fullName: fullName,
      specialty: specialty,
      hospitalOrClinic: hospitalOrClinic ?? 'MediConnect Clinic',
      experienceYears: experienceYears,
      consultationFee: consultationFee,
      profileImage: null,
      verificationStatus: 'APPROVED',
    );
  }
}

/// Explicit booking summary card before confirmation.
class BookingSummary {
  final String doctorName;
  final String specialty;
  final String? hospitalOrClinic;
  final String appointmentDate;
  final String startTime;
  final String endTime;
  final double consultationFee;
  final double serviceFee;
  final double totalAmount;
  final String currency;

  const BookingSummary({
    required this.doctorName,
    required this.specialty,
    this.hospitalOrClinic,
    required this.appointmentDate,
    required this.startTime,
    required this.endTime,
    required this.consultationFee,
    this.serviceFee = 0.0,
    required this.totalAmount,
    this.currency = 'lkr',
  });

  factory BookingSummary.fromJson(Map<String, dynamic> json) {
    return BookingSummary(
      doctorName: json['doctorName'] as String? ?? 'Doctor',
      specialty: json['specialty'] as String? ?? '',
      hospitalOrClinic: json['hospitalOrClinic'] as String?,
      appointmentDate: json['appointmentDate'] as String? ?? '',
      startTime: json['startTime'] as String? ?? '',
      endTime: json['endTime'] as String? ?? '',
      consultationFee: (json['consultationFee'] as num?)?.toDouble() ?? 2500.0,
      serviceFee: (json['serviceFee'] as num?)?.toDouble() ?? 0.0,
      totalAmount: (json['totalAmount'] as num?)?.toDouble() ?? 2500.0,
      currency: json['currency'] as String? ?? 'lkr',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorName': doctorName,
      'specialty': specialty,
      'hospitalOrClinic': hospitalOrClinic,
      'appointmentDate': appointmentDate,
      'startTime': startTime,
      'endTime': endTime,
      'consultationFee': consultationFee,
      'serviceFee': serviceFee,
      'totalAmount': totalAmount,
      'currency': currency,
    };
  }
}

/// Educational medicine card summary for AI Health Companion.
class MedicineCardSummary {
  final String medicineName;
  final String? activeIngredient;
  final List<String> commonUses;
  final List<String> precautions;
  final List<String> sideEffects;
  final List<String> warnings;
  final List<String> consultPharmacistWhen;
  final bool isPrescriptionRequired;

  const MedicineCardSummary({
    required this.medicineName,
    this.activeIngredient,
    this.commonUses = const [],
    this.precautions = const [],
    this.sideEffects = const [],
    this.warnings = const [],
    this.consultPharmacistWhen = const [],
    this.isPrescriptionRequired = false,
  });

  factory MedicineCardSummary.fromJson(Map<String, dynamic> json) {
    return MedicineCardSummary(
      medicineName: json['medicineName'] as String? ?? 'Medicine',
      activeIngredient: json['activeIngredient'] as String?,
      commonUses: _parseStringList(json['commonUses']),
      precautions: _parseStringList(json['precautions']),
      sideEffects: _parseStringList(json['sideEffects']),
      warnings: _parseStringList(json['warnings']),
      consultPharmacistWhen: _parseStringList(json['consultPharmacistWhen']),
      isPrescriptionRequired: json['isPrescriptionRequired'] == true ||
          json['isPrescriptionRequired']?.toString().toLowerCase() == 'true',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'medicineName': medicineName,
      'activeIngredient': activeIngredient,
      'commonUses': commonUses,
      'precautions': precautions,
      'sideEffects': sideEffects,
      'warnings': warnings,
      'consultPharmacistWhen': consultPharmacistWhen,
      'isPrescriptionRequired': isPrescriptionRequired,
    };
  }
}

/// Educational wellness & lifestyle card summary for AI Health Companion.
class WellnessCardSummary {
  final String category; // 'FOOD' | 'EXERCISE' | 'WELLNESS'
  final String title;
  final String summary;
  final List<String> tips;
  final List<String> sriLankanOptions;
  final String? safetyNote;

  const WellnessCardSummary({
    required this.category,
    required this.title,
    required this.summary,
    this.tips = const [],
    this.sriLankanOptions = const [],
    this.safetyNote,
  });

  factory WellnessCardSummary.fromJson(Map<String, dynamic> json) {
    return WellnessCardSummary(
      category: json['category'] as String? ?? 'WELLNESS',
      title: json['title'] as String? ?? 'Wellness Guidance',
      summary: json['summary'] as String? ?? '',
      tips: _parseStringList(json['tips']),
      sriLankanOptions: _parseStringList(json['sriLankanOptions']),
      safetyNote: json['safetyNote'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category,
      'title': title,
      'summary': summary,
      'tips': tips,
      'sriLankanOptions': sriLankanOptions,
      'safetyNote': safetyNote,
    };
  }
}

/// Image OCR and label analysis summary for AI Health Companion.
class ImageAnalysisSummary {
  final String detectedText;
  final String? identifiedMedicine;
  final String? activeIngredient;
  final String confidenceLevel; // 'HIGH' | 'MEDIUM' | 'LOW' | 'UNCERTAIN'
  final String? uncertaintyExplanation;
  final String? safetyAdvice;
  final bool requiresClearerPhoto;

  const ImageAnalysisSummary({
    required this.detectedText,
    this.identifiedMedicine,
    this.activeIngredient,
    this.confidenceLevel = 'UNCERTAIN',
    this.uncertaintyExplanation,
    this.safetyAdvice,
    this.requiresClearerPhoto = false,
  });

  factory ImageAnalysisSummary.fromJson(Map<String, dynamic> json) {
    return ImageAnalysisSummary(
      detectedText: json['detectedText'] as String? ?? '',
      identifiedMedicine: json['identifiedMedicine'] as String?,
      activeIngredient: json['activeIngredient'] as String?,
      confidenceLevel: json['confidenceLevel'] as String? ?? 'UNCERTAIN',
      uncertaintyExplanation: json['uncertaintyExplanation'] as String?,
      safetyAdvice: json['safetyAdvice'] as String?,
      requiresClearerPhoto: json['requiresClearerPhoto'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'detectedText': detectedText,
      'identifiedMedicine': identifiedMedicine,
      'activeIngredient': activeIngredient,
      'confidenceLevel': confidenceLevel,
      'uncertaintyExplanation': uncertaintyExplanation,
      'safetyAdvice': safetyAdvice,
      'requiresClearerPhoto': requiresClearerPhoto,
    };
  }
}

/// Full AI conversational companion session data model.
class BookingSession {
  final String id;
  final String patientUserId;
  final String state;
  final BookingPreferences preferences;
  final DoctorCardSummary? selectedDoctor;
  final SlotCardSummary? selectedSlot;
  final BookingSummary? bookingSummary;
  final List<DoctorCardSummary> candidateDoctors;
  final List<SlotCardSummary> candidateSlots;
  final String? appointmentId;
  final String? paymentId;
  final DateTime? holdExpiresAt;
  final List<ChatMessage> messages;
  final bool isUrgent;
  final String? urgencyReason;
  final String? activeIntent;
  final MedicineCardSummary? activeMedicineCard;
  final WellnessCardSummary? activeWellnessCard;
  final ImageAnalysisSummary? activeImageAnalysis;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime expiresAt;

  const BookingSession({
    required this.id,
    required this.patientUserId,
    required this.state,
    required this.preferences,
    this.selectedDoctor,
    this.selectedSlot,
    this.bookingSummary,
    this.candidateDoctors = const [],
    this.candidateSlots = const [],
    this.appointmentId,
    this.paymentId,
    this.holdExpiresAt,
    this.messages = const [],
    this.isUrgent = false,
    this.urgencyReason,
    this.activeIntent,
    this.activeMedicineCard,
    this.activeWellnessCard,
    this.activeImageAnalysis,
    required this.createdAt,
    required this.updatedAt,
    required this.expiresAt,
  });

  bool get isCollectingPreferences => state == 'COLLECTING_PREFERENCES';
  bool get isSearchingDoctors => state == 'SEARCHING_DOCTORS';
  bool get isAwaitingDoctor => state == 'AWAITING_DOCTOR_SELECTION';
  bool get isAwaitingSlot => state == 'AWAITING_SLOT_SELECTION';
  bool get isAwaitingConfirmation => state == 'AWAITING_BOOKING_CONFIRMATION';
  bool get isHoldCreated => state == 'BOOKING_HOLD_CREATED';
  bool get isAwaitingPayment => state == 'AWAITING_PAYMENT';
  bool get isPaymentPending => state == 'PAYMENT_PENDING_VERIFICATION';
  bool get isConfirmed => state == 'BOOKING_CONFIRMED';
  bool get isFailed => state == 'BOOKING_FAILED';
  bool get isCancelled => state == 'CANCELLED';
  bool get isExpired => state == 'EXPIRED';

  factory BookingSession.fromJson(Map<String, dynamic> json) {
    return BookingSession(
      id: json['id'] as String? ?? json['_id'] as String? ?? '',
      patientUserId: json['patientUserId'] as String? ?? '',
      state: json['state'] as String? ?? 'COLLECTING_PREFERENCES',
      preferences: json['preferences'] is Map<String, dynamic>
          ? BookingPreferences.fromJson(json['preferences'] as Map<String, dynamic>)
          : const BookingPreferences(),
      selectedDoctor: json['selectedDoctor'] is Map<String, dynamic>
          ? DoctorCardSummary.fromJson(json['selectedDoctor'] as Map<String, dynamic>)
          : null,
      selectedSlot: json['selectedSlot'] is Map<String, dynamic>
          ? SlotCardSummary.fromJson(json['selectedSlot'] as Map<String, dynamic>)
          : null,
      bookingSummary: json['bookingSummary'] is Map<String, dynamic>
          ? BookingSummary.fromJson(json['bookingSummary'] as Map<String, dynamic>)
          : null,
      candidateDoctors: (json['candidateDoctors'] is List)
          ? (json['candidateDoctors'] as List)
              .whereType<Map<String, dynamic>>()
              .map((e) => DoctorCardSummary.fromJson(e))
              .toList()
          : const [],
      candidateSlots: (json['candidateSlots'] is List)
          ? (json['candidateSlots'] as List)
              .whereType<Map<String, dynamic>>()
              .map((e) => SlotCardSummary.fromJson(e))
              .toList()
          : const [],
      appointmentId: json['appointmentId'] as String?,
      paymentId: json['paymentId'] as String?,
      holdExpiresAt: json['holdExpiresAt'] != null
          ? DateTime.tryParse(json['holdExpiresAt'].toString())
          : null,
      messages: (json['messages'] is List)
          ? (json['messages'] as List)
              .whereType<Map<String, dynamic>>()
              .map((e) => ChatMessage.fromJson(e))
              .toList()
          : const [],
      isUrgent: json['isUrgent'] == true ||
          json['isUrgent']?.toString().toLowerCase() == 'true',
      urgencyReason: json['urgencyReason'] as String?,
      activeIntent: json['activeIntent'] as String?,
      activeMedicineCard: json['activeMedicineCard'] is Map<String, dynamic>
          ? MedicineCardSummary.fromJson(
              json['activeMedicineCard'] as Map<String, dynamic>)
          : null,
      activeWellnessCard: json['activeWellnessCard'] is Map<String, dynamic>
          ? WellnessCardSummary.fromJson(
              json['activeWellnessCard'] as Map<String, dynamic>)
          : null,
      activeImageAnalysis: json['activeImageAnalysis'] is Map<String, dynamic>
          ? ImageAnalysisSummary.fromJson(
              json['activeImageAnalysis'] as Map<String, dynamic>)
          : null,
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
      expiresAt: json['expiresAt'] != null
          ? DateTime.tryParse(json['expiresAt'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'patientUserId': patientUserId,
      'state': state,
      'preferences': preferences.toJson(),
      'selectedDoctor': selectedDoctor?.toJson(),
      'selectedSlot': selectedSlot?.toJson(),
      'bookingSummary': bookingSummary?.toJson(),
      'candidateDoctors': candidateDoctors.map((e) => e.toJson()).toList(),
      'candidateSlots': candidateSlots.map((e) => e.toJson()).toList(),
      'appointmentId': appointmentId,
      'paymentId': paymentId,
      'holdExpiresAt': holdExpiresAt?.toIso8601String(),
      'messages': messages.map((e) => e.toJson()).toList(),
      'isUrgent': isUrgent,
      'urgencyReason': urgencyReason,
      'activeIntent': activeIntent,
      'activeMedicineCard': activeMedicineCard?.toJson(),
      'activeWellnessCard': activeWellnessCard?.toJson(),
      'activeImageAnalysis': activeImageAnalysis?.toJson(),
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
      'expiresAt': expiresAt.toIso8601String(),
    };
  }
}
