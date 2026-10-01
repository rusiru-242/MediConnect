import 'package:flutter/material.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/doctor.dart';
import '../../models/doctor_availability.dart';
import '../../services/appointment_service.dart';
import 'appointment_detail_screen.dart';

/// Screen where patient reviews booking details and submits the appointment request.
/// Strict requirement: NO payment requests or "Payment successful" messages.
class BookingConfirmationScreen extends StatefulWidget {
  final Doctor doctor;
  final String date;
  final TimeSlot slot;
  final AppointmentService? appointmentService;

  const BookingConfirmationScreen({
    super.key,
    required this.doctor,
    required this.date,
    required this.slot,
    this.appointmentService,
  });

  @override
  State<BookingConfirmationScreen> createState() =>
      _BookingConfirmationScreenState();
}

class _BookingConfirmationScreenState extends State<BookingConfirmationScreen> {
  late final AppointmentService _appointmentService;
  final TextEditingController _noteController = TextEditingController();

  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _appointmentService =
        widget.appointmentService ?? AppointmentService();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _submitBooking() async {
    if (_isSubmitting) return;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      final appointment = await _appointmentService.createAppointment(
        doctorId: widget.doctor.doctorId,
        availabilityId: widget.slot.availabilityId,
        date: widget.date,
        startTime: widget.slot.startTime,
        patientNote: _noteController.text.trim().isNotEmpty
            ? _noteController.text.trim()
            : null,
      );

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Appointment request submitted.'),
          backgroundColor: AppTheme.success,
          behavior: SnackBarBehavior.floating,
        ),
      );

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => AppointmentDetailScreen(
            appointment: appointment,
            appointmentId: appointment.id,
          ),
        ),
      );
    } on ConflictException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage =
            'This time slot was just booked by another patient. Please select another time.';
      });

      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Slot Unavailable'),
          content: Text(
            e.message.isNotEmpty
                ? e.message
                : 'This time slot was just booked by another patient. Please select another time.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.pop(context, true); // Pop back to refresh slots
              },
              child: const Text('Select Another Slot'),
            ),
          ],
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = e.message;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e.message),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = 'An unexpected error occurred. Please try again.';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('An unexpected error occurred. Please try again.'),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Confirm Booking'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Doctor Summary Card
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
                      radius: 28,
                      backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                      child: const Icon(
                        Icons.person,
                        color: AppTheme.primary,
                        size: 32,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.doctor.fullName,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            widget.doctor.specialty,
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppTheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (widget.doctor.hospitalOrClinic.isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Text(
                              widget.doctor.hospitalOrClinic,
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
              ),

              const SizedBox(height: 20),

              // Date & Time Summary Card
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
                        const Icon(
                          Icons.calendar_today,
                          size: 18,
                          color: AppTheme.primary,
                        ),
                        const SizedBox(width: 10),
                        const Text(
                          'Date:',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          widget.date,
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
                        const Icon(
                          Icons.access_time,
                          size: 18,
                          color: AppTheme.primary,
                        ),
                        const SizedBox(width: 10),
                        const Text(
                          'Time:',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${widget.slot.startTime} - ${widget.slot.endTime}',
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

              const SizedBox(height: 24),

              // Optional Reason / Note
              const Text(
                'Reason for Visit / Note (Optional)',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('booking_patient_note_input'),
                controller: _noteController,
                maxLines: 3,
                maxLength: 500,
                decoration: InputDecoration(
                  hintText: 'Describe your symptoms or reason for visit...',
                  hintStyle: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                  filled: true,
                  fillColor: AppTheme.surfaceVariant.withValues(alpha: 0.2),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: AppTheme.outline.withValues(alpha: 0.3),
                    ),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: AppTheme.outline.withValues(alpha: 0.3),
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                      color: AppTheme.primary,
                      width: 1.5,
                    ),
                  ),
                ),
              ),

              if (_errorMessage != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: AppTheme.error.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.error_outline,
                        color: AppTheme.error,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(
                            color: AppTheme.error,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              const SizedBox(height: 32),

              // Request Appointment Button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  key: const Key('request_appointment_button'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  onPressed: _isSubmitting ? null : _submitBooking,
                  child: _isSubmitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Text(
                          'Request Appointment',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
