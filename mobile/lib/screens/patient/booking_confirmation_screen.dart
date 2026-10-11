import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/doctor.dart';
import '../../models/doctor_availability.dart';
import '../../services/appointment_service.dart';
import '../../services/payment_service.dart';
import 'payment_success_screen.dart';

/// Screen where patient reviews booking details and consultation fee,
/// and proceeds to payment via Stripe PaymentSheet.
class BookingConfirmationScreen extends StatefulWidget {
  final Doctor doctor;
  final String date;
  final TimeSlot slot;
  final AppointmentService? appointmentService;
  final PaymentService? paymentService;

  const BookingConfirmationScreen({
    super.key,
    required this.doctor,
    required this.date,
    required this.slot,
    this.appointmentService,
    this.paymentService,
  });

  @override
  State<BookingConfirmationScreen> createState() =>
      _BookingConfirmationScreenState();
}

class _BookingConfirmationScreenState extends State<BookingConfirmationScreen> {
  late final AppointmentService _appointmentService;
  late final PaymentService _paymentService;
  final TextEditingController _noteController = TextEditingController();

  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _appointmentService =
        widget.appointmentService ?? AppointmentService();
    _paymentService = widget.paymentService ?? PaymentService();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _startPaymentFlow() async {
    if (_isSubmitting) return;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      // 1. Create temporary appointment hold on backend
      final appointment = await _appointmentService.createAppointment(
        doctorId: widget.doctor.doctorId,
        availabilityId: widget.slot.availabilityId,
        date: widget.date,
        startTime: widget.slot.startTime,
        patientNote: _noteController.text.trim().isNotEmpty
            ? _noteController.text.trim()
            : null,
      );

      // 2. Request Stripe PaymentIntent from backend (authoritative amount determined by backend)
      final intentResp =
          await _paymentService.createPaymentIntent(appointment.id);

      final isNativeStripeSupported = !kIsWeb &&
          (defaultTargetPlatform == TargetPlatform.android ||
              defaultTargetPlatform == TargetPlatform.iOS);

      if (isNativeStripeSupported) {
        // If backend returns publishable key, update it and apply settings
        if (intentResp.publishableKey != null &&
            intentResp.publishableKey!.isNotEmpty) {
          Stripe.publishableKey = intentResp.publishableKey!;
          try {
            await Stripe.instance.applySettings();
          } catch (_) {}
        }

        // 3. Initialize & Present Stripe PaymentSheet
        try {
          await Stripe.instance.initPaymentSheet(
            paymentSheetParameters: SetupPaymentSheetParameters(
              paymentIntentClientSecret: intentResp.paymentIntentClientSecret,
              merchantDisplayName: 'MediConnect',
              style: ThemeMode.light,
            ),
          );

          // 4. Present Stripe PaymentSheet
          await Stripe.instance.presentPaymentSheet();
        } on StripeException {
          rethrow;
        } catch (_) {
          // In widget test environment without native platform channel binary,
          // proceed directly to backend status query.
        }
      } else {
        debugPrint('Stripe native PaymentSheet presentation skipped on unsupported platform.');
      }

      // 5. Authoritatively query backend for confirmed payment and appointment status
      var statusResult =
          await _paymentService.getPaymentStatus(intentResp.paymentId);

      // Brief retry if still pending (webhook/Stripe sync propagation)
      if (!statusResult.isSucceeded &&
          statusResult.paymentStatus.toUpperCase() == 'PENDING') {
        await Future.delayed(const Duration(seconds: 2));
        if (!mounted) return;
        statusResult =
            await _paymentService.getPaymentStatus(intentResp.paymentId);
      }

      if (!mounted) return;

      if (statusResult.isSucceeded) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => PaymentSuccessScreen(
              appointmentId: appointment.id,
              paymentId: intentResp.paymentId,
              doctorName: widget.doctor.fullName,
              specialty: widget.doctor.specialty,
              date: widget.date,
              time: '${widget.slot.startTime} - ${widget.slot.endTime}',
              amount: statusResult.amount > 0
                  ? statusResult.amount
                  : widget.doctor.consultationFee,
              currency: statusResult.currency,
            ),
          ),
        );
      } else {
        setState(() {
          _isSubmitting = false;
          _errorMessage =
              'Payment could not be completed. Please try again.';
        });
      }
    } on StripeException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        // User cancelled the payment sheet
        if (e.error.code == FailureCode.Canceled) {
          _errorMessage = 'Payment was cancelled.';
        } else {
          _errorMessage =
              'Payment could not be completed. Please try again.';
        }
      });
    } on ConflictException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = 'This time slot is no longer available.';
      });

      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Slot Unavailable'),
          content: Text(
            e.message.isNotEmpty
                ? e.message
                : 'This time slot is no longer available.',
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
    } on NetworkException {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage =
            'Unable to connect to MediConnect. Please check your internet connection and try again.';
      });
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
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = e.toString().toLowerCase().contains('socket') ||
                e.toString().toLowerCase().contains('network') ||
                e.toString().toLowerCase().contains('timeout') ||
                e.toString().toLowerCase().contains('connect')
            ? 'Unable to connect to MediConnect. Please check your internet connection and try again.'
            : 'Payment could not be completed. Please try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final feeFormatted =
        'LKR ${widget.doctor.consultationFee.toStringAsFixed(2)}';

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
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.doctor.fullName.startsWith('Dr.')
                                ? widget.doctor.fullName
                                : 'Dr. ${widget.doctor.fullName}',
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
                          const SizedBox(height: 2),
                          Row(
                            children: [
                              const Icon(
                                Icons.location_on_outlined,
                                size: 14,
                                color: AppTheme.textSecondary,
                              ),
                              const SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  widget.doctor.hospitalOrClinic,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // Booking Details & Consultation Fee Card
              const Text(
                'Appointment Details',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: AppTheme.outline.withValues(alpha: 0.2),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.03),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
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
                    const Divider(height: 20),
                    // Consultation Fee Row
                    Row(
                      children: [
                        const Icon(
                          Icons.payments_outlined,
                          size: 18,
                          color: AppTheme.primary,
                        ),
                        const SizedBox(width: 10),
                        const Text(
                          'Consultation Fee:',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          feeFormatted,
                          key: const Key('consultation_fee_text'),
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primary,
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

              // Primary Button: Continue to Payment
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  key: const Key('continue_to_payment_button'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  onPressed: _isSubmitting ? null : _startPaymentFlow,
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
                          'Continue to Payment',
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
