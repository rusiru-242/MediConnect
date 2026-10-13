import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/notification_model.dart';
import 'package:mediconnect/providers/auth_provider.dart';
import 'package:mediconnect/providers/notification_provider.dart';
import 'package:mediconnect/screens/notifications/notifications_screen.dart';
import 'package:mediconnect/services/notification_service.dart';
import 'package:provider/provider.dart';

class MockNotificationService implements NotificationService {
  List<NotificationModel> mockItems = [];
  int mockUnreadCount = 0;

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
  Future<bool> markAsRead(String notificationId) async => true;

  @override
  Future<int> markAllAsRead() async {
    mockUnreadCount = 0;
    return 1;
  }

  @override
  Future<bool> registerDeviceToken(String fcmToken, {String deviceType = 'android'}) async => true;

  @override
  Future<bool> removeDeviceToken(String fcmToken) async => true;
}

void main() {
  group('NotificationsScreen Widget Tests', () {
    late MockNotificationService mockService;
    late NotificationProvider notificationProvider;
    late AuthProvider authProvider;

    setUp(() {
      mockService = MockNotificationService();
      notificationProvider = NotificationProvider(notificationService: mockService);
      authProvider = AuthProvider();
    });

    Widget createTestWidget() {
      return MultiProvider(
        providers: [
          ChangeNotifierProvider<NotificationProvider>.value(value: notificationProvider),
          ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
        ],
        child: const MaterialApp(
          home: NotificationsScreen(),
        ),
      );
    }

    testWidgets('Renders empty state when no notifications exist', (tester) async {
      mockService.mockItems = [];
      mockService.mockUnreadCount = 0;

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Notifications'), findsOneWidget);
      expect(find.text('You\'re all caught up!'), findsOneWidget);
      expect(find.byType(FilterChip), findsNWidgets(2));
    });

    testWidgets('Renders notifications feed and Mark all read button', (tester) async {
      mockService.mockItems = [
        NotificationModel(
          id: 'n1',
          recipientUserId: 'u1',
          type: NotificationType.appointmentConfirmed,
          title: 'Appointment Confirmed',
          body: 'Your doctor appointment is confirmed.',
          relatedAppointmentId: 'appt_1',
          isRead: false,
          createdAt: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
        NotificationModel(
          id: 'n2',
          recipientUserId: 'u1',
          type: NotificationType.paymentSuccess,
          title: 'Payment Successful',
          body: 'LKR 2,500 verified.',
          relatedPaymentId: 'pay_1',
          isRead: true,
          createdAt: DateTime.now().subtract(const Duration(hours: 2)),
        ),
      ];
      mockService.mockUnreadCount = 1;

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Appointment Confirmed'), findsOneWidget);
      expect(find.text('Payment Successful'), findsOneWidget);
      expect(find.text('View Appointment'), findsOneWidget);
      expect(find.text('View Payment'), findsOneWidget);
      expect(find.byKey(const Key('mark_all_read_button')), findsOneWidget);

      // Tap Mark all read
      await tester.tap(find.byKey(const Key('mark_all_read_button')));
      await tester.pumpAndSettle();

      // Button disappears when unreadCount is 0
      expect(find.byKey(const Key('mark_all_read_button')), findsNothing);
    });
  });
}
