import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/doctor.dart';
import '../models/doctor_availability.dart';

/// Service handling public doctor discovery, details, and doctor availability management.
class DoctorService {
  final ApiClient _apiClient;

  DoctorService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Retrieve paginated list of approved doctors for patients.
  Future<DoctorListResponse> getDoctors({
    int page = 1,
    int limit = 20,
    String? search,
    String? specialty,
  }) async {
    final queryParams = <String>[
      'page=$page',
      'limit=$limit',
    ];
    if (search != null && search.trim().isNotEmpty) {
      queryParams.add('search=${Uri.encodeComponent(search.trim())}');
    }
    if (specialty != null && specialty.trim().isNotEmpty && specialty.trim().toLowerCase() != 'all') {
      queryParams.add('specialty=${Uri.encodeComponent(specialty.trim())}');
    }

    final endpoint = '${ApiConstants.doctorsEndpoint}?${queryParams.join('&')}';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return DoctorListResponse.fromJson(response);
    }
    return DoctorListResponse(items: [], page: page, limit: limit, total: 0, totalPages: 0);
  }

  /// Retrieve detailed public profile for a specific approved doctor.
  Future<Doctor> getDoctorDetail(String doctorId) async {
    final endpoint = ApiConstants.doctorDetailEndpoint(doctorId);
    final response = await _apiClient.get(endpoint, includeAuth: true);
    return Doctor.fromJson(response as Map<String, dynamic>);
  }

  /// Retrieve generated available slots for an approved doctor.
  Future<List<DayAvailabilitySlots>> getDoctorAvailability(
    String doctorId, {
    String? date,
  }) async {
    final query = (date != null && date.trim().isNotEmpty) ? '?date=${date.trim()}' : '';
    final endpoint = '${ApiConstants.doctorSlotsEndpoint(doctorId)}$query';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is List) {
      return response
          .map((item) => DayAvailabilitySlots.fromJson(item as Map<String, dynamic>))
          .toList();
    } else if (response is Map<String, dynamic>) {
      if (response.containsKey('availabilities') && response['availabilities'] is List) {
        return (response['availabilities'] as List)
            .map((item) => DayAvailabilitySlots.fromJson(item as Map<String, dynamic>))
            .toList();
      }
      return [DayAvailabilitySlots.fromJson(response)];
    }
    return [];
  }

  /// Retrieve all availability schedules for the authenticated doctor.
  Future<List<DoctorAvailability>> getMyAvailabilities() async {
    final endpoint = ApiConstants.doctorMyAvailabilityEndpoint;
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is List) {
      return response
          .map((item) => DoctorAvailability.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  /// Create a new availability window for the authenticated doctor.
  Future<DoctorAvailability> createAvailability({
    required String date,
    required String startTime,
    required String endTime,
    int slotDurationMinutes = 30,
  }) async {
    final endpoint = ApiConstants.doctorMyAvailabilityEndpoint;
    final payload = {
      'date': date,
      'startTime': startTime,
      'endTime': endTime,
      'slotDurationMinutes': slotDurationMinutes,
    };
    final response = await _apiClient.post(endpoint, body: payload, includeAuth: true);
    return DoctorAvailability.fromJson(response as Map<String, dynamic>);
  }

  /// Update an existing availability window.
  Future<DoctorAvailability> updateAvailability(
    String availabilityId, {
    String? date,
    String? startTime,
    String? endTime,
    int? slotDurationMinutes,
    bool? isActive,
  }) async {
    final endpoint = ApiConstants.doctorAvailabilityDetailEndpoint(availabilityId);
    final payload = <String, dynamic>{};
    if (date != null) payload['date'] = date;
    if (startTime != null) payload['startTime'] = startTime;
    if (endTime != null) payload['endTime'] = endTime;
    if (slotDurationMinutes != null) payload['slotDurationMinutes'] = slotDurationMinutes;
    if (isActive != null) payload['isActive'] = isActive;

    final response = await _apiClient.put(endpoint, body: payload, includeAuth: true);
    return DoctorAvailability.fromJson(response as Map<String, dynamic>);
  }

  /// Soft-delete / deactivate an availability window.
  Future<void> deleteAvailability(String availabilityId) async {
    final endpoint = ApiConstants.doctorAvailabilityDetailEndpoint(availabilityId);
    await _apiClient.delete(endpoint, includeAuth: true);
  }
}
