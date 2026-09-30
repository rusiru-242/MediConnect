import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

import '../core/network/api_client.dart';
import '../core/network/api_exceptions.dart';
import '../core/storage/secure_storage_service.dart';
import '../models/auth_session.dart';
import '../models/doctor_application_status.dart';
import '../models/user_model.dart';
import '../services/auth_api_service.dart';
import '../services/google_auth_service.dart';

enum AuthStatus {
  initial,
  checking,
  authenticated,
  unauthenticated,
}

/// Authentication state provider managing user session, login, logout, and token recovery.
class AuthProvider extends ChangeNotifier {
  final AuthApiService _authApiService;
  final SecureStorageService _storageService;
  final GoogleAuthService _googleAuthService;

  AuthStatus _status = AuthStatus.initial;
  UserModel? _user;
  DoctorApplicationStatus? _doctorApplicationStatus;
  bool _isLoading = false;
  String? _errorMessage;

  AuthProvider({
    AuthApiService? authApiService,
    SecureStorageService? storageService,
    GoogleAuthService? googleAuthService,
  })  : _storageService = storageService ?? SecureStorageService(),
        _googleAuthService = googleAuthService ?? GoogleAuthService(),
        _authApiService =
            authApiService ?? AuthApiService(apiClient: ApiClient(storageService: storageService));

  AuthStatus get status => _status;
  UserModel? get user => _user;
  DoctorApplicationStatus? get doctorApplicationStatus => _doctorApplicationStatus;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _status == AuthStatus.authenticated;

  @visibleForTesting
  void setSessionForTesting(AuthSession session) {
    _user = session.user;
    _status = AuthStatus.authenticated;
    notifyListeners();
  }

  /// Clear any active error message.
  void clearError() {
    if (_errorMessage != null) {
      _errorMessage = null;
      notifyListeners();
    }
  }

  /// Verifies active session on application startup via GET /api/auth/me.
  /// Never relies solely on the presence of a token.
  Future<void> checkAuthSession() async {
    _status = AuthStatus.checking;
    _errorMessage = null;
    notifyListeners();

    try {
      final accessToken = await _storageService.getAccessToken();

      if (accessToken == null || accessToken.isEmpty) {
        _status = AuthStatus.unauthenticated;
        _user = null;
        notifyListeners();
        return;
      }

      // Token exists, verify with backend GET /api/auth/me
      // Note: ApiClient handles automatic refresh rotation on 401 if refresh token is available
      final user = await _authApiService.getCurrentUser();
      _user = user;
      _status = AuthStatus.authenticated;
      await _storageService.saveUserJson(jsonEncode(user.toJson()));
      notifyListeners();
    } on AuthException {
      // Token is invalid/expired and refresh failed
      await _storageService.clearAll();
      _user = null;
      _status = AuthStatus.unauthenticated;
      notifyListeners();
    } on NetworkException {
      // If offline, check if we have a valid cached user profile
      final cachedJson = await _storageService.getUserJson();
      if (cachedJson != null) {
        try {
          final decoded = jsonDecode(cachedJson) as Map<String, dynamic>;
          _user = UserModel.fromJson(decoded);
          _status = AuthStatus.authenticated;
          notifyListeners();
          return;
        } catch (_) {}
      }
      // Cannot verify and no cache available
      _user = null;
      _status = AuthStatus.unauthenticated;
      notifyListeners();
    } catch (_) {
      await _storageService.clearAll();
      _user = null;
      _status = AuthStatus.unauthenticated;
      notifyListeners();
    }
  }

