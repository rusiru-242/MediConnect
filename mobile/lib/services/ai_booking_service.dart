import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../core/network/api_exceptions.dart';
import '../models/booking_session.dart';

/// Service coordinating AI Conversational Booking sessions with MediConnect backend.
class AiBookingService {
  final ApiClient _apiClient;

  AiBookingService({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  BookingSession _parseSession(dynamic response, String actionDescription) {
    if (response is Map<String, dynamic>) {
      try {
        return BookingSession.fromJson(response);
      } catch (e, stack) {
        if (kDebugMode) {
          debugPrint(
            '[AiBookingService] Failed to parse BookingSession ($actionDescription): $e\n$stack',
          );
        }
        throw const ApiException(
          message: 'Unable to process assistant response. Please try again.',
        );
      }
    }
    throw ApiException(
      message: 'Unexpected server response format while $actionDescription.',
    );
  }

  static const _conversations = '/ai/conversations';

  Future<List<Map<String, dynamic>>> listConversations({int offset = 0}) async {
    final response = await _apiClient.get('$_conversations?offset=$offset');
    return (response as List).cast<Map<String, dynamic>>();
  }

  Future<BookingSession> createConversation() async {
    final response = await _apiClient.post(_conversations, body: {});
    return _parseSession(response, 'starting a conversation');
  }

  Future<BookingSession> sendConversationMessage(
    String sessionId,
    String message,
    String requestId,
  ) async {
    final response = await _apiClient.post(
      '$_conversations/$sessionId/messages',
      body: {'message': message, 'requestId': requestId},
    );
    return _parseSession(response, 'sending a message');
  }

  Future<void> renameConversation(String id, String title) async {
    await _apiClient.patch('$_conversations/$id', body: {'title': title});
  }

  Future<void> deleteConversation(String id) async {
    await _apiClient.delete('$_conversations/$id');
  }

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

    return _parseSession(response, 'creating booking session');
  }

  /// Retrieve current session state and transcript.
  Future<BookingSession> getSession(String sessionId) async {
    final response = await _apiClient.get(
      ApiConstants.aiBookingSessionDetailEndpoint(sessionId),
      includeAuth: true,
    );

    return _parseSession(response, 'fetching booking session');
  }

  /// Post a conversational message from the patient (supports optional imageUrl).
  Future<BookingSession> sendMessage(
    String sessionId,
    String message, {
    String? imageUrl,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionMessagesEndpoint(sessionId),
      body: {
        'message': message.trim(),
        if (imageUrl != null && imageUrl.trim().isNotEmpty)
          'imageUrl': imageUrl.trim(),
      },
      includeAuth: true,
    );

    return _parseSession(response, 'sending message');
  }

  /// Upload a medicine packaging or label photo for OCR/vision analysis.
  Future<Map<String, dynamic>> uploadMedicineImage(
    List<int> bytes,
    String filename,
  ) async {
    final multipartFile = http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: filename,
    );
    final response = await _apiClient.postMultipart(
      ApiConstants.aiBookingUploadImageEndpoint,
      fields: {},
      files: [multipartFile],
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response;
    }
    throw const ApiException(
      message: 'Unexpected response format when uploading medicine image.',
    );
  }

  /// Send an image directly to the active session for OCR and analysis.
  Future<BookingSession> sendImageMessage(
    String sessionId,
    List<int> bytes,
    String filename, {
    String? message,
  }) async {
    final multipartFile = http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: filename,
    );
    final response = await _apiClient.postMultipart(
      ApiConstants.aiBookingSessionImageEndpoint(sessionId),
      fields: {
        if (message != null && message.trim().isNotEmpty)
          'message': message.trim(),
      },
      files: [multipartFile],
      includeAuth: true,
    );

    return _parseSession(response, 'sending image message');
  }

  Future<BookingSession> viewSlots(
    String sessionId,
    String doctorId,
    String date,
  ) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionSelectDoctorEndpoint(sessionId),
      body: {'doctorId': doctorId, 'date': date},
    );
    return _parseSession(response, 'checking appointment slots');
  }

  /// Explicitly select a doctor from recommendation cards.
  Future<BookingSession> selectDoctor(String sessionId, String doctorId) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionSelectDoctorEndpoint(sessionId),
      body: {'doctorId': doctorId.trim()},
      includeAuth: true,
    );

    return _parseSession(response, 'selecting doctor');
  }

  /// Explicitly select an appointment slot from candidate slots.
  Future<BookingSession> selectSlot(
    String sessionId, {
    required String availabilityId,
    required String date,
    required String startTime,
    String? endTime,
    bool prepareProposal = false,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionSelectSlotEndpoint(sessionId),
      body: {
        'availabilityId': availabilityId.trim(),
        'date': date.trim(),
        'startTime': startTime.trim(),
        if (prepareProposal) 'prepareProposal': true,
        if (endTime != null && endTime.trim().isNotEmpty)
          'endTime': endTime.trim(),
      },
      includeAuth: true,
    );

    return _parseSession(response, 'selecting slot');
  }

  /// Explicitly confirm the booking hold before payment.
  Future<BookingSession> confirmBooking(
    String sessionId, {
    String? patientNote,
    String? proposalId,
    bool smsConsent = false,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionConfirmEndpoint(sessionId),
      body: {
        if (proposalId != null) 'proposalId': proposalId,
        if (smsConsent) 'smsConsent': true,
        if (patientNote != null && patientNote.trim().isNotEmpty)
          'patientNote': patientNote.trim(),
      },
      includeAuth: true,
    );

    return _parseSession(response, 'confirming booking');
  }

  /// Cancel session and release any held slot.
  Future<BookingSession> cancelSession(String sessionId) async {
    final response = await _apiClient.post(
      ApiConstants.aiBookingSessionCancelEndpoint(sessionId),
      includeAuth: true,
    );

    return _parseSession(response, 'cancelling session');
  }

  /// Sync payment and booking status authoritatively from backend.
  Future<BookingSession> syncPaymentStatus(String sessionId) async {
    final response = await _apiClient.get(
      ApiConstants.aiBookingSessionPaymentStatusEndpoint(sessionId),
      includeAuth: true,
    );

    return _parseSession(response, 'checking payment status');
  }
}
