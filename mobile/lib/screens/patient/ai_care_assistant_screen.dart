import 'dart:async';
import 'dart:math';
import 'ai_chat_history_sheet.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart' hide Card;

import '../../core/constants/api_constants.dart';
import '../../core/network/api_error_mapper.dart';
import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/booking_session.dart';
import '../../services/ai_booking_service.dart';
import '../../services/payment_service.dart';
import '../../widgets/safe_markdown_text.dart';
import 'doctor_detail_screen.dart';
import '../../utils/emergency_dialer.dart';
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

  /// Optional image source used by tests; production uses the platform file picker.
  final Future<({Uint8List bytes, String name})?> Function()? imagePicker;

  /// Opens the phone dialer pre-filled with [number] and returns whether it opened. It must
  /// never place a call by itself. Tests inject a fake; production uses [EmergencyDialer.open].
  final Future<bool> Function(String number)? emergencyDialer;

  const AiCareAssistantScreen({
    super.key,
    this.initialQuery,
    this.bookingService,
    this.paymentService,
    this.imagePicker,
    this.emergencyDialer,
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

  /// The reply that should scroll into view top-first once laid out (Phase 01). Cleared after it has scrolled.
  String? _revealReplyId;

  /// Focus of the single composer (Phase 01 keyboard UX). Sending or tapping outside dismisses the keyboard,
  /// and a reply never requests focus, so the keyboard is not reopened by the assistant.
  final FocusNode _composerFocus = FocusNode(debugLabel: 'ai_composer');

  BookingSession? _session;
  bool _isLoading = false;
  bool _isPaymentProcessing = false;
  String? _errorMessage;
  String? _pendingMessage;
  String? _requestId;
  final _random = Random.secure();

  PlatformFile? _selectedImage;
  String? _retryImageName;
  Uint8List? _selectedImageBytes;

  // Image upload lifecycle (BUG-026): progress, retry and cancel.
  bool _isUploadingImage = false;
  int _uploadGeneration = 0;
  final Map<String, Uint8List> _attachmentPreviews = {};
  ({Uint8List bytes, String name, String? text})? _failedUpload;

  // Real-time hold countdown timer
  Timer? _countdownTimer;
  bool _disposed = false;
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
    'கொழும்பில் இதய மருத்துவர்',
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
    _disposed = true;
    _uploadGeneration++;
    _countdownTimer?.cancel();
    _countdownTimer = null;
    _textController.dispose();
    _patientNoteController.dispose();
    _scrollController.dispose();
    _composerFocus.dispose();
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
    if (!mounted) {
      _countdownTimer?.cancel();
      return;
    }
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
      final history = await _bookingService.listConversations();
      var session = history.isEmpty || widget.initialQuery != null
          ? await _bookingService.createConversation()
          : await _bookingService.getSession(history.first['id'] as String);
      final initial = widget.initialQuery?.trim();
      if (initial != null && initial.isNotEmpty) {
        session = await _bookingService.sendConversationMessage(session.id, initial, _newRequestId());
      }
      if (!mounted) return;
      setState(() {
        _session = session;
        _isLoading = false;
      });
      if (session.holdExpiresAt != null) {
        _startHoldTimer(session.holdExpiresAt!);
      }
      _scrollToBottom(force: true);
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

  String _newRequestId() =>
      List.generate(20, (_) => _random.nextInt(16).toRadixString(16)).join();

  Future<void> _resetSession() => _switchConversation();

  Future<void> _switchConversation([String? id]) async {
    if (_isLoading || _isPaymentProcessing) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final session = id == null
          ? await _bookingService.createConversation()
          : await _bookingService.getSession(id);
      if (!mounted) return;
      _countdownTimer?.cancel();
      _textController.clear();
      _patientNoteController.clear();
      setState(() {
        _session = session;
        _remainingHoldTime = Duration.zero;
        _selectedImage = null;
        _selectedImageBytes = null;
        _pendingMessage = null;
        _requestId = null;
      });
      if (session.holdExpiresAt != null) _startHoldTimer(session.holdExpiresAt!);
      _scrollToBottom(force: true);
    } catch (_) {
      if (!mounted) return;
      setState(() => _errorMessage = 'Could not open the conversation. Please try again.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _openHistory() async {
    final result = await showModalBottomSheet<AiHistorySelection>(
      context: context,
      isScrollControlled: true,
      builder: (_) => AiChatHistorySheet(service: _bookingService, activeId: _session?.id),
    );
    if (!mounted || result == null) return;
    if (result.activeDeleted) setState(() => _session = null);
    if (result.open) await _switchConversation(result.id);
  }

  Future<void> _pickImage() async {
    if (widget.imagePicker != null) {
      final picked = await widget.imagePicker!();
      if (!mounted || picked == null) return;
      setState(() {
        _selectedImage = null;
        _retryImageName = picked.name;
        _selectedImageBytes = picked.bytes;
      });
      return;
    }
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
    if (_session == null || _isLoading || _isPaymentProcessing) return;

    _composerFocus.unfocus();
    _textController.clear();
    final imageBytesToSend = _selectedImageBytes;
    final imageNameToSend = _selectedImage?.name ?? _retryImageName ?? 'label.jpg';
    _retryImageName = null;

    // Optimistically show user's message in the transcript immediately
    final tempUserMsg = ChatMessage(
      id: 'temp_${DateTime.now().millisecondsSinceEpoch}',
      sender: 'user',
      content: text.isNotEmpty ? text : (hasImage ? 'Medicine photo' : ''),
      timestamp: DateTime.now(),
    );
    if (hasImage && imageBytesToSend != null) {
      _attachmentPreviews[tempUserMsg.id] = imageBytesToSend;
    }
    final generation = ++_uploadGeneration;

    final previous = _session;
    _sessionBeforeUpload = previous;
    setState(() {
      _isLoading = true;
      _isUploadingImage = hasImage;
      _failedUpload = null;
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
          activeMedicineCard: null,
          activeWellnessCard: null,
          activeImageAnalysis: null,
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
        if (_pendingMessage != text) {
          _pendingMessage = text;
          _requestId = _newRequestId();
        }
        updated = await _bookingService.sendConversationMessage(_session!.id, text, _requestId!);
        _pendingMessage = null;
        _requestId = null;
      }
      // Ignore results for uploads the user cancelled or for a screen that has been closed.
      if (!mounted || generation != _uploadGeneration) return;
      if (hasImage && imageBytesToSend != null) {
        final serverMessage = updated.messages.lastWhere(
          (m) => m.isUser,
          orElse: () => tempUserMsg,
        );
        _attachmentPreviews[serverMessage.id] = imageBytesToSend;
      }
      // Show a new reply from its beginning (Phase 01) unless the user has scrolled up to read history.
      final nearBottom = !_scrollController.hasClients || _scrollController.position.extentAfter <= 230;
      final reply = updated.messages.isNotEmpty && !updated.messages.last.isUser ? updated.messages.last : null;
      setState(() {
        _session = updated;
        _isLoading = false;
        _isUploadingImage = false;
        _revealReplyId = nearBottom ? reply?.id : null;
      });
      if (updated.holdExpiresAt != null) {
        _startHoldTimer(updated.holdExpiresAt!);
      }
      if (reply == null && nearBottom) _scrollToBottom();
    } catch (error) {
      if (!mounted || generation != _uploadGeneration) return;
      setState(() {
        _session = previous;
        _isLoading = false;
        _isUploadingImage = false;
        _errorMessage = hasImage
            ? 'Your photo was not analysed: ${ApiErrorMapper.mapException(error)}'
            : ApiErrorMapper.mapException(error);
        if (hasImage && imageBytesToSend != null) {
          // Keep the photo so the patient can retry without picking it again.
          _failedUpload = (bytes: imageBytesToSend, name: imageNameToSend, text: text.isEmpty ? null : text);
        }
        if (_textController.text.isEmpty) _textController.text = text;
      });
    }
  }

  BookingSession? _sessionBeforeUpload;

  void _cancelUpload() {
    if (!_isUploadingImage) return;
    _uploadGeneration++;
    setState(() {
      _session = _sessionBeforeUpload ?? _session;
      _isLoading = false;
      _isUploadingImage = false;
      _errorMessage = 'Upload cancelled. If the photo already reached MediConnect, its analysis may still appear '
          'in this chat after you reopen it.';
    });
  }

  void _retryFailedUpload() {
    final failed = _failedUpload;
    if (failed == null || _isLoading) return;
    setState(() {
      _selectedImageBytes = failed.bytes;
      _selectedImage = null;
      _retryImageName = failed.name;
      _failedUpload = null;
      _errorMessage = null;
    });
    _sendMessage(failed.text);
  }

  Future<void> _selectDoctor(String doctorId) async {
    if (_isLoading || _isPaymentProcessing || _session == null) return;
    final today = DateUtils.dateOnly(
      DateTime.now().toUtc().add(const Duration(hours: 5, minutes: 30)),
    );
    final selected = await showDatePicker(
      context: context,
      firstDate: today,
      lastDate: today.add(const Duration(days: 90)),
      initialDate: today,
    );
    if (!mounted || selected == null) return;
    final date = selected.toIso8601String().split('T').first;
    if (_session == null || _isLoading || _isPaymentProcessing) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updated = await _bookingService.viewSlots(_session!.id, doctorId, date);
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
    if (_session == null || _isLoading || _isPaymentProcessing) return;
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
        prepareProposal: true,
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

  String? _smsConsentProposal;

  Future<void> _refreshBooking() async {
    if (_session == null || _isLoading || _isPaymentProcessing) return;
    setState(() => _isLoading = true);
    try {
      final updated = await _bookingService.syncPaymentStatus(_session!.id);
      if (mounted) setState(() => _session = updated);
    } catch (_) {
      if (mounted) setState(() => _errorMessage = 'Booking status is temporarily unavailable.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _releaseReservation() async {
    if (_session == null || _isLoading || _isPaymentProcessing) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const Key('ai_release_reservation_dialog'),
        title: const Text('Release this reservation?'),
        content: const Text(
          'The time slot will be released now and any unfinished payment cancelled. You have not been charged.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep Reservation')),
          ElevatedButton(
            key: const Key('ai_release_reservation_confirm'),
            style: ElevatedButton.styleFrom(minimumSize: const Size(72, 40)),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Release'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    _countdownTimer?.cancel();
    setState(() => _errorMessage = null); // the earlier "payment cancelled, slot still held" note no longer applies
    await _cancelProposal();
  }

  Future<void> _cancelProposal() async {
    if (_session == null || _isLoading || _isPaymentProcessing) return;
    setState(() => _isLoading = true);
    try {
      final updated = await _bookingService.cancelSession(_session!.id);
      if (mounted) setState(() => _session = updated);
    } catch (_) {
      if (mounted) setState(() => _errorMessage = 'Could not cancel this booking.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _changeProposalDoctor() async {
    final doctors = _session?.candidateDoctors ?? [];
    final doctor = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            for (final doctor in doctors)
              ListTile(
                title: Text(doctor.fullName),
                subtitle: Text(doctor.specialty),
                onTap: () => Navigator.pop(context, doctor.doctorId),
              ),
          ],
        ),
      ),
    );
    if (mounted && doctor != null) await _selectDoctor(doctor);
  }

  Future<void> _confirmBooking() async {
    if (_session == null || _isLoading || _isPaymentProcessing) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final updated = await _bookingService.confirmBooking(
        _session!.id,
        proposalId: _session!.bookingSummary?.proposalId,
        smsConsent: _smsConsentProposal != null && _smsConsentProposal == _session!.bookingSummary?.proposalId,
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
      if (updated.bookingSummary?.proposalId != null &&
          updated.holdExpiresAt != null && updated.isAwaitingPayment) {
        await _startPaymentFlow();
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
                ? 'Payment was cancelled. You have not been charged. The slot stays held until the timer ends; '
                    'pay again or release the reservation.'
                : 'Payment failed: ${e.error.localizedMessage ?? "Try again"}';
          });
          return;
        }
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

      if (updatedSession.isConfirmed && updatedSession.bookingResult == null) {
        final doc = _session?.selectedDoctor;
        final slot = _session?.selectedSlot;
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => PaymentSuccessScreen(
              appointmentId: apptId,
              paymentId: intentResp.paymentId,
              doctorName: doc?.fullName ?? 'Doctor',
              specialty: doc?.specialty ?? '',
              date: slot?.date ?? '',
              time: slot != null ? '${slot.startTime} - ${slot.endTime}' : '',
              amount: statusResult.amount,
            ),
          ),
        );
      } else if (!updatedSession.isConfirmed) {
        setState(() {
          _errorMessage = statusResult.paymentStatus.toUpperCase() == 'FAILED'
              ? 'Payment failed. Please try again while the slot is held.'
              : 'Payment is awaiting verification. Check My Appointments for updates.';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isPaymentProcessing = false;
        _errorMessage = 'Payment processing error: ${e.toString()}';
      });
    }
  }

  void _scrollToBottom({bool force = false}) {
    if (!force && _scrollController.hasClients &&
        _scrollController.position.extentAfter > 230) {
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // The route may have been popped between scheduling and this frame (BUG-015): never touch
      // a scroll position whose render object has been detached.
      if (_disposed || !mounted || !_scrollController.hasClients) return;
      final position = _scrollController.position;
      if (!position.hasContentDimensions) return;
      {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  /// True while the backend reports an emergency for this conversation (BUG-042). The backend
  /// contract is `isUrgent: true` plus `activeIntent: EMERGENCY_GUIDANCE`; the session `state`
  /// stays `COLLECTING_PREFERENCES`, so the state alone must not drive routine booking UI.
  bool get _isEmergencyActive {
    final session = _session;
    if (session == null) return false;
    return session.isUrgent || session.activeIntent == 'EMERGENCY_GUIDANCE';
  }

  static final RegExp _sinhalaScript = RegExp(r'[඀-෿]');
  static final RegExp _tamilScript = RegExp(r'[஀-௿]');

  /// Language for emergency UI. The backend answers a Romanized Sinhala emergency in Sinhala but
  /// keeps `preferences.language = en`, so the script of the latest emergency reply decides first;
  /// then the conversation language; then the app locale.
  String get _emergencyLanguage {
    final messages = _session?.messages ?? const <ChatMessage>[];
    for (var i = messages.length - 1; i >= 0; i--) {
      final m = messages[i];
      if (m.isUser || m.metadata?['type'] != 'emergency') continue;
      if (_sinhalaScript.hasMatch(m.content)) return 'si';
      if (_tamilScript.hasMatch(m.content)) return 'ta';
      break;
    }
    final conversation = _session?.preferences.language;
    if (conversation == 'si' || conversation == 'ta') return conversation!;
    final app = Localizations.maybeLocaleOf(context)?.languageCode;
    return app == 'si' || app == 'ta' ? app! : 'en';
  }

  /// The latest emergency reply's structured metadata (category, crisisType, supportLines).
  Map<String, dynamic>? get _latestEmergencyMeta {
    final messages = _session?.messages ?? const <ChatMessage>[];
    for (var i = messages.length - 1; i >= 0; i--) {
      final m = messages[i];
      if (!m.isUser && m.metadata?['type'] == 'emergency') return m.metadata;
    }
    return null;
  }

  /// Self-harm gets a dedicated supportive experience, not the cardiac-style alarm (Phase 01).
  bool get _isMentalHealthCrisis {
    final meta = _latestEmergencyMeta;
    return meta != null && (meta['crisisType'] == 'mental_health' || meta['category'] == 'self_harm');
  }

  String _mentalHealthText(String key) {
    return _mentalHealthStrings[_emergencyLanguage]?[key] ?? _mentalHealthStrings['en']![key]!;
  }

  /// Verified numbers only (checked 2026-11-25): 1926 National Mental Health Helpline (NIMH, 24 hours),
  /// 1333 CCCline (24 hours), 1990 Suwa Seriya ambulance.
  static const Map<String, Map<String, String>> _mentalHealthStrings = {
    'en': {
      'title': "You don't have to face this alone",
      'body': 'Free, confidential support is available 24 hours. If you are in danger right now, call 1990.',
      'call1926': 'Call 1926 helpline',
      'call1333': 'Call 1333',
      'danger': 'In danger now? Call 1990',
      'dialog1926': 'Call the National Mental Health Helpline (1926)?',
      'dialog1333': 'Call CCCline crisis support (1333)?',
      'dialogBody': 'This opens your phone dialer with the number entered. The call starts only when you press '
          'the call button in the dialer.',
    },
    'si': {
      'title': 'ඔබ මෙයට තනියම මුහුණ දිය යුතු නැහැ',
      'body': 'නොමිලේ, රහසිගත සහාය පැය 24 පුරා ලබාගත හැකියි. ඔබ දැන් අනතුරේ නම් 1990 අමතන්න.',
      'call1926': '1926 අමතන්න',
      'call1333': '1333 අමතන්න',
      'danger': 'දැන් අනතුරේද? 1990 අමතන්න',
      'dialog1926': 'ජාතික මානසික සෞඛ්‍ය උපකාරක අංකය (1926) අමතන්නද?',
      'dialog1333': 'CCCline අර්බුද සහාය (1333) අමතන්නද?',
      'dialogBody': 'මෙය අංකය ඇතුළත් කළ ඔබගේ දුරකථන ඩයලරය විවෘත කරයි. ඇමතුම ආරම්භ වන්නේ ඔබ ඇමතුම් බොත්තම එබූ විට පමණි.',
    },
    'ta': {
      'title': 'இதை நீங்கள் தனியாக எதிர்கொள்ள வேண்டியதில்லை',
      'body': 'இலவச, இரகசிய ஆதரவு 24 மணி நேரமும் கிடைக்கும். நீங்கள் இப்போது ஆபத்தில் இருந்தால் 1990 ஐ அழைக்கவும்.',
      'call1926': '1926 ஐ அழைக்கவும்',
      'call1333': '1333 ஐ அழைக்கவும்',
      'danger': 'இப்போது ஆபத்தா? 1990 ஐ அழைக்கவும்',
      'dialog1926': 'தேசிய மனநல உதவி எண்ணை (1926) அழைக்கவா?',
      'dialog1333': 'CCCline நெருக்கடி ஆதரவை (1333) அழைக்கவா?',
      'dialogBody': 'இது எண் உள்ளிடப்பட்ட உங்கள் தொலைபேசி டயலரைத் திறக்கும். அழைப்பு பொத்தானை அழுத்தும்போது மட்டுமே அழைப்பு தொடங்கும்.',
    },
  };

  String _emergencyText(String key) {
    return _emergencyStrings[_emergencyLanguage]?[key] ?? _emergencyStrings['en']![key]!;
  }

  static const Map<String, Map<String, String>> _emergencyStrings = {
    'en': {
      'title': 'Possible medical emergency',
      'fallbackReason': 'Call 1990 now or go to the nearest Emergency Treatment Unit (ETU).',
      'call': 'Call 1990',
      'dialogTitle': 'Call 1990 Suwa Seriya ambulance?',
      'dialogBody': 'This opens your phone dialer with 1990 entered. The call starts only when you '
          'press the call button in the dialer.\n\nIf you cannot call, go to the nearest hospital '
          'Emergency Treatment Unit (ETU) or ask someone nearby to help.',
      'cancel': 'Cancel',
      'open': 'Open dialer',
      'dialerFailed': 'Could not open the phone dialer. Dial 1990 on your phone now.',
    },
    'si': {
      'title': 'හදිසි වෛද්‍ය තත්ත්වයක් විය හැක',
      'fallbackReason': 'දැන්ම 1990 අමතන්න, නැතහොත් ළඟම ඇති රෝහලේ හදිසි ප්‍රතිකාර ඒකකයට (ETU) යන්න.',
      'call': '1990 අමතන්න',
      'dialogTitle': '1990 සුවසැරිය ගිලන්රථ සේවය අමතන්නද?',
      'dialogBody': 'මෙය 1990 ඇතුළත් කළ ඔබගේ දුරකථන ඩයලරය විවෘත කරයි. ඇමතුම ආරම්භ වන්නේ ඔබ '
          'ඩයලරයේ ඇමතුම් බොත්තම එබූ විට පමණි.\n\nඇමතීමට නොහැකි නම් ළඟම ඇති රෝහලේ ETU වෙත යන්න, '
          'නැතහොත් අසල සිටින කෙනෙකුගෙන් උදව් ඉල්ලන්න.',
      'cancel': 'අවලංගු කරන්න',
      'open': 'ඩයලරය විවෘත කරන්න',
      'dialerFailed': 'දුරකථන ඩයලරය විවෘත කළ නොහැකි විය. දැන්ම ඔබගේ දුරකථනයෙන් 1990 අමතන්න.',
    },
    'ta': {
      'title': 'அவசர மருத்துவ நிலை இருக்கலாம்',
      'fallbackReason': 'இப்போதே 1990 ஐ அழைக்கவும் அல்லது அருகிலுள்ள அவசர சிகிச்சைப் பிரிவுக்கு (ETU) செல்லவும்.',
      'call': '1990 ஐ அழைக்கவும்',
      'dialogTitle': '1990 சுவசெரிய ஆம்புலன்ஸை அழைக்கவா?',
      'dialogBody': 'இது 1990 உள்ளிடப்பட்ட உங்கள் தொலைபேசி டயலரைத் திறக்கும். டயலரில் அழைப்பு '
          'பொத்தானை அழுத்தும்போது மட்டுமே அழைப்பு தொடங்கும்.\n\nஅழைக்க முடியாவிட்டால் அருகிலுள்ள '
          'மருத்துவமனையின் ETU க்குச் செல்லவும் அல்லது அருகில் உள்ளவரிடம் உதவி கேட்கவும்.',
      'cancel': 'ரத்துசெய்',
      'open': 'டயலரைத் திற',
      'dialerFailed': 'தொலைபேசி டயலரைத் திறக்க முடியவில்லை. இப்போதே உங்கள் தொலைபேசியில் 1990 ஐ அழைக்கவும்.',
    },
  };

  /// Asks for confirmation, then opens the dialer with 1990. Never places a call by itself.
  Future<void> _callAmbulance() => _callNumber('1990');

  /// Confirmation, then the dialer pre-filled with [number] (1990, 1926 or 1333). Never places a call.
  Future<void> _callNumber(String number) async {
    final isAmbulance = number == '1990';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const Key('ai_emergency_call_dialog'),
        icon: Icon(isAmbulance ? Icons.emergency_rounded : Icons.support_agent_rounded,
            color: isAmbulance ? Colors.red : const Color(0xFF5B4B8A)),
        title: Text(isAmbulance ? _emergencyText('dialogTitle') : _mentalHealthText('dialog$number')),
        content: Text(isAmbulance ? _emergencyText('dialogBody') : _mentalHealthText('dialogBody')),
        actions: [
          TextButton(
            key: const Key('ai_emergency_call_cancel'),
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(_emergencyText('cancel')),
          ),
          TextButton.icon(
            key: const Key('ai_emergency_call_confirm'),
            style: TextButton.styleFrom(foregroundColor: Colors.red.shade700),
            onPressed: () => Navigator.of(ctx).pop(true),
            icon: const Icon(Icons.phone),
            label: Text(_emergencyText('open')),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final opened = await (widget.emergencyDialer ?? EmergencyDialer.open)(number);
    if (!opened && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(isAmbulance ? _emergencyText('dialerFailed')
              : _emergencyText('dialerFailed').replaceAll('1990', number)),
          backgroundColor: AppTheme.error,
        ),
      );
    }
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
                                        doc.hospitalOrClinic?.isNotEmpty == true
                                            ? doc.hospitalOrClinic!
                                            : 'Clinic unavailable',
                                        style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                                      ),
                                    ),
                                    Text(
                                      doc.consultationFee == null
                                          ? 'Fee unavailable'
                                          : 'LKR ${doc.consultationFee!.toStringAsFixed(0)}',
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
    return PopScope(
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) return;
        // Release the text field focus and stop timers/scroll work before the route's render
        // objects are detached, so no callback touches a disposed render tree (BUG-015).
        FocusManager.instance.primaryFocus?.unfocus();
        _countdownTimer?.cancel();
        _uploadGeneration++;
      },
      child: _buildScaffold(context),
    );
  }

  Widget _buildScaffold(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('MediConnect AI Assistant', maxLines: 2, style: TextStyle(fontSize: 16)),
        actions: [
          IconButton(
            tooltip: 'Chat History',
            icon: const Icon(Icons.history),
            onPressed: _isLoading || _isPaymentProcessing ? null : _openHistory,
          ),
          TextButton.icon(
            onPressed: _isLoading || _isPaymentProcessing ? null : _resetSession,
            icon: const Icon(Icons.add_comment_outlined),
            label: const Text('New Chat'),
          ),
        ],
      ),
      body: SafeArea(
        // The composer must always fit (BUG-014 "composer disappears"). On the emulator, landscape
        // with the keyboard open left about 64 px for the body, and the fixed-height banners
        // pushed the composer off-screen (RenderFlex overflow). Everything except the conversation
        // list and the composer therefore gets a capped, scrollable share of the height.
        child: LayoutBuilder(
          builder: (context, constraints) => _buildBody(constraints.maxHeight),
        ),
      ),
    );
  }

  /// Body heights below this show only the conversation and the composer (for example landscape
  /// with the keyboard open). The banners return as soon as there is room again.
  static const double _tightBodyHeight = 240;

  /// Body heights below this hide the quick-prompt chips (about 86 px).
  static const double _compactBodyHeight = 420;

  Widget _buildBody(double height) {
    final tight = height < _tightBodyHeight;
    final compact = height < _compactBodyHeight;

    final header = <Widget>[
      // Stitch Clinical Clarity Informational Disclaimer Banner
      if (!compact || !_isEmergencyActive) _buildStitchDisclaimerBanner(),
      // Emergency Red-Flag Banner
      if (_isEmergencyActive) _buildEmergencyBanner(),
      // Error banner if any
      if (_errorMessage != null) _buildErrorBanner(),
    ];

    final attachments = <Widget>[
      // Selected Image Preview chip if attached
      if (_selectedImageBytes != null) _buildSelectedImagePreview(),
      // Upload & analysis progress stays visible above the composer (BUG-026)
      if (_isUploadingImage) _buildUploadProgress(),
    ];

    // Quick suggestion prompt chips: routine booking suggestions are hidden during an emergency
    // so they do not compete with the 1990 guidance (BUG-042).
    final showQuickPrompts = !compact &&
        _session != null &&
        !_isEmergencyActive &&
        (_session!.isCollectingPreferences || _session!.isSearchingDoctors);

    return Column(
      children: [
        if (!tight && header.isNotEmpty) _cappedSection(header, height * 0.35),

        // Main chat conversation list
        Expanded(
          child: _isLoading && _session == null
              ? const Center(child: CircularProgressIndicator())
              : _buildConversationView(),
        ),

        if (showQuickPrompts) _buildQuickPromptsBar(),

        if (!tight && attachments.isNotEmpty) _cappedSection(attachments, height * 0.3),

        // Bottom Chat Input Bar: the only fixed-height child, so it always fits.
        _buildInputArea(maxLines: tight ? 1 : 4),
      ],
    );
  }

  /// A section that takes at most [maxHeight] and scrolls when its content is taller.
  Widget _cappedSection(List<Widget> children, double maxHeight) {
    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: maxHeight),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: children),
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
    if (_isMentalHealthCrisis) return _buildMentalHealthBanner();
    // The backend's urgencyReason is English only, so it is shown only in the English banner.
    final reason = _emergencyLanguage == 'en' ? _session?.urgencyReason?.trim() : null;
    return Container(
      key: const Key('ai_emergency_banner'),
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
                Text(
                  _emergencyText('title'),
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                ),
                Text(
                  reason == null || reason.isEmpty
                      ? _emergencyText('fallbackReason')
                      : '$reason. ${_emergencyText('fallbackReason')}',
                  style: const TextStyle(color: Colors.white, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // The app theme gives every ElevatedButton `minimumSize: Size(double.infinity, 52)`.
          // Inside a Row that is an infinite-width constraint, which threw during layout, left the
          // screen's render tree half laid out, and caused BUG-014/015/042/043/045. A button placed
          // in a Row must always override `minimumSize` with a finite width.
          ElevatedButton.icon(
            key: const Key('ai_emergency_call_1990'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.red.shade700,
              minimumSize: const Size(72, 40),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
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

  static const Color _supportColor = Color(0xFF5B4B8A);

  /// Calm, supportive banner for a mental-health crisis (Phase 01). 1926 is primary; 1990 stays available for
  /// immediate danger, as the clinical requirement says escalation must not be removed.
  Widget _buildMentalHealthBanner() {
    return Container(
      key: const Key('ai_mental_health_banner'),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: const Color(0xFFEDE9F6),
      child: Row(
        children: [
          const Icon(Icons.favorite_rounded, color: _supportColor, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_mentalHealthText('title'),
                    style: const TextStyle(color: _supportColor, fontWeight: FontWeight.bold, fontSize: 14)),
                Text(_mentalHealthText('body'), style: const TextStyle(color: Color(0xFF3F3558), fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            key: const Key('ai_mental_health_call_1926'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _supportColor,
              foregroundColor: Colors.white,
              minimumSize: const Size(72, 40),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              visualDensity: VisualDensity.compact,
            ),
            onPressed: () => _callNumber('1926'),
            icon: const Icon(Icons.phone, size: 16),
            label: const Text('1926', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  /// Supportive actions under the latest self-harm reply (Phase 01).
  Widget _buildMentalHealthMessageAction() {
    return Padding(
      key: const Key('ai_mental_health_actions'),
      padding: const EdgeInsets.only(left: 40, bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ElevatedButton.icon(
            key: const Key('ai_mental_health_message_call_1926'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _supportColor,
              foregroundColor: Colors.white,
              minimumSize: const Size(double.infinity, 46),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => _callNumber('1926'),
            icon: const Icon(Icons.support_agent_rounded, size: 18),
            label: Text(_mentalHealthText('call1926'), style: const TextStyle(fontWeight: FontWeight.bold)),
          ),
          const SizedBox(height: 6),
          OutlinedButton.icon(
            key: const Key('ai_mental_health_call_1333'),
            style: OutlinedButton.styleFrom(
              foregroundColor: _supportColor,
              minimumSize: const Size(double.infinity, 42),
              side: const BorderSide(color: _supportColor),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () => _callNumber('1333'),
            icon: const Icon(Icons.phone_rounded, size: 16),
            label: Text(_mentalHealthText('call1333')),
          ),
          TextButton.icon(
            key: const Key('ai_mental_health_call_1990'),
            style: TextButton.styleFrom(foregroundColor: Colors.red.shade700),
            onPressed: () => _callNumber('1990'),
            icon: const Icon(Icons.emergency_rounded, size: 16),
            label: Text(_mentalHealthText('danger')),
          ),
        ],
      ),
    );
  }

  /// Dedicated 1990 action shown under the latest emergency reply (BUG-042).
  Widget _buildEmergencyMessageAction() {
    if (_isMentalHealthCrisis) return _buildMentalHealthMessageAction();
    return Padding(
      padding: const EdgeInsets.only(left: 40, bottom: 12),
      child: ElevatedButton.icon(
        key: const Key('ai_emergency_message_call'),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.red.shade700,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 46),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
        onPressed: _callAmbulance,
        icon: const Icon(Icons.phone_in_talk_rounded, size: 18),
        label: Text(_emergencyText('call'), style: const TextStyle(fontWeight: FontWeight.bold)),
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
          if (_session == null) TextButton(onPressed: _initSession, child: const Text('Retry')),
          if (_session != null && _failedUpload != null)
            TextButton(
              key: const Key('ai_care_assistant_retry_upload'),
              onPressed: _isLoading ? null : _retryFailedUpload,
              child: const Text('Retry'),
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
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      itemCount: messages.length + 1, // +1 for conversational action widgets (cards/slots)
      itemBuilder: (context, index) {
        if (index < messages.length) {
          final msg = messages[index];
          final doctors = msg.metadata?['doctors'] as List?;
          final structuredCards = index == messages.length - 1 && !msg.isUser
              ? _session?.assistantDoctorCards ?? const <DoctorCardSummary>[]
              : const <DoctorCardSummary>[];
          return Column(
            key: ValueKey(msg.id),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (msg.id == _revealReplyId)
                _RevealOnce(
                  key: ValueKey('reveal_${msg.id}'),
                  onRevealed: () => _revealReplyId = null,
                  child: _buildChatBubble(msg),
                )
              else
                _buildChatBubble(msg),
              if (!msg.isUser && msg.metadata?['type'] == 'emergency' && index == messages.length - 1)
                _buildEmergencyMessageAction(),
              if (msg.metadata?['type'] == 'booking_confirmed' &&
                  msg.metadata?['appointmentId'] != _session?.bookingResult?['reference'])
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.event_available),
                    title: const Text('Appointment confirmed'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.pushNamed(context, '/patient/my-appointments'),
                  ),
                ),
              // A03-BUG-012: cancel / reschedule requests are answered with the patient's upcoming appointments; the
              // change itself happens only in My Appointments (cancellation preview and refund rules first).
              if (msg.metadata?['type'] == 'appointment_management' && index == messages.length - 1)
                Card(
                  key: const ValueKey('manage_appointments_action'),
                  child: ListTile(
                    leading: const Icon(Icons.event_note),
                    title: const Text('Open My Appointments'),
                    subtitle: Text(msg.metadata?['action'] == 'reschedule'
                        ? 'Choose the appointment, then Reschedule'
                        : 'Choose the appointment, then Cancel Appointment'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.pushNamed(context, '/patient/my-appointments'),
                  ),
                ),
              if (doctors != null)
                ...doctors.map((doc) => _buildDoctorCandidateCard(
                  DoctorCardSummary.fromJson(Map<String, dynamic>.from(doc as Map)),
                  showProfile: msg.metadata?['type'] == 'doctor_details',
                ))
              else
                ...structuredCards.map((doctor) => _buildDoctorCandidateCard(doctor)),
            ],
          );
        }
        // Last item: candidate doctors or slots or summary card based on state
        return _buildInteractiveStateWidgets();
      },
    );
  }

  Widget _buildChatBubble(ChatMessage message) {
    final isUser = message.isUser;
    String displayContent = message.content;
    if (!isUser) {
      displayContent = displayContent
          .replaceAll(RegExp(r'\s*\*\([sS]ee the (?:wellness|medicine|exercise) card below[^\)]*\)\*?'), '')
          .replaceAll(RegExp(r'\s*\*\([^\)]*card එකෙන් බලන්න[^\)]*\)\*?'), '')
          .trim();
      if (displayContent.isEmpty) {
        return const SizedBox.shrink();
      }
    }

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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (isUser && (message.metadata?['attachment'] != null || _attachmentPreviews.containsKey(message.id)))
                    _buildAttachmentChip(message),
                  if (isUser)
                    Text(
                      message.content,
                      style: const TextStyle(color: Colors.white, fontSize: 14.5, height: 1.35),
                    )
                  else
                    SafeMarkdownText(
                      displayContent,
                      style: const TextStyle(color: AppTheme.textPrimary, fontSize: 14.5, height: 1.35),
                    ),
                ],
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

  Widget _buildAttachmentChip(ChatMessage message) {
    final bytes = _attachmentPreviews[message.id];
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (bytes != null)
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Image.memory(bytes, width: 56, height: 56, fit: BoxFit.cover,
                  errorBuilder: (_, _, _) => const Icon(Icons.broken_image_outlined, color: Colors.white, size: 20)),
            )
          else
            const Icon(Icons.image_outlined, color: Colors.white, size: 20),
          const SizedBox(width: 6),
          const Text('Photo attached', style: TextStyle(color: Colors.white70, fontSize: 12)),
        ],
      ),
    );
  }

  /// Visible progress while an image is uploaded and analysed (BUG-026).
  Widget _buildUploadProgress() {
    return Padding(
      key: const Key('ai_care_assistant_upload_progress'),
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 6),
      child: Row(
        children: [

          Expanded(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.outline.withValues(alpha: 0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Uploading and analysing your photo…',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
                  const SizedBox(height: 8),
                  const LinearProgressIndicator(),
                  const SizedBox(height: 6),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      key: const Key('ai_care_assistant_cancel_upload'),
                      onPressed: _cancelUpload,
                      child: const Text('Cancel'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInteractiveStateWidgets() {
    if (_session == null) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [

        // Active Educational Medicine Card (only when active intent is MEDICINE_INFORMATION)
        if (_session!.activeMedicineCard != null && _session!.activeIntent == 'MEDICINE_INFORMATION')
          _buildMedicineCard(_session!.activeMedicineCard!),

        // Active Educational Wellness Card (only when active intent is wellness)
        if (_session!.activeWellnessCard != null &&
            (_session!.activeIntent == 'HEALTHY_FOOD' ||
                _session!.activeIntent == 'EXERCISE_GUIDANCE' ||
                _session!.activeIntent == 'GENERAL_WELLNESS'))
          _buildWellnessCard(_session!.activeWellnessCard!),

        // Active Label & Packaging Analysis Card (only when active intent is image analysis)
        if (_session!.activeImageAnalysis != null && _session!.activeIntent == 'MEDICINE_IMAGE_ANALYSIS')
          _buildImageAnalysisCard(_session!.activeImageAnalysis!),

        // 1. Candidate Doctor Cards
        if (_session!.isAwaitingDoctor && _session!.candidateDoctors.isNotEmpty &&
            _session!.assistantDoctorCards.isEmpty &&
            !_session!.messages.any((msg) => msg.metadata?['doctors'] != null)) ...[
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
        if (_session!.bookingResult?['status'] == 'CONFIRMED')
          _buildVerifiedBookingResult(_session!.bookingResult!),
        if (_session!.bookingResult?['reconciliationState'] != null)
          const ListTile(
            title: Text('Payment under review'),
            subtitle: Text('This appointment is awaiting payment reconciliation.'),
          ),
        if (_session!.bookingResult != null)
          TextButton(onPressed: _isLoading || _isPaymentProcessing ? null : _refreshBooking,
              child: const Text('Refresh booking status')),
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
    final isSinhala = RegExp(r'[\u0D80-\u0DFF]').hasMatch(card.medicineName) ||
        card.commonUses.any((u) => RegExp(r'[\u0D80-\u0DFF]').hasMatch(u)) ||
        card.precautions.any((p) => RegExp(r'[\u0D80-\u0DFF]').hasMatch(p));

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
                      // BUG-016: each strength is shown with its own dosage form.
                      for (final row in card.formulations)
                        Text(
                          '${row['form']}: ${row['strength']}',
                          key: Key('ai_medicine_formulation_${row['form']}'),
                          style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                        ),
                      if (card.formulations.isNotEmpty)
                        const Text(
                          'Strengths are not dose recommendations.',
                          style: TextStyle(fontSize: 11.5, fontStyle: FontStyle.italic, color: AppTheme.textSecondary),
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
                      isSinhala ? 'වෛද්‍ය නිර්දේශය අවශ්‍යයි (Rx)' : 'Rx Required',
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
              Text(
                isSinhala ? 'ප්‍රධාන භාවිතයන්' : 'Common Uses',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
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
              Text(
                isSinhala ? 'අවවාද සහ පූර්වාරක්ෂාවන්' : 'Precautions',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
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
              Text(
                isSinhala ? 'විය හැකි අතුරු ආබාධ' : 'Possible Side Effects',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
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
                          isSinhala ? 'වැදගත් අනතුරු ඇඟවීම්' : 'Important Warnings',
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
                    Row(
                      children: [
                        const Icon(Icons.local_pharmacy_outlined, size: 16, color: AppTheme.primary),
                        const SizedBox(width: 6),
                        Text(
                          isSinhala ? 'වෛද්‍ය උපදෙස් පැතිය යුතු අවස්ථා:' : 'Consult a Doctor or Pharmacist if:',
                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold, color: AppTheme.darkNavy),
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
            Text(
              isSinhala
                  ? 'සාමාන්‍ය දැනුවත් කිරීම සඳහා පමණි. ඖෂධ භාවිතයේදී සුදුසුකම්ලත් වෛද්‍යවරයෙකුගේ හෝ ඖෂධවේදියෙකුගේ උපදෙස් පිළිපදින්න.'
                  : 'Educational information only. MediConnect AI never provides personal dosages or alters doctor prescriptions. Always consult a qualified physician or pharmacist.',
              style: const TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWellnessCard(WellnessCardSummary card) {
    final isSinhala = RegExp(r'[\u0D80-\u0DFF]').hasMatch(card.title) ||
        RegExp(r'[\u0D80-\u0DFF]').hasMatch(card.summary);
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
              Text(
                isSinhala ? 'වැදගත් ප්‍රායෝගික නිර්දේශ' : 'Key Practical Recommendations',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppTheme.primary),
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
                          isSinhala
                              ? (card.category.toUpperCase() == 'FOOD' ? 'ශ්‍රී ලාංකික සෞඛ්‍ය සම්පන්න ආහාර' : 'ප්‍රායෝගික ව්‍යායාම විකල්ප')
                              : 'Sri Lankan Healthy Choices',
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
    switch (analysis.status) {
      case 'provider_unavailable':
        badgeColor = Colors.grey.shade700;
        badgeText = 'Not analysed';
        break;
      case 'invalid_file':
        badgeColor = Colors.red.shade700;
        badgeText = 'Upload problem';
        break;
      case 'not_medicine':
        badgeColor = Colors.deepOrange;
        badgeText = 'Not a medicine label';
        break;
      case 'unreadable':
        badgeColor = Colors.deepOrange;
        badgeText = 'Text not readable';
        break;
      case 'multiple_packages':
        badgeColor = Colors.deepOrange;
        badgeText = 'Several packages';
        break;
      default:
        // A01: a photo reading never earns a "high confidence" claim; the badge says what was done, not how sure.
        if (analysis.identifiedMedicine != null) {
          badgeColor = Colors.amber.shade800;
          badgeText = 'Label read — verify with pharmacist';
        } else {
          badgeColor = Colors.deepOrange;
          badgeText = 'Label read — not in library';
        }
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
            // A01: the text read from the photo is already listed in the chat reply above, so the card no longer
            // repeats it; it shows only the library match, what could not be read, and who read the photo.
            if (analysis.identifiedMedicine != null) ...[
              Row(
                children: [
                  const Text('Library match: ', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  Flexible(
                    child: Text(
                      analysis.identifiedMedicine!,
                      key: const Key('ai_image_library_match'),
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.primary),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
            ],
            if (analysis.unreadableFields.isNotEmpty) ...[
              Text(
                'Not readable in this photo: ${analysis.unreadableFields.join(', ')}',
                key: const Key('ai_image_unreadable_fields'),
                style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 8),
            ],
            if (analysis.embeddedTextIgnored) ...[
              const Text(
                'Text in the photo that looked like instructions to the assistant was ignored.',
                key: Key('ai_image_embedded_text_ignored'),
                style: TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
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
            if (analysis.provider != null) ...[
              Text(
                'Read by ${analysis.provider == 'gemini' ? 'Google Gemini' : analysis.provider == 'openai' ? 'OpenAI' : analysis.provider}'
                '${analysis.model != null ? ' (${analysis.model})' : ''} — automated reading, not verified',
                key: const Key('ai_image_read_by'),
                style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 6),
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

  String _availabilityPreview(DoctorCardSummary doctor) {
    final slots = doctor.availableSlots
        .where((slot) => slot.date == doctor.requestedDate)
        .map((slot) => slot.startTime)
        .toList();
    final date = doctor.requestedDate;
    if (slots.isEmpty) return 'No open slots found for $date (Sri Lanka time).';
    final requested = doctor.requestedTime;
    if (requested != null && slots.contains(requested)) {
      return '$date · $requested (Sri Lanka time)';
    }
    final times = slots.take(3).join(', ');
    if (requested != null) {
      return 'Other times on $date · $times (Sri Lanka time)';
    }
    return '$date · $times (Sri Lanka time)';
  }

  Widget _buildDoctorCandidateCard(DoctorCardSummary doctor, {bool showProfile = false}) {
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
                  child: doctor.profileImage?.isNotEmpty == true
                      ? ClipOval(child: Image.network(
                          Uri.parse(ApiConstants.hostBaseUrl).resolve(doctor.profileImage!).toString(),
                          width: 48,
                          height: 48,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) => const Icon(Icons.person),
                        ))
                      : const Icon(Icons.person, size: 28, color: AppTheme.primary),
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
                          const Tooltip(
                            message: 'Verified doctor',
                            child: Icon(Icons.verified, size: 16, color: AppTheme.primary),
                          ),
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
                      doctor.consultationFee == null ? 'Fee unavailable' : 'LKR ${doctor.consultationFee!.toStringAsFixed(0)}',
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
                    [doctor.hospitalOrClinic, doctor.city].whereType<String>().where((value) => value.isNotEmpty).join(' / '),
                    style: const TextStyle(fontSize: 12.5, color: AppTheme.textSecondary),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (doctor.rating > 0) const Icon(Icons.star, size: 15, color: Colors.amber),
                const SizedBox(width: 4),
                Text(
                  doctor.rating > 0 ? doctor.rating.toStringAsFixed(1) : '',
                  style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                ),
              ],
            ),

            if (showProfile && (doctor.experienceYears > 0 || doctor.bio?.isNotEmpty == true)) ...[
              const SizedBox(height: 8),
              if (doctor.experienceYears > 0)
                Text('${doctor.experienceYears} years of experience'),
              if (doctor.bio?.isNotEmpty == true) Text(doctor.bio!),
            ],

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

            if (doctor.requestedDate != null) ...[
              const SizedBox(height: 8),
              Text(_availabilityPreview(doctor)),
            ],

            // Action Buttons
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    foregroundColor: AppTheme.primary,
                    side: const BorderSide(color: AppTheme.primary),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.person_outline, size: 15),
                  label: const Text('View Details', style: TextStyle(fontSize: 12.5)),
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DoctorDetailScreen(doctorId: doctor.doctorId),
                      ),
                    );
                  },
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    visualDensity: VisualDensity.compact,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.event_available, size: 15),
                  label: const Text('View Available Slots', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold)),
                  onPressed: _isLoading || _isPaymentProcessing ? null : () => _selectDoctor(doctor.doctorId),
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
            if (s.city != null) _buildSummaryRow('City', s.city!),
            // A03-BUG-015: the patient accepts an in-person clinic visit (no video consultation exists).
            _buildSummaryRow('Visit type', s.visitType == 'IN_PERSON' ? 'In-person at the clinic' : s.visitType),
            if (s.patientName != null) _buildSummaryRow('Patient', s.patientName!),
            if (s.proposalId != null) ...[
              _buildSummaryRow('Email', s.maskedEmail ?? 'Add a verified email in your account'),
              if (s.maskedPhone != null)
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('Send confirmation SMS to ${s.maskedPhone}'),
                  value: _smsConsentProposal == s.proposalId,
                  onChanged: _isLoading ? null : (value) => setState(
                    () => _smsConsentProposal = value == true ? s.proposalId : null,
                  ),
                )
              else
                const Text('Add a Sri Lankan mobile number in your account to receive SMS.'),
              if (s.selectionReason != null) Text(s.selectionReason!),
              const Text('Appointment times are shown in Sri Lanka time.'),
            ],
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
            if (s.proposalId != null)
              Wrap(
                children: [
                  TextButton(onPressed: _isLoading || _session!.candidateDoctors.isEmpty ? null : _changeProposalDoctor,
                      child: const Text('Change Doctor')),
                  TextButton(
                      onPressed: _isLoading || _session!.selectedDoctor == null ? null
                          : () => _selectDoctor(_session!.selectedDoctor!.doctorId),
                      child: const Text('Change Date/Time')),
                  TextButton(onPressed: _isLoading ? null : _cancelProposal, child: const Text('Cancel')),
                ],
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
                  : Text(
                      s.proposalId == null ? 'Confirm Booking' : 'Accept & Continue',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  static String _deliveryLabel(dynamic status) {
    switch (status?.toString()) {
      case 'sent':
      case 'delivered':
        return status.toString();
      case 'accepted':
        return 'accepted by provider';
      case 'skipped':
        return 'not requested';
      case 'failed':
        return 'not sent';
      case 'uncertain':
        return 'delivery unconfirmed';
      default:
        return 'pending';
    }
  }

  Widget _buildVerifiedBookingResult(Map<String, dynamic> result) {
    final notices = result['notifications'] as Map? ?? {};
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Appointment Confirmed', style: TextStyle(fontWeight: FontWeight.bold)),
            Text('Reference: ${result['reference']}'),
            if (result['doctor'] != null) Text(result['doctor'].toString()),
            Text('${result['date']} at ${result['time']} (Sri Lanka time)'),
            if (result['clinic'] != null) Text(result['clinic'].toString()),
            Text(result['paymentStatus'] == 'PAID' ? 'Paid' : 'No payment required'),
            // Truthful delivery wording (Phase 02): never implies an email/SMS was sent when it was not.
            Text('Email: ${_deliveryLabel(notices['email'])}', key: const Key('ai_booking_email_status')),
            Text('SMS: ${_deliveryLabel(notices['sms'])}', key: const Key('ai_booking_sms_status')),
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
            if (!isHoldExpired) ...[
              const SizedBox(height: 6),
              TextButton.icon(
                key: const Key('ai_release_reservation'),
                style: TextButton.styleFrom(foregroundColor: AppTheme.error, minimumSize: const Size(0, 40)),
                onPressed: _isPaymentProcessing || _isLoading ? null : _releaseReservation,
                icon: const Icon(Icons.event_busy_outlined, size: 18),
                label: const Text('Release Reservation'),
              ),
            ],
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
              errorBuilder: (_, _, _) => const Icon(Icons.broken_image_outlined, color: AppTheme.textSecondary),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _selectedImage?.name ?? _retryImageName ?? 'Packaging Image',
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

  /// The composer row (attach, text field, send) is one tap group: a tap on Send must not count as "outside"
  /// the text field. Otherwise the keyboard starts closing on pointer-down, the button moves away with the layout,
  /// and the tap is lost (found on the emulator in Phase 01). Send dismisses the keyboard itself.
  static const Object _composerTapGroup = #ai_composer_tap_group;

  Widget _buildInputArea({int maxLines = 4}) {
    return TapRegion(
      groupId: _composerTapGroup,
      child: _buildInputAreaContent(maxLines: maxLines),
    );
  }

  Widget _buildInputAreaContent({int maxLines = 4}) {
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
              focusNode: _composerFocus,
              groupId: _composerTapGroup,
              onTapOutside: (_) => _composerFocus.unfocus(),
              minLines: 1,
              maxLines: maxLines,
              maxLength: 2000,
              textInputAction: TextInputAction.send,
              decoration: InputDecoration(
                counterText: '',
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
            onPressed: _isLoading || _isPaymentProcessing ? null : () => _sendMessage(),
          ),
        ],
      ),
    );
  }
}


/// Scrolls its child into view with the child's top at the top of the viewport, once, after the first layout
/// (Phase 01: long replies are read from the start). It uses its own BuildContext, never a GlobalKey, and checks
/// `mounted` because the route can be popped before the post-frame callback runs (BUG-015).
class _RevealOnce extends StatefulWidget {
  final Widget child;
  final VoidCallback onRevealed;

  const _RevealOnce({super.key, required this.child, required this.onRevealed});

  @override
  State<_RevealOnce> createState() => _RevealOnceState();
}

class _RevealOnceState extends State<_RevealOnce> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      widget.onRevealed();
      Scrollable.ensureVisible(
        context,
        alignment: 0.0,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
