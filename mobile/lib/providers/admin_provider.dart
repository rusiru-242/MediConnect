import 'package:flutter/foundation.dart';
import '../core/network/api_exceptions.dart';
import '../models/admin_doctor_application.dart';
import '../services/admin_service.dart';

/// Provider managing admin state for doctor applications and verification.
class AdminProvider extends ChangeNotifier {
  final AdminService _adminService;

  List<AdminDoctorApplicationSummary> _applications = [];
  AdminDoctorApplicationDetail? _selectedApplication;

  int _pendingCount = 0;
  int _approvedCount = 0;
  int _rejectedCount = 0;

  String _currentFilter = 'PENDING';
  bool _isLoading = false;
  bool _isActionLoading = false;
  String? _errorMessage;

  AdminProvider({AdminService? adminService})
      : _adminService = adminService ?? AdminService();

  List<AdminDoctorApplicationSummary> get applications => _applications;
  AdminDoctorApplicationDetail? get selectedApplication => _selectedApplication;

  int get pendingCount => _pendingCount;
  int get approvedCount => _approvedCount;
  int get rejectedCount => _rejectedCount;

  String get currentFilter => _currentFilter;
  bool get isLoading => _isLoading;
  bool get isActionLoading => _isActionLoading;
  String? get errorMessage => _errorMessage;

  void clearError() {
    if (_errorMessage != null) {
      _errorMessage = null;
      notifyListeners();
    }
  }

  void setFilter(String filter) {
    _currentFilter = filter;
    notifyListeners();
  }

  /// Fetch applications for the given status filter.
  Future<void> fetchApplications({String? status}) async {
    final activeFilter = status ?? _currentFilter;
    _currentFilter = activeFilter;
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _applications = await _adminService.getDoctorApplications(status: activeFilter);
      _isLoading = false;
      notifyListeners();

      // Refresh overall summary counts in background
      _refreshCountsInBackground();
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
    } catch (_) {
      _errorMessage = 'Unable to load doctor applications. Please try again.';
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _refreshCountsInBackground() async {
    try {
      final pending = await _adminService.getDoctorApplications(status: 'PENDING');
      final approved = await _adminService.getDoctorApplications(status: 'APPROVED');
      final rejected = await _adminService.getDoctorApplications(status: 'REJECTED');

      _pendingCount = pending.length;
      _approvedCount = approved.length;
      _rejectedCount = rejected.length;
      notifyListeners();
    } catch (_) {
      // Ignore background count failure
    }
  }

  /// Fetch full details for a single doctor application.
  Future<void> fetchApplicationDetail(String doctorProfileId) async {
    _isLoading = true;
    _errorMessage = null;
    _selectedApplication = null;
    notifyListeners();

    try {
      _selectedApplication =
          await _adminService.getDoctorApplicationDetail(doctorProfileId);
      _isLoading = false;
      notifyListeners();
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isLoading = false;
      notifyListeners();
    } catch (_) {
      _errorMessage = 'Unable to load application details.';
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Approve a doctor application.
  Future<bool> approveDoctor(String doctorProfileId) async {
    _isActionLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _adminService.approveDoctor(doctorProfileId);
      _isActionLoading = false;

      // Update selected application state locally if loaded
      if (_selectedApplication != null &&
          _selectedApplication!.doctorProfileId == doctorProfileId) {
        await fetchApplicationDetail(doctorProfileId);
      }

      await fetchApplications(status: _currentFilter);
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isActionLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'Unable to approve application. Please try again.';
      _isActionLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Reject a doctor application with a reason.
  Future<bool> rejectDoctor(String doctorProfileId, String reason) async {
    _isActionLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _adminService.rejectDoctor(doctorProfileId, reason);
      _isActionLoading = false;

      if (_selectedApplication != null &&
          _selectedApplication!.doctorProfileId == doctorProfileId) {
        await fetchApplicationDetail(doctorProfileId);
      }

      await fetchApplications(status: _currentFilter);
      return true;
    } on ApiException catch (e) {
      _errorMessage = e.message;
      _isActionLoading = false;
      notifyListeners();
      return false;
    } catch (_) {
      _errorMessage = 'Unable to reject application. Please try again.';
      _isActionLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Retrieve raw document bytes for viewing.
  Future<List<int>?> fetchDocumentBytes(
    String doctorProfileId,
    String documentKey,
  ) async {
    try {
      return await _adminService.getDoctorDocumentBytes(
        doctorProfileId,
        documentKey,
      );
    } on ApiException catch (e) {
      _errorMessage = e.message;
      notifyListeners();
      return null;
    } catch (_) {
      _errorMessage = 'Unable to load document.';
      notifyListeners();
      return null;
    }
  }
}
