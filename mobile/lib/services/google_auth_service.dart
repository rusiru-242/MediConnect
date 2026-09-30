import 'package:google_sign_in/google_sign_in.dart';

import '../core/constants/api_constants.dart';

/// Service responsible for managing Google Sign-In interaction on Flutter.
class GoogleAuthService {
  bool _initialized = false;

  /// Initializes the GoogleSignIn instance with the configured backend serverClientId (OAuth Web Client ID).
  Future<void> initialize({String? serverClientId}) async {
    if (!_initialized) {
      await GoogleSignIn.instance.initialize(
        serverClientId: serverClientId ?? ApiConstants.googleServerClientId,
      );
      _initialized = true;
    }
  }

  /// Triggers Google Sign-In interactive flow and returns the Google ID token.
  ///
  /// Returns `null` if the user cleanly cancels the account picker without selecting an account.
  /// Throws [GoogleSignInException] or platform exceptions if an error occurs.
  Future<String?> authenticate({String? serverClientId}) async {
    await initialize(serverClientId: serverClientId);

    try {
      final account = await GoogleSignIn.instance.authenticate();
      return account.authentication.idToken;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) {
        return null;
      }
      rethrow;
    }
  }

  /// Signs the user out of the Google session to ensure future account pickers allow re-selection.
  Future<void> signOut() async {
    try {
      await GoogleSignIn.instance.signOut();
    } catch (_) {
      // Safe no-op if Google sign-out fails or is not active
    }
  }
}
