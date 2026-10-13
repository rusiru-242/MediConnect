import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' hide Card;

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/booking_session.dart';
import '../../services/ai_booking_service.dart';
import '../../services/payment_service.dart';
import 'my_appointments_screen.dart';
import 'payment_success_screen.dart';

/// Interactive conversational AI screen for discovering doctors,
/// choosing real appointment slots, reviewing summaries, and paying via Stripe.
class AiBookingAssistantScreen extends StatefulWidget {
  final String? initialQuery;
  final AiBookingService? bookingService;
  final PaymentService? paymentService;

  const AiBookingAssistantScreen({
    super.key,
    this.initialQuery,
    this.bookingService,
    this.paymentService,
  });

  @override
  State<AiBookingAssistantScreen> createState() =>
      _AiBookingAssistantScreenState();
}

class _AiBookingAssistantScreenState extends State<AiBookingAssistantScreen> {
  late final AiBookingService _bookingService;
  late final PaymentService _paymentService;

  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  BookingSession? _session;
  bool _isLoading = false;
  bool _isPaymentProcessing = false;
  String? _errorMessage;

  final List<String> _quickPrompts = [
    'Cardiologist in Colombo',
    'Dermatologist tomorrow morning',
    'General Physician under LKR 3000',
    'මට කොළඹ හෘද රෝග වෛද්‍යවරයෙක් අවශ්‍යයි',
  ];

