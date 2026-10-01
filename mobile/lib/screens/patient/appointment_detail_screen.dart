import 'package:flutter/material.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../services/appointment_service.dart';

/// Screen displaying complete details of an appointment for a patient.
/// Allows cancellation if status is PENDING or CONFIRMED.
class AppointmentDetailScreen extends StatefulWidget {
  final Appointment? appointment;
  final String? appointmentId;
  final AppointmentService? appointmentService;

  const AppointmentDetailScreen({
    super.key,
    this.appointment,
    this.appointmentId,
    this.appointmentService,
  });

  @override
  State<AppointmentDetailScreen> createState() =>
      _AppointmentDetailScreenState();
}

class _AppointmentDetailScreenState extends State<AppointmentDetailScreen> {
  late final AppointmentService _appointmentService;
  Appointment? _appointment;
  String? _effectiveId;

  bool _isLoading = false;
  String? _errorMessage;
  bool _isCancelling = false;

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

  Future<void> _promptCancelAppointment() async {
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
              'Are you sure you want to cancel this appointment? This action cannot be undone.',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 16),
            TextField(
              key: const Key('cancellation_reason_input'),
              controller: reasonController,
              decoration: const InputDecoration(
                labelText: 'Reason for cancellation (optional)',
                hintText: 'e.g. Schedule conflict, feeling better...',
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
            key: const Key('confirm_cancel_button'),
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

    setState(() {
      _isCancelling = true;
    });

    try {
      final updated = await _appointmentService.cancelPatientAppointment(
        _appointment!.id,
        reason: reasonController.text.trim().isNotEmpty
            ? reasonController.text.trim()
            : null,
      );

      if (!mounted) return;
      setState(() {
        _appointment = updated;
        _isCancelling = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Appointment has been cancelled.'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isCancelling = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e is ApiException ? e.message : 'Failed to cancel appointment.'),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
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
        title: const Text('Appointment Details'),
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
                          // Status and ID banner
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

                          // Doctor Details Card
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
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    CircleAvatar(
                                      radius: 26,
                                      backgroundColor:
                                          AppTheme.primary.withValues(alpha: 0.1),
                                      child: const Icon(
                                        Icons.person,
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
                                            _appointment!.doctorName ??
                                                'Doctor Profile',
                                            style: const TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.bold,
                                              color: AppTheme.textPrimary,
                                            ),
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            _appointment!.specialty ??
                                                'Consultant',
                                            style: const TextStyle(
                                              fontSize: 13,
                                              color: AppTheme.primary,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          if (_appointment!.hospitalOrClinic !=
                                                  null &&
                                              _appointment!.hospitalOrClinic!
                                                  .isNotEmpty) ...[
                                            const SizedBox(height: 2),
                                            Text(
                                              _appointment!.hospitalOrClinic!,
                                              style: const TextStyle(
                                                fontSize: 12,
                                                color: AppTheme.textSecondary,
                                              ),
                                            ),
                                          ],
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 16),

                          // Date & Time Card
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

                          // Patient Note (if present)
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
                                    'Patient Note',
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

                          // Cancellation Details (if cancelled)
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
                            const SizedBox(height: 24),
                          ],

                          // Cancel Appointment Action
                          if (_appointment!.canCancel) ...[
                            const SizedBox(height: 20),
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                key: const Key('cancel_appointment_button'),
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: AppTheme.error,
                                  side: const BorderSide(color: AppTheme.error),
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                icon: _isCancelling
                                    ? const SizedBox(
                                        height: 18,
                                        width: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: AppTheme.error,
                                        ),
                                      )
                                    : const Icon(Icons.cancel_outlined),
                                label: Text(
                                  _isCancelling
                                      ? 'Cancelling...'
                                      : 'Cancel Appointment',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w600),
                                ),
                                onPressed: _isCancelling
                                    ? null
                                    : _promptCancelAppointment,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
    );
  }
}
