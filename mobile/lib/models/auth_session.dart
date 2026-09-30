import 'user_model.dart';

/// Represents the authentication payload returned on successful login.
class AuthSession {
  final String message;
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final int expiresIn;
  final UserModel user;

  const AuthSession({
    required this.message,
    required this.accessToken,
    required this.refreshToken,
    this.tokenType = 'bearer',
    required this.expiresIn,
    required this.user,
  });

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(
      message: json['message']?.toString() ?? 'Login successful.',
      accessToken: json['accessToken']?.toString() ?? '',
      refreshToken: json['refreshToken']?.toString() ?? '',
      tokenType: json['tokenType']?.toString() ?? 'bearer',
      expiresIn: (json['expiresIn'] as num?)?.toInt() ?? 3600,
      user: UserModel.fromJson(json['user'] as Map<String, dynamic>),
    );
  }
}
