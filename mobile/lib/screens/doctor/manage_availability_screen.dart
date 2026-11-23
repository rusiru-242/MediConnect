import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/doctor_availability.dart';
import '../../services/doctor_service.dart';

/// Comprehensive Doctor Availability & Leave Calendar Screen (Phase 54).
/// Allows doctors to configure weekly working hours, manage leave, block times,
/// view calendar overview, and manage individual availability windows.
class ManageAvailabilityScreen extends StatefulWidget {
  final DoctorService? doctorService;

  const ManageAvailabilityScreen({super.key, this.doctorService});

  @override
  State<ManageAvailabilityScreen> createState() => _ManageAvailabilityScreenState();
}

class _ManageAvailabilityScreenState extends State<ManageAvailabilityScreen>
    with SingleTickerProviderStateMixin {
  late final DoctorService _doctorService;
  late final TabController _tabController;

  bool _isLoading = false;
  String? _errorMessage;

  // Calendar State
  DateTime _currentMonth = DateTime.now();
  DateTime _selectedDate = DateTime.now();
  DoctorCalendarOverview? _calendarOverview;
  CalendarDayOverview? _selectedDayOverview;

  // Weekly Schedule State
  String _configuredTimezone = 'Asia/Colombo';
  int _configuredSlotDuration = 30;
  List<WeekdaySchedule> _weekdays = [];
  bool _isSavingWeeklySchedule = false;

  // Leave & Blocked Times State
  List<DoctorLeave> _leaves = [];
  List<DoctorBlockedTime> _blockedTimes = [];
  List<DoctorAvailability> _availabilities = [];

  @override
  void initState() {
    super.initState();
    _doctorService = widget.doctorService ?? DoctorService();
    _tabController = TabController(length: 3, vsync: this);
    _loadAllData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAllData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final monthStr = '${_currentMonth.year}-${_currentMonth.month.toString().padLeft(2, '0')}';
      
      // Load in parallel
      final results = await Future.wait([
        _doctorService.getMyAvailabilities(),
        _doctorService.getWeeklySchedule().catchError((_) => _fallbackWeeklySchedule()),
        _doctorService.getMyLeaves().catchError((_) => <DoctorLeave>[]),
        _doctorService.getMyBlockedTimes().catchError((_) => <DoctorBlockedTime>[]),
        _doctorService.getCalendarOverview(month: monthStr).catchError((_) => DoctorCalendarOverview(month: monthStr, days: [])),
      ]);

      if (!mounted) return;

      final availList = results[0] as List<DoctorAvailability>;
      final weekly = results[1] as DoctorWeeklySchedule;
      final leavesList = results[2] as List<DoctorLeave>;
      final blocksList = results[3] as List<DoctorBlockedTime>;
      final calOverview = results[4] as DoctorCalendarOverview;

      setState(() {
        _availabilities = availList;
        _configuredTimezone = weekly.timezone;
        _configuredSlotDuration = weekly.slotDurationMinutes;
        _weekdays = List.from(weekly.weekdays);
        _leaves = leavesList;
        _blockedTimes = blocksList;
        _calendarOverview = calOverview;
        _isLoading = false;
      });

      _updateSelectedDayOverview();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to connect to MediConnect. Please try again.';
        _isLoading = false;
      });
    }
  }

  DoctorWeeklySchedule _fallbackWeeklySchedule() {
    return DoctorWeeklySchedule(
      doctorUserId: '',
      doctorProfileId: '',
      timezone: 'Asia/Colombo',
      slotDurationMinutes: 30,
      weekdays: [
        WeekdaySchedule(day: 'monday', isEnabled: true, sessions: [
          WorkingSession(startTime: '09:00', endTime: '12:00'),
          WorkingSession(startTime: '14:00', endTime: '17:00'),
        ]),
        WeekdaySchedule(day: 'tuesday', isEnabled: true, sessions: [
          WorkingSession(startTime: '09:00', endTime: '13:00'),
        ]),
        WeekdaySchedule(day: 'wednesday', isEnabled: false, sessions: []),
        WeekdaySchedule(day: 'thursday', isEnabled: true, sessions: [
          WorkingSession(startTime: '09:00', endTime: '17:00'),
        ]),
        WeekdaySchedule(day: 'friday', isEnabled: true, sessions: [
          WorkingSession(startTime: '09:00', endTime: '12:00'),
        ]),
        WeekdaySchedule(day: 'saturday', isEnabled: false, sessions: []),
        WeekdaySchedule(day: 'sunday', isEnabled: false, sessions: []),
      ],
    );
  }

  void _updateSelectedDayOverview() {
    final selStr = _formatDate(_selectedDate);
    if (_calendarOverview != null && _calendarOverview!.days.isNotEmpty) {
      final match = _calendarOverview!.days.where((d) => d.date == selStr);
      if (match.isNotEmpty) {
        setState(() {
          _selectedDayOverview = match.first;
        });
        return;
      }
    }
    setState(() {
      _selectedDayOverview = null;
    });
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }

  void _changeMonth(int delta) {
    setState(() {
      _currentMonth = DateTime(_currentMonth.year, _currentMonth.month + delta, 1);
    });
    _loadAllData();
  }

  // -------------------------------------------------------------
  // WEEKLY WORKING SCHEDULE HANDLERS
  // -------------------------------------------------------------
  Future<void> _saveWeeklySchedule() async {
    setState(() {
      _isSavingWeeklySchedule = true;
    });

    try {
      final updated = await _doctorService.updateWeeklySchedule(
        weekdays: _weekdays,
        timezone: _configuredTimezone,
        slotDurationMinutes: _configuredSlotDuration,
      );

      if (!mounted) return;
      setState(() {
        _configuredTimezone = updated.timezone;
        _configuredSlotDuration = updated.slotDurationMinutes;
        _weekdays = List.from(updated.weekdays);
        _isSavingWeeklySchedule = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.success,
          content: Text('Weekly schedule saved successfully!'),
        ),
      );
      _loadAllData();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isSavingWeeklySchedule = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppTheme.error,
          content: Text('Failed to save weekly schedule: $e'),
        ),
      );
    }
  }

  void _toggleWeekday(int index, bool enabled) {
    setState(() {
      final current = _weekdays[index];
      _weekdays[index] = current.copyWith(
        isEnabled: enabled,
        sessions: enabled && current.sessions.isEmpty
            ? [WorkingSession(startTime: '09:00', endTime: '12:00')]
            : current.sessions,
      );
    });
  }

  void _removeSession(int dayIndex, int sessionIndex) {
    setState(() {
      final current = _weekdays[dayIndex];
      final newSessions = List<WorkingSession>.from(current.sessions)..removeAt(sessionIndex);
      _weekdays[dayIndex] = current.copyWith(sessions: newSessions);
    });
  }

  Future<void> _addSession(int dayIndex) async {
    final startTime = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 14, minute: 0),
      helpText: 'Select Session Start Time',
    );
    if (startTime == null || !mounted) return;

    final endTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: startTime.hour + 2, minute: startTime.minute),
      helpText: 'Select Session End Time',
    );
    if (endTime == null || !mounted) return;

    final startMinutes = startTime.hour * 60 + startTime.minute;
    final endMinutes = endTime.hour * 60 + endTime.minute;

    if (startMinutes >= endMinutes) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.error,
          content: Text('Start time must be strictly earlier than end time.'),
        ),
      );
      return;
    }

    final startStr = '${startTime.hour.toString().padLeft(2, '0')}:${startTime.minute.toString().padLeft(2, '0')}';
    final endStr = '${endTime.hour.toString().padLeft(2, '0')}:${endTime.minute.toString().padLeft(2, '0')}';

    setState(() {
      final current = _weekdays[dayIndex];
      final newSessions = List<WorkingSession>.from(current.sessions)
        ..add(WorkingSession(startTime: startStr, endTime: endStr));
      _weekdays[dayIndex] = current.copyWith(sessions: newSessions);
    });
  }

  // -------------------------------------------------------------
  // LEAVE APPLICATION & CONFLICT RESOLUTION
  // -------------------------------------------------------------
  Future<void> _showApplyLeaveSheet() async {
    String selectedType = 'PERSONAL';
    DateTime startDate = _selectedDate.isBefore(DateTime.now()) ? DateTime.now() : _selectedDate;
    DateTime endDate = startDate;
    bool isPartialDay = false;
    TimeOfDay startTime = const TimeOfDay(hour: 9, minute: 0);
    TimeOfDay endTime = const TimeOfDay(hour: 13, minute: 0);
    final reasonController = TextEditingController();

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (sheetContext, setSheetState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 20,
                bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 24,
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Schedule Doctor Leave',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close_rounded),
                          onPressed: () => Navigator.of(sheetContext).pop(),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: selectedType,
                      decoration: const InputDecoration(
                        labelText: 'Leave Type',
                        prefixIcon: Icon(Icons.category_rounded, color: AppTheme.primary),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'PERSONAL', child: Text('Personal Leave')),
                        DropdownMenuItem(value: 'MEDICAL', child: Text('Medical Leave')),
                        DropdownMenuItem(value: 'VACATION', child: Text('Vacation')),
                        DropdownMenuItem(value: 'PUBLIC_HOLIDAY', child: Text('Public Holiday')),
                        DropdownMenuItem(value: 'OTHER', child: Text('Other')),
                      ],
                      onChanged: (val) => setSheetState(() => selectedType = val ?? 'PERSONAL'),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.date_range_rounded, size: 18),
                            label: Text('From: ${_formatDate(startDate)}'),
                            onPressed: () async {
                              final picked = await showDatePicker(
                                context: sheetContext,
                                initialDate: startDate,
                                firstDate: DateTime.now().subtract(const Duration(days: 1)),
                                lastDate: DateTime.now().add(const Duration(days: 365)),
                              );
                              if (picked != null) {
                                setSheetState(() {
                                  startDate = picked;
                                  if (endDate.isBefore(startDate)) endDate = startDate;
                                });
                              }
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.date_range_rounded, size: 18),
                            label: Text('To: ${_formatDate(endDate)}'),
                            onPressed: isPartialDay
                                ? null
                                : () async {
                                    final picked = await showDatePicker(
                                      context: sheetContext,
                                      initialDate: endDate,
                                      firstDate: startDate,
                                      lastDate: DateTime.now().add(const Duration(days: 365)),
                                    );
                                    if (picked != null) {
                                      setSheetState(() => endDate = picked);
                                    }
                                  },
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Partial-day leave only'),
                      subtitle: const Text('Block specific consultation hours on this date'),
                      value: isPartialDay,
                      onChanged: (v) {
                        setSheetState(() {
                          isPartialDay = v;
                          if (isPartialDay) endDate = startDate;
                        });
                      },
                    ),
                    if (isPartialDay) ...[
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () async {
                                final t = await showTimePicker(context: sheetContext, initialTime: startTime);
                                if (t != null) setSheetState(() => startTime = t);
                              },
                              child: Text('Start: ${startTime.format(sheetContext)}'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () async {
                                final t = await showTimePicker(context: sheetContext, initialTime: endTime);
                                if (t != null) setSheetState(() => endTime = t);
                              },
                              child: Text('End: ${endTime.format(sheetContext)}'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                    ],
                    TextField(
                      controller: reasonController,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Private Reason (Optional)',
                        hintText: 'e.g. Attending Annual Medical Congress',
                      ),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: () async {
                        final sStr = _formatDate(startDate);
                        final eStr = _formatDate(endDate);
                        final sTimeStr = isPartialDay
                            ? '${startTime.hour.toString().padLeft(2, '0')}:${startTime.minute.toString().padLeft(2, '0')}'
                            : null;
                        final eTimeStr = isPartialDay
                            ? '${endTime.hour.toString().padLeft(2, '0')}:${endTime.minute.toString().padLeft(2, '0')}'
                            : null;

                        Navigator.of(sheetContext).pop();
                        await _submitLeaveApplication(
                          leaveType: selectedType,
                          startDate: sStr,
                          endDate: eStr,
                          startTime: sTimeStr,
                          endTime: eTimeStr,
                          reason: reasonController.text.trim().isEmpty ? null : reasonController.text.trim(),
                        );
                      },
                      child: const Text('Confirm & Save Leave'),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _submitLeaveApplication({
    required String leaveType,
    required String startDate,
    required String endDate,
    String? startTime,
    String? endTime,
    String? reason,
    bool resolveConflicts = false,
  }) async {
    try {
      await _doctorService.createLeave(
        leaveType: leaveType,
        startDate: startDate,
        endDate: endDate,
        startTime: startTime,
        endTime: endTime,
        reason: reason,
        resolveConflicts: resolveConflicts,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.success,
          content: Text('Leave scheduled successfully.'),
        ),
      );
      _loadAllData();
    } catch (e) {
      if (!mounted) return;
      // Check for conflict error with appointments
      final errStr = e.toString();
      if (errStr.contains('conflicts') || errStr.contains('409')) {
        final resolve = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Appointment Conflicts Detected'),
            content: const Text(
              'There are existing patient appointments booked during this leave window.\n\n'
              'Would you like to automatically cancel these appointments and notify the patients through the MediConnect Notification Center?',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('Cancel Request'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
                onPressed: () => Navigator.of(ctx).pop(true),
                child: const Text('Cancel Appointments & Confirm Leave'),
              ),
            ],
          ),
        );

        if (resolve == true) {
          await _submitLeaveApplication(
            leaveType: leaveType,
            startDate: startDate,
            endDate: endDate,
            startTime: startTime,
            endTime: endTime,
            reason: reason,
            resolveConflicts: true,
          );
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppTheme.error,
            content: Text('Failed to schedule leave: $e'),
          ),
        );
      }
    }
  }

  Future<void> _cancelLeave(String leaveId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel Scheduled Leave'),
        content: const Text('Are you sure you want to cancel this leave? Your consultation slots will become bookable again.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('No')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Cancel Leave'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _doctorService.cancelLeave(leaveId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Leave cancelled successfully.')),
      );
      _loadAllData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to cancel leave: $e')),
      );
    }
  }

  // -------------------------------------------------------------
  // BLOCKED TIME HANDLERS
  // -------------------------------------------------------------
  Future<void> _showBlockTimeSheet() async {
    DateTime blockDate = _selectedDate;
    TimeOfDay startTime = const TimeOfDay(hour: 10, minute: 0);
    TimeOfDay endTime = const TimeOfDay(hour: 11, minute: 0);
    final reasonController = TextEditingController();

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (sheetContext, setSheetState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 20,
                bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 24,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Block Time Window',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close_rounded),
                        onPressed: () => Navigator.of(sheetContext).pop(),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.calendar_today_rounded, size: 18),
                    label: Text('Date: ${_formatDate(blockDate)}'),
                    onPressed: () async {
                      final picked = await showDatePicker(
                        context: sheetContext,
                        initialDate: blockDate,
                        firstDate: DateTime.now().subtract(const Duration(days: 1)),
                        lastDate: DateTime.now().add(const Duration(days: 365)),
                      );
                      if (picked != null) setSheetState(() => blockDate = picked);
                    },
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () async {
                            final t = await showTimePicker(context: sheetContext, initialTime: startTime);
                            if (t != null) setSheetState(() => startTime = t);
                          },
                          child: Text('Start: ${startTime.format(sheetContext)}'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () async {
                            final t = await showTimePicker(context: sheetContext, initialTime: endTime);
                            if (t != null) setSheetState(() => endTime = t);
                          },
                          child: Text('End: ${endTime.format(sheetContext)}'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: reasonController,
                    decoration: const InputDecoration(
                      labelText: 'Reason (Optional)',
                      hintText: 'e.g. Administrative Duty or Team Meeting',
                    ),
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: () async {
                      final sTimeStr = '${startTime.hour.toString().padLeft(2, '0')}:${startTime.minute.toString().padLeft(2, '0')}';
                      final eTimeStr = '${endTime.hour.toString().padLeft(2, '0')}:${endTime.minute.toString().padLeft(2, '0')}';
                      Navigator.of(sheetContext).pop();
                      try {
                        await _doctorService.createBlockedTime(
                          date: _formatDate(blockDate),
                          startTime: sTimeStr,
                          endTime: eTimeStr,
                          reason: reasonController.text.trim().isEmpty ? null : reasonController.text.trim(),
                        );
                        if (!mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(backgroundColor: AppTheme.success, content: Text('Time window blocked.')),
                        );
                        _loadAllData();
                      } catch (e) {
                        if (!mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(backgroundColor: AppTheme.error, content: Text('Failed to block time: $e')),
                        );
                      }
                    },
                    child: const Text('Save Blocked Time'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _deleteBlockedTime(String blockId) async {
    try {
      await _doctorService.deleteBlockedTime(blockId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Blocked time removed.')),
      );
      _loadAllData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to remove block: $e')),
      );
    }
  }

  // -------------------------------------------------------------
  // LEGACY AVAILABILITY WINDOW HANDLERS
  // -------------------------------------------------------------
  Future<void> _handleDeleteLegacy(DoctorAvailability item) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove Availability Window'),
        content: Text('Deactivate availability on ${item.date} (${item.startTime} - ${item.endTime})?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _doctorService.deleteAvailability(item.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Availability window removed.')),
      );
      _loadAllData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to delete availability: $e')),
      );
    }
  }

  Future<void> _navigateToAddAvailability([DoctorAvailability? existing]) async {
    final result = await Navigator.of(context).pushNamed(
      '/doctor/add-availability',
      arguments: existing,
    );
    if (result == true) {
      _loadAllData();
    }
  }

  // -------------------------------------------------------------
  // MAIN BUILD
  // -------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Availability & Calendar'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadAllData,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          tabs: const [
            Tab(icon: Icon(Icons.calendar_month_rounded), text: 'Calendar'),
            Tab(icon: Icon(Icons.view_week_rounded), text: 'Weekly'),
            Tab(icon: Icon(Icons.event_busy_rounded), text: 'Leave & Dates'),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('manage_availability_fab'),
        onPressed: () => _navigateToAddAvailability(),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add Window'),
      ),
      body: SafeArea(
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _errorMessage != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.cloud_off_rounded, size: 54, color: AppTheme.error),
                          const SizedBox(height: 16),
                          Text(_errorMessage!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, color: AppTheme.textSecondary)),
                          const SizedBox(height: 16),
                          ElevatedButton.icon(
                            onPressed: _loadAllData,
                            icon: const Icon(Icons.refresh_rounded, size: 18),
                            label: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  )
                : TabBarView(
                    controller: _tabController,
                    children: [
                      _buildCalendarTab(),
                      _buildWeeklyScheduleTab(),
                      _buildLeaveAndDatesTab(),
                    ],
                  ),
      ),
    );
  }

  // -------------------------------------------------------------
  // TAB 1: CALENDAR VIEW
  // -------------------------------------------------------------
  Widget _buildCalendarTab() {
    final monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    final monthTitle = '${monthNames[_currentMonth.month - 1]} ${_currentMonth.year}';

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 80),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Month Selector Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.outline.withValues(alpha: 0.3)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.chevron_left_rounded, color: AppTheme.primary),
                  onPressed: () => _changeMonth(-1),
                ),
                Expanded(
                  child: Center(
                    child: Text(
                      monthTitle,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    ),
                  ),
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.chevron_right_rounded, color: AppTheme.primary),
                  onPressed: () => _changeMonth(1),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Legend / Indicators
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
            ),
            child: Wrap(
              alignment: WrapAlignment.spaceAround,
              spacing: 8,
              runSpacing: 6,
              children: [
                _buildLegendItem(color: AppTheme.primary, label: 'Available'),
                _buildLegendItem(color: Colors.amber.shade800, label: 'Leave'),
                _buildLegendItem(color: Colors.purple.shade700, label: 'Booked'),
                _buildLegendItem(color: Colors.grey.shade400, label: 'Unavailable'),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Days Grid / Selector
          _buildMonthGrid(),
          const SizedBox(height: 16),

          // Selected Day Details Card
          _buildSelectedDayDetailCard(),
          const SizedBox(height: 20),

          // Upcoming Availability Section
          _buildUpcomingAvailabilitySection(),
        ],
      ),
    );
  }

  Widget _buildUpcomingAvailabilitySection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Expanded(
              child: Text(
                'Upcoming Availability',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ),
            if (_availabilities.isNotEmpty)
              Text(
                '${_availabilities.length} scheduled',
                style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
          ],
        ),
        const SizedBox(height: 8),
        if (_availabilities.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12.0),
            child: Text(
              'No date-specific availability windows scheduled.',
              style: TextStyle(color: AppTheme.textSecondary, fontStyle: FontStyle.italic),
            ),
          )
        else
          ..._availabilities.map((item) => _buildLegacyAvailabilityCard(item)),
      ],
    );
  }

  Widget _buildLegendItem({required Color color, required String label}) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppTheme.textSecondary),
        ),
      ],
    );
  }

  Widget _buildMonthGrid() {
    final year = _currentMonth.year;
    final month = _currentMonth.month;
    final daysInMonth = DateUtils.getDaysInMonth(year, month);
    final firstDayOffset = DateTime(year, month, 1).weekday - 1; // 0 = Mon, 6 = Sun

    final weekdayHeaders = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          // Weekday header row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: weekdayHeaders
                .map((w) => SizedBox(
                      width: 36,
                      child: Center(
                        child: Text(
                          w,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                    ))
                .toList(),
          ),
          const Divider(height: 16),
          // Day grid
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: 42, // 6 weeks * 7 days
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              childAspectRatio: 1.0,
            ),
            itemBuilder: (context, index) {
              final dayNum = index - firstDayOffset + 1;
              if (dayNum < 1 || dayNum > daysInMonth) {
                return const SizedBox.shrink();
              }

              final cellDate = DateTime(year, month, dayNum);
              final dateStr = _formatDate(cellDate);
              final isSelected = _formatDate(_selectedDate) == dateStr;

              // Find day status from overview
              CalendarDayOverview? dayOv;
              if (_calendarOverview != null) {
                final matches = _calendarOverview!.days.where((d) => d.date == dateStr);
                if (matches.isNotEmpty) dayOv = matches.first;
              }

              Color badgeColor = Colors.grey.shade300;
              if (dayOv != null) {
                if (dayOv.status == 'LEAVE') {
                  badgeColor = Colors.amber.shade700;
                } else if (dayOv.bookedAppointmentsCount > 0) {
                  badgeColor = Colors.purple.shade600;
                } else if (dayOv.status == 'AVAILABLE') {
                  badgeColor = AppTheme.primary;
                }
              }

              return InkWell(
                onTap: () {
                  setState(() {
                    _selectedDate = cellDate;
                  });
                  _updateSelectedDayOverview();
                },
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  margin: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    color: isSelected ? AppTheme.primary.withValues(alpha: 0.15) : null,
                    borderRadius: BorderRadius.circular(10),
                    border: isSelected
                        ? Border.all(color: AppTheme.primary, width: 2)
                        : null,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '$dayNum',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                          color: isSelected ? AppTheme.primary : AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Container(
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(color: badgeColor, shape: BoxShape.circle),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSelectedDayDetailCard() {
    final selStr = _formatDate(_selectedDate);
    final dayOv = _selectedDayOverview;

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
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
                        selStr,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      ),
                      Text(
                        dayOv?.weekday.toUpperCase() ?? '',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
                _buildDayStatusBadge(dayOv?.status ?? 'UNAVAILABLE'),
              ],
            ),
            const Divider(height: 24),

            // If on leave
            if (dayOv?.leave != null) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.amber.shade300),
                ),
                child: Row(
                  children: [
                    Icon(Icons.beach_access_rounded, color: Colors.amber.shade900),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'On Leave: ${dayOv!.leave!.leaveType}',
                            style: TextStyle(fontWeight: FontWeight.bold, color: Colors.amber.shade900),
                          ),
                          if (dayOv.leave!.reason != null)
                            Text(
                              dayOv.leave!.reason!,
                              style: TextStyle(fontSize: 12, color: Colors.amber.shade800),
                            ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: () => _cancelLeave(dayOv.leave!.id),
                      child: const Text('Cancel Leave', style: TextStyle(color: AppTheme.error)),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
            ],

            // Blocked times
            if (dayOv != null && dayOv.blockedTimes.isNotEmpty) ...[
              const Text('Blocked Windows:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              const SizedBox(height: 6),
              ...dayOv.blockedTimes.map((b) => Padding(
                    padding: const EdgeInsets.only(bottom: 6.0),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('• ${b.startTime} - ${b.endTime} (${b.reason ?? "Blocked"})'),
                        IconButton(
                          icon: const Icon(Icons.delete_outline_rounded, size: 18, color: AppTheme.error),
                          onPressed: () => _deleteBlockedTime(b.id),
                        ),
                      ],
                    ),
                  )),
              const SizedBox(height: 12),
            ],

            // Booked Appointments
            if (dayOv != null && dayOv.appointments.isNotEmpty) ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Booked Appointments:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  Text('${dayOv.appointments.length} patients', style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                ],
              ),
              const SizedBox(height: 6),
              ...dayOv.appointments.map((a) => Container(
                    margin: const EdgeInsets.only(bottom: 6),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppTheme.background,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.person_outline_rounded, size: 18, color: AppTheme.primary),
                            const SizedBox(width: 8),
                            Text(a.patientName, style: const TextStyle(fontWeight: FontWeight.w600)),
                          ],
                        ),
                        Text('${a.startTime} - ${a.endTime}', style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ],
                    ),
                  )),
              const SizedBox(height: 12),
            ],

            // Available Slots
            if (dayOv != null && dayOv.slots.isNotEmpty) ...[
              Text(
                'Available Slots (${dayOv.slots.length}):',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: dayOv.slots
                    .map((s) => Chip(
                          backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                          label: Text(s.startTime, style: const TextStyle(color: AppTheme.primary, fontWeight: FontWeight.bold)),
                        ))
                    .toList(),
              ),
            ] else if (dayOv?.leave == null) ...[
              const Text('No bookable slots on this date.', style: TextStyle(color: AppTheme.textSecondary, fontStyle: FontStyle.italic)),
            ],

            const SizedBox(height: 16),
            // Quick Day Actions
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.beach_access_rounded, size: 16),
                    label: const Text('Set Leave'),
                    onPressed: _showApplyLeaveSheet,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.block_rounded, size: 16),
                    label: const Text('Block Time'),
                    onPressed: _showBlockTimeSheet,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDayStatusBadge(String status) {
    Color bg;
    Color fg;
    String label = status;

    switch (status) {
      case 'AVAILABLE':
        bg = AppTheme.success.withValues(alpha: 0.15);
        fg = AppTheme.success;
        label = 'Available';
        break;
      case 'LEAVE':
        bg = Colors.amber.shade100;
        fg = Colors.amber.shade900;
        label = 'On Leave';
        break;
      case 'BLOCKED':
        bg = AppTheme.error.withValues(alpha: 0.15);
        fg = AppTheme.error;
        label = 'Blocked';
        break;
      case 'UNAVAILABLE':
      default:
        bg = Colors.grey.shade200;
        fg = Colors.grey.shade700;
        label = 'Unavailable';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
      child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: fg)),
    );
  }

  // -------------------------------------------------------------
  // TAB 2: WEEKLY SCHEDULE EDITOR
  // -------------------------------------------------------------
  Widget _buildWeeklyScheduleTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 80),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Config Header (Timezone & Slot Duration)
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.public_rounded, color: AppTheme.primary, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        'Timezone: $_configuredTimezone',
                        style: const TextStyle(fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Slot Duration:', style: TextStyle(fontWeight: FontWeight.w600)),
                      DropdownButton<int>(
                        value: _configuredSlotDuration,
                        items: const [
                          DropdownMenuItem(value: 15, child: Text('15 Minutes')),
                          DropdownMenuItem(value: 20, child: Text('20 Minutes')),
                          DropdownMenuItem(value: 30, child: Text('30 Minutes')),
                          DropdownMenuItem(value: 45, child: Text('45 Minutes')),
                          DropdownMenuItem(value: 60, child: Text('60 Minutes')),
                        ],
                        onChanged: (val) {
                          if (val != null) {
                            setState(() => _configuredSlotDuration = val);
                          }
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // 7 Weekday Cards
          ...List.generate(_weekdays.length, (idx) {
            final day = _weekdays[idx];
            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          day.day[0].toUpperCase() + day.day.substring(1),
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                        ),
                        Switch(
                          value: day.isEnabled,
                          activeThumbColor: AppTheme.primary,
                          onChanged: (val) => _toggleWeekday(idx, val),
                        ),
                      ],
                    ),
                    if (day.isEnabled) ...[
                      const Divider(height: 16),
                      if (day.sessions.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8.0),
                          child: Text('No sessions added yet.', style: TextStyle(color: AppTheme.textSecondary, fontStyle: FontStyle.italic)),
                        )
                      else
                        ...List.generate(day.sessions.length, (sIdx) {
                          final session = day.sessions[sIdx];
                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: AppTheme.background,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: [
                                    const Icon(Icons.access_time_rounded, size: 18, color: AppTheme.primary),
                                    const SizedBox(width: 8),
                                    Text('${session.startTime} – ${session.endTime}', style: const TextStyle(fontWeight: FontWeight.bold)),
                                  ],
                                ),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline_rounded, size: 20, color: AppTheme.error),
                                  onPressed: () => _removeSession(idx, sIdx),
                                ),
                              ],
                            ),
                          );
                        }),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          onPressed: () => _addSession(idx),
                          icon: const Icon(Icons.add_rounded, size: 18),
                          label: const Text('Add Session'),
                        ),
                      ),
                    ] else
                      const Text('Not Available', style: TextStyle(color: AppTheme.textSecondary, fontStyle: FontStyle.italic)),
                  ],
                ),
              ),
            );
          }),

          const SizedBox(height: 16),
          ElevatedButton.icon(
            key: const Key('save_weekly_schedule_button'),
            onPressed: _isSavingWeeklySchedule ? null : _saveWeeklySchedule,
            icon: _isSavingWeeklySchedule
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.save_rounded),
            label: const Text('Save Weekly Schedule'),
          ),
        ],
      ),
    );
  }

  // -------------------------------------------------------------
  // TAB 3: LEAVE & UPCOMING WINDOWS (TEST 26 BACKWARD COMPATIBLE)
  // -------------------------------------------------------------
  Widget _buildLeaveAndDatesTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 80),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Action Buttons
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _showApplyLeaveSheet,
                  icon: const Icon(Icons.beach_access_rounded, size: 18),
                  label: const Text('Schedule Leave'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _showBlockTimeSheet,
                  icon: const Icon(Icons.block_rounded, size: 18),
                  label: const Text('Block Time'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Scheduled Leaves Section
          const Text('Scheduled Leave Records', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary)),
          const SizedBox(height: 8),
          if (_leaves.isEmpty)
            const Text('No active leave scheduled.', style: TextStyle(color: AppTheme.textSecondary, fontStyle: FontStyle.italic))
          else
            ..._leaves.map((l) => Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ListTile(
                    leading: const Icon(Icons.beach_access_rounded, color: Colors.amber),
                    title: Text('${l.leaveType} (${l.startDate} to ${l.endDate})'),
                    subtitle: Text(l.reason ?? (l.startTime != null ? '${l.startTime} - ${l.endTime}' : 'Full day')),
                    trailing: l.status == 'ACTIVE'
                        ? IconButton(
                            icon: const Icon(Icons.cancel_outlined, color: AppTheme.error),
                            onPressed: () => _cancelLeave(l.id),
                          )
                        : const Text('Cancelled', style: TextStyle(color: Colors.grey)),
                  ),
                )),

          const SizedBox(height: 20),
          const Text('Blocked Time Windows', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary)),
          const SizedBox(height: 8),
          if (_blockedTimes.isEmpty)
            const Text('No blocked times configured.', style: TextStyle(color: AppTheme.textSecondary, fontStyle: FontStyle.italic))
          else
            ..._blockedTimes.map((b) => Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ListTile(
                    leading: const Icon(Icons.block_rounded, color: AppTheme.error),
                    title: Text('${b.date} (${b.startTime} - ${b.endTime})'),
                    subtitle: Text(b.reason ?? 'Blocked'),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline_rounded, color: AppTheme.error),
                      onPressed: () => _deleteBlockedTime(b.id),
                    ),
                  ),
                )),

          const SizedBox(height: 24),

          // Preserves TEST 26: "Upcoming Availability" Section
          _buildUpcomingAvailabilitySection(),
        ],
      ),
    );
  }

  Widget _buildLegacyAvailabilityCard(DoctorAvailability item) {
    final statusColor = item.isActive ? AppTheme.success : AppTheme.error;
    final statusText = item.isActive ? 'Active' : 'Disabled';

    return Card(
      key: Key('availability_card_${item.id}'),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      const Icon(Icons.event_available_rounded, size: 20, color: AppTheme.primary),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          item.date,
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    statusText,
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: statusColor),
                  ),
                ),
              ],
            ),
            const Divider(height: 20),
            Row(
              children: [
                const Icon(Icons.access_time_rounded, size: 18, color: AppTheme.textSecondary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${item.startTime} - ${item.endTime}',
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: AppTheme.textPrimary),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.timer_outlined, size: 18, color: AppTheme.textSecondary),
                const SizedBox(width: 4),
                Text(
                  '${item.slotDurationMinutes} min',
                  style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: () => _navigateToAddAvailability(item),
                  icon: const Icon(Icons.edit_outlined, size: 16),
                  label: const Text('Edit'),
                ),
                const SizedBox(width: 8),
                TextButton.icon(
                  style: TextButton.styleFrom(foregroundColor: AppTheme.error),
                  onPressed: () => _handleDeleteLegacy(item),
                  icon: const Icon(Icons.delete_outline_rounded, size: 16),
                  label: const Text('Remove'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
