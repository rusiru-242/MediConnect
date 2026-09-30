import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';

void main() {
  group('ApiException hierarchy', () {
    test('NetworkException provides user-friendly default message', () {
      const exception = NetworkException();
      expect(
        exception.message,
        'Unable to connect to MediConnect. Please check your internet connection and try again.',
      );
      expect(exception.toString(), exception.message);
    });

    test('AuthException stores message and 401 status code', () {
      const exception = AuthException(
        message: 'Invalid email or password.',
        statusCode: 401,
      );
      expect(exception.message, 'Invalid email or password.');
      expect(exception.statusCode, 401);
    });

    test('ValidationException stores details and 422 status code', () {
      const exception = ValidationException(
        message: 'Email format is invalid.',
        statusCode: 422,
        details: {'field': 'email'},
      );
      expect(exception.message, 'Email format is invalid.');
      expect(exception.statusCode, 422);
      expect(exception.details, isNotNull);
    });
  });
}
