import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../core/network/api_client.dart';
import '../models/patient_profile.dart';

/// R02: the signed-in user's profile picture and (patients) profile data.
/// The backend always uses the authenticated identity; no user id is ever sent.
class ProfileService {
  final ApiClient _client;

  ProfileService({ApiClient? client}) : _client = client ?? ApiClient();

  Future<PatientProfile> myProfile() async {
    final response = await _client.get('/profile/me', includeAuth: true);
    return PatientProfile.fromJson(Map<String, dynamic>.from(response as Map));
  }

  /// Sends only the given fields; a null value clears that field on the server.
  Future<PatientProfile> updateProfile(Map<String, dynamic> changes) async {
    final response = await _client.patch('/profile/me', body: changes, includeAuth: true);
    return PatientProfile.fromJson(Map<String, dynamic>.from(response as Map));
  }

  /// Uploads a picture. [cropX], [cropY] and [cropSize] are fractions of the image (the square chosen on screen);
  /// the server crops, resizes to 512 x 512, strips metadata and stores it. Returns the new picture URL.
  Future<String> uploadPicture(
    List<int> bytes, {
    required String filename,
    double? cropX,
    double? cropY,
    double? cropSize,
    void Function(int sent, int total)? onProgress,
  }) async {
    final lower = filename.toLowerCase();
    final subtype = lower.endsWith('.png') ? 'png' : lower.endsWith('.webp') ? 'webp' : 'jpeg';
    final response = await _client.postMultipart(
      '/profile/me/picture',
      fields: {
        if (cropX != null) 'cropX': cropX.toStringAsFixed(5),
        if (cropY != null) 'cropY': cropY.toStringAsFixed(5),
        if (cropSize != null) 'cropSize': cropSize.toStringAsFixed(5),
      },
      files: [
        http.MultipartFile.fromBytes('file', bytes, filename: 'avatar.$subtype', contentType: MediaType('image', subtype)),
      ],
      includeAuth: true,
      onProgress: onProgress,
    );
    return (response as Map)['profileImage'] as String;
  }

  Future<void> removePicture() async {
    await _client.delete('/profile/me/picture', includeAuth: true);
  }
}
