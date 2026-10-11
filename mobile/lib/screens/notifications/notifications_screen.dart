import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../models/notification_model.dart';
import '../../providers/auth_provider.dart';
import '../../providers/notification_provider.dart';

/// Full-featured in-app Notification Center for MediConnect patients and doctors.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<NotificationProvider>();
      provider.fetchNotifications(refresh: true);
    });

    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      context.read<NotificationProvider>().loadMore();
    }
  }

  String _formatRelativeTime(DateTime dateTime) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inSeconds < 60) {
      return 'Just now';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours}h ago';
    } else if (difference.inDays == 1) {
      return 'Yesterday';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}d ago';
    } else {
      return '${dateTime.day}/${dateTime.month}/${dateTime.year}';
    }
  }

  void _handleNotificationTap(NotificationModel item) {
    final provider = context.read<NotificationProvider>();
    if (!item.isRead) {
      provider.markAsRead(item.id);
    }

    final authProvider = context.read<AuthProvider>();
    final isDoctor = authProvider.user?.role == 'DOCTOR';

    // Route to appointment detail
    if (item.relatedAppointmentId != null && item.relatedAppointmentId!.isNotEmpty) {
      if (isDoctor) {
        Navigator.of(context).pushNamed(
          '/doctor/appointment-detail',
          arguments: {'appointmentId': item.relatedAppointmentId},
        );
      } else {
        Navigator.of(context).pushNamed(
          '/patient/appointment-detail',
          arguments: {'appointmentId': item.relatedAppointmentId},
        );
      }
    }
    // Route to payments
    else if ((item.relatedPaymentId != null && item.relatedPaymentId!.isNotEmpty) ||
        item.type == NotificationType.paymentSuccess ||
        item.type == NotificationType.paymentFailed) {
      Navigator.of(context).pushNamed('/patient/payments');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        elevation: 0,
        actions: [
          Consumer<NotificationProvider>(
            builder: (context, provider, _) {
              if (provider.unreadCount == 0) return const SizedBox.shrink();
              return TextButton.icon(
                key: const Key('mark_all_read_button'),
                icon: const Icon(Icons.done_all_rounded, size: 18),
                label: const Text('Mark all read'),
                onPressed: () => provider.markAllAsRead(),
                style: TextButton.styleFrom(
                  foregroundColor: AppTheme.primary,
                ),
              );
            },
          ),
        ],
      ),
      body: Consumer<NotificationProvider>(
        builder: (context, provider, _) {
          return Column(
            children: [
              // Filter chips (All / Unread)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                color: Colors.white,
                child: Row(
                  children: [
                    FilterChip(
                      label: const Text('All'),
                      selected: !provider.unreadOnly,
                      onSelected: (selected) {
                        if (selected) provider.toggleFilter(false);
                      },
                      selectedColor: AppTheme.primaryContainer,
                      checkmarkColor: AppTheme.primary,
                      labelStyle: TextStyle(
                        color: !provider.unreadOnly
                            ? AppTheme.primary
                            : AppTheme.textSecondary,
                        fontWeight: !provider.unreadOnly
                            ? FontWeight.bold
                            : FontWeight.normal,
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilterChip(
                      label: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text('Unread'),
                          if (provider.unreadCount > 0) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppTheme.primary,
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                '${provider.unreadCount}',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      selected: provider.unreadOnly,
                      onSelected: (selected) {
                        if (selected) provider.toggleFilter(true);
                      },
                      selectedColor: AppTheme.primaryContainer,
                      checkmarkColor: AppTheme.primary,
                      labelStyle: TextStyle(
                        color: provider.unreadOnly
                            ? AppTheme.primary
                            : AppTheme.textSecondary,
                        fontWeight: provider.unreadOnly
                            ? FontWeight.bold
                            : FontWeight.normal,
                      ),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),

              // Main Feed
              Expanded(
                child: _buildFeed(provider),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildFeed(NotificationProvider provider) {
    if (provider.isLoading && provider.notifications.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (provider.errorMessage != null && provider.notifications.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded,
                  size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(
                provider.errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => provider.fetchNotifications(refresh: true),
                child: const Text('Try Again'),
              ),
            ],
          ),
        ),
      );
    }

    if (provider.notifications.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: const BoxDecoration(
                  color: AppTheme.primaryContainer,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.notifications_none_rounded,
                  size: 56,
                  color: AppTheme.primary,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                provider.unreadOnly
                    ? 'No unread notifications'
                    : 'You\'re all caught up!',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                provider.unreadOnly
                    ? 'All your notifications have been marked as read.'
                    : 'When you receive appointment or payment updates, they will appear here.',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => provider.fetchNotifications(refresh: true),
      child: ListView.separated(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: provider.notifications.length + (provider.hasMore ? 1 : 0),
        separatorBuilder: (context, index) => const Divider(height: 1),
        itemBuilder: (context, index) {
          if (index == provider.notifications.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            );
          }

          final item = provider.notifications[index];
          return _buildNotificationTile(item);
        },
      ),
    );
  }

  Widget _buildNotificationTile(NotificationModel item) {
    final bool isUnread = !item.isRead;

    return Material(
      color: isUnread
          ? AppTheme.primaryContainer.withAlpha(50)
          : Colors.white,
      child: InkWell(
        onTap: () => _handleNotificationTap(item),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Notification type icon
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: item.iconColor.withAlpha(25),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  item.icon,
                  color: item.iconColor,
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),

              // Title, body, timestamp
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: isUnread
                                  ? FontWeight.w700
                                  : FontWeight.w600,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          _formatRelativeTime(item.createdAt),
                          style: TextStyle(
                            fontSize: 12,
                            color: isUnread
                                ? AppTheme.primary
                                : AppTheme.textSecondary,
                            fontWeight: isUnread
                                ? FontWeight.w600
                                : FontWeight.normal,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.body,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppTheme.textSecondary,
                        height: 1.35,
                      ),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (item.relatedAppointmentId != null ||
                        item.relatedPaymentId != null) ...[
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Text(
                            item.relatedAppointmentId != null
                                ? 'View Appointment'
                                : 'View Payment',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.primary,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(
                            Icons.arrow_forward_rounded,
                            size: 14,
                            color: AppTheme.primary,
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),

              // Unread dot indicator
              if (isUnread) ...[
                const SizedBox(width: 8),
                Container(
                  margin: const EdgeInsets.only(top: 6),
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppTheme.primary,
                    shape: BoxShape.circle,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