  /// Authenticate patient credentials with POST /api/auth/login.
  Future<bool> login({
    required String email,
    required String password,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final session = await _authApiService.login(
        email: email,
        password: password,
      );

      // Store tokens securely
      await _storageService.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      // Cache user profile
      await _storageService.saveUserJson(jsonEncode(session.user.toJson()));

      _user = session.user;
      _status = AuthStatus.authenticated;
      _isLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _errorMessage = 'An unexpected error occurred. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Authenticate patient using Google Sign-In against POST /api/auth/google.
  ///
  /// Flow:
  /// 1. Interactively prompt account picker via Google Sign-In SDK.
  /// 2. If canceled by user, cleanly exit without error.
  /// 3. Extract real Google ID token.
  /// 4. Submit token to backend POST /api/auth/google.
  /// 5. Store MediConnect accessToken & refreshToken securely.
  /// 6. Set user session and notify listeners.
  Future<bool> signInWithGoogle() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final idToken = await _googleAuthService.authenticate();

      // Clean cancellation: user dismissed account picker without choosing an account
      if (idToken == null) {
        _isLoading = false;
        notifyListeners();
        return false;
      }

      if (idToken.trim().isEmpty) {
        _errorMessage = 'Google authentication did not provide an ID token. Please try again.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      final session = await _authApiService.authenticateWithGoogle(
        idToken: idToken,
      );

      // Store tokens securely in MediConnect storage
      await _storageService.saveTokens(
        accessToken: session.accessToken,
        refreshToken: session.refreshToken,
      );

      // Cache user profile safely
      await _storageService.saveUserJson(jsonEncode(session.user.toJson()));

      _user = session.user;
      _status = AuthStatus.authenticated;
      _isLoading = false;
      notifyListeners();
      return true;
    } on GoogleSignInException {
      _errorMessage = 'Google Sign-In could not be completed. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'Unable to connect to MediConnect. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Register a new patient account against POST /api/auth/register.
  /// Does NOT automatically log the patient in.
  Future<bool> register({
    required String fullName,
    required String email,
    required String phone,
    required String password,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _authApiService.registerPatient(
        fullName: fullName,
        email: email,
        phone: phone,
        password: password,
      );
      _isLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'An unexpected error occurred. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Register a new doctor account with documents against POST /api/auth/register-doctor.
  /// Does NOT automatically log the doctor in.
  Future<bool> registerDoctor({
    required String fullName,
    required String email,
    required String phone,
    required String password,
    required String specialty,
    required String medicalRegistrationNumber,
    required String qualifications,
    required String hospitalOrClinic,
    required int experienceYears,
    String? bio,
    required http.MultipartFile identityDocument,
    required http.MultipartFile medicalRegistrationDocument,
    required http.MultipartFile qualificationDocument,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _authApiService.registerDoctor(
        fullName: fullName,
        email: email,
        phone: phone,
        password: password,
        specialty: specialty,
        medicalRegistrationNumber: medicalRegistrationNumber,
        qualifications: qualifications,
        hospitalOrClinic: hospitalOrClinic,
        experienceYears: experienceYears,
        bio: bio,
        identityDocument: identityDocument,
        medicalRegistrationDocument: medicalRegistrationDocument,
        qualificationDocument: qualificationDocument,
      );
      _isLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'An unexpected error occurred during doctor registration. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Fetch application status for an authenticated doctor.
  Future<void> fetchDoctorApplicationStatus() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final appStatus = await _authApiService.getDoctorApplicationStatus();
      _doctorApplicationStatus = appStatus;
      _isLoading = false;
      notifyListeners();
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
    } catch (_) {
      _errorMessage = 'Unable to fetch application status. Please check your connection.';
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Verify email with submitted 6-digit OTP against POST /api/auth/verify-email.
  /// Does NOT automatically log the user in.
  Future<bool> verifyEmail({
    required String email,
    required String otp,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _authApiService.verifyEmail(
        email: email,
        otp: otp,
      );
      _isLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'An unexpected error occurred. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Resend verification OTP code against POST /api/auth/resend-verification.
  Future<String?> resendVerificationOtp({
    required String email,
  }) async {
    _errorMessage = null;
    try {
      final msg = await _authApiService.resendVerificationOtp(email: email);
      return msg;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      notifyListeners();
      return null;
    } catch (_) {
      _errorMessage = 'Unable to resend verification code. Please try again.';
      notifyListeners();
      return null;
    }
  }

  /// Request a password reset OTP against POST /api/auth/forgot-password.
  Future<String?> forgotPassword({
    required String email,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final message = await _authApiService.forgotPassword(email: email);
      _isLoading = false;
      notifyListeners();
      return message;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return null;
    } catch (_) {
      _errorMessage = 'Unable to request password reset. Please try again.';
      _isLoading = false;
      notifyListeners();
      return null;
    }
  }

  /// Verify 6-digit reset OTP against POST /api/auth/verify-reset-otp and obtain resetToken.
  Future<String?> verifyResetOtp({
    required String email,
    required String otp,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final resetToken = await _authApiService.verifyResetOtp(
        email: email,
        otp: otp,
      );
      _isLoading = false;
      notifyListeners();
      return resetToken;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return null;
    } catch (_) {
      _errorMessage = 'Unable to verify reset code. Please try again.';
      _isLoading = false;
      notifyListeners();
      return null;
    }
  }

  /// Reset password against POST /api/auth/reset-password using verified resetToken.
  Future<bool> resetPassword({
    required String resetToken,
    required String newPassword,
    required String confirmPassword,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _authApiService.resetPassword(
        resetToken: resetToken,
        newPassword: newPassword,
        confirmPassword: confirmPassword,
      );
      _isLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'Unable to reset password. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Log out patient, revoking session on backend and clearing secure storage.
  Future<void> logout() async {
    _isLoading = true;
    notifyListeners();

    try {
      final refreshToken = await _storageService.getRefreshToken();
      if (refreshToken != null && refreshToken.isNotEmpty) {
        try {
          await _authApiService.logout(refreshToken);
        } catch (_) {
          // Safe local session cleanup even if network request fails
        }
      }
    } finally {
      // Clear Google sign-in session to allow re-selection of account on subsequent sign-in
      await _googleAuthService.signOut();

      await _storageService.clearAll();
      _user = null;
      _doctorApplicationStatus = null;
      _status = AuthStatus.unauthenticated;
      _isLoading = false;
      _errorMessage = null;
      notifyListeners();
    }
  }
}
