// Data models for Digital Prescriptions and Structured Medication Items (Phase 21).

class MedicationItem {
  final String medicationName;
  final String strength;
  final String dose;
  final String route;
  final String frequency;
  final String duration;
  final String quantity;
  final String? additionalInstructions;

  const MedicationItem({
    required this.medicationName,
    required this.strength,
    required this.dose,
    this.route = 'Oral',
    required this.frequency,
    required this.duration,
    required this.quantity,
    this.additionalInstructions,
  });

  factory MedicationItem.fromJson(Map<String, dynamic> json) {
    return MedicationItem(
      medicationName: json['medicationName']?.toString() ?? '',
      strength: json['strength']?.toString() ?? '',
      dose: json['dose']?.toString() ?? '',
      route: json['route']?.toString() ?? 'Oral',
      frequency: json['frequency']?.toString() ?? '',
      duration: json['duration']?.toString() ?? '',
      quantity: json['quantity']?.toString() ?? '',
      additionalInstructions: json['additionalInstructions']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'medicationName': medicationName,
      'strength': strength,
      'dose': dose,
      'route': route,
      'frequency': frequency,
      'duration': duration,
      'quantity': quantity,
      if (additionalInstructions != null && additionalInstructions!.trim().isNotEmpty)
        'additionalInstructions': additionalInstructions!.trim(),
    };
  }
}

class Prescription {
  final String id;
  final String prescriptionId;
  final String medicalRecordId;
  final String appointmentId;
  final String patientUserId;
  final String? patientName;
  final String doctorUserId;
  final String? doctorName;
  final String? doctorSpecialty;
  final String? slmcRegistrationNumber;
  final String? hospitalOrClinic;
  final DateTime issuedAt;
  final String status;
  final List<MedicationItem> medicationItems;
  final String? instructions;
  final List<Map<String, dynamic>> amendmentHistory;

  const Prescription({
    required this.id,
    required this.prescriptionId,
    required this.medicalRecordId,
    required this.appointmentId,
    required this.patientUserId,
    this.patientName,
    required this.doctorUserId,
    this.doctorName,
    this.doctorSpecialty,
    this.slmcRegistrationNumber,
    this.hospitalOrClinic,
    required this.issuedAt,
    required this.status,
    required this.medicationItems,
    this.instructions,
    this.amendmentHistory = const [],
  });

  factory Prescription.fromJson(Map<String, dynamic> json) {
    final rawItems = json['medicationItems'];
    final itemsList = <MedicationItem>[];
    if (rawItems is List) {
      for (final item in rawItems) {
        if (item is Map<String, dynamic>) {
          itemsList.add(MedicationItem.fromJson(item));
        }
      }
    }

    final rawAmendments = json['amendmentHistory'];
    final amendmentsList = <Map<String, dynamic>>[];
    if (rawAmendments is List) {
      for (final a in rawAmendments) {
        if (a is Map<String, dynamic>) {
          amendmentsList.add(a);
        }
      }
    }

    DateTime parsedIssuedAt = DateTime.now();
    if (json['issuedAt'] != null) {
      parsedIssuedAt = DateTime.tryParse(json['issuedAt'].toString()) ?? DateTime.now();
    } else if (json['createdAt'] != null) {
      parsedIssuedAt = DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now();
    }

    return Prescription(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      prescriptionId: json['prescriptionId']?.toString() ?? '',
      medicalRecordId: json['medicalRecordId']?.toString() ?? '',
      appointmentId: json['appointmentId']?.toString() ?? '',
      patientUserId: json['patientUserId']?.toString() ?? '',
      patientName: json['patientName']?.toString(),
      doctorUserId: json['doctorUserId']?.toString() ?? '',
      doctorName: json['doctorName']?.toString(),
      doctorSpecialty: json['doctorSpecialty']?.toString(),
      slmcRegistrationNumber: json['slmcRegistrationNumber']?.toString(),
      hospitalOrClinic: json['hospitalOrClinic']?.toString(),
      issuedAt: parsedIssuedAt,
      status: json['status']?.toString() ?? 'ISSUED',
      medicationItems: itemsList,
      instructions: json['instructions']?.toString(),
      amendmentHistory: amendmentsList,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'prescriptionId': prescriptionId,
      'medicalRecordId': medicalRecordId,
      'appointmentId': appointmentId,
      'patientUserId': patientUserId,
      'patientName': patientName,
      'doctorUserId': doctorUserId,
      'doctorName': doctorName,
      'doctorSpecialty': doctorSpecialty,
      'slmcRegistrationNumber': slmcRegistrationNumber,
      'hospitalOrClinic': hospitalOrClinic,
      'issuedAt': issuedAt.toIso8601String(),
      'status': status,
      'medicationItems': medicationItems.map((e) => e.toJson()).toList(),
      'instructions': instructions,
      'amendmentHistory': amendmentHistory,
    };
  }
}
