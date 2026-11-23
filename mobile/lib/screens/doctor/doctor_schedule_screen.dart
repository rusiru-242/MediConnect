import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../models/consultation.dart';
import '../../services/consultation_service.dart';
import 'consultation_details_screen.dart';
import 'create_care_plan_screen.dart';

/// Doctor Today's Schedule & Consultation Management Screen (Phase 57).
class DoctorScheduleScreen extends StatefulWidget {
  final ConsultationService? consultationService;

  const DoctorScheduleScreen({super.key, this.consultationService});

  @override
  State<DoctorScheduleScreen> createState() => _DoctorScheduleScreenState();
}

class _DoctorScheduleScreenState extends State<DoctorScheduleScreen> {
  late final ConsultationService _consultationService;

  DoctorDailySchedule? _schedule;
  bool _isLoading = true;
  String? _errorMessage;
  String? _activeActionAppointmentId;

  String? _selectedDate;

  @override
  void initState() {
    super.initState();
    _consultationService = widget.consultationService ?? ConsultationService();
    _loadSchedule();
  }

  Future<void> _loadSchedule() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final schedule = _selectedDate == null
          ? await _consultationService.getTodaySchedule()
          : await _consultationService.getScheduleByDate(_selectedDate!);
      if (!mounted) return;
      setState(() {
        _schedule = schedule;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Unable to load daily schedule. Please check your connection.';
      });
    }
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final initial = _selectedDate != null ? DateTime.tryParse(_selectedDate!) ?? now : now;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) {
      final formatted = '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
      setState(() {
        _selectedDate = formatted;
      });
      _loadSchedule();
    }
  }

  void _resetToToday() {
    if (_selectedDate == null) return;
    setState(() {
      _selectedDate = null;
    });
    _loadSchedule();
  }

  Future<void> _handleStartConsultation(ScheduleAppointmentItem item) async {
    if (_activeActionAppointmentId != null) return;

    setState(() => _activeActionAppointmentId = item.appointmentId);
    try {
      await _consultationService.startConsultation(item.appointmentId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Consultation started for ${item.patientName}.'),
          backgroundColor: AppTheme.success,
        ),
      );
      await _loadSchedule();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to start consultation: ${e.toString().replaceAll("Exception:", "").trim()}'),
          backgroundColor: AppTheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _activeActionAppointmentId = null);
    }
  }

  Future<void> _handleCompleteConsultation(ScheduleAppointmentItem item) async {
    if (_activeActionAppointmentId != null) return;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Complete this consultation?', style: TextStyle(fontWeight: FontWeight.bold)),
        content: Text('Are you sure you want to conclude the consultation for ${item.patientName}?'),
        actions: [
          TextButton(
            key: const Key('complete_consultation_cancel_button'),
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('complete_consultation_confirm_button'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Complete Consultation'),
          ),
        ],
      ),
    );

    if (confirm != true || !mounted) return;

    setState(() => _activeActionAppointmentId = item.appointmentId);
    try {
      await _consultationService.completeConsultation(item.appointmentId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Consultation completed for ${item.patientName}.'),
          backgroundColor: AppTheme.success,
        ),
      );
      await _loadSchedule();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to complete consultation: ${e.toString().replaceAll("Exception:", "").trim()}'),
          backgroundColor: AppTheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _activeActionAppointmentId = null);
    }
  }

  void _navigateToDetail(ScheduleAppointmentItem item) async {
    final result = await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ConsultationDetailsScreen(
          appointmentId: item.appointmentId,
          consultationService: _consultationService,
        ),
      ),
    );
    if (result == true) {
      _loadSchedule();
    }
  }

  void _navigateToCreateFollowUpPlan(ScheduleAppointmentItem item) async {
    final appt = Appointment(
      id: item.appointmentId,
      patientUserId: item.patientUserId,
      doctorUserId: '',
      doctorProfileId: '',
      availabilityId: '',
      appointmentDate: item.appointmentDate,
      startTime: item.startTime,
      endTime: item.endTime,
      status: item.bookingStatus,
      patientName: item.patientName,
      patientEmail: item.patientEmail,
    );

    final result = await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => CreateCarePlanScreen(
          appointment: appt,
        ),
      ),
    );
    if (result == true) {
      _loadSchedule();
    }
  }

  Color _getConsultationStatusColor(String status) {
    switch (status.toUpperCase()) {
      case 'IN_PROGRESS':
        return Colors.green.shade700;
      case 'COMPLETED':
        return Colors.deepPurple;
      case 'NOT_STARTED':
      default:
        return const Color(0xFF1565C0);
    }
  }

  Widget _buildConsultationBadge(String status) {
    final color = _getConsultationStatusColor(status);
    final label = status.replaceAll('_', ' ');
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0D1B2A);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FC),
      appBar: AppBar(
        title: const Text(
          "Today's Schedule",
          style: TextStyle(fontWeight: FontWeight.bold, color: navy),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: navy),
        actions: [
          IconButton(
            tooltip: 'Select Date',
            icon: const Icon(Icons.calendar_month_rounded),
            onPressed: _pickDate,
          ),
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadSchedule,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 48),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 15),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _loadSchedule,
                          icon: const Icon(Icons.refresh_rounded),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadSchedule,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // 1. Date & Timezone Header Bar
                        _buildDateHeaderBar(),
                        const SizedBox(height: 16),

                        // 2. Daily Statistics KPI Grid
                        if (_schedule != null) _buildDailyStatsGrid(_schedule!.stats),
                        const SizedBox(height: 20),

                        // 3. Next Eligible Patient Card
                        _buildNextPatientSection(),
                        const SizedBox(height: 20),

                        // 4. Chronological Appointment Schedule
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              "Appointments (${_schedule?.appointments.length ?? 0})",
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: navy,
                              ),
                            ),
                            if (_selectedDate != null)
                              TextButton(
                                onPressed: _resetToToday,
                                child: const Text('Back to Today'),
                              ),
                          ],
                        ),
                        const SizedBox(height: 10),

                        if (_schedule == null || _schedule!.appointments.isEmpty)
                          _buildEmptyAppointmentsCard()
                        else
                          ..._schedule!.appointments.map(_buildAppointmentCard),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildDateHeaderBar() {
    final dateDisplay = _schedule?.date ?? _selectedDate ?? 'Today';
    final tzDisplay = _schedule?.timezone ?? 'Asia/Colombo';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              const Icon(Icons.event_note_rounded, size: 20, color: Color(0xFF1565C0)),
              const SizedBox(width: 8),
              Text(
                dateDisplay,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF0D1B2A)),
              ),
            ],
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFF1565C0).withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.access_time_rounded, size: 13, color: Color(0xFF1565C0)),
                const SizedBox(width: 4),
                Text(
                  tzDisplay,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1565C0),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDailyStatsGrid(DailyScheduleStats stats) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Daily Overview',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Color(0xFF0D1B2A)),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            _buildStatCard('Total', stats.totalScheduled.toString(), const Color(0xFF0D1B2A), Icons.calendar_today_rounded),
            const SizedBox(width: 8),
            _buildStatCard('Upcoming', stats.upcoming.toString(), const Color(0xFF1565C0), Icons.alarm_rounded),
            const SizedBox(width: 8),
            _buildStatCard('Waiting', stats.waiting.toString(), Colors.amber.shade800, Icons.hourglass_top_rounded),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            _buildStatCard('In Progress', stats.inProgress.toString(), Colors.green.shade700, Icons.pending_rounded),
            const SizedBox(width: 8),
            _buildStatCard('Completed', stats.completed.toString(), Colors.deepPurple, Icons.check_circle_rounded),
            const SizedBox(width: 8),
            _buildStatCard('Cancelled', stats.cancelled.toString(), Colors.red.shade700, Icons.cancel_rounded),
          ],
        ),
      ],
    );
  }

  Widget _buildStatCard(String label, String value, Color color, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.outline.withValues(alpha: 0.15)),
        ),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 13, color: color),
                const SizedBox(width: 4),
                Text(
                  label,
                  style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              value,
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: color),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNextPatientSection() {
    final next = _schedule?.nextPatient;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: const [
            Icon(Icons.person_pin_rounded, color: Color(0xFF1565C0), size: 20),
            SizedBox(width: 6),
            Text(
              'Next Patient',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (next == null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
            ),
            child: Row(
              children: [
                Icon(Icons.check_circle_outline_rounded, color: Colors.green.shade600, size: 24),
                const SizedBox(width: 12),
                const Expanded(
                  child: Text(
                    'No upcoming patients for today.',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF0D1B2A),
                    ),
                  ),
                ),
              ],
            ),
          )
        else
          Container(
            key: const Key('next_patient_card'),
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF1565C0),
                  const Color(0xFF1E88E5),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF1565C0).withValues(alpha: 0.25),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.schedule_rounded, color: Colors.white, size: 13),
                          const SizedBox(width: 4),
                          Text(
                            '${next.startTime} - ${next.endTime}',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    _buildNextPatientConsultationBadge(next.consultationStatus),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  next.patientName,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (next.patientNote != null && next.patientNote!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    'Note: ${next.patientNote}',
                    style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        key: const Key('next_patient_view_details_button'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
                          side: const BorderSide(color: Colors.white),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        onPressed: () => _navigateToDetail(next),
                        child: const Text('View Details', style: TextStyle(fontWeight: FontWeight.bold)),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: ElevatedButton(
                        key: const Key('next_patient_start_button'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: const Color(0xFF1565C0),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        onPressed: _activeActionAppointmentId == next.appointmentId
                            ? null
                            : () {
                                if (next.isInProgress) {
                                  _handleCompleteConsultation(next);
                                } else {
                                  _handleStartConsultation(next);
                                }
                              },
                        child: _activeActionAppointmentId == next.appointmentId
                            ? const SizedBox(
                                height: 16,
                                width: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Text(
                                next.isInProgress ? 'Complete Consultation' : 'Start Consultation',
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildNextPatientConsultationBadge(String status) {
    final isProgress = status.toUpperCase() == 'IN_PROGRESS';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isProgress ? Colors.greenAccent.shade700 : Colors.white.withValues(alpha: 0.25),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        status.replaceAll('_', ' '),
        style: TextStyle(
          color: isProgress ? Colors.white : Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildEmptyAppointmentsCard() {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(Icons.event_available_rounded, size: 48, color: Colors.grey.shade400),
          const SizedBox(height: 12),
          const Text(
            'No appointments scheduled for this date.',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF0D1B2A)),
          ),
        ],
      ),
    );
  }

  Widget _buildAppointmentCard(ScheduleAppointmentItem item) {
    const navy = Color(0xFF0D1B2A);
    final isBusy = (_activeActionAppointmentId == item.appointmentId);

    return Card(
      key: Key('schedule_appointment_card_${item.appointmentId}'),
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0.5,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: item.isInProgress
              ? Colors.green.shade400
              : AppTheme.outline.withValues(alpha: 0.2),
          width: item.isInProgress ? 1.5 : 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Time & Status Badges
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    const Icon(Icons.access_time_rounded, size: 15, color: Color(0xFF1565C0)),
                    const SizedBox(width: 5),
                    Text(
                      '${item.startTime} - ${item.endTime}',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: navy),
                    ),
                  ],
                ),
                Row(
                  children: [
                    _buildConsultationBadge(item.consultationStatus),
                    const SizedBox(width: 6),
                    _buildBookingStatusBadge(item.bookingStatus),
                  ],
                ),
              ],
            ),
            const Divider(height: 18),

            // Patient Name & Notes
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 18,
                  backgroundColor: const Color(0xFF1565C0).withValues(alpha: 0.1),
                  child: const Icon(Icons.person, size: 18, color: Color(0xFF1565C0)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.patientName,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: navy),
                      ),
                      if (item.patientNote != null && item.patientNote!.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          item.patientNote!,
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),

            // Clinical Badges if any
            if (item.hasPrescription || item.hasMedicalRecord || item.hasCarePlan) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  if (item.hasCarePlan)
                    _buildMiniBadge('Care Plan', Icons.assignment_turned_in_rounded, Colors.purple),
                  if (item.hasPrescription)
                    _buildMiniBadge('Rx Issued', Icons.medication_rounded, Colors.teal),
                  if (item.hasMedicalRecord)
                    _buildMiniBadge('Notes Documented', Icons.description_rounded, Colors.indigo),
                ],
              ),
            ],

            const SizedBox(height: 14),

            // Action Buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF1565C0),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    onPressed: () => _navigateToDetail(item),
                    child: const Text('View Details', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  ),
                ),
                const SizedBox(width: 8),

                if (!item.isCancelled && item.isNotStarted) ...[
                  Expanded(
                    child: ElevatedButton(
                      key: Key('start_consultation_button_${item.appointmentId}'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1565C0),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      onPressed: isBusy ? null : () => _handleStartConsultation(item),
                      child: isBusy
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('Start', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ] else if (!item.isCancelled && item.isInProgress) ...[
                  Expanded(
                    child: ElevatedButton(
                      key: Key('complete_consultation_button_${item.appointmentId}'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green.shade700,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      onPressed: isBusy ? null : () => _handleCompleteConsultation(item),
                      child: isBusy
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('Complete', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ] else if (item.isCompleted) ...[
                  Expanded(
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.deepPurple,
                        side: const BorderSide(color: Colors.deepPurple),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      icon: const Icon(Icons.assignment_add, size: 14),
                      label: const Text('Follow-up', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      onPressed: () => _navigateToCreateFollowUpPlan(item),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBookingStatusBadge(String status) {
    Color c = AppTheme.textSecondary;
    if (status == 'CONFIRMED') c = Colors.green.shade700;
    if (status == 'CANCELLED') c = AppTheme.error;
    if (status == 'PENDING') c = Colors.amber.shade800;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: c.withValues(alpha: 0.2)),
      ),
      child: Text(
        status,
        style: TextStyle(fontSize: 10, color: c, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildMiniBadge(String text, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: color),
          const SizedBox(width: 3),
          Text(text, style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
