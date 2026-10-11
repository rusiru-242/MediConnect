import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'notification_service.dart';

/// Background message handler for FCM. Must be a top-level function.
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
    debugPrint('[FCM] Handling background message: ${message.messageId}');
  } catch (e) {
    debugPrint('[FCM] Error in background message handler: $e');
  }
}

/// Manages Firebase Cloud Messaging lifecycle, permissions, token synchronization,
/// and incoming push notification interactions safely.
class FcmService {
  static final FcmService _instance = FcmService._internal();
  factory FcmService() => _instance;
  FcmService._internal();

  final NotificationService _notificationService = NotificationService();
  final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

  bool _isInitialized = false;
  String? _currentToken;

  /// Check if Firebase Messaging is initialized
  bool get isInitialized => _isInitialized;

  /// Active FCM registration token
  String? get currentToken => _currentToken;

  /// Initialize Firebase app and messaging listeners safely without crashing.
  Future<void> initialize() async {
    if (_isInitialized) return;

    try {
      // 1. Initialize Firebase Core safely
      await Firebase.initializeApp();
      _isInitialized = true;
      debugPrint('[FCM] Firebase initialized successfully.');

      // 2. Register background handler
      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

      // 3. Request permissions (required for Android 13+ and iOS)
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission(
        alert: true,
        announcement: false,
        badge: true,
        carPlay: false,
        criticalAlert: false,
        provisional: false,
        sound: true,
      );
      debugPrint('[FCM] Permission status: ${settings.authorizationStatus}');

      // 4. Retrieve current device token
      try {
        _currentToken = await messaging.getToken();
        if (_currentToken != null && kDebugMode) {
          debugPrint('[FCM] Device token obtained: ${_currentToken!.substring(0, 10)}...');
        }
      } catch (tokenErr) {
        debugPrint('[FCM] Could not retrieve FCM token: $tokenErr');
      }

      // 5. Listen for token refresh events
      messaging.onTokenRefresh.listen((newToken) {
        _currentToken = newToken;
        debugPrint('[FCM] Device token refreshed.');
        // Automatically sync refreshed token with backend
        _notificationService.registerDeviceToken(
          newToken,
          deviceType: Platform.isIOS ? 'ios' : 'android',
        ).catchError((_) => false);
      });

      // 6. Foreground message listener
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        debugPrint('[FCM] Foreground message received: ${message.notification?.title}');
        _handleForegroundMessage(message);
      });

      // 7. Background app opened via notification tap
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        debugPrint('[FCM] Notification tapped while app in background.');
        routeFromMessage(message);
      });

      // 8. Terminated app launched via notification tap
      final initialMessage = await messaging.getInitialMessage();
      if (initialMessage != null) {
        debugPrint('[FCM] Terminated app launched via notification tap.');
        // Allow UI to mount before routing
        WidgetsBinding.instance.addPostFrameCallback((_) {
          routeFromMessage(initialMessage);
        });
      }
    } catch (e) {
      // Graceful fallback when Firebase config / Google Services are unavailable
      _isInitialized = false;
      debugPrint('[FCM] Firebase initialization skipped or failed: $e');
    }
  }

  /// Sync current device token to backend upon authenticated login.
  Future<void> syncTokenWithBackend() async {
    if (_currentToken == null || _currentToken!.isEmpty) {
      try {
        if (_isInitialized) {
          _currentToken = await FirebaseMessaging.instance.getToken();
        }
      } catch (_) {}
    }

    if (_currentToken != null && _currentToken!.isNotEmpty) {
      try {
        await _notificationService.registerDeviceToken(
          _currentToken!,
          deviceType: Platform.isIOS ? 'ios' : 'android',
        );
        debugPrint('[FCM] Token synchronized with backend successfully.');
      } catch (e) {
        debugPrint('[FCM] Failed to sync token with backend: $e');
      }
    }
  }

  /// Unregister device token upon user logout.
  Future<void> removeTokenOnLogout() async {
    if (_currentToken != null && _currentToken!.isNotEmpty) {
      try {
        await _notificationService.removeDeviceToken(_currentToken!);
        debugPrint('[FCM] Token removed from backend upon logout.');
      } catch (e) {
        debugPrint('[FCM] Error removing token from backend: $e');
      }
    }
  }

  /// Handle notification arriving while user is actively in the app.
  void _handleForegroundMessage(RemoteMessage message) {
    final context = navigatorKey.currentContext;
    if (context == null) return;

    final title = message.notification?.title ?? 'Notification';
    final body = message.notification?.body ?? '';

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
            if (body.isNotEmpty) Text(body, maxLines: 2, overflow: TextOverflow.ellipsis),
          ],
        ),
        action: SnackBarAction(
          label: 'View',
          textColor: Colors.white,
          onPressed: () => routeFromMessage(message),
        ),
        duration: const Duration(seconds: 4),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Route user to the appropriate screen based on notification payload data.
  void routeFromMessage(RemoteMessage message) {
    final nav = navigatorKey.currentState;
    if (nav == null) return;

    final data = message.data;
    final appointmentId = data['relatedAppointmentId']?.toString();
    final paymentId = data['relatedPaymentId']?.toString();
    final type = data['type']?.toString();

    if (appointmentId != null && appointmentId.isNotEmpty) {
      // Determine if appointment detail is for patient or doctor
      nav.pushNamed('/patient/appointment-detail', arguments: {'appointmentId': appointmentId});
    } else if (paymentId != null && paymentId.isNotEmpty || type == 'PAYMENT_SUCCESS' || type == 'PAYMENT_FAILED') {
      nav.pushNamed('/patient/payments');
    } else {
      nav.pushNamed('/notifications');
    }
  }
}
