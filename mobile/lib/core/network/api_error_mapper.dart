import 'dart:async';
import 'dart:io';

import 'api_exceptions.dart';

/// Centralized mapper to convert raw backend responses, HTTP status codes,
/// and FastAPI 422 validation errors into short, friendly MediConnect UI messages.
///
/// Prevents exposing technical backend internals (Pydantic, database, stack traces).
class ApiErrorMapper {
  ApiErrorMapper._();

  // Canonical MediConnect user-friendly error strings
  static const String invalidEmailMessage = 'Please enter a valid email address.';
  static const String duplicateEmailMessage = 'An account with this email already exists.';
  static const String invalidPhoneMessage = 'Please enter a valid mobile number.';
  static const String weakPasswordMessage = 'Please use a stronger password.';
  static const String incorrectCredentialsMessage = 'Incorrect email or password.';
  static const String emailNotVerifiedMessage = 'Please verify your email before logging in.';
  static const String invalidOtpMessage = 'The verification code is incorrect.';
  static const String expiredOtpMessage = 'The verification code has expired. Please request a new code.';
  static const String networkFailureMessage = 'Unable to connect to MediConnect. Please try again.';
  static const String serverErrorMessage = 'Something went wrong. Please try again.';
  static const String defaultValidationMessage = 'Invalid information provided. Please check your inputs.';

  /// Technical marker substrings that must NEVER be shown to end users.
  static const List<String> _technicalKeywords = [
    'value error',
    'value_error',
    'validation error',
    'type error',
    'type_error',
    'syntax error',
    'syntaxerror',
    'nameerror',
    'traceback',
    'pymongo',
    'mongodb',
    'internal server error',
    'database error',
    'exception',
    'pydantic',
    'sqlite',
    'sql',
    'insert_one',
    'find_one',
    '[object object]',
  ];

  /// Maps an HTTP response body and status code to a safe, user-friendly message.
  static String fromResponseBody(dynamic body, int statusCode) {
    // 1. If body is a Map, inspect 'detail', 'message', or 'error'
    if (body is Map<String, dynamic>) {
      final detail = body['detail'];

      // Case A: FastAPI 422 RequestValidationError list
      if (detail is List && detail.isNotEmpty) {
        final mappedFromList = _mapValidationList(detail, statusCode);
        if (mappedFromList != null) {
          return mappedFromList;
        }
      }

      // Case B: detail is a single string (HTTPException)
      if (detail is String && detail.trim().isNotEmpty) {
        return _mapMessageText(detail, statusCode);
      }

      // Case C: detail is a nested Map
      if (detail is Map && detail['msg'] != null) {
        return _mapMessageText(detail['msg'].toString(), statusCode);
      }

      // Case D: 'message' field
      if (body['message'] is String && (body['message'] as String).trim().isNotEmpty) {
        return _mapMessageText(body['message'] as String, statusCode);
      }

      // Case E: 'error' field
      if (body['error'] is String && (body['error'] as String).trim().isNotEmpty) {
        return _mapMessageText(body['error'] as String, statusCode);
      }
    }

    // 2. Fall back to status code defaults
    return _statusFallback(statusCode);
  }

