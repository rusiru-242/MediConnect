/// Models representing public doctor profile and discovery responses.
library;

class Doctor {
  final String doctorId;
  final String fullName;
  final String specialty;
  final String hospitalOrClinic;
  final int experienceYears;
  final String? bio;
  final String? profileImage;
  final String verificationStatus;
  final String? qualifications;

  Doctor({
    required this.doctorId,
    required this.fullName,
    required this.specialty,
    required this.hospitalOrClinic,
    required this.experienceYears,
    this.bio,
    this.profileImage,
    this.verificationStatus = 'APPROVED',
    this.qualifications,
  });

  factory Doctor.fromJson(Map<String, dynamic> json) {
    return Doctor(
      doctorId: (json['doctorId'] ?? json['id'] ?? '').toString(),
      fullName: (json['fullName'] ?? '').toString(),
      specialty: (json['specialty'] ?? '').toString(),
      hospitalOrClinic: (json['hospitalOrClinic'] ?? '').toString(),
      experienceYears: json['experienceYears'] is num ? (json['experienceYears'] as num).toInt() : 0,
      bio: json['bio']?.toString(),
      profileImage: json['profileImage']?.toString(),
      verificationStatus: (json['verificationStatus'] ?? 'APPROVED').toString(),
      qualifications: json['qualifications']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'doctorId': doctorId,
      'fullName': fullName,
      'specialty': specialty,
      'hospitalOrClinic': hospitalOrClinic,
      'experienceYears': experienceYears,
      'bio': bio,
      'profileImage': profileImage,
      'verificationStatus': verificationStatus,
      'qualifications': qualifications,
    };
  }
}

class DoctorListResponse {
  final List<Doctor> items;
  final int page;
  final int limit;
  final int total;
  final int totalPages;

  DoctorListResponse({
    required this.items,
    required this.page,
    required this.limit,
    required this.total,
    required this.totalPages,
  });

  factory DoctorListResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return DoctorListResponse(
      items: rawItems.map((e) => Doctor.fromJson(e as Map<String, dynamic>)).toList(),
      page: json['page'] is num ? (json['page'] as num).toInt() : 1,
      limit: json['limit'] is num ? (json['limit'] as num).toInt() : 20,
      total: json['total'] is num ? (json['total'] as num).toInt() : 0,
      totalPages: json['totalPages'] is num ? (json['totalPages'] as num).toInt() : 0,
    );
  }
}
