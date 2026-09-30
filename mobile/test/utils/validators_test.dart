import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/core/utils/validators.dart';

void main() {
  group('Validators', () {
    test('validateFullName enforces presence and length', () {
      expect(Validators.validateFullName(null), 'Full name is required.');
      expect(Validators.validateFullName(''), 'Full name is required.');
      expect(Validators.validateFullName('  '), 'Full name is required.');
      expect(Validators.validateFullName('A'), 'Full name must be at least 2 characters long.');
      expect(Validators.validateFullName('Kasun Perera'), isNull);
    });

    test('validateEmail checks standard email syntax', () {
      expect(Validators.validateEmail(null), 'Email address is required.');
      expect(Validators.validateEmail(''), 'Email address is required.');
      expect(Validators.validateEmail('invalid-email'), 'Please enter a valid email address.');
      expect(Validators.validateEmail('test@'), 'Please enter a valid email address.');
      expect(Validators.validateEmail('patient@example.com'), isNull);
    });

    test('validatePhone accepts valid Sri Lankan mobile numbers', () {
      expect(Validators.validatePhone(null), 'Phone number is required.');
      expect(Validators.validatePhone(''), 'Phone number is required.');
      expect(Validators.validatePhone('12345'), isNotNull);
      expect(Validators.validatePhone('0771234567'), isNull);
      expect(Validators.validatePhone('+94771234567'), isNull);
      expect(Validators.validatePhone('0719876543'), isNull);
      expect(Validators.validatePhone('+94719876543'), isNull);
      expect(Validators.validatePhone('0112345678'), isNotNull); // Landline not mobile
    });

    test('validatePassword enforces strong password requirements', () {
      expect(Validators.validatePassword(null), 'Password is required.');
      expect(Validators.validatePassword('short'), 'Password must be at least 8 characters long.');
      expect(Validators.validatePassword('alllowercase123!'), 'Password must contain at least one uppercase letter.');
      expect(Validators.validatePassword('ALLUPPERCASE123!'), 'Password must contain at least one lowercase letter.');
      expect(Validators.validatePassword('NoDigitsHere!'), 'Password must contain at least one number.');
      expect(Validators.validatePassword('NoSpecialChar123'), 'Password must contain at least one special character.');
      expect(Validators.validatePassword('Password@123'), isNull);
    });

    test('validateConfirmPassword ensures matching password', () {
      expect(Validators.validateConfirmPassword(null, 'Password@123'), 'Please confirm your password.');
      expect(Validators.validateConfirmPassword('Different@123', 'Password@123'), 'Passwords do not match.');
      expect(Validators.validateConfirmPassword('Password@123', 'Password@123'), isNull);
    });

    test('validateOtp ensures exactly 6 numeric digits', () {
      expect(Validators.validateOtp(null), 'Verification code is required.');
      expect(Validators.validateOtp(''), 'Verification code is required.');
      expect(Validators.validateOtp('12345'), 'Verification code must be exactly 6 digits.');
      expect(Validators.validateOtp('1234567'), 'Verification code must be exactly 6 digits.');
      expect(Validators.validateOtp('12345a'), 'Verification code must be exactly 6 digits.');
      expect(Validators.validateOtp('123456'), isNull);
    });
  });
}
