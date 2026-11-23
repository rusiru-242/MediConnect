import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../models/notification_model.dart';

/// Service interfacing with the MediConnect Notification API endpoints.
class NotificationService {
  final ApiClient _apiClient;

  NotificationService({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  /// Fetch paginated notifications for the authenticated user.
  Future<NotificationListResponse> getNotifications({
    int page = 1,
    int limit = 20,
    bool unreadOnly = false,
  }) async {
    final endpoint =
        '${ApiConstants.notificationsEndpoint}?page=$page&limit=$limit&unread_only=$unreadOnly';
    final response = await _apiClient.get(endpoint, includeAuth: true);

    if (response is Map<String, dynamic>) {
      return NotificationListResponse.fromJson(response);
    }
    throw Exception('Unexpected response format when fetching notifications.');
  }

  /// Get current unread notification count.
  Future<int> getUnreadCount() async {
    final response = await _apiClient.get(
      ApiConstants.unreadCountEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic> && response.containsKey('unreadCount')) {
      return (response['unreadCount'] as num).toInt();
    }
    return 0;
  }

  /// Mark a specific notification as read.
  Future<bool> markAsRead(String notificationId) async {
    final response = await _apiClient.patch(
      ApiConstants.readNotificationEndpoint(notificationId),
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return false;
  }

  /// Mark all unread notifications for current user as read.
  Future<int> markAllAsRead() async {
    final response = await _apiClient.patch(
      ApiConstants.readAllNotificationsEndpoint,
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return (response['modifiedCount'] as num?)?.toInt() ?? 0;
    }
    return 0;
  }

  /// Register or refresh an FCM device push token with the backend.
  Future<bool> registerDeviceToken(
    String fcmToken, {
    String deviceType = 'android',
  }) async {
    final response = await _apiClient.post(
      ApiConstants.deviceTokensEndpoint,
      body: {
        'fcmToken': fcmToken,
        'deviceType': deviceType,
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return false;
  }

  /// Remove an FCM device token on logout.
  Future<bool> removeDeviceToken(String fcmToken) async {
    final response = await _apiClient.delete(
      ApiConstants.deviceTokensEndpoint,
      body: {
        'fcmToken': fcmToken,
      },
      includeAuth: true,
    );

    if (response is Map<String, dynamic>) {
      return response['success'] == true;
    }
    return false;
  }
}
