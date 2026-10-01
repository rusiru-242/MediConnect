import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/network/api_error_mapper.dart';
import 'package:mediconnect/core/network/api_exceptions.dart';

void main() {
  group('ApiErrorMapper', () {
    test('1. Maps FastAPI 422 email validation error to friendly message', () {
      final pydanticBody = {
        'detail': [
          {
            'type': 'value_error',
            'loc': ['body', 'email'],
            'msg':
                'value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email.',
            'input': 'test@example.com',
          }
        ]
      };

      final result = ApiErrorMapper.fromResponseBody(pydanticBody, 422);
      expect(result, 'Please enter a valid email address.');
      expect(result, isNot(contains('value is not a valid email address')));
      expect(result, isNot(contains('special-use or reserved name')));
      expect(result, isNot(contains('body.email')));
    });

    test('2. Maps raw string invalid email error to friendly message', () {
      final body = {
        'detail':
            'value is not a valid email address: The part after the @-sign is a special-use or reserved name that cannot be used with email.'
      };
      final result = ApiErrorMapper.fromResponseBody(body, 422);
      expect(result, 'Please enter a valid email address.');
    });

    test('3. Maps duplicate email (409) to friendly message', () {
      final body = {'detail': 'An account with this email already exists.'};
      expect(
        ApiErrorMapper.fromResponseBody(body, 409),
        'An account with this email already exists.',
      );

      // Fallback with empty body
      expect(
        ApiErrorMapper.fromResponseBody(null, 409),
        'An account with this email already exists.',
      );
    });

    test('4. Maps phone validation errors to friendly message', () {
      final pydanticPhoneBody = {
        'detail': [
          {
            'type': 'value_error',
            'loc': ['body', 'phone'],
            'msg': 'Value error, Invalid Sri Lankan mobile format.',
            'input': '12345',
          }
        ]
      };
      expect(
        ApiErrorMapper.fromResponseBody(pydanticPhoneBody, 422),
        'Please enter a valid mobile number.',
      );
    });

    test('5. Maps weak password errors to friendly message', () {
      final pydanticPasswordBody = {
        'detail': [
          {
            'type': 'value_error',
            'loc': ['body', 'password'],
            'msg': 'Value error, Password must contain at least one uppercase letter.',
          }
        ]
      };
      expect(
        ApiErrorMapper.fromResponseBody(pydanticPasswordBody, 422),
        'Please use a stronger password.',
      );
    });

    test('6. Maps login credential rejection to friendly message', () {
      final body = {'detail': 'Invalid email or password.'};
      expect(
        ApiErrorMapper.fromResponseBody(body, 401),
        'Incorrect email or password.',
      );
    });

    test('7. Maps unverified email to friendly message', () {
      final body = {
        'detail': 'Email verification is required before logging in. Please verify your email.'
      };
      expect(
        ApiErrorMapper.fromResponseBody(body, 403),
        'Please verify your email before logging in.',
      );
    });

    test('8. Maps invalid and expired OTP errors', () {
      final invalidOtpBody = {'detail': 'The verification code is incorrect.'};
      expect(
        ApiErrorMapper.fromResponseBody(invalidOtpBody, 400),
        'The verification code is incorrect.',
      );

      final expiredOtpBody = {
        'detail': 'The verification code has expired. Please request a new code.'
      };
      expect(
        ApiErrorMapper.fromResponseBody(expiredOtpBody, 400),
        'The verification code has expired. Please request a new code.',
      );
    });

    test('9. Maps network and connectivity exceptions', () {
      const netEx = NetworkException();
      expect(
        ApiErrorMapper.mapException(netEx),
        'Unable to connect to MediConnect. Please try again.',
      );

      final socketEx = const SocketException('Failed host lookup');
      expect(
        ApiErrorMapper.mapException(socketEx),
        'Unable to connect to MediConnect. Please try again.',
      );
    });

    test('10. Maps server errors and sanitizes technical leaks', () {
      final dbErrorBody = {
        'detail': 'A database error occurred while querying pymongo user collection.'
      };
      final result = ApiErrorMapper.fromResponseBody(dbErrorBody, 500);
      expect(result, 'Something went wrong. Please try again.');
      expect(result, isNot(contains('pymongo')));
      expect(result, isNot(contains('database')));
    });

    test('11. Doctor field loc mappings', () {
      final medRegBody = {
        'detail': [
          {
            'loc': ['body', 'medicalRegistrationNumber'],
            'msg': 'Field required',
            'type': 'missing',
          }
        ]
      };
      expect(
        ApiErrorMapper.fromResponseBody(medRegBody, 422),
        'Please enter a valid medical registration number.',
      );
    });
  });
}
