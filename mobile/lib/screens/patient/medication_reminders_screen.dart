import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/medication_reminder.dart';
import '../../services/medication_reminder_service.dart';
import 'create_medication_reminder_screen.dart';
import 'reminder_settings_screen.dart';

/// Primary hub for patient medication reminders, today's schedule, and adherence tracking (Phase 22).
class MedicationRemindersScreen extends StatefulWidget {
  final MedicationReminderService? service;

  const MedicationRemindersScreen({super.key, this.service});

  @override
  State<MedicationRemindersScreen> createState() => _MedicationRemindersScreenState();
}

class _MedicationRemindersScreenState extends State<MedicationRemindersScreen>
    with SingleTickerProviderStateMixin {
  late final MedicationReminderService _service;
  late final TabController _tabController;

  TodayScheduleResponse? _todaySchedule;
  List<MedicationReminder> _reminders = [];
  List<MedicationEvent> _history = [];
  AdherenceSummary? _adherence;

  bool _isLoadingToday = false;
  bool _isLoadingReminders = false;
  bool _isLoadingHistory = false;

  String? _todayError;
  String? _remindersError;
  String? _historyError;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? MedicationReminderService();
    _tabController = TabController(length: 3, vsync: this);
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    await Future.wait([
      _loadTodaySchedule(),
      _loadReminders(),
      _loadHistoryAndAdherence(),
    ]);
  }

  Future<void> _loadTodaySchedule() async {
    setState(() {
      _isLoadingToday = true;
      _todayError = null;
    });
    try {
      final schedule = await _service.getTodaySchedule();
      if (mounted) {
        setState(() {
          _todaySchedule = schedule;
          _isLoadingToday = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _todayError = e.toString().replaceAll('Exception:', '').trim();
          _isLoadingToday = false;
        });
      }
    }
  }

  Future<void> _loadReminders() async {
    setState(() {
      _isLoadingReminders = true;
      _remindersError = null;
    });
    try {
      final res = await _service.getReminders();
      if (mounted) {
        setState(() {
          _reminders = res.items;
          _isLoadingReminders = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _remindersError = e.toString().replaceAll('Exception:', '').trim();
          _isLoadingReminders = false;
        });
      }
    }
  }

  Future<void> _loadHistoryAndAdherence() async {
    setState(() {
      _isLoadingHistory = true;
      _historyError = null;
    });
    try {
      final histRes = await _service.getHistory();
      final adhRes = await _service.getAdherenceSummary();
      if (mounted) {
        setState(() {
          _history = histRes.items;
          _adherence = adhRes;
          _isLoadingHistory = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _historyError = e.toString().replaceAll('Exception:', '').trim();
          _isLoadingHistory = false;
        });
      }
    }
  }

  Future<void> _handleAction({
    required TodayScheduleItem item,
    required String status,
    int? snoozeMinutes,
  }) async {
    try {
      await _service.recordEvent(
        reminderId: item.reminderDbId,
        scheduledOccurrenceTime: item.scheduledOccurrenceTime,
        status: status,
        snoozeMinutes: snoozeMinutes,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            status == 'TAKEN'
                ? 'Marked as taken. Well done!'
                : status == 'SKIPPED'
                    ? 'Dose marked as skipped.'
                    : 'Reminder snoozed for $snoozeMinutes minutes.',
          ),
          backgroundColor: status == 'TAKEN' ? AppTheme.success : AppTheme.primary,
          duration: const Duration(seconds: 2),
        ),
      );

      // Refresh schedule and adherence
      _loadTodaySchedule();
      _loadHistoryAndAdherence();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not update status: $e'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  Future<void> _showSnoozeDialog(TodayScheduleItem item) async {
    final pickedMinutes = await showDialog<int>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: const Text('Snooze Reminder'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.of(ctx).pop(15),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 6.0),
              child: Text('15 Minutes', style: TextStyle(fontSize: 16)),
            ),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.of(ctx).pop(30),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 6.0),
              child: Text('30 Minutes', style: TextStyle(fontSize: 16)),
            ),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.of(ctx).pop(60),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 6.0),
              child: Text('1 Hour', style: TextStyle(fontSize: 16)),
            ),
          ),
        ],
      ),
    );

    if (pickedMinutes != null) {
      _handleAction(item: item, status: 'SNOOZED', snoozeMinutes: pickedMinutes);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Medication Reminders'),
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppTheme.primary,
          labelColor: AppTheme.primary,
          unselectedLabelColor: AppTheme.textSecondary,
          labelStyle: const TextStyle(fontWeight: FontWeight.bold),
          tabs: const [
            Tab(text: 'Today'),
            Tab(text: 'My Medications'),
            Tab(text: 'History'),
          ],
        ),
      ),
      floatingActionButton: _tabController.index == 1
          ? FloatingActionButton.extended(
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              onPressed: () async {
                final created = await Navigator.of(context).push<bool>(
                  MaterialPageRoute(builder: (_) => const CreateMedicationReminderScreen()),
                );
                if (created == true) {
                  _loadAll();
                }
              },
              icon: const Icon(Icons.add),
              label: const Text('Add Reminder'),
            )
          : null,
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildTodayTab(),
          _buildMyMedicationsTab(),
          _buildHistoryTab(),
        ],
      ),
    );
  }

  Widget _buildTodayTab() {
    if (_isLoadingToday) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_todayError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(_todayError!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadTodaySchedule,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final schedule = _todaySchedule;
    final items = schedule?.items ?? [];

    return RefreshIndicator(
      onRefresh: _loadTodaySchedule,
      child: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // Today Header & Progress Card
          Container(
            padding: const EdgeInsets.all(16.0),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppTheme.primary, AppTheme.primaryDark],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16.0),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Today\'s Schedule',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18.0,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      schedule?.date ?? '',
                      style: const TextStyle(color: Colors.white70, fontSize: 13.0),
                    ),
                  ],
                ),
                const SizedBox(height: 12.0),
                Text(
                  items.isEmpty
                      ? 'No medications scheduled for today.'
                      : '${schedule?.takenCount ?? 0} of ${schedule?.totalScheduled ?? 0} doses completed',
                  style: const TextStyle(color: Colors.white, fontSize: 14.0),
                ),
                const SizedBox(height: 8.0),
                LinearProgressIndicator(
                  value: (schedule?.totalScheduled ?? 0) > 0
                      ? ((schedule?.takenCount ?? 0) / (schedule?.totalScheduled ?? 1))
                          .clamp(0.0, 1.0)
                      : 0.0,
                  backgroundColor: Colors.white24,
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                  minHeight: 6.0,
                  borderRadius: BorderRadius.circular(3.0),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16.0),

          if (items.isEmpty)
            Container(
              padding: const EdgeInsets.all(32.0),
              alignment: Alignment.center,
              child: Column(
                children: [
                  Icon(Icons.event_available, size: 56, color: AppTheme.textMuted.withValues(alpha: 0.5)),
                  const SizedBox(height: 12),
                  const Text(
                    'All caught up for today!',
                    style: TextStyle(fontSize: 16.0, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'No pending doses found. To schedule a reminder from your doctor\'s prescription, check the "My Medications" tab.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 13.0, color: AppTheme.textSecondary),
                  ),
                ],
              ),
            )
          else ...[
            const Text(
              'Scheduled Doses',
              style: TextStyle(
                fontSize: 15.0,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8.0),
            for (final it in items) _buildTodayItemCard(it),
          ],
        ],
      ),
    );
  }

  Widget _buildTodayItemCard(TodayScheduleItem item) {
    Color badgeColor = AppTheme.secondary;
    Color badgeBg = AppTheme.secondaryContainer;
    String badgeText = item.status;

    if (item.status == 'TAKEN') {
      badgeColor = AppTheme.success;
      badgeBg = AppTheme.successContainer;
    } else if (item.status == 'SKIPPED') {
      badgeColor = Colors.orange.shade800;
      badgeBg = Colors.orange.shade50;
    } else if (item.status == 'SNOOZED') {
      badgeColor = Colors.purple.shade700;
      badgeBg = Colors.purple.shade50;
      badgeText = 'SNOOZED (${item.snoozeMinutes ?? 15}m)';
    }

    final isPendingOrSnoozed = item.status == 'PENDING' || item.status == 'SNOOZED';

    return Container(
      margin: const EdgeInsets.only(bottom: 12.0),
      padding: const EdgeInsets.all(14.0),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14.0),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10.0, vertical: 6.0),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceVariant,
                  borderRadius: BorderRadius.circular(8.0),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.access_time, size: 16, color: AppTheme.primary),
                    const SizedBox(width: 4),
                    Text(
                      item.timeStr,
                      style: const TextStyle(fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
                decoration: BoxDecoration(
                  color: badgeBg,
                  borderRadius: BorderRadius.circular(6.0),
                ),
                child: Text(
                  badgeText,
                  style: TextStyle(
                    color: badgeColor,
                    fontSize: 11.0,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10.0),
          Text(
            item.medicationName,
            style: const TextStyle(
              fontSize: 16.0,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 2.0),
          Text(
            '${item.strength} • ${item.dose} • ${item.route}',
            style: const TextStyle(fontSize: 13.0, color: AppTheme.textSecondary),
          ),
          if (item.additionalInstructions != null && item.additionalInstructions!.isNotEmpty) ...[
            const SizedBox(height: 6.0),
            Text(
              'Instruction: ${item.additionalInstructions}',
              style: const TextStyle(
                fontSize: 12.0,
                fontStyle: FontStyle.italic,
                color: AppTheme.textMuted,
              ),
            ),
          ],
          if (isPendingOrSnoozed) ...[
            const Divider(height: 20.0, color: AppTheme.border),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.success,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      padding: const EdgeInsets.symmetric(vertical: 8.0),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8.0)),
                    ),
                    onPressed: () => _handleAction(item: item, status: 'TAKEN'),
                    icon: const Icon(Icons.check, size: 18),
                    label: const Text('Take', style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                ),
                const SizedBox(width: 8.0),
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.textSecondary,
                      padding: const EdgeInsets.symmetric(vertical: 8.0),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8.0)),
                    ),
                    onPressed: () => _handleAction(item: item, status: 'SKIPPED'),
                    icon: const Icon(Icons.close, size: 18),
                    label: const Text('Skip'),
                  ),
                ),
                const SizedBox(width: 8.0),
                IconButton(
                  tooltip: 'Snooze',
                  icon: const Icon(Icons.snooze, color: AppTheme.primary),
                  onPressed: () => _showSnoozeDialog(item),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMyMedicationsTab() {
    if (_isLoadingReminders) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_remindersError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(_remindersError!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadReminders,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_reminders.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadReminders,
        child: ListView(
          padding: const EdgeInsets.all(32.0),
          children: [
            const SizedBox(height: 40),
            Icon(Icons.medication_outlined, size: 64, color: AppTheme.textMuted.withValues(alpha: 0.5)),
            const SizedBox(height: 16),
            const Text(
              'No Medication Reminders Yet',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 17.0, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 8),
            const Text(
              'Set reminders for your active prescriptions to stay on track with doctor-prescribed regimens.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13.0, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12.0),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10.0)),
              ),
              onPressed: () async {
                final created = await Navigator.of(context).push<bool>(
                  MaterialPageRoute(builder: (_) => const CreateMedicationReminderScreen()),
                );
                if (created == true) {
                  _loadAll();
                }
              },
              icon: const Icon(Icons.add),
              label: const Text('Add Medication Reminder'),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadReminders,
      child: ListView.builder(
        padding: const EdgeInsets.all(16.0),
        itemCount: _reminders.length,
        itemBuilder: (_, index) {
          final reminder = _reminders[index];
          return Container(
            margin: const EdgeInsets.only(bottom: 12.0),
            padding: const EdgeInsets.all(14.0),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14.0),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            reminder.medicationName,
                            style: const TextStyle(
                              fontSize: 16.0,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 2.0),
                          Text(
                            '${reminder.strength} • ${reminder.dose} • ${reminder.frequency}',
                            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                          ),
                        ],
                      ),
                    ),
                    Switch(
                      value: reminder.enabled,
                      activeTrackColor: AppTheme.primary,
                      onChanged: (val) async {
                        try {
                          await _service.updateReminder(reminder.id, enabled: val);
                          _loadReminders();
                        } catch (e) {
                          if (!mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Failed: $e'), backgroundColor: AppTheme.error),
                          );
                        }
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 8.0),
                Wrap(
                  spacing: 6.0,
                  runSpacing: 6.0,
                  children: reminder.scheduledTimes.map((t) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
                      decoration: BoxDecoration(
                        color: AppTheme.primaryContainer,
                        borderRadius: BorderRadius.circular(6.0),
                      ),
                      child: Text(
                        t,
                        style: const TextStyle(
                          color: AppTheme.onPrimaryContainer,
                          fontSize: 12.0,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    );
                  }).toList(),
                ),
                const Divider(height: 20.0, color: AppTheme.border),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Rx: ${reminder.prescriptionId}',
                      style: const TextStyle(fontSize: 11.5, color: AppTheme.textMuted),
                    ),
                    TextButton.icon(
                      style: TextButton.styleFrom(
                        padding: EdgeInsets.zero,
                        minimumSize: const Size(50, 30),
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      onPressed: () async {
                        final updated = await Navigator.of(context).push<bool>(
                          MaterialPageRoute(
                            builder: (_) => ReminderSettingsScreen(reminder: reminder),
                          ),
                        );
                        if (updated == true) {
                          _loadAll();
                        }
                      },
                      icon: const Icon(Icons.settings, size: 16),
                      label: const Text('Settings'),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildHistoryTab() {
    if (_isLoadingHistory) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_historyError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(_historyError!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadHistoryAndAdherence,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final adh = _adherence;

    return RefreshIndicator(
      onRefresh: _loadHistoryAndAdherence,
      child: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // Adherence Rate Card (Non-judgmental presentation)
          Container(
            padding: const EdgeInsets.all(16.0),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16.0),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '30-Day Medication Adherence',
                  style: TextStyle(
                    fontSize: 15.0,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 6.0),
                const Text(
                  'A summary of your recorded schedule. Skipped doses reflect your self-reported log.',
                  style: TextStyle(fontSize: 12.0, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 16.0),
                Row(
                  children: [
                    Text(
                      '${adh?.adherenceRatePercent.toStringAsFixed(1) ?? "100.0"}%',
                      style: const TextStyle(
                        fontSize: 32.0,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primary,
                      ),
                    ),
                    const SizedBox(width: 16.0),
                    Expanded(
                      child: Column(
                        children: [
                          LinearProgressIndicator(
                            value: ((adh?.adherenceRatePercent ?? 100) / 100).clamp(0.0, 1.0),
                            backgroundColor: AppTheme.surfaceVariant,
                            valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.primary),
                            minHeight: 8.0,
                            borderRadius: BorderRadius.circular(4.0),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24.0, color: AppTheme.border),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildAdherenceStat(
                      label: 'Taken',
                      value: '${adh?.takenDoses ?? 0}',
                      color: AppTheme.success,
                    ),
                    _buildAdherenceStat(
                      label: 'Skipped',
                      value: '${adh?.skippedDoses ?? 0}',
                      color: Colors.orange.shade800,
                    ),
                    _buildAdherenceStat(
                      label: 'Active',
                      value: '${adh?.activeRemindersCount ?? 0}',
                      color: AppTheme.primary,
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 18.0),

          const Text(
            'Intake Event History',
            style: TextStyle(
              fontSize: 15.0,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8.0),

          if (_history.isEmpty)
            Container(
              padding: const EdgeInsets.all(24.0),
              alignment: Alignment.center,
              child: const Text(
                'No recorded intake events yet. Log your doses from the "Today" tab.',
                style: TextStyle(fontSize: 13.0, color: AppTheme.textSecondary),
              ),
            )
          else
            for (final ev in _history) _buildHistoryEventCard(ev),
        ],
      ),
    );
  }

  Widget _buildAdherenceStat({
    required String label,
    required String value,
    required Color color,
  }) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(fontSize: 18.0, fontWeight: FontWeight.bold, color: color),
        ),
        const SizedBox(height: 2.0),
        Text(label, style: const TextStyle(fontSize: 12.0, color: AppTheme.textSecondary)),
      ],
    );
  }

  Widget _buildHistoryEventCard(MedicationEvent event) {
    Color badgeColor = AppTheme.success;
    Color badgeBg = AppTheme.successContainer;
    if (event.status == 'SKIPPED') {
      badgeColor = Colors.orange.shade800;
      badgeBg = Colors.orange.shade50;
    } else if (event.status == 'SNOOZED') {
      badgeColor = Colors.purple.shade700;
      badgeBg = Colors.purple.shade50;
    }

    final localTime = event.scheduledOccurrenceTime.toLocal();
    final timeStr =
        '${localTime.year}-${localTime.month.toString().padLeft(2, '0')}-${localTime.day.toString().padLeft(2, '0')} ${localTime.hour.toString().padLeft(2, '0')}:${localTime.minute.toString().padLeft(2, '0')}';

    return Container(
      margin: const EdgeInsets.only(bottom: 8.0),
      padding: const EdgeInsets.all(12.0),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12.0),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  event.medicationName ?? 'Prescribed Medication',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                    fontSize: 14.0,
                  ),
                ),
                const SizedBox(height: 2.0),
                Text(
                  timeStr,
                  style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary),
                ),
                if (event.notes != null && event.notes!.isNotEmpty) ...[
                  const SizedBox(height: 2.0),
                  Text(
                    event.notes!,
                    style: const TextStyle(
                      fontSize: 11.5,
                      fontStyle: FontStyle.italic,
                      color: AppTheme.textMuted,
                    ),
                  ),
                ],
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
            decoration: BoxDecoration(
              color: badgeBg,
              borderRadius: BorderRadius.circular(6.0),
            ),
            child: Text(
              event.status,
              style: TextStyle(
                color: badgeColor,
                fontSize: 11.0,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
