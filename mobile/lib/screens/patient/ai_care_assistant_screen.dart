import 'dart:async';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' hide Card;

import '../../core/network/api_error_mapper.dart';
import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/booking_session.dart';
import '../../services/ai_booking_service.dart';
import '../../services/payment_service.dart';
import 'doctor_detail_screen.dart';
import 'payment_success_screen.dart';

/// Unified MediConnect AI Care Assistant Screen (Phase 39).
///
/// Combines intelligent doctor recommendation, multi-factor matching,
/// discrete slot pre-fetching, and explicit booking confirmation into a single
/// conversational interface.
class AiCareAssistantScreen extends StatefulWidget {
  final String? initialQuery;
  final AiBookingService? bookingService;
  final PaymentService? paymentService;

  const AiCareAssistantScreen({
    super.key,
    this.initialQuery,
    this.bookingService,
    this.paymentService,
  });

  @override
  State<AiCareAssistantScreen> createState() => _AiCareAssistantScreenState();
}

class _AiCareAssistantScreenState extends State<AiCareAssistantScreen> {
  late final AiBookingService _bookingService;
  late final PaymentService _paymentService;

  final TextEditingController _textController = TextEditingController();
  final TextEditingController _patientNoteController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  BookingSession? _session;
  bool _isLoading = false;
  bool _isPaymentProcessing = false;
  String? _errorMessage;

  PlatformFile? _selectedImage;
  Uint8List? _selectedImageBytes;

  // Real-time hold countdown timer
  Timer? _countdownTimer;
  Duration _remainingHoldTime = Duration.zero;

  final List<Map<String, dynamic>> _quickActionCategories = [
    {'label': 'Find Doctor', 'icon': Icons.person_search_rounded, 'prompt': 'Find a doctor in Colombo'},
    {'label': 'Book Slot', 'icon': Icons.calendar_month_rounded, 'prompt': 'Book an appointment for tomorrow'},
    {'label': 'Medicine Info', 'icon': Icons.medication_rounded, 'prompt': 'What is paracetamol used for?'},
    {'label': 'Scan Label', 'icon': Icons.camera_alt_rounded, 'isImagePicker': true},
    {'label': 'Healthy Food', 'icon': Icons.restaurant_rounded, 'prompt': 'Healthy Sri Lankan breakfast ideas'},
    {'label': 'Exercise Tips', 'icon': Icons.directions_run_rounded, 'prompt': 'Beginner morning walking and mobility routine'},
  ];

