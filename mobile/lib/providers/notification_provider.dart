import 'package:flutter/foundation.dart';

import '../models/notification_model.dart';
import '../services/notification_service.dart';

/// State management provider for in-app notifications and unread badge count.
class NotificationProvider extends ChangeNotifier {
  final NotificationService _notificationService;

  NotificationProvider({NotificationService? notificationService})
      : _notificationService = notificationService ?? NotificationService();

  List<NotificationModel> _notifications = [];
  int _unreadCount = 0;
  bool _isLoading = false;
  bool _isLoadingMore = false;
  int _currentPage = 1;
  int _totalPages = 1;
  String? _errorMessage;
  bool _unreadOnly = false;

  // Getters
  List<NotificationModel> get notifications => _notifications;
  int get unreadCount => _unreadCount;
  bool get isLoading => _isLoading;
  bool get isLoadingMore => _isLoadingMore;
  bool get hasMore => _currentPage < _totalPages;
  String? get errorMessage => _errorMessage;
  bool get unreadOnly => _unreadOnly;

  /// Fetch first page or refresh notification feed.
  Future<void> fetchNotifications({bool refresh = false, bool? unreadOnly}) async {
    if (unreadOnly != null) {
      _unreadOnly = unreadOnly;
    }

    if (refresh) {
      _currentPage = 1;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _notificationService.getNotifications(
        page: _currentPage,
        limit: 20,
        unreadOnly: _unreadOnly,
      );

      _notifications = response.items;
      _totalPages = response.totalPages;
      _unreadCount = response.unreadCount;
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Could not load notifications. Please try again.';
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Paginated infinite scroll loader for subsequent pages.
  Future<void> loadMore() async {
    if (_isLoadingMore || !hasMore || _isLoading) return;

    _isLoadingMore = true;
    notifyListeners();

    try {
      final nextPage = _currentPage + 1;
      final response = await _notificationService.getNotifications(
        page: nextPage,
        limit: 20,
        unreadOnly: _unreadOnly,
      );

      _currentPage = nextPage;
      _totalPages = response.totalPages;
      _unreadCount = response.unreadCount;
      _notifications.addAll(response.items);
      _isLoadingMore = false;
      notifyListeners();
    } catch (e) {
      _isLoadingMore = false;
      notifyListeners();
    }
  }

  /// Refresh badge count independently (e.g. periodically or on app resume).
  Future<void> refreshUnreadCount() async {
    try {
      final count = await _notificationService.getUnreadCount();
      _unreadCount = count;
      notifyListeners();
    } catch (_) {}
  }

  /// Mark single notification as read with optimistic UI update.
  Future<void> markAsRead(String id) async {
    final index = _notifications.indexWhere((n) => n.id == id);
    if (index != -1 && !_notifications[index].isRead) {
      _notifications[index] = _notifications[index].copyWith(
        isRead: true,
        readAt: DateTime.now(),
      );
      if (_unreadCount > 0) {
        _unreadCount--;
      }
      notifyListeners();

      try {
        await _notificationService.markAsRead(id);
      } catch (_) {
        // Safe silent rollback if needed, though backend will be updated on next fetch
      }
    }
  }

  /// Mark all unread notifications as read.
  Future<void> markAllAsRead() async {
    if (_unreadCount == 0) return;

    final now = DateTime.now();
    _notifications = _notifications
        .map((n) => n.isRead ? n : n.copyWith(isRead: true, readAt: now))
        .toList();
    _unreadCount = 0;
    notifyListeners();

    try {
      await _notificationService.markAllAsRead();
    } catch (_) {
      // Re-fetch count if error
      refreshUnreadCount();
    }
  }

  /// Toggle unread filter.
  void toggleFilter(bool unreadOnly) {
    if (_unreadOnly != unreadOnly) {
      _unreadOnly = unreadOnly;
      fetchNotifications(refresh: true);
    }
  }
}
