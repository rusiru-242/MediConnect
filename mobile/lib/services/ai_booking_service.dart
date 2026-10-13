import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/booking_session.dart';

/// Service coordinating AI Conversational Booking sessions with MediConnect backend.
class AiBookingService {
  final ApiClient _apiClient;

  AiBookingService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  /// Create or initiate a new AI Booking session.
  Future<BookingSession> createSession({String? initialMessage}) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionsEndpoint,
      body: {
        if (initialMessage != null && initialMessage.trim().isNotEmpty)
          'initialMessage': initialMessage.trim(),
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when creating booking session.');
  }

  /// Retrieve current session state and transcript.
  Future<BookingSession> getSession(String sessionId) async {
    final response = await _apiClient.get(
      ApiConstants.aiBookingSessionDetailEndpoint(sessionId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching booking session.');
  }

  /// Post a conversational message from the patient.
  Future<BookingSession> sendMessage(String sessionId, String message) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionMessagesEndpoint(sessionId),
      body: {'message': message.trim()},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when sending message.');
  }

  /// Explicitly select a doctor from recommendation cards.
  Future<BookingSession> selectDoctor(String sessionId, String doctorId) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionSelectDoctorEndpoint(sessionId),
      body: {'doctorId': doctorId.trim()},
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when selecting doctor.');
  }

  /// Explicitly select an appointment slot from candidate slots.
  Future<BookingSession> selectSlot(
    String sessionId, {
    required String availabilityId,
    required String date,
    required String startTime,
    String? endTime,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionSelectSlotEndpoint(sessionId),
      body: {
        'availabilityId': availabilityId.trim(),
        'date': date.trim(),
        'startTime': startTime.trim(),
        if (endTime != null && endTime.trim().isNotEmpty)
          'endTime': endTime.trim(),
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when selecting slot.');
  }

  /// Explicitly confirm the booking hold before payment.
  Future<BookingSession> confirmBooking(
    String sessionId, {
    String? patientNote,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionConfirmEndpoint(sessionId),
      body: {
        if (patientNote != null && patientNote.trim().isNotEmpty)
          'patientNote': patientNote.trim(),
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when confirming booking.');
  }

  /// Cancel session and release any held slot.
  Future<BookingSession> cancelSession(String sessionId) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionCancelEndpoint(sessionId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when cancelling session.');
  }

  /// Sync payment and booking status authoritatively from backend.
  Future<BookingSession> syncPaymentStatus(String sessionId) async {
    final response = await _apiClient.get(
      ApiConstants.aiBookingSessionPaymentStatusEndpoint(sessionId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return BookingSession.fromJson(response);
    }
    throw Exception('Unexpected response format when checking payment status.');
  }
}
