/// User representation returned by MediConnect backend.
class UserModel {
  final String id;
  final String fullName;
  final String email;
  final String? phone;
  final String role;
  final bool emailVerified;
  final String accountStatus;
  final String? profileImage;
  final DateTime? createdAt;
  final List<String> authProviders;

  const UserModel({
    required this.id,
    required this.fullName,
    required this.email,
    this.phone,
    required this.role,
    required this.emailVerified,
    required this.accountStatus,
    this.profileImage,
    this.createdAt,
    this.authProviders = const [],
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    DateTime? parsedDate;
    if (json['createdAt'] != null) {
      parsedDate = DateTime.tryParse(json['createdAt'].toString());
    }

    List<String> providers = [];
    if (json['authProviders'] is List) {
      providers = (json['authProviders'] as List)
          .map((item) => item.toString())
          .toList();
    }

    return UserModel(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      fullName: json['fullName']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      phone: json['phone']?.toString(),
      role: json['role']?.toString() ?? 'PATIENT',
      emailVerified: json['emailVerified'] == true,
      accountStatus: json['accountStatus']?.toString() ?? 'PENDING',
      profileImage: json['profileImage']?.toString(),
      createdAt: parsedDate,
      authProviders: providers,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'fullName': fullName,
      'email': email,
      'phone': phone,
      'role': role,
      'emailVerified': emailVerified,
      'accountStatus': accountStatus,
      'profileImage': profileImage,
      'createdAt': createdAt?.toIso8601String(),
      'authProviders': authProviders,
    };
  }

  UserModel copyWith({
    String? id,
    String? fullName,
    String? email,
    String? phone,
    String? role,
    bool? emailVerified,
    String? accountStatus,
    String? profileImage,
    DateTime? createdAt,
    List<String>? authProviders,
  }) {
    return UserModel(
      id: id ?? this.id,
      fullName: fullName ?? this.fullName,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      role: role ?? this.role,
      emailVerified: emailVerified ?? this.emailVerified,
      accountStatus: accountStatus ?? this.accountStatus,
      profileImage: profileImage ?? this.profileImage,
      createdAt: createdAt ?? this.createdAt,
      authProviders: authProviders ?? this.authProviders,
    );
  }
}
