import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/health_chat.dart';

/// Service coordinating AI Health Symptom Guidance & Doctor Referral sessions.
class AiHealthChatService {
  final ApiClient _apiClient;

  AiHealthChatService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  /// Create a new confidential health guidance session.
  Future<HealthChatSession> createSession({
    String language = 'en',
    bool consentGiven = true,
    String? initialMessage,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiHealthChatSessionsEndpoint,
      body: {
        'language': language,
        'consentGiven': consentGiven,
        if (initialMessage != null && initialMessage.trim().isNotEmpty)
          'initialMessage': initialMessage.trim(),
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return HealthChatSession.fromJson(response);
    }
    throw Exception('Unexpected response format when creating health chat session.');
  }

  /// Retrieve session state and messages transcript.
  Future<HealthChatSession> getSession(String sessionId) async {
    final response = await _apiClient.get(
      ApiConstants.aiHealthChatSessionDetailEndpoint(sessionId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return HealthChatSession.fromJson(response);
    }
    throw Exception('Unexpected response format when retrieving health chat session.');
  }

  /// Send patient conversational message.
  Future<HealthChatSession> sendMessage(
    String sessionId,
    String message, {
    String? language,
  }) async {
    final response = await _apiClient.post(
      ApiConstants.aiHealthChatSessionMessagesEndpoint(sessionId),
      body: {
        'message': message.trim(),
        if (language != null && language.isNotEmpty) 'language': language,

      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return HealthChatSession.fromJson(response);
    }
    throw Exception('Unexpected response format when sending health message.');
  }

  /// Permanently delete conversation transcript for patient privacy.
  Future<bool> deleteSession(String sessionId) async {
    final response = await _apiClient.delete(
      ApiConstants.aiHealthChatSessionDetailEndpoint(sessionId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return true;
  }
}
