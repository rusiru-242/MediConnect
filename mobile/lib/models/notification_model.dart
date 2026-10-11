import 'package:flutter/material.dart';

/// Supported notification types matching the MediConnect backend.
enum NotificationType {
  bookingCreated,
  appointmentConfirmed,
  appointmentCancelled,
  appointmentCompleted,
  paymentSuccess,
  paymentFailed,
  appointmentReminder24h,
  appointmentReminder1h,
  system,
}

extension NotificationTypeExtension on NotificationType {
  static NotificationType fromString(String? type) {
    switch (type) {
      case 'BOOKING_CREATED':
        return NotificationType.bookingCreated;
      case 'APPOINTMENT_CONFIRMED':
        return NotificationType.appointmentConfirmed;
      case 'APPOINTMENT_CANCELLED':
        return NotificationType.appointmentCancelled;
      case 'APPOINTMENT_COMPLETED':
        return NotificationType.appointmentCompleted;
      case 'PAYMENT_SUCCESS':
        return NotificationType.paymentSuccess;
      case 'PAYMENT_FAILED':
        return NotificationType.paymentFailed;
      case 'APPOINTMENT_REMINDER_24H':
        return NotificationType.appointmentReminder24h;
      case 'APPOINTMENT_REMINDER_1H':
        return NotificationType.appointmentReminder1h;
      default:
        return NotificationType.system;
    }
  }

  String get rawValue {
    switch (this) {
      case NotificationType.bookingCreated:
        return 'BOOKING_CREATED';
      case NotificationType.appointmentConfirmed:
        return 'APPOINTMENT_CONFIRMED';
      case NotificationType.appointmentCancelled:
        return 'APPOINTMENT_CANCELLED';
      case NotificationType.appointmentCompleted:
        return 'APPOINTMENT_COMPLETED';
      case NotificationType.paymentSuccess:
        return 'PAYMENT_SUCCESS';
      case NotificationType.paymentFailed:
        return 'PAYMENT_FAILED';
      case NotificationType.appointmentReminder24h:
        return 'APPOINTMENT_REMINDER_24H';
      case NotificationType.appointmentReminder1h:
        return 'APPOINTMENT_REMINDER_1H';
      case NotificationType.system:
        return 'SYSTEM';
    }
  }
}

/// Data model representing an in-app notification.
class NotificationModel {
  final String id;
  final String recipientUserId;
  final NotificationType type;
  final String title;
  final String body;
  final String? relatedAppointmentId;
  final String? relatedPaymentId;
  final bool isRead;
  final DateTime? readAt;
  final DateTime createdAt;

  const NotificationModel({
    required this.id,
    required this.recipientUserId,
    required this.type,
    required this.title,
    required this.body,
    this.relatedAppointmentId,
    this.relatedPaymentId,
    required this.isRead,
    this.readAt,
    required this.createdAt,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id']?.toString() ?? json['_id']?.toString() ?? '',
      recipientUserId: json['recipientUserId']?.toString() ?? '',
      type: NotificationTypeExtension.fromString(json['type']?.toString()),
      title: json['title']?.toString() ?? '',
      body: json['body']?.toString() ?? '',
      relatedAppointmentId: json['relatedAppointmentId']?.toString(),
      relatedPaymentId: json['relatedPaymentId']?.toString(),
      isRead: json['isRead'] == true,
      readAt: json['readAt'] != null
          ? DateTime.tryParse(json['readAt'].toString())
          : null,
      createdAt: json['createdAt'] != null
          ? (DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now())
          : DateTime.now(),
    );
  }

  NotificationModel copyWith({
    String? id,
    String? recipientUserId,
    NotificationType? type,
    String? title,
    String? body,
    String? relatedAppointmentId,
    String? relatedPaymentId,
    bool? isRead,
    DateTime? readAt,
    DateTime? createdAt,
  }) {
    return NotificationModel(
      id: id ?? this.id,
      recipientUserId: recipientUserId ?? this.recipientUserId,
      type: type ?? this.type,
      title: title ?? this.title,
      body: body ?? this.body,
      relatedAppointmentId: relatedAppointmentId ?? this.relatedAppointmentId,
      relatedPaymentId: relatedPaymentId ?? this.relatedPaymentId,
      isRead: isRead ?? this.isRead,
      readAt: readAt ?? this.readAt,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  IconData get icon {
    switch (type) {
      case NotificationType.bookingCreated:
        return Icons.calendar_today_rounded;
      case NotificationType.appointmentConfirmed:
        return Icons.event_available_rounded;
      case NotificationType.appointmentCancelled:
        return Icons.event_busy_rounded;
      case NotificationType.appointmentCompleted:
        return Icons.task_alt_rounded;
      case NotificationType.paymentSuccess:
        return Icons.check_circle_rounded;
      case NotificationType.paymentFailed:
        return Icons.error_outline_rounded;
      case NotificationType.appointmentReminder24h:
      case NotificationType.appointmentReminder1h:
        return Icons.alarm_rounded;
      case NotificationType.system:
        return Icons.notifications_rounded;
    }
  }

  Color get iconColor {
    switch (type) {
      case NotificationType.bookingCreated:
        return const Color(0xFF1E88E5); // Blue
      case NotificationType.appointmentConfirmed:
        return const Color(0xFF2E7D32); // Green
      case NotificationType.appointmentCancelled:
        return const Color(0xFFD32F2F); // Red
      case NotificationType.appointmentCompleted:
        return const Color(0xFF00897B); // Teal
      case NotificationType.paymentSuccess:
        return const Color(0xFF2E7D32); // Green
      case NotificationType.paymentFailed:
        return const Color(0xFFC62828); // Red
      case NotificationType.appointmentReminder24h:
      case NotificationType.appointmentReminder1h:
        return const Color(0xFFF57C00); // Orange
      case NotificationType.system:
        return const Color(0xFF5E35B1); // Purple
    }
  }
}

/// Paginated notifications container.
class NotificationListResponse {
  final List<NotificationModel> items;
  final int total;
  final int page;
  final int limit;
  final int totalPages;
  final int unreadCount;

  const NotificationListResponse({
    required this.items,
    required this.total,
    required this.page,
    required this.limit,
    required this.totalPages,
    required this.unreadCount,
  });

  factory NotificationListResponse.fromJson(Map<String, dynamic> json) {
    final list = json['items'] as List<dynamic>? ?? [];
    return NotificationListResponse(
      items: list
          .map((e) => NotificationModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: (json['total'] as num?)?.toInt() ?? 0,
      page: (json['page'] as num?)?.toInt() ?? 1,
      limit: (json['limit'] as num?)?.toInt() ?? 20,
      totalPages: (json['totalPages'] as num?)?.toInt() ?? 1,
      unreadCount: (json['unreadCount'] as num?)?.toInt() ?? 0,
    );
  }
}
