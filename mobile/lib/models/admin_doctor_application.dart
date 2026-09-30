/// Models for Admin Doctor Verification Workflow.
library;

class AdminDoctorApplicationSummary {
  final String doctorProfileId;
  final String userId;
  final String fullName;
  final String email;
  final String? phone;
  final String specialty;
  final String medicalRegistrationNumber;
  final String hospitalOrClinic;
  final int experienceYears;
  final String verificationStatus;
  final DateTime submittedAt;

  const AdminDoctorApplicationSummary({
    required this.doctorProfileId,
    required this.userId,
    required this.fullName,
    required this.email,
    this.phone,
    required this.specialty,
    required this.medicalRegistrationNumber,
    required this.hospitalOrClinic,
    required this.experienceYears,
    required this.verificationStatus,
    required this.submittedAt,
  });

  bool get isPending => verificationStatus == 'PENDING';
  bool get isApproved => verificationStatus == 'APPROVED';
  bool get isRejected => verificationStatus == 'REJECTED';

  factory AdminDoctorApplicationSummary.fromJson(Map<String, dynamic> json) {
    return AdminDoctorApplicationSummary(
      doctorProfileId: json['doctorProfileId']?.toString() ?? '',
      userId: json['userId']?.toString() ?? '',
      fullName: json['fullName']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      phone: json['phone']?.toString(),
      specialty: json['specialty']?.toString() ?? '',
      medicalRegistrationNumber: json['medicalRegistrationNumber']?.toString() ?? '',
      hospitalOrClinic: json['hospitalOrClinic']?.toString() ?? '',
      experienceYears: json['experienceYears'] is int
          ? json['experienceYears']
          : int.tryParse(json['experienceYears']?.toString() ?? '') ?? 0,
      verificationStatus: json['verificationStatus']?.toString() ?? 'PENDING',
      submittedAt: DateTime.tryParse(json['submittedAt']?.toString() ?? '') ?? DateTime.now(),
    );
  }
}

class AdminDoctorDocumentMetadata {
  final String documentKey;
  final String title;
  final String filename;
  final String mimeType;
  final int sizeBytes;
  final DateTime? uploadedAt;

  const AdminDoctorDocumentMetadata({
    required this.documentKey,
    required this.title,
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
    this.uploadedAt,
  });

  bool get isPdf => mimeType == 'application/pdf' || filename.toLowerCase().endsWith('.pdf');
  bool get isImage =>
      mimeType.startsWith('image/') ||
      filename.toLowerCase().endsWith('.jpg') ||
      filename.toLowerCase().endsWith('.jpeg') ||
      filename.toLowerCase().endsWith('.png');

  factory AdminDoctorDocumentMetadata.fromJson(Map<String, dynamic> json) {
    return AdminDoctorDocumentMetadata(
      documentKey: json['documentKey']?.toString() ?? '',
      title: json['title']?.toString() ?? 'Document',
      filename: json['filename']?.toString() ?? '',
      mimeType: json['mimeType']?.toString() ?? 'application/octet-stream',
      sizeBytes: json['sizeBytes'] is int
          ? json['sizeBytes']
          : int.tryParse(json['sizeBytes']?.toString() ?? '') ?? 0,
      uploadedAt: json['uploadedAt'] != null
          ? DateTime.tryParse(json['uploadedAt'].toString())
          : null,
    );
  }
}

class AdminDoctorApplicationDetail {
  final String doctorProfileId;
  final String userId;
  final String fullName;
  final String email;
  final String? phone;
  final String specialty;
  final String medicalRegistrationNumber;
  final String qualifications;
  final String hospitalOrClinic;
  final int experienceYears;
  final String? bio;
  final String verificationStatus;
  final String? rejectionReason;
  final DateTime submittedAt;
  final DateTime? verifiedAt;
  final String? verifiedBy;
  final List<AdminDoctorDocumentMetadata> documents;

  const AdminDoctorApplicationDetail({
    required this.doctorProfileId,
    required this.userId,
    required this.fullName,
    required this.email,
    this.phone,
    required this.specialty,
    required this.medicalRegistrationNumber,
    required this.qualifications,
    required this.hospitalOrClinic,
    required this.experienceYears,
    this.bio,
    required this.verificationStatus,
    this.rejectionReason,
    required this.submittedAt,
    this.verifiedAt,
    this.verifiedBy,
    required this.documents,
  });

  bool get isPending => verificationStatus == 'PENDING';
  bool get isApproved => verificationStatus == 'APPROVED';
  bool get isRejected => verificationStatus == 'REJECTED';

  factory AdminDoctorApplicationDetail.fromJson(Map<String, dynamic> json) {
    final docsList = (json['documents'] as List<dynamic>?)
            ?.map((d) => AdminDoctorDocumentMetadata.fromJson(d as Map<String, dynamic>))
            .toList() ??
        [];

    return AdminDoctorApplicationDetail(
      doctorProfileId: json['doctorProfileId']?.toString() ?? '',
      userId: json['userId']?.toString() ?? '',
      fullName: json['fullName']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      phone: json['phone']?.toString(),
      specialty: json['specialty']?.toString() ?? '',
      medicalRegistrationNumber: json['medicalRegistrationNumber']?.toString() ?? '',
      qualifications: json['qualifications']?.toString() ?? '',
      hospitalOrClinic: json['hospitalOrClinic']?.toString() ?? '',
      experienceYears: json['experienceYears'] is int
          ? json['experienceYears']
          : int.tryParse(json['experienceYears']?.toString() ?? '') ?? 0,
      bio: json['bio']?.toString(),
      verificationStatus: json['verificationStatus']?.toString() ?? 'PENDING',
      rejectionReason: json['rejectionReason']?.toString(),
      submittedAt: DateTime.tryParse(json['submittedAt']?.toString() ?? '') ?? DateTime.now(),
      verifiedAt: json['verifiedAt'] != null
          ? DateTime.tryParse(json['verifiedAt'].toString())
          : null,
      verifiedBy: json['verifiedBy']?.toString(),
      documents: docsList,
    );
  }
}
