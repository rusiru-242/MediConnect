import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../storage/secure_storage_service.dart';

/// Centralized API configuration for MediConnect.
class ApiConstants {
  ApiConstants._();

  /// Optional compile-time environment override via --dart-define=API_BASE_URL=...
  ///
  /// Examples:
  /// - Physical Android device with ADB reverse:
  ///   --dart-define=API_BASE_URL=http://127.0.0.1:8000
  /// - Android Emulator:
  ///   --dart-define=API_BASE_URL=http://10.0.2.2:8000
  /// - Custom network IP:
  ///   --dart-define=API_BASE_URL=http://192.168.248.238:8000
  static const String _envBaseUrl = String.fromEnvironment('API_BASE_URL');

  static String? _activeHostBaseUrl;
  static Completer<String?>? _activeDetectCompleter;

  /// Cleans any trailing slash or '/api' suffix to get the raw host URL.
  static String cleanHostUrl(String url) {
    var cleaned = url.trim();
    if (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    if (cleaned.endsWith('/api')) {
      cleaned = cleaned.substring(0, cleaned.length - 4);
    }
    if (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    return cleaned;
  }

  /// Centralized backend default host URL without trailing slash or '/api' prefix.
  static String get defaultHostBaseUrl {
    if (_envBaseUrl.isNotEmpty) {
      return cleanHostUrl(_envBaseUrl);
    }
    if (kIsWeb) {
      return 'http://127.0.0.1:8000';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      // 127.0.0.1 works seamlessly with `adb reverse tcp:8000 tcp:8000`
      return 'http://127.0.0.1:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  /// Active backend host URL.
  static String get hostBaseUrl => _activeHostBaseUrl ?? defaultHostBaseUrl;

  /// Default API base URL ending with '/api'.
  static String get defaultBaseUrl => '$defaultHostBaseUrl/api';

  /// Active API base URL ending with '/api'.
  static String get baseUrl => '$hostBaseUrl/api';

  /// Setter allowing runtime override.
  static set baseUrl(String value) {
    setBaseUrl(value);
  }

  /// Explicitly updates active base URL.
  static void setBaseUrl(String value) {
    _activeHostBaseUrl = cleanHostUrl(value);
  }

  /// Resets active base URL back to default.
  static void resetToDefault() {
    _activeHostBaseUrl = null;
  }

  /// Candidate host URLs to probe for connectivity.
  static List<String> get candidateHostUrls {
    final list = <String>[];
    if (_envBaseUrl.isNotEmpty) {
      list.add(cleanHostUrl(_envBaseUrl));
    }
    if (kIsWeb) {
      list.add('http://127.0.0.1:8000');
    } else if (defaultTargetPlatform == TargetPlatform.android) {
      // 1. Physical phone over USB with ADB reverse
      list.add('http://127.0.0.1:8000');
      // 2. Local Wi-Fi / Hotspot LAN IP of host machine
      list.add('http://192.168.248.238:8000');
      // 3. Android Emulator loopback
      list.add('http://10.0.2.2:8000');
    } else {
      list.add('http://127.0.0.1:8000');
    }
    return list;
  }

  /// Discovers and configures the active backend host on startup.
  static Future<void> initialize({
    SecureStorageService? storageService,
    http.Client? client,
  }) async {
    final storage = storageService ?? SecureStorageService();
    try {
      final savedUrl = await storage.getServerUrl();
      if (savedUrl != null && savedUrl.trim().isNotEmpty) {
        setBaseUrl(savedUrl.trim());
        if (kDebugMode) {
          debugPrint('[ApiConfig] Using saved server URL: $baseUrl');
        }
        return;
      }
    } catch (_) {}

    // Auto-probe candidate URLs concurrently
    await autoDetectBaseUrl(storageService: storage, client: client);
  }

  /// Concurrently probes candidate endpoints to auto-detect which host is reachable.
  /// - If [force] is false and a custom server URL is already saved, the saved URL is respected.
  /// - Deduplicates overlapping concurrent scans to prevent redundant network traffic.
  /// - Probes only the anonymous /health endpoint without transmitting any patient data or tokens.
  static Future<String?> autoDetectBaseUrl({
    SecureStorageService? storageService,
    http.Client? client,
    bool force = false,
  }) async {
    // If an auto-detection is already in progress, await its result rather than launching a duplicate scan
    if (_activeDetectCompleter != null) {
      return _activeDetectCompleter!.future;
    }

    final completer = Completer<String?>();
    _activeDetectCompleter = completer;

    try {
      final storage = storageService ?? SecureStorageService();
      String? savedUrl;
      try {
        savedUrl = await storage.getServerUrl();
      } catch (_) {}

      // If user manually saved a server URL and not forced, respect it without overriding
      if (!force && savedUrl != null && savedUrl.trim().isNotEmpty) {
        setBaseUrl(savedUrl.trim());
        completer.complete(baseUrl);
        return baseUrl;
      }

      final httpClient = client ?? http.Client();
      final candidates = <String>[];
      if (savedUrl != null && savedUrl.trim().isNotEmpty) {
        candidates.add(cleanHostUrl(savedUrl));
      }
      for (final h in candidateHostUrls) {
        if (!candidates.contains(h)) {
          candidates.add(h);
        }
      }

      final futures = candidates.map((host) async {
        try {
          final uri = Uri.parse('$host/health');
          // Anonymous GET check only - no auth headers, cookies, or sensitive data
          final response = await httpClient.get(uri).timeout(
            const Duration(milliseconds: 1500),
          );
          if (response.statusCode == 200) {
            return host;
          }
        } catch (_) {}
        return null;
      });

      final results = await Future.wait(futures);
      final workingHost = results.firstWhere((h) => h != null, orElse: () => null);
      if (workingHost != null) {
        setBaseUrl(workingHost);
        if (kDebugMode) {
          debugPrint('[ApiConfig] Auto-detected reachable backend: $baseUrl');
        }
        completer.complete(baseUrl);
        return baseUrl;
      }
      completer.complete(null);
      return null;
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[ApiConfig] Auto-detection completed without match: $e');
      }
      completer.complete(null);
      return null;
    } finally {
      _activeDetectCompleter = null;
    }
  }

  // Request timeout duration
  static const Duration timeoutDuration = Duration(seconds: 15);

  // Authentication endpoints
  static const String loginEndpoint = '/auth/login';
  static const String registerEndpoint = '/auth/register';
  static const String verifyEmailEndpoint = '/auth/verify-email';
  static const String resendVerificationEndpoint = '/auth/resend-verification';
  static const String forgotPasswordEndpoint = '/auth/forgot-password';
  static const String verifyResetOtpEndpoint = '/auth/verify-reset-otp';
  static const String resetPasswordEndpoint = '/auth/reset-password';
  static const String refreshEndpoint = '/auth/refresh';
  static const String logoutEndpoint = '/auth/logout';
  static const String meEndpoint = '/auth/me';
  static const String googleAuthEndpoint = '/auth/google';
  static const String registerDoctorEndpoint = '/auth/register-doctor';

  // Doctor endpoints
  static const String doctorApplicationStatusEndpoint = '/doctors/me/application-status';
  static const String doctorsEndpoint = '/doctors';
  static String doctorDetailEndpoint(String id) => '/doctors/$id';
  static String doctorSlotsEndpoint(String id) => '/doctors/$id/availability';
  static const String doctorMyAvailabilityEndpoint = '/doctors/me/availability';
  static String doctorAvailabilityDetailEndpoint(String id) => '/doctors/me/availability/$id';

  // AI Recommendation endpoints
  static const String aiDoctorRecommendationsEndpoint = '/ai/doctor-recommendations';

  // AI Booking Assistant endpoints (Phase 19)
  static const String aiBookingSessionsEndpoint = '/ai/booking/sessions';
  static String aiBookingSessionDetailEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId';
  static String aiBookingSessionMessagesEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId/messages';
  static String aiBookingSessionSelectDoctorEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId/select-doctor';
  static String aiBookingSessionSelectSlotEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId/select-slot';
  static String aiBookingSessionConfirmEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId/confirm';
  static String aiBookingSessionCancelEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId/cancel';
  static String aiBookingSessionPaymentStatusEndpoint(String sessionId) => '/ai/booking/sessions/$sessionId/payment-status';

  // Admin endpoints
  static const String adminDoctorApplicationsEndpoint = '/admin/doctors/applications';
  static String adminDoctorApplicationDetailEndpoint(String id) => '/admin/doctors/applications/$id';
  static String adminDoctorDocumentEndpoint(String id, String docKey) =>
      '/admin/doctors/applications/$id/documents/$docKey';
  static String adminDoctorApproveEndpoint(String id) => '/admin/doctors/$id/approve';
  static String adminDoctorRejectEndpoint(String id) => '/admin/doctors/$id/reject';

  // Appointment endpoints
  static const String appointmentsEndpoint = '/appointments';
  static const String myAppointmentsEndpoint = '/appointments/me';
  static String appointmentDetailEndpoint(String id) => '/appointments/$id';
  static String cancelAppointmentEndpoint(String id) => '/appointments/$id/cancel';

  // Doctor Appointment endpoints
  static const String doctorMyAppointmentsEndpoint = '/doctors/me/appointments';
  static String doctorConfirmAppointmentEndpoint(String id) => '/doctors/me/appointments/$id/confirm';
  static String doctorCompleteAppointmentEndpoint(String id) => '/doctors/me/appointments/$id/complete';
  static String doctorCancelAppointmentEndpoint(String id) => '/doctors/me/appointments/$id/cancel';

  // Payment endpoints
  static const String createPaymentIntentEndpoint = '/payments/create-intent';
  static String paymentStatusEndpoint(String paymentId) => '/payments/$paymentId/status';
  static const String paymentHistoryEndpoint = '/payments/me';

  // Notification endpoints
  static const String notificationsEndpoint = '/notifications';
  static const String unreadCountEndpoint = '/notifications/unread-count';
  static String readNotificationEndpoint(String id) => '/notifications/$id/read';
  static const String readAllNotificationsEndpoint = '/notifications/read-all';
  static const String deviceTokensEndpoint = '/notifications/devices';

  /// Stripe Publishable Key (safe for mobile client).
  /// Backend returns publishableKey in create-intent response, or can be passed via env.
  static const String defaultStripePublishableKey = String.fromEnvironment(
    'STRIPE_PUBLISHABLE_KEY',
    defaultValue: 'pk_test_51MockKeyForStripeInitializationMediConnect0001',
  );

  /// Google OAuth Web Client ID (audience for ID tokens verified by backend).
  static const String googleServerClientId =
      '80346479357-pe3nov35fcpamn13q49llh4hc4amc1lj.apps.googleusercontent.com';
}
