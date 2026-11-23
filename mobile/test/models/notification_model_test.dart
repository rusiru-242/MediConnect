import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/notification_model.dart';

void main() {
  group('NotificationModel Tests', () {
    test('Correctly parses full notification JSON', () {
      final json = {
        'id': 'notif_123',
        'recipientUserId': 'user_456',
        'type': 'APPOINTMENT_CONFIRMED',
        'title': 'Appointment Confirmed',
        'body': 'Your appointment with Dr. John has been confirmed.',
        'relatedAppointmentId': 'appt_789',
        'relatedPaymentId': 'pay_012',
        'isRead': false,
        'readAt': null,
        'createdAt': '2026-10-11T10:00:00Z',
      };

      final model = NotificationModel.fromJson(json);

      expect(model.id, 'notif_123');
      expect(model.recipientUserId, 'user_456');
      expect(model.type, NotificationType.appointmentConfirmed);
      expect(model.title, 'Appointment Confirmed');
      expect(model.body, 'Your appointment with Dr. John has been confirmed.');
      expect(model.relatedAppointmentId, 'appt_789');
      expect(model.relatedPaymentId, 'pay_012');
      expect(model.isRead, false);
      expect(model.readAt, isNull);
      expect(model.createdAt, isA<DateTime>());
      expect(model.icon, isNotNull);
      expect(model.iconColor, isNotNull);
    });

    test('Correctly handles default fallback values for minimal JSON', () {
      final json = {
        '_id': 'notif_mongo_id',
        'recipientUserId': 'user_1',
        'title': 'Simple Alert',
        'body': 'Simple Body',
      };

      final model = NotificationModel.fromJson(json);

      expect(model.id, 'notif_mongo_id');
      expect(model.type, NotificationType.system);
      expect(model.isRead, false);
      expect(model.relatedAppointmentId, isNull);
    });

    test('copyWith updates specified fields only', () {
      final original = NotificationModel(
        id: '1',
        recipientUserId: 'u1',
        type: NotificationType.system,
        title: 'Original Title',
        body: 'Original Body',
        isRead: false,
        createdAt: DateTime.now(),
      );

      final updated = original.copyWith(isRead: true, title: 'New Title');

      expect(updated.id, original.id);
      expect(updated.isRead, true);
      expect(updated.title, 'New Title');
      expect(updated.body, original.body);
    });

    test('NotificationListResponse correctly parses paginated items', () {
      final json = {
        'items': [
          {
            'id': '1',
            'recipientUserId': 'u1',
            'type': 'PAYMENT_SUCCESS',
            'title': 'Payment Success',
            'body': 'Payment of LKR 2500 received.',
            'isRead': true,
            'createdAt': '2026-10-11T09:00:00Z',
          },
          {
            'id': '2',
            'recipientUserId': 'u1',
            'type': 'APPOINTMENT_REMINDER_24H',
            'title': 'Reminder',
            'body': 'Appointment tomorrow.',
            'isRead': false,
            'createdAt': '2026-10-11T09:30:00Z',
          },
        ],
        'total': 2,
        'page': 1,
        'limit': 20,
        'totalPages': 1,
        'unreadCount': 1,
      };

      final response = NotificationListResponse.fromJson(json);

      expect(response.total, 2);
      expect(response.unreadCount, 1);
      expect(response.items.length, 2);
      expect(response.items[0].type, NotificationType.paymentSuccess);
      expect(response.items[1].type, NotificationType.appointmentReminder24h);
    });
  });
}
