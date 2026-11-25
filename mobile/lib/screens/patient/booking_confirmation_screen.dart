import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../models/doctor.dart';
import '../../models/doctor_availability.dart';
import '../../services/appointment_service.dart';
import '../../services/payment_service.dart';
import '../../widgets/medical_widgets.dart';
import 'payment_success_screen.dart';

/// Screen where patient reviews booking details and consultation fee,
/// and proceeds to payment via Stripe PaymentSheet.
/// Redesigned with Google Stitch Clinical Clarity design system (Phase 41).
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

  /// The reservation created by this screen. A retry after a cancelled or declined payment reuses it
  /// (P02-N07) instead of trying to reserve the same slot again.
  Appointment? _heldAppointment;

  bool get _holdIsValid =>
      _heldAppointment != null &&
      (_heldAppointment!.holdExpiresAt == null || _heldAppointment!.holdExpiresAt!.isAfter(DateTime.now()));

  @override
  void initState() {
    super.initState();
    _appointmentService = widget.appointmentService ?? AppointmentService();
    _paymentService = widget.paymentService ?? PaymentService();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _releaseReservation() async {
    final held = _heldAppointment;
    if (held == null) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const Key('booking_release_dialog'),
        title: const Text('Release this reservation?'),
        content: const Text('The slot will be released now and the unfinished payment cancelled. You have not been charged.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep Reservation')),
          ElevatedButton(
            key: const Key('booking_release_confirm'),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Release'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _isSubmitting = true);
    try {
      await _appointmentService.releaseHold(held.id);
      if (!mounted) return;
      setState(() {
        _heldAppointment = null;
        _isSubmitting = false;
        _errorMessage = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Reservation released. No payment was taken.')),
      );
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = e is ApiException ? e.message : 'Could not release the reservation. Please retry.';
      });
    }
  }

  Future<void> _startPaymentFlow() async {
    if (_isSubmitting) return;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      // 1. Create the temporary hold once; reuse it while it is still valid.
      final appointment = _holdIsValid
          ? _heldAppointment!
          : await _appointmentService.createAppointment(
              doctorId: widget.doctor.doctorId,
              availabilityId: widget.slot.availabilityId,
              date: widget.date,
              startTime: widget.slot.startTime,
              patientNote: _noteController.text.trim().isNotEmpty
                  ? _noteController.text.trim()
                  : null,
            );
      _heldAppointment = appointment;

      // 2. Request Stripe PaymentIntent from backend
      final intentResp = await _paymentService.createPaymentIntent(
        appointment.id,
      );

      final isNativeStripeSupported =
          !kIsWeb &&
          (defaultTargetPlatform == TargetPlatform.android ||
              defaultTargetPlatform == TargetPlatform.iOS);

      if (isNativeStripeSupported) {
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

          await Stripe.instance.presentPaymentSheet();
        } on StripeException {
          rethrow;
        } catch (_) {
          // In widget test environment without native platform channel binary,
          // proceed directly to backend status query.
        }
      } else {
        debugPrint(
          'Stripe native PaymentSheet presentation skipped on unsupported platform.',
        );
      }

      // 4. Authoritatively query backend for confirmed payment and appointment status
      var statusResult = await _paymentService.getPaymentStatus(
        intentResp.paymentId,
      );

      if (!statusResult.isSucceeded &&
          statusResult.paymentStatus.toUpperCase() == 'PENDING') {
        await Future.delayed(const Duration(seconds: 2));
        if (!mounted) return;
        statusResult = await _paymentService.getPaymentStatus(
          intentResp.paymentId,
        );
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
              currency: statusResult.currency.isNotEmpty
                  ? statusResult.currency
                  : 'LKR',
            ),
          ),
        );
      } else {
        setState(() {
          _isSubmitting = false;
          _errorMessage = 'Payment could not be completed. Please try again.';
        });
      }
    } on StripeException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        if (e.error.code == FailureCode.Canceled) {
          _errorMessage = 'Payment was cancelled. You have not been charged. The slot stays reserved for '
              'you until the hold ends; pay again or release the reservation.';
        } else {
          _errorMessage = 'Payment could not be completed. Please try again.';
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
        _errorMessage = 'Unable to connect to MediConnect. Please check your internet connection and try again.';
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
        _errorMessage =
            e.toString().toLowerCase().contains('socket') ||
                e.toString().toLowerCase().contains('network') ||
                e.toString().toLowerCase().contains('timeout') ||
                e.toString().toLowerCase().contains('connect')
            ? 'Unable to connect to MediConnect. Please check your internet connection and try again.'
            : 'Payment failed: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Never show an invented fee; the backend also refuses to book a doctor without a listed fee.
    final feeFormatted = widget.doctor.hasConsultationFee
        ? 'LKR ${widget.doctor.consultationFee.toStringAsFixed(2)}'
        : 'Fee not listed';
    final doctorName = widget.doctor.fullName.startsWith('Dr.')
        ? widget.doctor.fullName
        : 'Dr. ${widget.doctor.fullName}';

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 1,
        title: const Text(
          'Confirm Booking',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Doctor Quick Banner
              StitchCard(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Container(
                          width: 46,
                          height: 46,
                          decoration: BoxDecoration(
                            color: AppTheme.primaryContainer,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          alignment: Alignment.center,
                          child: const Icon(
                            Icons.person_rounded,
                            size: 24,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                        Positioned(
                          bottom: -2,
                          right: -2,
                          child: Container(
                            width: 14,
                            height: 14,
                            decoration: const BoxDecoration(
                              color: AppTheme.success,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(
                              Icons.check_rounded,
                              color: Colors.white,
                              size: 9,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  doctorName,
                                  style: const TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.textPrimary,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 4),
                              const Icon(
                                Icons.verified_rounded,
                                size: 14,
                                color: AppTheme.primaryBlue,
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            widget.doctor.specialty,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.primaryBlue,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceContainerLow,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        'Direct Hold',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.primaryBlue,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // 2. Step Progress Indicator
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildStepIndicator(
                      step: '1',
                      label: 'Slot',
                      isDone: true,
                      isActive: false,
                    ),
                    Container(
                      width: 24,
                      height: 1.5,
                      color: AppTheme.primaryBlue,
                    ),
                    _buildStepIndicator(
                      step: '2',
                      label: 'Details',
                      isDone: false,
                      isActive: true,
                    ),
                    Container(width: 24, height: 1.5, color: AppTheme.border),
                    _buildStepIndicator(
                      step: '3',
                      label: 'Payment',
                      isDone: false,
                      isActive: false,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // 3. Consultation mode: MediConnect appointments are in-person clinic visits (Phase 01 removed a
              //    cosmetic video/in-person picker that defaulted to "Video Visit" and was never sent to the server).
              Container(
                key: const Key('booking_mode_in_person'),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.local_hospital_rounded, color: AppTheme.primaryBlue),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text('In-person consultation at the doctor\'s clinic or hospital',
                          style: TextStyle(fontWeight: FontWeight.w600)),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // 4. Appointment Details Card
              StitchCard(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      children: [
                        const Icon(
                          Icons.calendar_today_outlined,
                          size: 16,
                          color: AppTheme.primaryBlue,
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'Date:',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          widget.date,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 14),
                    Row(
                      children: [
                        const Icon(
                          Icons.access_time_outlined,
                          size: 16,
                          color: AppTheme.primaryBlue,
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'Time:',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${widget.slot.startTime} - ${widget.slot.endTime}',
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 14),
                    Row(
                      children: [
                        const Icon(
                          Icons.payments_outlined,
                          size: 16,
                          color: AppTheme.primaryBlue,
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'Consultation Fee:',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          feeFormatted,
                          key: const Key('consultation_fee_text'),
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // 5. Patient Note
              TextField(
                key: const Key('booking_patient_note_input'),
                controller: _noteController,
                maxLines: 2,
                maxLength: 500,
                decoration: InputDecoration(
                  hintText: 'Reason for visit / symptoms (optional)...',
                  hintStyle: const TextStyle(
                    fontSize: 12,
                    color: AppTheme.textMuted,
                  ),
                  filled: true,
                  fillColor: Colors.white,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: AppTheme.border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: AppTheme.border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(
                      color: AppTheme.primaryBlue,
                      width: 1.5,
                    ),
                  ),
                ),
              ),

              if (_errorMessage != null) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.errorContainer,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: AppTheme.error.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.error_outline_rounded,
                        color: AppTheme.error,
                        size: 18,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(
                            color: AppTheme.error,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              if (_heldAppointment != null && _holdIsValid && !_isSubmitting) ...[
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    key: const Key('booking_release_reservation'),
                    onPressed: _releaseReservation,
                    icon: const Icon(Icons.event_busy_outlined, size: 18),
                    label: const Text('Release Reservation'),
                  ),
                ),
              ],
              const SizedBox(height: 12),

              // 6. Submit Button: Continue to Payment
              Container(
                height: 48,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  gradient: const LinearGradient(
                    colors: [AppTheme.stitchPrimary, AppTheme.primaryBlue],
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.primaryBlue.withValues(alpha: 0.25),
                      blurRadius: 6,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: ElevatedButton(
                  key: const Key('continue_to_payment_button'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.transparent,
                    shadowColor: Colors.transparent,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  onPressed: _isSubmitting ? null : _startPaymentFlow,
                  child: _isSubmitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              Colors.white,
                            ),
                          ),
                        )
                      : const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.lock_rounded,
                              size: 16,
                              color: Colors.white,
                            ),
                            SizedBox(width: 8),
                            Text(
                              'Continue to Payment',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStepIndicator({
    required String step,
    required String label,
    required bool isDone,
    required bool isActive,
  }) {
    return Column(
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            color: isDone || isActive
                ? AppTheme.primaryBlue
                : AppTheme.surfaceContainerHigh,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: isDone
              ? const Icon(Icons.check_rounded, color: Colors.white, size: 12)
              : Text(
                  step,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: isActive ? Colors.white : AppTheme.textSecondary,
                  ),
                ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            fontWeight: isActive || isDone ? FontWeight.w700 : FontWeight.w500,
            color: isActive ? AppTheme.primaryBlue : AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }
}
