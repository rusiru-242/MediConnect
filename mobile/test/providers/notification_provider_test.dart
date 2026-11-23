import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/notification_model.dart';
import 'package:mediconnect/providers/notification_provider.dart';
import 'package:mediconnect/services/notification_service.dart';

class FakeNotificationService implements NotificationService {
  List<NotificationModel> mockItems = [];
  int mockUnreadCount = 0;
  bool markAsReadCalled = false;
  bool markAllAsReadCalled = false;

  @override
  Future<NotificationListResponse> getNotifications({
    int page = 1,
    int limit = 20,
    bool unreadOnly = false,
  }) async {
    final filtered = unreadOnly ? mockItems.where((e) => !e.isRead).toList() : mockItems;
    return NotificationListResponse(
      items: filtered,
      total: filtered.length,
      page: page,
      limit: limit,
      totalPages: 1,
      unreadCount: mockUnreadCount,
    );
  }

  @override
  Future<int> getUnreadCount() async => mockUnreadCount;

  @override
  Future<bool> markAsRead(String notificationId) async {
    markAsReadCalled = true;
    return true;
  }

  @override
  Future<int> markAllAsRead() async {
    markAllAsReadCalled = true;
    return mockUnreadCount;
  }

  @override
  Future<bool> registerDeviceToken(String fcmToken, {String deviceType = 'android'}) async => true;

  @override
  Future<bool> removeDeviceToken(String fcmToken) async => true;
}

void main() {
  group('NotificationProvider Tests', () {
    late FakeNotificationService fakeService;
    late NotificationProvider provider;

    setUp(() {
      fakeService = FakeNotificationService();
      provider = NotificationProvider(notificationService: fakeService);
    });

    test('Initial state is empty', () {
      expect(provider.notifications, isEmpty);
      expect(provider.unreadCount, 0);
      expect(provider.isLoading, false);
      expect(provider.errorMessage, isNull);
    });

    test('fetchNotifications updates items and unread count', () async {
      final notif = NotificationModel(
        id: '1',
        recipientUserId: 'u1',
        type: NotificationType.bookingCreated,
        title: 'New Booking',
        body: 'Slot booked',
        isRead: false,
        createdAt: DateTime.now(),
      );
      fakeService.mockItems = [notif];
      fakeService.mockUnreadCount = 1;

      await provider.fetchNotifications(refresh: true);

      expect(provider.notifications.length, 1);
      expect(provider.notifications.first.id, '1');
      expect(provider.unreadCount, 1);
      expect(provider.isLoading, false);
    });

    test('markAsRead performs optimistic update', () async {
      final notif = NotificationModel(
        id: '1',
        recipientUserId: 'u1',
        type: NotificationType.system,
        title: 'Test',
        body: 'Body',
        isRead: false,
        createdAt: DateTime.now(),
      );
      fakeService.mockItems = [notif];
      fakeService.mockUnreadCount = 1;

      await provider.fetchNotifications(refresh: true);
      expect(provider.notifications.first.isRead, false);
      expect(provider.unreadCount, 1);

      await provider.markAsRead('1');

      expect(provider.notifications.first.isRead, true);
      expect(provider.unreadCount, 0);
      expect(fakeService.markAsReadCalled, true);
    });

    test('markAllAsRead marks all items read and resets count', () async {
      final n1 = NotificationModel(
        id: '1',
        recipientUserId: 'u1',
        type: NotificationType.system,
        title: 'T1',
        body: 'B1',
        isRead: false,
        createdAt: DateTime.now(),
      );
      final n2 = NotificationModel(
        id: '2',
        recipientUserId: 'u1',
        type: NotificationType.system,
        title: 'T2',
        body: 'B2',
        isRead: false,
        createdAt: DateTime.now(),
      );
      fakeService.mockItems = [n1, n2];
      fakeService.mockUnreadCount = 2;

      await provider.fetchNotifications(refresh: true);
      expect(provider.unreadCount, 2);

      await provider.markAllAsRead();

      expect(provider.unreadCount, 0);
      expect(provider.notifications.every((n) => n.isRead), true);
      expect(fakeService.markAllAsReadCalled, true);
    });
  });
}