  final List<String> _quickPrompts = [
    'Headache for 3 days',
    'Cardiologist in Colombo',
    'Budget under LKR 3000',
    'What is paracetamol used for?',
    'Metformin side effects and precautions',
    'Healthy Sri Lankan breakfast ideas',
    'Beginner walking exercise routine',
    'Dermatologist tomorrow morning',
    'Show me doctors with lower consultation fees',
    'ළමා වෛද්‍යවරයෙක් අවශ්‍යයි',
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
    _countdownTimer?.cancel();
    _textController.dispose();
    _patientNoteController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _startHoldTimer(DateTime holdExpiresAt) {
    _countdownTimer?.cancel();
    _updateRemainingTime(holdExpiresAt);
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      _updateRemainingTime(holdExpiresAt);
    });
  }

  void _updateRemainingTime(DateTime holdExpiresAt) {
    final diff = holdExpiresAt.difference(DateTime.now());
    if (diff.isNegative) {
      _countdownTimer?.cancel();
      setState(() {
        _remainingHoldTime = Duration.zero;
      });
    } else {
      setState(() {
        _remainingHoldTime = diff;
      });
    }
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
      if (session.holdExpiresAt != null) {
        _startHoldTimer(session.holdExpiresAt!);
      }
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
        _errorMessage = 'Could not start AI Care Assistant session. Please try again.';
      });
    }
  }

  Future<void> _resetSession() async {
    _countdownTimer?.cancel();
    setState(() {
      _session = null;
      _isLoading = true;
      _errorMessage = null;
      _remainingHoldTime = Duration.zero;
    });

    try {
      final session = await _bookingService.createSession();
      if (!mounted) return;
      setState(() {
        _session = session;
        _isLoading = false;
      });
      _scrollToBottom();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to reset assistant session.';
      });
    }
  }

  Future<void> _pickImage() async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['jpg', 'jpeg', 'png'],
      );

      if (files.isNotEmpty) {
        final file = files.first;
        final bytes = await file.readAsBytes();

        if (bytes.lengthInBytes > 5 * 1024 * 1024) {
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Selected image exceeds 5MB size limit.'),
              backgroundColor: AppTheme.error,
            ),
          );
          return;
        }

        setState(() {
          _selectedImage = file;
          _selectedImageBytes = bytes;
        });
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not select image: $e'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  void _clearSelectedImage() {
    setState(() {
      _selectedImage = null;
      _selectedImageBytes = null;
    });
  }

  Future<void> _sendMessage([String? promptText]) async {
    final text = promptText ?? _textController.text.trim();
    final hasImage = _selectedImageBytes != null;
    if (text.isEmpty && !hasImage) return;
    if (_session == null || _isLoading) return;

    _textController.clear();
    final imageBytesToSend = _selectedImageBytes;
    final imageNameToSend = _selectedImage?.name ?? 'label.jpg';

    // Optimistically show user's message in the transcript immediately
    final tempUserMsg = ChatMessage(
      id: 'temp_${DateTime.now().millisecondsSinceEpoch}',
      sender: 'user',
      content: text.isNotEmpty ? text : (hasImage ? '[Attached Image]' : ''),
      timestamp: DateTime.now(),
    );

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _selectedImage = null;
      _selectedImageBytes = null;
      if (_session != null) {
        _session = BookingSession(
          id: _session!.id,
          patientUserId: _session!.patientUserId,
          state: _session!.state,
          preferences: _session!.preferences,
          selectedDoctor: _session!.selectedDoctor,
          selectedSlot: _session!.selectedSlot,
          bookingSummary: _session!.bookingSummary,
          candidateDoctors: _session!.candidateDoctors,
          candidateSlots: _session!.candidateSlots,
          appointmentId: _session!.appointmentId,
          paymentId: _session!.paymentId,
          holdExpiresAt: _session!.holdExpiresAt,
          messages: [..._session!.messages, tempUserMsg],
          isUrgent: _session!.isUrgent,
          urgencyReason: _session!.urgencyReason,
          activeIntent: _session!.activeIntent,
          activeMedicineCard: _session!.activeMedicineCard,
          activeWellnessCard: _session!.activeWellnessCard,
          activeImageAnalysis: _session!.activeImageAnalysis,
          createdAt: _session!.createdAt,
          updatedAt: DateTime.now(),
          expiresAt: _session!.expiresAt,
        );
      }
    });
    _scrollToBottom();

    try {
      final BookingSession updated;
      if (hasImage && imageBytesToSend != null) {
        updated = await _bookingService.sendImageMessage(
          _session!.id,
          imageBytesToSend,
          imageNameToSend,
          message: text.isNotEmpty ? text : null,
        );
      } else {
        updated = await _bookingService.sendMessage(_session!.id, text);
      }
      if (!mounted) return;
      setState(() {
        _session = updated;
        _isLoading = false;
      });
      if (updated.holdExpiresAt != null) {
        _startHoldTimer(updated.holdExpiresAt!);
      }
      _scrollToBottom();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = e.message;
        if (_textController.text.isEmpty && text.isNotEmpty) {
          _textController.text = text;
        }
      });
    } catch (e, stack) {
      debugPrint('[AiCareAssistant] Failed to send message: $e\n$stack');
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = ApiErrorMapper.mapException(e);
        if (_textController.text.isEmpty && text.isNotEmpty) {
          _textController.text = text;
        }
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
      final updated = await _bookingService.selectDoctor(_session!.id, doctorId);
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
      final updated = await _bookingService.confirmBooking(
        _session!.id,
        patientNote: _patientNoteController.text.trim().isNotEmpty
            ? _patientNoteController.text.trim()
            : null,
      );
      if (!mounted) return;
      setState(() {
        _session = updated;
        _isLoading = false;
      });
      if (updated.holdExpiresAt != null) {
        _startHoldTimer(updated.holdExpiresAt!);
      }
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
        _errorMessage = 'Booking hold confirmation failed. Slot may have been taken.';
      });
    }
  }

  Future<void> _startPaymentFlow() async {
    if (_session == null || _session!.appointmentId == null || _isPaymentProcessing) {
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

      var statusResult = await _paymentService.getPaymentStatus(intentResp.paymentId);
      if (!statusResult.isSucceeded &&
          statusResult.paymentStatus.toUpperCase() == 'PENDING') {
        await Future.delayed(const Duration(seconds: 2));
        if (!mounted) return;
        statusResult = await _paymentService.getPaymentStatus(intentResp.paymentId);
      }

      final updatedSession = await _bookingService.syncPaymentStatus(_session!.id);
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
              amount: statusResult.amount > 0 ? statusResult.amount : 2500.0,
            ),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPaymentProcessing = false;
        _errorMessage = 'Payment processing error: ${e.toString()}';
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _callAmbulance() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.emergency_rounded, color: Colors.red),
            SizedBox(width: 8),
            Text('Emergency Hotline: 1990'),
          ],
        ),
        content: const Text(
          'Please dial 1990 immediately on your phone to reach Suwa Seriya Free Emergency Ambulance Service in Sri Lanka, or proceed to the nearest emergency department.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showDoctorComparisonDialog() {
    if (_session == null || _session!.candidateDoctors.isEmpty) return;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return DraggableScrollableSheet(
          initialChildSize: 0.7,
          minChildSize: 0.4,
          maxChildSize: 0.9,
          expand: false,
          builder: (_, scrollController) {
            return Container(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Row(
                    children: [
                      Icon(Icons.compare_arrows_rounded, color: AppTheme.primary),
                      SizedBox(width: 8),
                      Text(
                        'Compare Candidate Doctors',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Expanded(
                    child: ListView.separated(
                      controller: scrollController,
                      itemCount: _session!.candidateDoctors.length,
                      separatorBuilder: (context, index) => const Divider(height: 24),
                      itemBuilder: (_, i) {
                        final doc = _session!.candidateDoctors[i];
                        return Card(
                          elevation: 1,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                            side: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    CircleAvatar(
                                      radius: 20,
                                      backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                                      child: const Icon(Icons.person, color: AppTheme.primary),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            doc.fullName,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 16,
                                            ),
                                          ),
                                          Text(
                                            doc.specialty,
                                            style: const TextStyle(
                                              color: AppTheme.primary,
                                              fontSize: 13,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    if (doc.matchScore != null)
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: Colors.green.shade50,
                                          borderRadius: BorderRadius.circular(8),
                                          border: Border.all(color: Colors.green.shade200),
                                        ),
                                        child: Text(
                                          '${doc.matchScore!.round()}% Match',
                                          style: TextStyle(
                                            color: Colors.green.shade800,
                                            fontWeight: FontWeight.bold,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 10),
                                if (doc.qualifications != null && doc.qualifications!.isNotEmpty)
                                  Padding(
                                    padding: const EdgeInsets.only(bottom: 6),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.school_outlined, size: 16, color: AppTheme.textSecondary),
                                        const SizedBox(width: 6),
                                        Expanded(
                                          child: Text(
                                            doc.qualifications!,
                                            style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                Row(
                                  children: [
                                    const Icon(Icons.local_hospital_outlined, size: 16, color: AppTheme.textSecondary),
                                    const SizedBox(width: 6),
                                    Expanded(
                                      child: Text(
                                        doc.hospitalOrClinic ?? 'MediConnect Partner Clinic',
                                        style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                                      ),
                                    ),
                                    Text(
                                      'LKR ${doc.consultationFee.toStringAsFixed(0)}',
                                      style: const TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.primary,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppTheme.primary,
                                    foregroundColor: Colors.white,
                                    minimumSize: const Size(double.infinity, 38),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                  ),
                                  onPressed: () {
                                    Navigator.pop(ctx);
                                    _selectDoctor(doc.doctorId);
                                  },
                                  child: Text('Select ${doc.fullName}'),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.auto_awesome, color: Colors.amberAccent, size: 20),
            SizedBox(width: 8),
            Text(
              'MediConnect AI Assistant',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Start Fresh / Clear Conversation',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _resetSession,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Stitch Clinical Clarity Informational Disclaimer Banner
            _buildStitchDisclaimerBanner(),

            // Emergency Red-Flag Banner
            if (_session?.isUrgent == true) _buildEmergencyBanner(),

            // Error banner if any
            if (_errorMessage != null) _buildErrorBanner(),

            // Main chat conversation list
            Expanded(
              child: _isLoading && _session == null
                  ? const Center(child: CircularProgressIndicator())
                  : _buildConversationView(),
            ),

            // Quick suggestion prompt chips
            if (_session != null &&
                (_session!.isCollectingPreferences || _session!.isSearchingDoctors))
              _buildQuickPromptsBar(),

            // Selected Image Preview chip if attached
            if (_selectedImageBytes != null) _buildSelectedImagePreview(),

            // Bottom Chat Input Bar
            _buildInputArea(),
          ],
        ),
      ),
    );
  }

  Widget _buildStitchDisclaimerBanner() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: const Row(
        children: [
          Icon(Icons.info_outline_rounded, size: 16, color: AppTheme.primaryBlue),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'Informational Assistant • For medical emergencies, call 1990 immediately.',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmergencyBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: Colors.red.shade700,
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Colors.white, size: 26),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Potential Emergency Detected',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
                Text(
                  _session?.urgencyReason ??
                      'If you have acute chest pain or severe distress, call 1990 immediately.',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.red.shade700,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              visualDensity: VisualDensity.compact,
            ),
            onPressed: _callAmbulance,
            icon: const Icon(Icons.phone, size: 16),
            label: const Text('1990', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorBanner() {
    return Container(
      width: double.infinity,
      color: Colors.amber.shade100,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Icon(Icons.info_outline, color: Colors.amber.shade900, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _errorMessage!,
              style: TextStyle(color: Colors.amber.shade900, fontSize: 13),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 16),
            onPressed: () => setState(() => _errorMessage = null),
          ),
        ],
      ),
    );
  }

  Widget _buildConversationView() {
    final messages = _session?.messages ?? [];

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      itemCount: messages.length + 1, // +1 for conversational action widgets (cards/slots)
      itemBuilder: (context, index) {
        if (index < messages.length) {
          final msg = messages[index];
          return _buildChatBubble(msg);
        }
        // Last item: candidate doctors or slots or summary card based on state
        return _buildInteractiveStateWidgets();
      },
    );
  }

  Widget _buildChatBubble(ChatMessage message) {
    final isUser = message.isUser;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            CircleAvatar(
              radius: 16,
              backgroundColor: AppTheme.primary.withValues(alpha: 0.15),
              child: const Icon(Icons.smart_toy_rounded, size: 18, color: AppTheme.primary),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser ? AppTheme.primary : Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: isUser ? const Radius.circular(16) : const Radius.circular(4),
                  bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(16),
                ),
                border: isUser
                    ? null
                    : Border.all(color: AppTheme.outline.withValues(alpha: 0.3)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Text(
                message.content,
                style: TextStyle(
                  color: isUser ? Colors.white : AppTheme.textPrimary,
                  fontSize: 14.5,
                  height: 1.35,
                ),
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 8),
            CircleAvatar(
              radius: 16,
              backgroundColor: AppTheme.primary,
              child: const Icon(Icons.person, size: 18, color: Colors.white),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInteractiveStateWidgets() {
    if (_session == null) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Active Educational Medicine Card
        if (_session!.activeMedicineCard != null)
          _buildMedicineCard(_session!.activeMedicineCard!),

        // Active Educational Wellness Card
        if (_session!.activeWellnessCard != null)
          _buildWellnessCard(_session!.activeWellnessCard!),

        // Active Label & Packaging Analysis Card
        if (_session!.activeImageAnalysis != null)
          _buildImageAnalysisCard(_session!.activeImageAnalysis!),

        // 1. Candidate Doctor Cards
        if (_session!.isAwaitingDoctor && _session!.candidateDoctors.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Recommended Doctors (${_session!.candidateDoctors.length})',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                    color: AppTheme.textPrimary,
                  ),
                ),
                if (_session!.candidateDoctors.length > 1)
                  TextButton.icon(
                    onPressed: _showDoctorComparisonDialog,
                    icon: const Icon(Icons.compare_arrows_rounded, size: 16),
                    label: const Text('Compare', style: TextStyle(fontSize: 13)),
                  ),
              ],
            ),
          ),
          ..._session!.candidateDoctors.map((doc) => _buildDoctorCandidateCard(doc)),
        ],

        // 2. Candidate Slots
        if (_session!.isAwaitingSlot && _session!.candidateSlots.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8.0),
            child: Text(
              'Select an available slot for ${_session!.selectedDoctor?.fullName ?? "Doctor"}:',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            ),
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _session!.candidateSlots.map((slot) {
              return ActionChip(
                backgroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                  side: const BorderSide(color: AppTheme.primary, width: 1.2),
                ),
                avatar: const Icon(Icons.access_time_rounded, size: 16, color: AppTheme.primary),
                label: Text(
                  '${slot.startTime} - ${slot.endTime}',
                  style: const TextStyle(
                    color: AppTheme.primary,
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
                onPressed: () => _selectSlot(slot),
              );
            }).toList(),
          ),
        ],

        // 3. Awaiting Explicit Confirmation: Booking Summary Card
        if (_session!.isAwaitingConfirmation && _session!.bookingSummary != null)
          _buildBookingSummaryCard(),

        // 4. Booking Hold Created / Awaiting Payment Card
        if ((_session!.isHoldCreated || _session!.isAwaitingPayment) &&
            _session!.appointmentId != null)
          _buildHoldTimerAndPaymentCard(),
      ],
    );
  }

  Widget _buildMedicineCard(MedicineCardSummary card) {
    return Card(
      key: const Key('ai_medicine_card'),
      elevation: 2,
      margin: const EdgeInsets.only(top: 8, bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppTheme.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.medication_rounded, color: AppTheme.primary, size: 22),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        card.medicineName,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.darkNavy,
                        ),
                      ),
                      if (card.activeIngredient != null && card.activeIngredient!.isNotEmpty)
                        Text(
                          'Active Ingredient: ${card.activeIngredient}',
                          style: const TextStyle(
                            fontSize: 12.5,
                            color: AppTheme.textSecondary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                    ],
                  ),
                ),
                if (card.isPrescriptionRequired)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.amber.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.amber.shade300),
                    ),
                    child: Text(
                      'Rx Required',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: Colors.amber.shade900,
                      ),
                    ),
                  ),
              ],
            ),
            if (card.commonUses.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text(
                'Common Uses',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
              ),
              const SizedBox(height: 4),
              ...card.commonUses.map((u) => Padding(
                    padding: const EdgeInsets.only(left: 4, bottom: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ', style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.bold)),
                        Expanded(child: Text(u, style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary))),
                      ],
                    ),
                  )),
            ],
            if (card.precautions.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text(
                'Precautions',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
              ),
              const SizedBox(height: 4),
              ...card.precautions.map((p) => Padding(
                    padding: const EdgeInsets.only(left: 4, bottom: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ', style: TextStyle(color: AppTheme.secondary, fontWeight: FontWeight.bold)),
                        Expanded(child: Text(p, style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary))),
                      ],
                    ),
                  )),
            ],
            if (card.sideEffects.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text(
                'Possible Side Effects',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
              ),
              const SizedBox(height: 4),
              ...card.sideEffects.map((s) => Padding(
                    padding: const EdgeInsets.only(left: 4, bottom: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ', style: TextStyle(color: Colors.orange, fontWeight: FontWeight.bold)),
                        Expanded(child: Text(s, style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary))),
                      ],
                    ),
                  )),
            ],
            if (card.warnings.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.warning_amber_rounded, size: 16, color: Colors.red.shade700),
                        const SizedBox(width: 6),
                        Text(
                          'Important Warnings',
                          style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold, color: Colors.red.shade900),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ...card.warnings.map((w) => Text('• $w', style: TextStyle(fontSize: 12, color: Colors.red.shade900))),
                  ],
                ),
              ),
            ],
            if (card.consultPharmacistWhen.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.local_pharmacy_outlined, size: 16, color: AppTheme.primary),
                        SizedBox(width: 6),
                        Text(
                          'Consult a Doctor or Pharmacist if:',
                          style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold, color: AppTheme.darkNavy),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ...card.consultPharmacistWhen.map((c) => Text('• $c', style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary))),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 8),
            const Text(
              'Educational information only. MediConnect AI never provides personal dosages or alters doctor prescriptions. Always consult a qualified physician or pharmacist.',
              style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWellnessCard(WellnessCardSummary card) {
    IconData icon;
    Color accentColor;
    switch (card.category.toUpperCase()) {
      case 'FOOD':
        icon = Icons.restaurant_rounded;
        accentColor = Colors.teal;
        break;
      case 'EXERCISE':
        icon = Icons.directions_run_rounded;
        accentColor = AppTheme.primary;
        break;
      default:
        icon = Icons.spa_rounded;
        accentColor = Colors.indigo;
    }

    return Card(
      key: const Key('ai_wellness_card'),
      elevation: 2,
      margin: const EdgeInsets.only(top: 8, bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppTheme.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: accentColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: accentColor, size: 22),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        card.title,
                        style: const TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.darkNavy,
                        ),
                      ),
                      Container(
                        margin: const EdgeInsets.only(top: 2),
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: accentColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          card.category,
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.bold,
                            color: accentColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              card.summary,
              style: const TextStyle(fontSize: 13.5, color: AppTheme.textPrimary, height: 1.35),
            ),
            if (card.tips.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text(
                'Key Practical Recommendations',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
              ),
              const SizedBox(height: 4),
              ...card.tips.map((tip) => Padding(
                    padding: const EdgeInsets.only(left: 4, bottom: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check_circle_outline, size: 15, color: AppTheme.primary),
                        const SizedBox(width: 6),
                        Expanded(child: Text(tip, style: const TextStyle(fontSize: 12.5, color: AppTheme.textPrimary))),
                      ],
                    ),
                  )),
            ],
            if (card.sriLankanOptions.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.eco_rounded, size: 16, color: Colors.green.shade800),
                        const SizedBox(width: 6),
                        Text(
                          'Sri Lankan Healthy Choices',
                          style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold, color: Colors.green.shade900),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ...card.sriLankanOptions.map((opt) => Text('• $opt', style: TextStyle(fontSize: 12, color: Colors.green.shade900))),
                  ],
                ),
              ),
            ],
            if (card.safetyNote != null && card.safetyNote!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.amber.shade200),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.health_and_safety_outlined, size: 16, color: Colors.amber.shade900),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        card.safetyNote!,
                        style: TextStyle(fontSize: 12, color: Colors.amber.shade900),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildImageAnalysisCard(ImageAnalysisSummary analysis) {
    Color badgeColor;
    String badgeText;
    switch (analysis.confidenceLevel.toUpperCase()) {
      case 'HIGH':
        badgeColor = Colors.green;
        badgeText = 'High Confidence';
        break;
      case 'MEDIUM':
        badgeColor = Colors.amber.shade800;
        badgeText = 'Moderate Confidence';
        break;
      default:
        badgeColor = Colors.deepOrange;
        badgeText = 'Uncertain';
    }

    return Card(
      key: const Key('ai_image_analysis_card'),
      elevation: 2,
      margin: const EdgeInsets.only(top: 8, bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppTheme.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.document_scanner_rounded, color: AppTheme.primary, size: 22),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    'Label & Packaging Analysis',
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.darkNavy,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: badgeColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: badgeColor.withValues(alpha: 0.3)),
                  ),
                  child: Text(
                    badgeText,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: badgeColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (analysis.detectedText.isNotEmpty) ...[
              const Text(
                'Detected Packaging Text:',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 12, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 4),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.background,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.border),
                ),
                child: Text(
                  analysis.detectedText,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: AppTheme.textPrimary),
                ),
              ),
              const SizedBox(height: 10),
            ],
            if (analysis.identifiedMedicine != null) ...[
              Row(
                children: [
                  const Text('Identified Medicine: ', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  Text(
                    analysis.identifiedMedicine!,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.primary),
                  ),
                ],
              ),
              if (analysis.activeIngredient != null)
                Text(
                  'Active Ingredient: ${analysis.activeIngredient}',
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                ),
              const SizedBox(height: 8),
            ],
            if (analysis.uncertaintyExplanation != null) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.orange.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.orange.shade200),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.info_outline, size: 16, color: Colors.orange.shade800),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        analysis.uncertaintyExplanation!,
                        style: TextStyle(fontSize: 12, color: Colors.orange.shade900),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
            ],
            if (analysis.safetyAdvice != null) ...[
              Text(
                analysis.safetyAdvice!,
                style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 8),
            ],
            if (analysis.requiresClearerPhoto) ...[
              const SizedBox(height: 4),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.primary,
                  minimumSize: const Size(double.infinity, 38),
                ),
                onPressed: _pickImage,
                icon: const Icon(Icons.camera_alt_outlined, size: 16),
                label: const Text('Upload / Retake Clearer Photo'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildDoctorCandidateCard(DoctorCardSummary doctor) {
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: AppTheme.primary.withValues(alpha: 0.12),
                  child: const Icon(Icons.person, size: 28, color: AppTheme.primary),
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
                              doctor.fullName,
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 15.5,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.verified, size: 16, color: AppTheme.primary),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        doctor.specialty,
                        style: const TextStyle(
                          color: AppTheme.primary,
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        ),
                      ),
                      if (doctor.qualifications != null && doctor.qualifications!.isNotEmpty)
                        Text(
                          doctor.qualifications!,
                          style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary),
                        ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (doctor.matchScore != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.green.shade50,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: Colors.green.shade200),
                        ),
                        child: Text(
                          '${doctor.matchScore!.round()}% Match',
                          style: TextStyle(
                            color: Colors.green.shade800,
                            fontWeight: FontWeight.bold,
                            fontSize: 11,
                          ),
                        ),
                      ),
                    const SizedBox(height: 4),
                    Text(
                      'LKR ${doctor.consultationFee.toStringAsFixed(0)}',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14.5,
                        color: AppTheme.primary,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 10),

            // Hospital & Rating Row
            Row(
              children: [
                const Icon(Icons.location_on_outlined, size: 15, color: AppTheme.textSecondary),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    doctor.hospitalOrClinic ?? 'MediConnect Partner Hospital',
                    style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const Icon(Icons.star, size: 15, color: Colors.amber),
                const SizedBox(width: 4),
                Text(
                  doctor.rating.toStringAsFixed(1),
                  style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                ),
              ],
            ),

            // Match Reasons
            if (doctor.matchReasons.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: doctor.matchReasons.take(2).map((r) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 2),
                      child: Row(
                        children: [
                          const Icon(Icons.check_circle_outline, size: 13, color: AppTheme.primary),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              r,
                              style: const TextStyle(fontSize: 11.5, color: AppTheme.textPrimary),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ),
            ],

            // Action Buttons
            const SizedBox(height: 12),
            Row(
              children: [
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    foregroundColor: AppTheme.primary,
                    side: const BorderSide(color: AppTheme.primary),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.person_outline, size: 15),
                  label: const Text('View Profile', style: TextStyle(fontSize: 12.5)),
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DoctorDetailScreen(doctor: doctor.toDoctor()),
                      ),
                    );
                  },
                ),
                const Spacer(),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    visualDensity: VisualDensity.compact,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.event_available, size: 15),
                  label: const Text('Select Doctor', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold)),
                  onPressed: () => _selectDoctor(doctor.doctorId),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBookingSummaryCard() {
    final s = _session!.bookingSummary!;

    return Card(
      elevation: 3,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppTheme.primary, width: 1.5),
      ),
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
                    color: AppTheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.assignment_outlined, color: AppTheme.primary),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Booking Summary',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                      Text(
                        'Please review details before confirming hold',
                        style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
            _buildSummaryRow('Doctor', s.doctorName, isBold: true),
            _buildSummaryRow('Specialty', s.specialty),
            if (s.hospitalOrClinic != null)
              _buildSummaryRow('Location', s.hospitalOrClinic!),
            _buildSummaryRow('Date', s.appointmentDate),
            _buildSummaryRow('Time', '${s.startTime} - ${s.endTime}'),
            const Divider(height: 20),
            _buildSummaryRow(
              'Consultation Fee',
              'LKR ${s.consultationFee.toStringAsFixed(2)}',
            ),
            _buildSummaryRow(
              'Service Fee',
              'LKR ${s.serviceFee.toStringAsFixed(2)}',
            ),
            const SizedBox(height: 4),
            _buildSummaryRow(
              'Total Amount',
              'LKR ${s.totalAmount.toStringAsFixed(2)}',
              isBold: true,
              valueColor: AppTheme.primary,
            ),
            const SizedBox(height: 14),
            // Patient Note Input
            TextField(
              controller: _patientNoteController,
              decoration: InputDecoration(
                hintText: 'Add an optional note or symptoms for the doctor...',
                hintStyle: const TextStyle(fontSize: 12.5),
                isDense: true,
                filled: true,
                fillColor: AppTheme.background,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
                ),
              ),
              maxLines: 2,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primary,
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 48),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: _isLoading ? null : _confirmBooking,
              child: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                    )
                  : const Text(
                      'Confirm Booking',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryRow(String label, String value,
      {bool isBold = false, Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
              color: valueColor ?? AppTheme.textPrimary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHoldTimerAndPaymentCard() {
    final minutes = _remainingHoldTime.inMinutes;
    final seconds = _remainingHoldTime.inSeconds % 60;
    final timerText =
        '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    final isHoldExpired = _remainingHoldTime == Duration.zero;

    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: isHoldExpired ? Colors.red : Colors.green,
          width: 1.5,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                Icon(
                  isHoldExpired ? Icons.timer_off_outlined : Icons.lock_clock_rounded,
                  color: isHoldExpired ? Colors.red : Colors.green,
                  size: 24,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isHoldExpired ? 'Reservation Hold Expired' : '10-Minute Hold Active',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: isHoldExpired ? Colors.red : Colors.green.shade800,
                          fontSize: 15,
                        ),
                      ),
                      Text(
                        'Ref: ${_session!.appointmentId ?? "Hold reserved"}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isHoldExpired ? Colors.red.shade50 : Colors.green.shade50,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    timerText,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: isHoldExpired ? Colors.red : Colors.green.shade800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (!isHoldExpired)
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 46),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: _isPaymentProcessing ? null : _startPaymentFlow,
                icon: const Icon(Icons.payment_rounded, size: 18),
                label: _isPaymentProcessing
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                      )
                    : const Text(
                        'Proceed to Payment (Stripe)',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
              ),
            if (isHoldExpired)
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.primary,
                  minimumSize: const Size(double.infinity, 42),
                ),
                onPressed: _resetSession,
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Slot Expired. Search Again'),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildSelectedImagePreview() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: Colors.white,
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.border),
            ),
            clipBehavior: Clip.antiAlias,
            child: Image.memory(
              _selectedImageBytes!,
              fit: BoxFit.cover,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _selectedImage?.name ?? 'Packaging Image',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                ),
                const Text(
                  'Medicine packaging / label photo attached',
                  style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
          IconButton(
            key: const Key('ai_care_assistant_remove_image'),
            icon: const Icon(Icons.cancel_outlined, size: 20, color: AppTheme.textSecondary),
            onPressed: _clearSelectedImage,
            tooltip: 'Remove Image',
          ),
        ],
      ),
    );
  }

  Widget _buildQuickPromptsBar() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Category Action Chips
        SizedBox(
          height: 38,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _quickActionCategories.length,
            separatorBuilder: (context, index) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final cat = _quickActionCategories[index];
              return ActionChip(
                backgroundColor: AppTheme.primary.withValues(alpha: 0.08),
                side: const BorderSide(color: AppTheme.border),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                avatar: Icon(cat['icon'] as IconData, size: 16, color: AppTheme.primary),
                label: Text(
                  cat['label'] as String,
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.primary),
                ),
                onPressed: () {
                  if (cat['isImagePicker'] == true) {
                    _pickImage();
                  } else {
                    _sendMessage(cat['prompt'] as String);
                  }
                },
              );
            },
          ),
        ),
        const SizedBox(height: 6),
        // Suggested prompt chips
        SizedBox(
          height: 34,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _quickPrompts.length,
            separatorBuilder: (context, index) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final prompt = _quickPrompts[index];
              return ActionChip(
                backgroundColor: Colors.white,
                side: const BorderSide(color: AppTheme.border),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                label: Text(
                  prompt,
                  style: const TextStyle(fontSize: 11.5, color: AppTheme.textPrimary),
                ),
                onPressed: () => _sendMessage(prompt),
              );
            },
          ),
        ),
        const SizedBox(height: 4),
      ],
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          IconButton(
            key: const Key('ai_care_assistant_attach_image'),
            tooltip: 'Upload medicine package photo',
            icon: const Icon(Icons.add_a_photo_outlined, color: AppTheme.primary, size: 22),
            onPressed: _isLoading ? null : _pickImage,
          ),
          Expanded(
            child: TextField(
              key: const Key('ai_care_assistant_input'),
              controller: _textController,
              decoration: InputDecoration(
                hintText: 'Ask about medicines, food, exercise, or find doctors...',
                hintStyle: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                isDense: true,
                filled: true,
                fillColor: AppTheme.background,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
                ),
              ),
              onSubmitted: (val) => _sendMessage(),
            ),
          ),
          const SizedBox(width: 6),
          IconButton.filled(
            key: const Key('ai_care_assistant_send'),
            style: IconButton.styleFrom(
              backgroundColor: AppTheme.primary,
              foregroundColor: Colors.white,
            ),
            icon: _isLoading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                  )
                : const Icon(Icons.send_rounded, size: 20),
            onPressed: _isLoading ? null : () => _sendMessage(),
          ),
        ],
      ),
    );
  }
}
