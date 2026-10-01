/// Base exception class for all MediConnect API communication.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic details;

  const ApiException({
    required this.message,
    this.statusCode,
    this.details,
  });

  @override
  String toString() => message;
}

/// Thrown when backend cannot be reached, connection drops, or request times out.
class NetworkException extends ApiException {
  const NetworkException({
    super.message =
        'Unable to connect to MediConnect. Please check your internet connection and try again.',
    super.statusCode,
  });
}

/// Thrown when credentials are invalid or session expired.
class AuthException extends ApiException {
  const AuthException({
    required super.message,
    super.statusCode,
  });
}

/// Thrown when request payload fails validation.
class ValidationException extends ApiException {
  const ValidationException({
    required super.message,
    super.statusCode,
    super.details,
  });
}

/// Thrown when a resource conflict occurs (e.g. HTTP 409 slot already booked).
class ConflictException extends ApiException {
  const ConflictException({
    required super.message,
    super.statusCode = 409,
    super.details,
  });
}
