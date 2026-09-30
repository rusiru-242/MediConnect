import 'package:flutter_test/flutter_test.dart';
import 'package:mediconnect/models/auth_session.dart';
import 'package:mediconnect/models/user_model.dart';

void main() {
  group('UserModel', () {
    test('fromJson correctly parses complete user payload', () {
      final json = {
        'id': '674c1f8a89b0',
        'fullName': 'Kasun Perera',
        'email': 'kasun@example.com',
        'phone': '+94771234567',
        'role': 'PATIENT',
        'emailVerified': true,
        'accountStatus': 'ACTIVE',
        'createdAt': '2026-09-30T10:00:00.000Z',
        'authProviders': ['LOCAL'],
      };

      final user = UserModel.fromJson(json);

      expect(user.id, '674c1f8a89b0');
      expect(user.fullName, 'Kasun Perera');
      expect(user.email, 'kasun@example.com');
      expect(user.phone, '+94771234567');
      expect(user.role, 'PATIENT');
      expect(user.emailVerified, true);
      expect(user.accountStatus, 'ACTIVE');
      expect(user.authProviders, ['LOCAL']);
    });

    test('toJson produces expected structure', () {
      final user = UserModel(
        id: '123',
        fullName: 'Jane Doe',
        email: 'jane@example.com',
        role: 'PATIENT',
        emailVerified: false,
        accountStatus: 'PENDING',
      );

      final json = user.toJson();

      expect(json['id'], '123');
      expect(json['fullName'], 'Jane Doe');
      expect(json['email'], 'jane@example.com');
      expect(json['emailVerified'], false);
    });
  });

  group('AuthSession', () {
    test('fromJson correctly parses auth login response', () {
      final json = {
        'message': 'Login successful.',
        'accessToken': 'jwt.access.token',
        'refreshToken': 'jwt.refresh.token',
        'tokenType': 'bearer',
        'expiresIn': 3600,
        'user': {
          'id': '999',
          'fullName': 'Test Patient',
          'email': 'patient@example.com',
          'role': 'PATIENT',
          'emailVerified': true,
          'accountStatus': 'ACTIVE',
        },
      };

      final session = AuthSession.fromJson(json);

      expect(session.message, 'Login successful.');
      expect(session.accessToken, 'jwt.access.token');
      expect(session.refreshToken, 'jwt.refresh.token');
      expect(session.expiresIn, 3600);
      expect(session.user.fullName, 'Test Patient');
      expect(session.user.email, 'patient@example.com');
    });
  });
}
