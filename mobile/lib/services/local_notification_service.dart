import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

/// Callback for when a notification is tapped.
typedef NotificationTapCallback = void Function(String? payload);

/// Manages local privacy-preserving medication reminder notifications (Phase 22).
class LocalNotificationService {
  static final LocalNotificationService _instance = LocalNotificationService._internal();
  factory LocalNotificationService() => _instance;
  LocalNotificationService._internal();

  final FlutterLocalNotificationsPlugin _notificationsPlugin = FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;
  NotificationTapCallback? onNotificationTap;

  static const String _channelId = 'mediconnect_medication_reminders';
  static const String _channelName = 'Medication Reminders';
  static const String _channelDesc =
      'Privacy-preserving daily reminders to check your medication schedule';

  /// Initialize timezones and local notifications plugin safely.
  Future<bool> initialize({NotificationTapCallback? onTap}) async {
    if (_isInitialized) return true;

    try {
      onNotificationTap = onTap;

      // 1. Initialize timezone database
      tz_data.initializeTimeZones();
      // Default to Asia/Colombo or local
      try {
        tz.setLocalLocation(tz.getLocation('Asia/Colombo'));
      } catch (_) {
        tz.setLocalLocation(tz.getLocation('UTC'));
      }

      // 2. Android and iOS settings
      const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
      const iosSettings = DarwinInitializationSettings(
        requestAlertPermission: false,
        requestBadgePermission: false,
        requestSoundPermission: false,
      );

      const initSettings = InitializationSettings(
        android: androidSettings,
        iOS: iosSettings,
      );

      final initialized = await _notificationsPlugin.initialize(
        settings: initSettings,
        onDidReceiveNotificationResponse: (NotificationResponse response) {
          debugPrint('[Notification] Tapped payload: ${response.payload}');
          onNotificationTap?.call(response.payload);
        },
      );

      _isInitialized = initialized ?? true;
      debugPrint('[Notification] LocalNotificationService initialized: $_isInitialized');
      return _isInitialized;
    } catch (e) {
      debugPrint('[Notification] Initialization warning (mocked in tests): $e');
      _isInitialized = false;
      return false;
    }
  }

  /// Request runtime notification permissions (required for Android 13+ and iOS).
  Future<bool> requestPermissions() async {
    try {
      if (kIsWeb) return false;

      if (defaultTargetPlatform == TargetPlatform.android) {
        final androidImpl = _notificationsPlugin
            .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
        if (androidImpl != null) {
          final granted = await androidImpl.requestNotificationsPermission();
          return granted ?? false;
        }
      } else if (defaultTargetPlatform == TargetPlatform.iOS) {
        final iosImpl = _notificationsPlugin
            .resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>();
        if (iosImpl != null) {
          final granted = await iosImpl.requestPermissions(
            alert: true,
            badge: true,
            sound: true,
          );
          return granted ?? false;
        }
      }
      return true;
    } catch (e) {
      debugPrint('[Notification] Permission request error: $e');
      return false;
    }
  }

  /// Check whether notifications are enabled for the app.
  Future<bool> areNotificationsEnabled() async {
    try {
      if (kIsWeb) return false;
      if (defaultTargetPlatform == TargetPlatform.android) {
        final androidImpl = _notificationsPlugin
            .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
        if (androidImpl != null) {
          return await androidImpl.areNotificationsEnabled() ?? true;
        }
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Schedule a daily privacy-preserving reminder notification at HH:MM local time.
  /// Note: Section 4 requirement: Never place diagnosis or sensitive drug names on lockscreen.
  Future<bool> scheduleDailyMedicationReminder({
    required int notificationId,
    required int hour,
    required int minute,
    required String payload,
  }) async {
    try {
      final now = tz.TZDateTime.now(tz.local);
      var scheduledDate = tz.TZDateTime(
        tz.local,
        now.year,
        now.month,
        now.day,
        hour,
        minute,
      );

      // If scheduled time has already passed today, schedule starting tomorrow
      if (scheduledDate.isBefore(now)) {
        scheduledDate = scheduledDate.add(const Duration(days: 1));
      }

      const androidDetails = AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDesc,
        importance: Importance.high,
        priority: Priority.high,
        ticker: 'Medication reminder',
      );

      const notificationDetails = NotificationDetails(
        android: androidDetails,
        iOS: DarwinNotificationDetails(),
      );

      // Privacy-preserving notification copy (Phase 22 requirement)
      const privacyTitle = "Medication Schedule Reminder";
      const privacyBody = "It's time to check your medication schedule.";

      await _notificationsPlugin.zonedSchedule(
        id: notificationId,
        title: privacyTitle,
        body: privacyBody,
        scheduledDate: scheduledDate,
        notificationDetails: notificationDetails,
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        matchDateTimeComponents: DateTimeComponents.time,
        payload: payload,
      );

      debugPrint('[Notification] Scheduled daily reminder #$notificationId at $hour:$minute');
      return true;
    } catch (e) {
      debugPrint('[Notification] Error scheduling notification: $e');
      return false;
    }
  }

  /// Cancel a specific scheduled notification by ID.
  Future<void> cancelReminder(int notificationId) async {
    try {
      await _notificationsPlugin.cancel(id: notificationId);
      debugPrint('[Notification] Cancelled notification #$notificationId');
    } catch (e) {
      debugPrint('[Notification] Error cancelling notification: $e');
    }
  }

  /// Cancel all scheduled medication reminders.
  Future<void> cancelAllReminders() async {
    try {
      await _notificationsPlugin.cancelAll();
      debugPrint('[Notification] Cancelled all scheduled notifications');
    } catch (e) {
      debugPrint('[Notification] Error cancelling all notifications: $e');
    }
  }
}
