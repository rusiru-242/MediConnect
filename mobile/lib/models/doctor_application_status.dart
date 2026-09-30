/// Application status model returned by GET /api/doctors/me/application-status.
class DoctorApplicationStatus {
  final String doctorId;
  final String specialty;
  final String verificationStatus;
  final DateTime submittedAt;
  final String? rejectionReason;

  const DoctorApplicationStatus({
    required this.doctorId,
    required this.specialty,
    required this.verificationStatus,
    required this.submittedAt,
    this.rejectionReason,
  });

  bool get isPending => verificationStatus == 'PENDING';
  bool get isApproved => verificationStatus == 'APPROVED';
  bool get isRejected => verificationStatus == 'REJECTED';

  factory DoctorApplicationStatus.fromJson(Map<String, dynamic> json) {
    return DoctorApplicationStatus(
      doctorId: json['doctorId']?.toString() ?? '',
      specialty: json['specialty']?.toString() ?? '',
      verificationStatus: json['verificationStatus']?.toString() ?? 'PENDING',
      submittedAt: DateTime.tryParse(json['submittedAt']?.toString() ?? '') ?? DateTime.now(),
      rejectionReason: json['rejectionReason']?.toString(),
    );
  }
}
