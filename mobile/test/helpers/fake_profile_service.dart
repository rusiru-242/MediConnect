import 'package:mediconnect/core/network/api_exceptions.dart';
import 'package:mediconnect/models/patient_profile.dart';
import 'package:mediconnect/services/profile_service.dart';

/// R02 test double: an in-memory profile service (no network).
class FakeProfileService implements ProfileService {
  PatientProfile profile;
  bool failLoad = false;
  int uploadFailuresLeft = 0;
  int uploads = 0;
  int removals = 0;
  Map<String, dynamic>? lastChanges;
  Map<String, double?>? lastCrop;
  String nextUrl = '/api/profile/pictures/PAT-1?v=new1';

  FakeProfileService({PatientProfile? profile})
      : profile = profile ?? const PatientProfile(fullName: 'Jane Doe', email: 'jane@example.com');

  @override
  Future<PatientProfile> myProfile() async {
    if (failLoad) throw const NetworkException();
    return profile;
  }

  @override
  Future<PatientProfile> updateProfile(Map<String, dynamic> changes) async {
    lastChanges = changes;
    final json = <String, dynamic>{
      'fullName': changes['fullName'] ?? profile.fullName,
      'email': profile.email,
      'healthProfile': {
        'heightCm': changes.containsKey('heightCm') ? changes['heightCm'] : profile.heightCm,
        'weightKg': changes.containsKey('weightKg') ? changes['weightKg'] : profile.weightKg,
        'allergyStatus': changes['allergyStatus'] ?? profile.allergyStatus,
        'allergies': changes['allergies'] ?? profile.allergies,
        'emergencyContact': changes.containsKey('emergencyContact')
            ? changes['emergencyContact']
            : profile.emergencyContact?.toJson(),
      },
    };
    profile = PatientProfile.fromJson(json);
    return profile;
  }

  @override
  Future<String> uploadPicture(List<int> bytes,
      {required String filename, double? cropX, double? cropY, double? cropSize,
      void Function(int sent, int total)? onProgress}) async {
    uploads++;
    lastCrop = {'x': cropX, 'y': cropY, 'size': cropSize};
    onProgress?.call(bytes.length ~/ 2, bytes.length);
    if (uploadFailuresLeft > 0) {
      uploadFailuresLeft--;
      throw const NetworkException();
    }
    onProgress?.call(bytes.length, bytes.length);
    return nextUrl;
  }

  @override
  Future<void> removePicture() async {
    removals++;
  }
}
