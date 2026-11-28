/// R02 (resolves A05-O1): the patient's own profile as stored on the server. Every health value is optional and
/// patient-reported; nothing here has a default. Recorded allergies come from the medical record with provenance.
class EmergencyContact {
  final String name;
  final String? relationship;
  final String phone;

  const EmergencyContact({required this.name, this.relationship, required this.phone});

  factory EmergencyContact.fromJson(Map<String, dynamic> json) => EmergencyContact(
        name: json['name']?.toString() ?? '',
        relationship: json['relationship']?.toString(),
        phone: json['phone']?.toString() ?? '',
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        if (relationship != null && relationship!.isNotEmpty) 'relationship': relationship,
        'phone': phone,
      };
}

class RecordedAllergy {
  final String allergen;
  final String? severity;
  final String sourceLabel;
  final String? clinicalDate;

  const RecordedAllergy({required this.allergen, this.severity, required this.sourceLabel, this.clinicalDate});

  factory RecordedAllergy.fromJson(Map<String, dynamic> json) => RecordedAllergy(
        allergen: json['allergen']?.toString() ?? '',
        severity: json['severity']?.toString(),
        sourceLabel: json['sourceLabel']?.toString() ?? 'Medical record',
        clinicalDate: json['clinicalDate']?.toString(),
      );
}

class PatientProfile {
  static const notProvided = 'not_provided';
  static const noneKnown = 'none_known';
  static const hasAllergies = 'has_allergies';

  final String fullName;
  final String? email;
  final String? phone;
  final String? profileImage;
  final double? heightCm;
  final double? weightKg;
  final double? bmi;
  final String? bmiNote;
  final String allergyStatus;
  final List<String> allergies;
  final EmergencyContact? emergencyContact;
  final List<RecordedAllergy> recordedAllergies;

  const PatientProfile({
    required this.fullName,
    this.email,
    this.phone,
    this.profileImage,
    this.heightCm,
    this.weightKg,
    this.bmi,
    this.bmiNote,
    this.allergyStatus = notProvided,
    this.allergies = const [],
    this.emergencyContact,
    this.recordedAllergies = const [],
  });

  static double? _num(dynamic v) => v is num ? v.toDouble() : null;

  factory PatientProfile.fromJson(Map<String, dynamic> json) {
    final hp = Map<String, dynamic>.from((json['healthProfile'] as Map?) ?? const {});
    final contact = hp['emergencyContact'];
    return PatientProfile(
      fullName: json['fullName']?.toString() ?? '',
      email: json['email']?.toString(),
      phone: json['phone']?.toString(),
      profileImage: json['profileImage']?.toString(),
      heightCm: _num(hp['heightCm']),
      weightKg: _num(hp['weightKg']),
      bmi: _num(hp['bmi']),
      bmiNote: hp['bmiNote']?.toString(),
      allergyStatus: hp['allergyStatus']?.toString() ?? notProvided,
      allergies: ((hp['allergies'] as List?) ?? const []).map((e) => e.toString()).toList(),
      emergencyContact: contact is Map ? EmergencyContact.fromJson(Map<String, dynamic>.from(contact)) : null,
      recordedAllergies: ((json['recordedAllergies'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => RecordedAllergy.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
    );
  }
}
