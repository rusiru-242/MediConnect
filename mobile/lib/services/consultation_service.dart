import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/consultation.dart';

/// Client API Service for Doctor Daily Schedule and Consultation Management (Phase 57).
class ConsultationService {
  final ApiClient _apiClient;

  ConsultationService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  /// Retrieve today's schedule, stats, and next patient in doctor's timezone.
  Future<DoctorDailySchedule> getTodaySchedule() async {
    final response = await _apiClient.get(
      ApiConstants.doctorScheduleTodayEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DoctorDailySchedule.fromJson(response);
    }
    throw Exception('Failed to load today schedule.');
  }

  /// Retrieve schedule for a specific date (YYYY-MM-DD).
  Future<DoctorDailySchedule> getScheduleByDate(String date) async {
    final response = await _apiClient.get(
      ApiConstants.doctorScheduleDateEndpoint(date),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DoctorDailySchedule.fromJson(response);
    }
    throw Exception('Failed to load schedule for date $date.');
  }

  /// Retrieve daily appointment statistics summary.
  Future<DailyScheduleStats> getScheduleSummary([String? date]) async {
    final response = await _apiClient.get(
      ApiConstants.doctorScheduleSummaryEndpoint(date),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return DailyScheduleStats.fromJson(response);
    }
    throw Exception('Failed to load schedule statistics.');
  }

  /// Retrieve full consultation details for an assigned appointment.
  Future<ConsultationDetail> getConsultationDetails(String appointmentId) async {
    final response = await _apiClient.get(
      ApiConstants.doctorConsultationDetailEndpoint(appointmentId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return ConsultationDetail.fromJson(response);
    }
    throw Exception('Failed to load consultation details.');
  }

  /// Start a consultation session for an appointment.
  Future<ConsultationSession> startConsultation(String appointmentId, {String? notes}) async {
    final response = await _apiClient.post(
      ApiConstants.doctorConsultationStartEndpoint(appointmentId),
      body: notes != null && notes.isNotEmpty ? {'notes': notes} : {},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return ConsultationSession.fromJson(response);
    }
    throw Exception('Failed to start consultation.');
  }

  /// Complete a consultation session for an appointment.
  Future<ConsultationSession> completeConsultation(String appointmentId, {String? notes}) async {
    final response = await _apiClient.post(
      ApiConstants.doctorConsultationCompleteEndpoint(appointmentId),
      body: notes != null && notes.isNotEmpty ? {'notes': notes} : {},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return ConsultationSession.fromJson(response);
    }
    throw Exception('Failed to complete consultation.');
  }
}
