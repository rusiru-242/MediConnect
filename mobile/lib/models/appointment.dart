/// Appointment model representing a booking between a patient and a doctor.
library;

class Appointment {
  final String id;
  final String patientUserId;
  final String doctorUserId;
  final String doctorProfileId;
  final String availabilityId;
  final String appointmentDate;
  final String startTime;
  final String endTime;
  final String status; // PENDING | CONFIRMED | COMPLETED | CANCELLED
  final String paymentStatus; // UNPAID | PENDING | PAID | FAILED | REFUNDED
  /// Fee recorded on the appointment when it was booked. Null when the backend has none (never a default).
  final double? consultationFee;
  final DateTime? holdExpiresAt;
  final String? patientNote;
  final String? cancelledBy;
  final String? cancellationReason;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  // Enriched fields (joined from other collections by backend)
  final String? patientName;
  final String? patientEmail;
  final String? doctorName;
  final String? doctorProfileImage; // R02: API path of the doctor's picture (from the backend)
  final String? specialty;
  final String? hospitalOrClinic;

  // Booking and payment facts from the backend (BUG-058/BUG-059). All optional; nothing is inferred.
  final String? bookingReference;
  final String visitType;
  final double? consultationFeeAtBooking;
  final String? currency;
  final double? amountPaid;
  final DateTime? paidAt;
  final String? paymentId;
  final String? paymentReconciliationState;
  final double? refundedAmount;
  final String? refundStatus;

  const Appointment({
    required this.id,
    required this.patientUserId,
    required this.doctorUserId,
    required this.doctorProfileId,
    required this.availabilityId,
    required this.appointmentDate,
    required this.startTime,
    required this.endTime,
    required this.status,
    this.paymentStatus = 'UNPAID',
    this.consultationFee,
    this.holdExpiresAt,
    this.patientNote,
    this.cancelledBy,
    this.cancellationReason,
    this.createdAt,
    this.updatedAt,
    this.patientName,
    this.patientEmail,
    this.doctorName,
    this.doctorProfileImage,
    this.specialty,
    this.hospitalOrClinic,
    this.bookingReference,
    this.visitType = 'IN_PERSON',
    this.consultationFeeAtBooking,
    this.currency,
    this.amountPaid,
    this.paidAt,
    this.paymentId,
    this.paymentReconciliationState,
    this.refundedAmount,
    this.refundStatus,
  });

  static double? _money(dynamic value) => value is num ? value.toDouble() : null;

  factory Appointment.fromJson(Map<String, dynamic> json) {
    return Appointment(
      id: (json['id'] ?? json['_id'] ?? '').toString(),
      patientUserId: (json['patientUserId'] ?? '').toString(),
      doctorUserId: (json['doctorUserId'] ?? '').toString(),
      doctorProfileId: (json['doctorProfileId'] ?? '').toString(),
      availabilityId: (json['availabilityId'] ?? '').toString(),
      appointmentDate: (json['appointmentDate'] ?? '').toString(),
      startTime: (json['startTime'] ?? '').toString(),
      endTime: (json['endTime'] ?? '').toString(),
      status: (json['status'] ?? 'PENDING').toString(),
      paymentStatus: (json['paymentStatus'] ?? 'UNPAID').toString(),
      consultationFee: _money(json['consultationFee']),
      holdExpiresAt: json['holdExpiresAt'] != null
          ? DateTime.tryParse(json['holdExpiresAt'].toString())
          : null,
      patientNote: json['patientNote']?.toString(),
      cancelledBy: json['cancelledBy']?.toString(),
      cancellationReason: json['cancellationReason']?.toString(),
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString())
          : null,
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'].toString())
          : null,
      patientName: json['patientName']?.toString(),
      patientEmail: json['patientEmail']?.toString(),
      doctorName: json['doctorName']?.toString(),
      doctorProfileImage: json['doctorProfileImage']?.toString(),
      specialty: json['specialty']?.toString(),
      hospitalOrClinic: json['hospitalOrClinic']?.toString(),
      bookingReference: json['bookingReference']?.toString(),
      visitType: (json['visitType'] ?? 'IN_PERSON').toString(),
      consultationFeeAtBooking: _money(json['consultationFeeAtBooking']),
      currency: json['currency']?.toString(),
      amountPaid: _money(json['amountPaid']),
      paidAt: json['paidAt'] != null ? DateTime.tryParse(json['paidAt'].toString()) : null,
      paymentId: json['paymentId']?.toString(),
      paymentReconciliationState: json['paymentReconciliationState']?.toString(),
      refundedAmount: _money(json['refundedAmount']),
      refundStatus: json['refundStatus']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'patientUserId': patientUserId,
      'doctorUserId': doctorUserId,
      'doctorProfileId': doctorProfileId,
      'availabilityId': availabilityId,
      'appointmentDate': appointmentDate,
      'startTime': startTime,
      'endTime': endTime,
      'status': status,
      'patientNote': patientNote,
      'cancelledBy': cancelledBy,
      'cancellationReason': cancellationReason,
      'createdAt': createdAt?.toIso8601String(),
      'updatedAt': updatedAt?.toIso8601String(),
      'patientName': patientName,
      'patientEmail': patientEmail,
      'doctorName': doctorName,
      'doctorProfileImage': doctorProfileImage,
      'specialty': specialty,
      'hospitalOrClinic': hospitalOrClinic,
    };
  }

  bool get isPending => status == 'PENDING';
  bool get isConfirmed => status == 'CONFIRMED';
  bool get isCompleted => status == 'COMPLETED';
  bool get isCancelled => status == 'CANCELLED';
  bool get isActive => isPending || isConfirmed;
  bool get canCancel => isPending || isConfirmed;
  bool get isPaid => paymentStatus == 'PAID';
  bool get isUnpaidReservation => isPending && !isPaid;

  /// The fee to show for this booking: the amount stored at booking time, never a profile or default fee.
  double? get bookedFee => consultationFeeAtBooking ?? consultationFee;

  /// Full booking reference (the appointment id unless the backend supplies one).
  String get reference => bookingReference ?? id;
}

class AppointmentListResponse {
  final List<Appointment> items;
  final int page;
  final int limit;
  final int total;
  final int totalPages;

  const AppointmentListResponse({
    required this.items,
    required this.page,
    required this.limit,
    required this.total,
    required this.totalPages,
  });

  factory AppointmentListResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return AppointmentListResponse(
      items: rawItems
          .map((e) => Appointment.fromJson(e as Map<String, dynamic>))
          .toList(),
      page: (json['page'] as num?)?.toInt() ?? 1,
      limit: (json['limit'] as num?)?.toInt() ?? 20,
      total: (json['total'] as num?)?.toInt() ?? 0,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 0,
    );
  }
}