  @override
  void initState() {
    super.initState();
    _bookingService = widget.bookingService ?? AiBookingService();
    _paymentService = widget.paymentService ?? PaymentService();
    _initSession();
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _initSession() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final session = await _bookingService.createSession(
        initialMessage: widget.initialQuery,
      );
      if (!mounted) return;
      setState(() {
        _session = session;
        _isLoading = false;
      });
      _scrollToBottom();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Could not start booking session. Please try again.';
      });
    }
  }

  Future<void> _sendMessage([String? promptText]) async {
    final text = promptText ?? _textController.text.trim();
    if (text.isEmpty || _session == null || _isLoading) return;

    _textController.clear();
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updated = await _bookingService.sendMessage(_session!.id, text);
      if (!mounted) return;
      setState(() {
        _session = updated;
        _isLoading = false;
      });
      _scrollToBottom();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to send message. Please check your connection.';
      });
    }
  }

  Future<void> _selectDoctor(String doctorId) async {
    if (_session == null || _isLoading) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updated =
          await _bookingService.selectDoctor(_session!.id, doctorId);
      if (!mounted) return;
      setState(() {
        _session = updated;
        _isLoading = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Could not select doctor. Please try again.';
      });
    }
  }

  Future<void> _selectSlot(SlotCardSummary slot) async {
    if (_session == null || _isLoading) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updated = await _bookingService.selectSlot(
        _session!.id,
        availabilityId: slot.availabilityId,
        date: slot.date,
        startTime: slot.startTime,
        endTime: slot.endTime,
      );
      if (!mounted) return;
      setState(() {
        _session = updated;
        _isLoading = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Could not select slot. Please try again.';
      });
    }
  }

  Future<void> _confirmBooking() async {
    if (_session == null || _isLoading) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updated = await _bookingService.confirmBooking(_session!.id);
      if (!mounted) return;
      setState(() {
        _session = updated;
        _isLoading = false;
      });
      _scrollToBottom();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Booking confirmation failed. Slot may have been taken.';
      });
    }
  }

  Future<void> _startPaymentFlow() async {
    if (_session == null ||
        _session!.appointmentId == null ||
        _isPaymentProcessing) {
      return;
    }

    setState(() {
      _isPaymentProcessing = true;
      _errorMessage = null;
    });

    try {
      final apptId = _session!.appointmentId!;
      final intentResp = await _paymentService.createPaymentIntent(apptId);

      final isNativeStripeSupported = !kIsWeb &&
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

        try {
          await Stripe.instance.initPaymentSheet(
            paymentSheetParameters: SetupPaymentSheetParameters(
              paymentIntentClientSecret: intentResp.paymentIntentClientSecret,
              merchantDisplayName: 'MediConnect',
              style: ThemeMode.light,
            ),
          );
          await Stripe.instance.presentPaymentSheet();
        } on StripeException catch (e) {
          if (!mounted) return;
          setState(() {
            _isPaymentProcessing = false;
            _errorMessage = e.error.code == FailureCode.Canceled
                ? 'Payment was cancelled.'
                : 'Payment failed: ${e.error.localizedMessage ?? "Try again"}';
          });
          return;
        } catch (_) {}
      }

      // Check authoritative payment status from backend
      var statusResult =
          await _paymentService.getPaymentStatus(intentResp.paymentId);
      if (!statusResult.isSucceeded &&
          statusResult.paymentStatus.toUpperCase() == 'PENDING') {
        await Future.delayed(const Duration(seconds: 2));
        if (!mounted) return;
        statusResult =
            await _paymentService.getPaymentStatus(intentResp.paymentId);
      }

      // Sync backend session state
      final updatedSession =
          await _bookingService.syncPaymentStatus(_session!.id);
      if (!mounted) return;

      setState(() {
        _session = updatedSession;
        _isPaymentProcessing = false;
      });

      if (statusResult.isSucceeded || updatedSession.isConfirmed) {
        final doc = _session?.selectedDoctor;
        final slot = _session?.selectedSlot;
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => PaymentSuccessScreen(
              appointmentId: apptId,
              paymentId: intentResp.paymentId,
              doctorName: doc?.fullName ?? 'Doctor',
              specialty: doc?.specialty ?? '',
              date: slot?.date ?? '',
              time: slot != null ? '${slot.startTime} - ${slot.endTime}' : '',
              amount: statusResult.amount > 0
                  ? statusResult.amount
                  : (doc?.consultationFee ?? 2500.0),
              currency: statusResult.currency,
            ),
          ),
        );
      } else {
        setState(() {
          _errorMessage = 'Payment could not be verified. Please check payment status.';
        });
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isPaymentProcessing = false;
        _errorMessage = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPaymentProcessing = false;
        _errorMessage = 'Payment flow encountered an issue. Please try again.';
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _showEmergencyDialog(String? reason) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.emergency, color: Colors.red, size: 48),
        title: const Text(
          'Emergency Alert (1990)',
          style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red),
        ),
        content: Text(
          reason ??
              'Critical symptoms detected. In Sri Lanka, please call 1990 Suwa Seriya immediately '
              'or visit the nearest hospital emergency unit (ETU).',
          style: const TextStyle(fontSize: 15),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Understood'),
          ),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Please dial 1990 on your mobile phone.'),
                  backgroundColor: Colors.red,
                ),
              );
            },
            icon: const Icon(Icons.phone),
            label: const Text('Call 1990'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppTheme.primaryTeal.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.auto_awesome, color: AppTheme.primaryTeal, size: 20),
            ),
            const SizedBox(width: 10),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('AI Booking Assistant', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                Text('Bilingual (EN / SI) • Verified Doctors', style: TextStyle(fontSize: 11, color: Colors.grey)),
              ],
            ),
          ],
        ),
        actions: [
          if (_session != null && !_session!.isConfirmed && !_session!.isCancelled)
            IconButton(
              icon: const Icon(Icons.close),
              tooltip: 'Cancel Session',
              onPressed: () async {
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Cancel Session?'),
                    content: const Text('Are you sure you want to end this booking session? Any temporary holds will be released.'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('No')),
                      TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Yes, Cancel')),
                    ],
                  ),
                );
                if (confirm == true && _session != null) {
                  await _bookingService.cancelSession(_session!.id);
                  if (!context.mounted) return;
                  Navigator.pop(context);
                }
              },
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Urgent caution banner if emergency detected
            if (_session?.isUrgent == true)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Colors.red.shade300),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Colors.red, size: 28),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Potential Emergency Detected',
                            style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red, fontSize: 13),
                          ),
                          Text(
                            _session?.urgencyReason ?? 'Immediate medical attention advised.',
                            style: TextStyle(fontSize: 12, color: Colors.red.shade900),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      ),
                      onPressed: () => _showEmergencyDialog(_session?.urgencyReason),
                      child: const Text('1990', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                    ),
                  ],
                ),
              ),

            // Error banner
            if (_errorMessage != null)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.red.shade100,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline, color: Colors.red, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(color: Colors.red, fontSize: 12),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 16, color: Colors.red),
                      onPressed: () => setState(() => _errorMessage = null),
                    ),
                  ],
                ),
              ),

            // Transcript message list
            Expanded(
              child: _session == null && _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      itemCount: (_session?.messages.length ?? 0) + 1,
                      itemBuilder: (context, index) {
                        if (index == (_session?.messages.length ?? 0)) {
                          // Render inline interactive components after last message
                          return _buildInteractivePanel();
                        }
                        final msg = _session!.messages[index];
                        return _buildChatBubble(msg);
                      },
                    ),
            ),

            // Quick suggestion prompts
            if (_session != null &&
                (_session!.isCollectingPreferences || _session!.isSearchingDoctors))
              Container(
                height: 40,
                margin: const EdgeInsets.only(bottom: 4),
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  itemCount: _quickPrompts.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 8),
                  itemBuilder: (ctx, i) {
                    final prompt = _quickPrompts[i];
                    return ActionChip(
                      label: Text(prompt, style: const TextStyle(fontSize: 12)),
                      backgroundColor: Colors.grey.shade100,
                      onPressed: () => _sendMessage(prompt),
                    );
                  },
                ),
              ),

            // Text input row
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    offset: const Offset(0, -2),
                    blurRadius: 4,
                  ),
                ],
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendMessage(),
                      decoration: InputDecoration(
                        hintText: 'Type your booking request in EN or SI...',
                        hintStyle: TextStyle(fontSize: 13, color: Colors.grey.shade500),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide(color: Colors.grey.shade300),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide(color: Colors.grey.shade300),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: const BorderSide(color: AppTheme.primary, width: 1.5),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    style: IconButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                    ),
                    icon: _isLoading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.send_rounded, size: 20),
                    onPressed: _isLoading ? null : () => _sendMessage(),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChatBubble(ChatMessage msg) {
    if (msg.isSystem) {
      return Center(
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: Colors.grey.shade200,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            msg.content,
            style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
          ),
        ),
      );
    }

    final isUser = msg.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.primaryTeal : Colors.grey.shade100,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 16),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              msg.content,
              style: TextStyle(
                color: isUser ? Colors.white : Colors.black87,
                fontSize: 14,
                height: 1.35,
              ),
            ),
            const SizedBox(height: 2),
            Align(
              alignment: Alignment.bottomRight,
              child: Text(
                '${msg.timestamp.hour.toString().padLeft(2, '0')}:${msg.timestamp.minute.toString().padLeft(2, '0')}',
                style: TextStyle(
                  fontSize: 9,
                  color: isUser ? Colors.white70 : Colors.grey.shade500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInteractivePanel() {
    if (_session == null) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 1. Doctor Candidate Cards Carousel/List
        if (_session!.candidateDoctors.isNotEmpty &&
            (_session!.isAwaitingDoctor || _session!.isSearchingDoctors))
          _buildDoctorCandidateList(),

        // 2. Slot Selection Chips
        if (_session!.candidateSlots.isNotEmpty && _session!.isAwaitingSlot)
          _buildSlotSelectionList(),

        // 3. Booking Summary Card before confirmation
        if (_session!.bookingSummary != null && _session!.isAwaitingConfirmation)
          _buildBookingSummaryCard(),

        // 4. Hold Created & Pay Now Panel
        if (_session!.isAwaitingPayment || _session!.isHoldCreated)
          _buildPaymentActionCard(),

        // 5. Booking Confirmed Success Card
        if (_session!.isConfirmed)
          _buildConfirmedCard(),

        const SizedBox(height: 16),
      ],
    );
  }

  Widget _buildDoctorCandidateList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 8),
          child: Text(
            'Recommended Specialists',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.grey),
          ),
        ),
        SizedBox(
          height: 185,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: _session!.candidateDoctors.length,
            separatorBuilder: (_, _) => const SizedBox(width: 10),
            itemBuilder: (ctx, i) {
              final doc = _session!.candidateDoctors[i];
              return Container(
                width: 250,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: Colors.grey.shade200),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.04),
                      blurRadius: 6,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: AppTheme.primaryTeal.withValues(alpha: 0.15),
                          child: const Icon(Icons.person, color: AppTheme.primaryTeal),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                doc.fullName,
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              Text(
                                doc.specialty,
                                style: const TextStyle(fontSize: 11, color: AppTheme.primaryTeal),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      doc.hospitalOrClinic ?? 'Clinic',
                      style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const Spacer(),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'LKR ${doc.consultationFee.toStringAsFixed(0)}',
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.darkNavy),
                        ),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            backgroundColor: AppTheme.primaryTeal,
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            minimumSize: const Size(80, 32),
                          ),
                          onPressed: () => _selectDoctor(doc.doctorId),
                          child: const Text('Select', style: TextStyle(fontSize: 11)),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildSlotSelectionList() {
    final slots = _session!.candidateSlots;
    final docName = _session!.selectedDoctor?.fullName ?? 'Doctor';

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.teal.shade100),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.schedule, color: AppTheme.primaryTeal, size: 18),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Available Slots for $docName',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: slots.map((s) {
              return ActionChip(
                backgroundColor: AppTheme.primaryTeal.withValues(alpha: 0.08),
                avatar: const Icon(Icons.access_time, size: 14, color: AppTheme.primaryTeal),
                label: Text(
                  '${s.startTime} - ${s.endTime}',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.darkNavy),
                ),
                onPressed: () => _selectSlot(s),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildBookingSummaryCard() {
    final summary = _session!.bookingSummary!;
    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryTeal.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.receipt_long, color: AppTheme.primaryTeal),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Booking Summary', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                      Text('Review details before temporary hold', style: TextStyle(fontSize: 11, color: Colors.grey)),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 20),
            _buildSummaryRow('Doctor:', summary.doctorName),
            _buildSummaryRow('Specialty:', summary.specialty),
            if (summary.hospitalOrClinic != null)
              _buildSummaryRow('Location:', summary.hospitalOrClinic!),
            _buildSummaryRow('Date:', summary.appointmentDate),
            _buildSummaryRow('Time Slot:', '${summary.startTime} - ${summary.endTime}'),
            _buildSummaryRow('Consultation Fee:', 'LKR ${summary.consultationFee.toStringAsFixed(0)}'),
            _buildSummaryRow('Service Fee:', 'LKR ${summary.serviceFee.toStringAsFixed(0)}'),
            const Divider(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Total Payable:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                Text(
                  'LKR ${summary.totalAmount.toStringAsFixed(0)}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppTheme.primaryTeal),
                ),
              ],
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              height: 44,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryTeal,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: _isLoading ? null : _confirmBooking,
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Confirm Booking', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
          Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildPaymentActionCard() {
    final total = _session?.bookingSummary?.totalAmount ?? 2500.0;
    return Card(
      color: Colors.teal.shade50,
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.teal.shade300),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                const Icon(Icons.timer_outlined, color: AppTheme.primaryTeal, size: 24),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    '10-Minute Hold Reserved',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.darkNavy),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryTeal,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Text('HOLD ACTIVE', style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Your slot has been reserved. Complete payment securely via Stripe to confirm.',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              height: 46,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.darkNavy,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: _isPaymentProcessing ? null : _startPaymentFlow,
                icon: _isPaymentProcessing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.payment),
                label: Text(
                  _isPaymentProcessing ? 'Opening Stripe...' : 'Pay Now (LKR ${total.toStringAsFixed(0)})',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfirmedCard() {
    return Card(
      color: Colors.green.shade50,
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.green.shade300),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Icon(Icons.check_circle, color: Colors.green, size: 40),
            const SizedBox(height: 8),
            const Text(
              'Appointment Confirmed!',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.green),
            ),
            const SizedBox(height: 4),
            Text(
              'Your consultation has been confirmed. You will receive notifications before your appointment.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
            ),
            const SizedBox(height: 14),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                foregroundColor: Colors.white,
              ),
              onPressed: () {
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const MyAppointmentsScreen()),
                );
              },
              child: const Text('View in My Appointments'),
            ),
          ],
        ),
      ),
    );
  }
}