  /// Inspects a FastAPI 422 validation error list:
  /// [
  ///   {
  ///     "type": "value_error",
  ///     "loc": ["body", "email"],
  ///     "msg": "...",
  ///     "input": "..."
  ///   }
  /// ]
  static String? _mapValidationList(List<dynamic> list, int statusCode) {
    // Check all error items, prioritizing known user-facing fields
    for (final item in list) {
      if (item is! Map) continue;

      // Check 'loc' field path
      final loc = item['loc'];
      final rawMsg = item['msg']?.toString() ?? '';

      if (loc is List) {
        final locStrings = loc.map((e) => e.toString().toLowerCase()).toList();

        // 1. Email field
        if (locStrings.any((s) => s.contains('email'))) {
          return invalidEmailMessage;
        }

        // 2. Phone field
        if (locStrings.any((s) => s.contains('phone') || s.contains('mobile'))) {
          return invalidPhoneMessage;
        }

        // 3. Password fields
        if (locStrings.any((s) => s.contains('password'))) {
          final msgLower = rawMsg.toLowerCase();
          if (msgLower.contains('required') || msgLower.contains('missing')) {
            return 'Password is required.';
          }
          return weakPasswordMessage;
        }

        // 4. Full name
        if (locStrings.any((s) => s == 'fullname' || s == 'name')) {
          return 'Please enter a valid full name.';
        }

        // 5. OTP / Verification code
        if (locStrings.any((s) => s == 'otp' || s == 'code')) {
          return invalidOtpMessage;
        }

        // 6. Doctor specific fields
        if (locStrings.any((s) => s.contains('medicalregistrationnumber') || s.contains('license'))) {
          return 'Please enter a valid medical registration number.';
        }
        if (locStrings.any((s) => s.contains('specialty'))) {
          return 'Please select a valid medical specialty.';
        }
        if (locStrings.any((s) => s.contains('qualifications'))) {
          return 'Please enter your medical qualifications.';
        }
        if (locStrings.any((s) => s.contains('hospitalorclinic'))) {
          return 'Please enter your hospital or clinic affiliation.';
        }
        if (locStrings.any((s) => s.contains('experienceyears'))) {
          return 'Please enter valid years of experience.';
        }
        if (locStrings.any((s) =>
            s.contains('document') || s.contains('file') || s.contains('identity') || s.contains('qualification'))) {
          return 'Please upload the required verification documents.';
        }

        // 7. Appointment booking date / time
        if (locStrings.any((s) => s.contains('date') || s.contains('starttime') || s.contains('endtime'))) {
          return 'Please select a valid date and time.';
        }
      }

      // If loc didn't match a specific field, try mapping the item's message
      if (rawMsg.isNotEmpty) {
        final mapped = _mapMessageText(rawMsg, statusCode);
        if (mapped != serverErrorMessage && mapped != defaultValidationMessage) {
          return mapped;
        }
      }
    }

    return null;
  }

  /// Maps a raw backend message string to a user-friendly UI message.
  static String _mapMessageText(String rawMessage, int? statusCode) {
    var cleaned = rawMessage.trim();

    // Strip common technical prefixes
    if (cleaned.startsWith('Value error, ')) {
      cleaned = cleaned.substring('Value error, '.length).trim();
    } else if (cleaned.startsWith('Validation error: ')) {
      cleaned = cleaned.substring('Validation error: '.length).trim();
    }

    final lower = cleaned.toLowerCase();

    // 1. Login credentials check (must precede email format check)
    if (_isLoginCredentialsError(lower, statusCode)) {
      return incorrectCredentialsMessage;
    }

    // 2. Email format / invalid email errors (including Pydantic / email-validator)
    if (_isEmailFormatError(lower)) {
      return invalidEmailMessage;
    }

    // 3. Duplicate email / account already exists
    if (lower.contains('already exists') ||
        lower.contains('duplicate') ||
        lower.contains('email is already registered')) {
      return duplicateEmailMessage;
    }

    // 4. Phone format errors
    if (_isPhoneFormatError(lower)) {
      return invalidPhoneMessage;
    }

    // 5. Password strength / requirements
    if (_isPasswordStrengthError(lower)) {
      return weakPasswordMessage;
    }

    // 6. Email verification required
    if (lower.contains('verify your email') ||
        lower.contains('email verification is required') ||
        lower.contains('email not verified') ||
        lower.contains('pending verification')) {
      return emailNotVerifiedMessage;
    }

    // 7. OTP expired
    if ((lower.contains('expired') || lower.contains('expiration')) &&
        (lower.contains('otp') || lower.contains('code') || lower.contains('verification'))) {
      return expiredOtpMessage;
    }

    // 8. OTP incorrect
    if ((lower.contains('incorrect') || lower.contains('invalid') || lower.contains('wrong')) &&
        (lower.contains('otp') || lower.contains('code') || lower.contains('verification'))) {
      return invalidOtpMessage;
    }

    // 9. OTP attempt limit
    if (lower.contains('maximum verification attempts') || lower.contains('maximum attempts')) {
      return 'Maximum attempts exceeded. Please request a new code.';
    }

    // 10. Resend cooldown message (keep friendly cooldown count if present)
    if (lower.contains('please wait') && lower.contains('seconds')) {
      return cleaned;
    }

    // 11. Appointment slot conflict
    if (lower.contains('slot') || lower.contains('no longer available') || lower.contains('already booked')) {
      return 'This time slot is no longer available.';
    }

    // 12. Cannot book in the past
    if (lower.contains('in the past')) {
      return 'Cannot book an appointment in the past.';
    }

    // 13. Account suspended
    if (lower.contains('suspended') || lower.contains('deactivated')) {
      return 'Your account is suspended. Please contact support.';
    }

    // 14. Reset token invalid / expired
    if (lower.contains('reset token') || (lower.contains('token') && lower.contains('expired'))) {
      return 'The reset link has expired. Please request a new one.';
    }

    // 15. Check for technical leaking (stack traces, Pydantic details, database errors)
    if (_containsTechnicalLeak(lower)) {
      if (statusCode != null && statusCode >= 500) {
        return serverErrorMessage;
      }
      if (statusCode == 422) {
        return defaultValidationMessage;
      }
      return serverErrorMessage;
    }

    // 16. If the message is already clean, concise, and user-friendly, display it
    if (cleaned.isNotEmpty && cleaned.length < 150) {
      return cleaned;
    }

    return _statusFallback(statusCode);
  }

