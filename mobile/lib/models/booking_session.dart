import 'doctor.dart';
import 'doctor_availability.dart';

/// Represents a single conversational message in an AI booking session.
class ChatMessage {
  final String id;
  final String sender; // 'user' | 'assistant' | 'system'
  final String content;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;

  const ChatMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.timestamp,
    this.metadata,
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
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'sender': sender,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'metadata': metadata,
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

  const BookingPreferences({
    this.specialty,
    this.city,
    this.date,
    this.timeRange,
    this.maxFee,
    this.language = 'en',
    this.patientNote,
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
    };
  }
}

/// Summary card for doctor candidates in conversational flow.
class DoctorCardSummary {
  final String doctorId;
  final String doctorProfileId;
  final String doctorUserId;
  final String fullName;
  final String specialty;
  final String? hospitalOrClinic;
  final int experienceYears;
  final double consultationFee;
  final double rating;
  final String? nextAvailableDate;
  final String? matchReason;

  const DoctorCardSummary({
    required this.doctorId,
    required this.doctorProfileId,
    required this.doctorUserId,
    required this.fullName,
    required this.specialty,
    this.hospitalOrClinic,
    this.experienceYears = 0,
    required this.consultationFee,
    this.rating = 4.8,
    this.nextAvailableDate,
    this.matchReason,
  });

  factory DoctorCardSummary.fromJson(Map<String, dynamic> json) {
    return DoctorCardSummary(
      doctorId: json['doctorId'] as String? ?? '',
      doctorProfileId: json['doctorProfileId'] as String? ?? '',
      doctorUserId: json['doctorUserId'] as String? ?? '',
      fullName: json['fullName'] as String? ?? 'Doctor',
      specialty: json['specialty'] as String? ?? '',
      hospitalOrClinic: json['hospitalOrClinic'] as String?,
      experienceYears: (json['experienceYears'] as num?)?.toInt() ?? 0,
      consultationFee: (json['consultationFee'] as num?)?.toDouble() ?? 2500.0,
      rating: (json['rating'] as num?)?.toDouble() ?? 4.8,
      nextAvailableDate: json['nextAvailableDate'] as String?,
      matchReason: json['matchReason'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorId': doctorId,
      'doctorProfileId': doctorProfileId,
      'doctorUserId': doctorUserId,
      'fullName': fullName,
      'specialty': specialty,
      'hospitalOrClinic': hospitalOrClinic,
      'experienceYears': experienceYears,
      'consultationFee': consultationFee,
      'rating': rating,
      'nextAvailableDate': nextAvailableDate,
      'matchReason': matchReason,
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

/// Full AI conversational booking session data model.
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
      id: json['id'] as String? ?? '',
      patientUserId: json['patientUserId'] as String? ?? '',
      state: json['state'] as String? ?? 'COLLECTING_PREFERENCES',
      preferences: json['preferences'] != null
          ? BookingPreferences.fromJson(json['preferences'] as Map<String, dynamic>)
          : const BookingPreferences(),
      selectedDoctor: json['selectedDoctor'] != null
          ? DoctorCardSummary.fromJson(json['selectedDoctor'] as Map<String, dynamic>)
          : null,
      selectedSlot: json['selectedSlot'] != null
          ? SlotCardSummary.fromJson(json['selectedSlot'] as Map<String, dynamic>)
          : null,
      bookingSummary: json['bookingSummary'] != null
          ? BookingSummary.fromJson(json['bookingSummary'] as Map<String, dynamic>)
          : null,
      candidateDoctors: (json['candidateDoctors'] as List<dynamic>?)
              ?.map((e) => DoctorCardSummary.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      candidateSlots: (json['candidateSlots'] as List<dynamic>?)
              ?.map((e) => SlotCardSummary.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      appointmentId: json['appointmentId'] as String?,
      paymentId: json['paymentId'] as String?,
      holdExpiresAt: json['holdExpiresAt'] != null
          ? DateTime.tryParse(json['holdExpiresAt'] as String)
          : null,
      messages: (json['messages'] as List<dynamic>?)
              ?.map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      isUrgent: json['isUrgent'] as bool? ?? false,
      urgencyReason: json['urgencyReason'] as String?,
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'] as String) ?? DateTime.now()
          : DateTime.now(),
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'] as String) ?? DateTime.now()
          : DateTime.now(),
      expiresAt: json['expiresAt'] != null
          ? DateTime.tryParse(json['expiresAt'] as String) ?? DateTime.now()
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
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
      'expiresAt': expiresAt.toIso8601String(),
    };
  }
}
