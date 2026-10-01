import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/appointment.dart';

/// Service handling patient and doctor appointment operations.
class AppointmentService {
  final ApiClient _apiClient;

  AppointmentService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  /// Patient creates a new appointment request.
  /// Throws [ConflictException] if HTTP 409 slot already booked.
  Future<Appointment> createAppointment({
    required String doctorId,
    String? availabilityId,
    required String date,
    required String startTime,
    String? patientNote,
  }) async {
    final payload = <String, dynamic>{
      'doctorId': doctorId,
      'date': date,
      'startTime': startTime,
    };
    if (availabilityId != null && availabilityId.isNotEmpty) {
      payload['availabilityId'] = availabilityId;
    }
    if (patientNote != null && patientNote.trim().isNotEmpty) {
      payload['patientNote'] = patientNote.trim();
    }

    final response = await _apiClient.post(
      ApiConstants.appointmentsEndpoint,
      body: payload,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      if (response.containsKey('appointment') &&
          response['appointment'] is Map<String, dynamic>) {
        return Appointment.fromJson(
            response['appointment'] as Map<String, dynamic>);
      }
      return Appointment.fromJson(response);
    }
    throw Exception('Unexpected response format when creating appointment.');
  }

  /// Patient retrieves their appointment history.
  Future<AppointmentListResponse> getMyAppointments({
    int page = 1,
    int limit = 20,
    String? status,
  }) async {
    final queryParams = <String>[
      'page=$page',
      'limit=$limit',
    ];
    if (status != null && status.trim().isNotEmpty && status.trim().toUpperCase() != 'ALL') {
      queryParams.add('status=${status.trim().toUpperCase()}');
    }

    final endpoint = '${ApiConstants.myAppointmentsEndpoint}?${queryParams.join('&')}';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return AppointmentListResponse.fromJson(response);
    }
    return AppointmentListResponse(items: [], page: page, limit: limit, total: 0, totalPages: 0);
  }

  /// Retrieve appointment details (patient or doctor access).
  Future<Appointment> getAppointmentDetail(String appointmentId) async {
    final endpoint = ApiConstants.appointmentDetailEndpoint(appointmentId);
    final response = await _apiClient.get(endpoint, includeAuth: true);
    return Appointment.fromJson(response as Map<String, dynamic>);
  }

  /// Patient cancels their own appointment.
  Future<Appointment> cancelPatientAppointment(
    String appointmentId, {
    String? reason,
  }) async {
    final endpoint = ApiConstants.cancelAppointmentEndpoint(appointmentId);
    final body = <String, dynamic>{};
    if (reason != null && reason.trim().isNotEmpty) {
      body['reason'] = reason.trim();
    }

    final response = await _apiClient.post(
      endpoint,
      body: body,
      includeAuth: true,
    );
    return Appointment.fromJson(response as Map<String, dynamic>);
  }

  /// Doctor retrieves their assigned appointments.
  Future<AppointmentListResponse> getDoctorAppointments({
    int page = 1,
    int limit = 20,
    String? date,
    String? status,
  }) async {
    final queryParams = <String>[
      'page=$page',
      'limit=$limit',
    ];
    if (date != null && date.trim().isNotEmpty) {
      queryParams.add('date=${date.trim()}');
    }
    if (status != null && status.trim().isNotEmpty && status.trim().toUpperCase() != 'ALL') {
      queryParams.add('status=${status.trim().toUpperCase()}');
    }

    final endpoint = '${ApiConstants.doctorMyAppointmentsEndpoint}?${queryParams.join('&')}';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return AppointmentListResponse.fromJson(response);
    }
    return AppointmentListResponse(items: [], page: page, limit: limit, total: 0, totalPages: 0);
  }

  /// Doctor confirms a PENDING appointment.
  Future<Appointment> confirmDoctorAppointment(String appointmentId) async {
    final endpoint = ApiConstants.doctorConfirmAppointmentEndpoint(appointmentId);
    final response = await _apiClient.post(
      endpoint,
      includeAuth: true,
    );
    return Appointment.fromJson(response as Map<String, dynamic>);
  }

  /// Doctor marks a CONFIRMED appointment as COMPLETED.
  Future<Appointment> completeDoctorAppointment(String appointmentId) async {
    final endpoint = ApiConstants.doctorCompleteAppointmentEndpoint(appointmentId);
    final response = await _apiClient.post(
      endpoint,
      includeAuth: true,
    );
    return Appointment.fromJson(response as Map<String, dynamic>);
  }

  /// Doctor cancels an appointment.
  Future<Appointment> cancelDoctorAppointment(
    String appointmentId, {
    String? reason,
  }) async {
    final endpoint = ApiConstants.doctorCancelAppointmentEndpoint(appointmentId);
    final body = <String, dynamic>{};
    if (reason != null && reason.trim().isNotEmpty) {
      body['reason'] = reason.trim();
    }

    final response = await _apiClient.post(
      endpoint,
      body: body,
      includeAuth: true,
    );
    return Appointment.fromJson(response as Map<String, dynamic>);
  }
}