  /// Maps an exception or error object thrown in the Flutter app to a safe message.
  static String mapException(Object error) {
    if (error is NetworkException) {
      return networkFailureMessage;
    }
    if (error is SocketException || error is TimeoutException || error is HttpException) {
      return networkFailureMessage;
    }
    if (error is AuthException) {
      return _mapMessageText(error.message, error.statusCode ?? 401);
    }
    if (error is ValidationException) {
      if (error.details != null) {
        return fromResponseBody(error.details, 422);
      }
      return _mapMessageText(error.message, 422);
    }
    if (error is ConflictException) {
      if (error.details != null) {
        return fromResponseBody(error.details, 409);
      }
      return _mapMessageText(error.message, 409);
    }
    if (error is ApiException) {
      if (error.details != null) {
        return fromResponseBody(error.details, error.statusCode ?? 400);
      }
      return _mapMessageText(error.message, error.statusCode);
    }

    final errorString = error.toString().toLowerCase();
    if (errorString.contains('socket') ||
        errorString.contains('connection') ||
        errorString.contains('network') ||
        errorString.contains('failed host lookup') ||
        errorString.contains('timeout')) {
      return networkFailureMessage;
    }

    return serverErrorMessage;
  }

  // --- Helper detection methods ---

  static bool _isEmailFormatError(String lower) {
    if (lower.contains('password')) return false;

    return lower.contains('value is not a valid email address') ||
        lower.contains('part after the @-sign') ||
        lower.contains('special-use or reserved name') ||
        lower.contains('reserved name that cannot be used with email') ||
        lower.contains('not a valid email') ||
        lower.contains('please enter a valid email') ||
        lower.contains('email format is invalid') ||
        (lower.contains('email') && lower.contains('format')) ||
        (lower.contains('email') && (lower.contains('invalid') || lower.contains('not valid')));
  }

  static bool _isPhoneFormatError(String lower) {
    return lower.contains('valid mobile number') ||
        lower.contains('valid phone') ||
        lower.contains('sri lankan mobile') ||
        lower.contains('invalid phone') ||
        lower.contains('invalid mobile') ||
        (lower.contains('phone') && (lower.contains('digit') || lower.contains('format')));
  }

  static bool _isPasswordStrengthError(String lower) {
    return lower.contains('password must') ||
        lower.contains('password should') ||
        lower.contains('use a stronger password') ||
        lower.contains('weak password') ||
        lower.contains('uppercase letter') ||
        lower.contains('lowercase letter') ||
        lower.contains('special character') ||
        lower.contains('at least 8 characters');
  }

  static bool _isLoginCredentialsError(String lower, int? statusCode) {
    return lower.contains('incorrect email or password') ||
        lower.contains('invalid email or password') ||
        lower.contains('invalid credentials') ||
        lower.contains('incorrect credentials') ||
        (statusCode == 401 && (lower.contains('password') || lower.contains('credential')));
  }

  static bool _containsTechnicalLeak(String lower) {
    for (final keyword in _technicalKeywords) {
      if (lower.contains(keyword)) {
        return true;
      }
    }
    return lower.contains('body.') || lower.contains('loc:');
  }

  static String _statusFallback(int? statusCode) {
    switch (statusCode) {
      case 400:
        return 'Invalid request. Please check your information.';
      case 401:
        return incorrectCredentialsMessage;
      case 403:
        return 'Access denied. You do not have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 409:
        return duplicateEmailMessage;
      case 422:
        return defaultValidationMessage;
      case 429:
        return 'Too many requests. Please wait a moment before trying again.';
      case 500:
      case 502:
      case 503:
      case 504:
        return serverErrorMessage;
      default:
        return serverErrorMessage;
    }
  }
}
