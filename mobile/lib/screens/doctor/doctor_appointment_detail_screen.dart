import 'package:flutter/material.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../services/appointment_service.dart';

/// Doctor's detail view for managing an assigned appointment.
/// Supports state transitions:
/// - PENDING -> CONFIRMED
/// - CONFIRMED -> COMPLETED
/// - PENDING/CONFIRMED -> CANCELLED
class DoctorAppointmentDetailScreen extends StatefulWidget {
  final Appointment? appointment;
  final String? appointmentId;
  final AppointmentService? appointmentService;

  const DoctorAppointmentDetailScreen({
    super.key,
    this.appointment,
    this.appointmentId,
    this.appointmentService,
  });

  @override
  State<DoctorAppointmentDetailScreen> createState() =>
      _DoctorAppointmentDetailScreenState();
}

class _DoctorAppointmentDetailScreenState
    extends State<DoctorAppointmentDetailScreen> {
  late final AppointmentService _appointmentService;
  Appointment? _appointment;
  String? _effectiveId;

  bool _isLoading = false;
  String? _errorMessage;
  bool _isActionInProgress = false;

  @override
  void initState() {
    super.initState();
    _appointmentService =
        widget.appointmentService ?? AppointmentService();
    _appointment = widget.appointment;
    _effectiveId = widget.appointment?.id ?? widget.appointmentId;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_appointment == null && _effectiveId == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Appointment) {
        _appointment = args;
        _effectiveId = args.id;
      } else if (args is String) {
        _effectiveId = args;
      }
    }

    if (_appointment == null && _effectiveId != null && !_isLoading) {
      _loadAppointment();
    }
  }

  Future<void> _loadAppointment() async {
    if (_effectiveId == null) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final appt = await _appointmentService.getAppointmentDetail(_effectiveId!);
      if (!mounted) return;
      setState(() {
        _appointment = appt;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e is ApiException ? e.message : 'Unable to load appointment details.';
        _isLoading = false;
      });
    }
  }

  Future<void> _confirmAppointment() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Appointment'),
        content: const Text(
          'Are you sure you want to accept and confirm this appointment request?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('confirm_action_dialog_button'),
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.success),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isActionInProgress = true);
    try {
      final updated = await _appointmentService.confirmDoctorAppointment(_appointment!.id);
      if (!mounted) return;
      setState(() {
        _appointment = updated;
        _isActionInProgress = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Appointment confirmed successfully.'),
          backgroundColor: AppTheme.success,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isActionInProgress = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e is ApiException ? e.message : 'Failed to confirm appointment.'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  Future<void> _completeAppointment() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Complete Consultation'),
        content: const Text(
          'Mark this consultation as completed? Make sure the scheduled consultation time has occurred.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            key: const Key('complete_action_dialog_button'),
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primary),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Mark Completed'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isActionInProgress = true);
    try {
      final updated = await _appointmentService.completeDoctorAppointment(_appointment!.id);
      if (!mounted) return;
      setState(() {
        _appointment = updated;
        _isActionInProgress = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Appointment marked as completed.'),
          backgroundColor: AppTheme.success,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isActionInProgress = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e is ApiException ? e.message : 'Cannot complete appointment yet.'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  Future<void> _cancelAppointment() async {
    final reasonController = TextEditingController();

    final shouldCancel = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel Appointment'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Are you sure you need to cancel this appointment?',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 16),
            TextField(
              key: const Key('doctor_cancellation_reason_input'),
              controller: reasonController,
              decoration: const InputDecoration(
                labelText: 'Reason for cancellation (optional)',
                hintText: 'e.g. Emergency, Doctor unavailable...',
                border: OutlineInputBorder(),
              ),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Keep Appointment'),
          ),
          ElevatedButton(
            key: const Key('doctor_confirm_cancel_button'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm Cancel'),
          ),
        ],
      ),
    );

    if (shouldCancel != true || !mounted) return;

    setState(() => _isActionInProgress = true);
    try {
      final updated = await _appointmentService.cancelDoctorAppointment(
        _appointment!.id,
        reason: reasonController.text.trim().isNotEmpty
            ? reasonController.text.trim()
            : null,
      );
      if (!mounted) return;
      setState(() {
        _appointment = updated;
        _isActionInProgress = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Appointment has been cancelled.'),
          backgroundColor: AppTheme.success,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isActionInProgress = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e is ApiException ? e.message : 'Failed to cancel appointment.'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  Widget _buildStatusChip(String status) {
    Color bg;
    Color fg;
    IconData icon;

    switch (status.toUpperCase()) {
      case 'PENDING':
        bg = Colors.amber.shade100;
        fg = Colors.amber.shade900;
        icon = Icons.hourglass_top;
        break;
      case 'CONFIRMED':
        bg = Colors.green.shade100;
        fg = Colors.green.shade800;
        icon = Icons.check_circle_outline;
        break;
      case 'COMPLETED':
        bg = Colors.blue.shade100;
        fg = Colors.blue.shade800;
        icon = Icons.task_alt;
        break;
      case 'CANCELLED':
        bg = Colors.red.shade100;
        fg = Colors.red.shade800;
        icon = Icons.cancel_outlined;
        break;
      default:
        bg = Colors.grey.shade200;
        fg = Colors.grey.shade800;
        icon = Icons.info_outline;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: fg),
          const SizedBox(width: 6),
          Text(
            status.toUpperCase(),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: fg,
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Manage Appointment'),
        centerTitle: true,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline,
                            color: AppTheme.error, size: 48),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 15),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadAppointment,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _appointment == null
                  ? const Center(child: Text('Appointment not found.'))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Status & ID
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              _buildStatusChip(_appointment!.status),
                              Text(
                                'ID: ${_appointment!.id.substring(0, _appointment!.id.length > 8 ? 8 : _appointment!.id.length)}...',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: AppTheme.textSecondary,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ),

                          const SizedBox(height: 20),

                          // Patient info card
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: AppTheme.surfaceVariant.withValues(alpha: 0.3),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: AppTheme.outline.withValues(alpha: 0.2),
                              ),
                            ),
                            child: Row(
                              children: [
                                CircleAvatar(
                                  radius: 26,
                                  backgroundColor:
                                      AppTheme.primary.withValues(alpha: 0.1),
                                  child: const Icon(
                                    Icons.person_outline,
                                    color: AppTheme.primary,
                                    size: 30,
                                  ),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        _appointment!.patientName ?? 'Patient',
                                        style: const TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.bold,
                                          color: AppTheme.textPrimary,
                                        ),
                                      ),
                                      if (_appointment!.patientEmail != null &&
                                          _appointment!.patientEmail!.isNotEmpty) ...[
                                        const SizedBox(height: 4),
                                        Text(
                                          _appointment!.patientEmail!,
                                          style: const TextStyle(
                                            fontSize: 13,
                                            color: AppTheme.textSecondary,
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 16),

                          // Date & Time card
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: AppTheme.surfaceVariant.withValues(alpha: 0.3),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: AppTheme.outline.withValues(alpha: 0.2),
                              ),
                            ),
                            child: Column(
                              children: [
                                Row(
                                  children: [
                                    const Icon(Icons.calendar_today,
                                        size: 18, color: AppTheme.primary),
                                    const SizedBox(width: 10),
                                    const Text('Date:',
                                        style: TextStyle(
                                            fontSize: 14,
                                            color: AppTheme.textSecondary)),
                                    const Spacer(),
                                    Text(
                                      _appointment!.appointmentDate,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                  ],
                                ),
                                const Divider(height: 20),
                                Row(
                                  children: [
                                    const Icon(Icons.access_time,
                                        size: 18, color: AppTheme.primary),
                                    const SizedBox(width: 10),
                                    const Text('Time:',
                                        style: TextStyle(
                                            fontSize: 14,
                                            color: AppTheme.textSecondary)),
                                    const Spacer(),
                                    Text(
                                      '${_appointment!.startTime} - ${_appointment!.endTime}',
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 16),

                          // Patient Note
                          if (_appointment!.patientNote != null &&
                              _appointment!.patientNote!.isNotEmpty) ...[
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: AppTheme.surfaceVariant
                                    .withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: AppTheme.outline
                                      .withValues(alpha: 0.2),
                                ),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Reason for Visit / Patient Note',
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                      color: AppTheme.textSecondary,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    _appointment!.patientNote!,
                                    style: const TextStyle(
                                      fontSize: 14,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 16),
                          ],

                          // Cancellation reason (if cancelled)
                          if (_appointment!.isCancelled) ...[
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: AppTheme.error.withValues(alpha: 0.08),
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: AppTheme.error.withValues(alpha: 0.2),
                                ),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(Icons.info_outline,
                                          color: AppTheme.error, size: 18),
                                      const SizedBox(width: 8),
                                      Text(
                                        'Cancelled by ${_appointment!.cancelledBy ?? "Unknown"}',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: AppTheme.error,
                                          fontSize: 13,
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (_appointment!.cancellationReason !=
                                          null &&
                                      _appointment!.cancellationReason!
                                          .isNotEmpty) ...[
                                    const SizedBox(height: 6),
                                    Text(
                                      'Reason: ${_appointment!.cancellationReason}',
                                      style: const TextStyle(
                                        fontSize: 13,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                            const SizedBox(height: 20),
                          ],

                          // Action Buttons
                          if (_appointment!.isPending) ...[
                            const SizedBox(height: 20),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                key: const Key('doctor_confirm_button'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.success,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                icon: _isActionInProgress
                                    ? const SizedBox(
                                        height: 18,
                                        width: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.check_circle_outline),
                                label: const Text(
                                  'Confirm Appointment',
                                  style: TextStyle(
                                      fontSize: 15,
                                      fontWeight: FontWeight.bold),
                                ),
                                onPressed: _isActionInProgress
                                    ? null
                                    : _confirmAppointment,
                              ),
                            ),
                            const SizedBox(height: 12),
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                key: const Key('doctor_cancel_button'),
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: AppTheme.error,
                                  side: const BorderSide(color: AppTheme.error),
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                icon: const Icon(Icons.cancel_outlined),
                                label: const Text('Cancel Appointment'),
                                onPressed: _isActionInProgress
                                    ? null
                                    : _cancelAppointment,
                              ),
                            ),
                          ],

                          if (_appointment!.isConfirmed) ...[
                            const SizedBox(height: 20),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                key: const Key('doctor_complete_button'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.primary,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                icon: _isActionInProgress
                                    ? const SizedBox(
                                        height: 18,
                                        width: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.task_alt),
                                label: const Text(
                                  'Mark as Completed',
                                  style: TextStyle(
                                      fontSize: 15,
                                      fontWeight: FontWeight.bold),
                                ),
                                onPressed: _isActionInProgress
                                    ? null
                                    : _completeAppointment,
                              ),
                            ),
                            const SizedBox(height: 12),
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                key: const Key('doctor_cancel_button'),
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: AppTheme.error,
                                  side: const BorderSide(color: AppTheme.error),
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                icon: const Icon(Icons.cancel_outlined),
                                label: const Text('Cancel Appointment'),
                                onPressed: _isActionInProgress
                                    ? null
                                    : _cancelAppointment,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
    );
  }
}
