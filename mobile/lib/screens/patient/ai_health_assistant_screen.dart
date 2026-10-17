import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/health_chat.dart';
import '../../services/health_chat_service.dart';

/// Screen providing AI Symptom Guidance & Doctor Referral Chatbot (Phase 20).
class AiHealthAssistantScreen extends StatefulWidget {
  final AiHealthChatService? chatService;
  final String initialLanguage;

  const AiHealthAssistantScreen({
    super.key,
    this.chatService,
    this.initialLanguage = 'en',
  });

  @override
  State<AiHealthAssistantScreen> createState() => _AiHealthAssistantScreenState();
}

class _AiHealthAssistantScreenState extends State<AiHealthAssistantScreen> {
  late final AiHealthChatService _chatService;
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  HealthChatSession? _session;
  bool _isLoading = true;
  bool _isSending = false;
  String? _errorMessage;
  late String _currentLanguage;
  bool _showDisclaimer = true;

  final List<String> _starterQuestionsEn = [
    'I have had a mild headache for 2 days',
    'What causes frequent acid reflux & heartburn?',
    'Mild rash on my arm with slight itching',
    'How much water should I drink daily?',
  ];

  final List<String> _starterQuestionsSi = [
    'මට දින දෙකක සිට හිසරදය තියෙනවා',
    'නිතර බඩ දැවිල්ල ඇතිවීමට හේතු මොනවාද?',
    'උගුර රිදෙනවා සහ ඇඟපත වේදනාව',
    'දිනකට ජලය කොපමණ පානය කළ යුතුද?',
  ];

  @override
  void initState() {
    super.initState();
    _chatService = widget.chatService ?? AiHealthChatService();
    _currentLanguage = widget.initialLanguage;
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
      final session = await _chatService.createSession(
        language: _currentLanguage,
        consentGiven: true,
      );
      if (mounted) {
        setState(() {
          _session = session;
          _isLoading = false;
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to start AI Health Assistant. Please check your connection and retry.';
          _isLoading = false;
        });
      }
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

  Future<void> _sendMessage(String text) async {
    final cleanText = text.trim();
    if (cleanText.isEmpty || _session == null || _isSending) return;

    _textController.clear();
    setState(() {
      _isSending = true;
      _errorMessage = null;
    });

    try {
      final updated = await _chatService.sendMessage(
        _session!.id,
        cleanText,
        language: _currentLanguage,
      );
      if (mounted) {
        setState(() {
          _session = updated;
          _isSending = false;
        });
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSending = false;
          _errorMessage = 'Failed to get a response. Please check your internet connection.';
        });
      }
    }
  }

  Future<void> _confirmDeleteSession() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Conversation?'),
        content: const Text(
          'This will permanently delete your symptoms transcript to protect your medical privacy. '
          'This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade700),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete & Start Fresh', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirmed == true && _session != null) {
      setState(() => _isLoading = true);
      try {
        await _chatService.deleteSession(_session!.id);
      } catch (_) {}
      if (mounted) {
        _initSession();
      }
    }
  }

  void _toggleLanguage() {
    setState(() {
      _currentLanguage = _currentLanguage == 'en' ? 'si' : 'en';
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          _currentLanguage == 'si'
              ? 'භාෂාව සිංහලට මාරු කරන ලදී (Language set to Sinhala)'
              : 'Language set to English',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.health_and_safety_rounded, color: Colors.tealAccent, size: 24),
            SizedBox(width: 8),
            Text('AI Health Assistant', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ],
        ),
        actions: [
          IconButton(
            key: const Key('health_chat_language_toggle'),
            icon: Chip(
              label: Text(
                _currentLanguage.toUpperCase(),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: Colors.white),
              ),
              backgroundColor: AppTheme.primaryLight,
              padding: EdgeInsets.zero,
              visualDensity: VisualDensity.compact,
            ),
            tooltip: 'Switch Language (EN / SI)',
            onPressed: _toggleLanguage,
          ),
          IconButton(
            key: const Key('health_chat_delete_button'),
            icon: const Icon(Icons.delete_outline_rounded),
            tooltip: 'Delete Chat (Privacy)',
            onPressed: _confirmDeleteSession,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (_showDisclaimer) _buildDisclaimerBanner(),
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _errorMessage != null && (_session == null || _session!.messages.isEmpty)
                      ? _buildErrorView()
                      : _buildChatList(),
            ),
            if (_isSending) _buildTypingIndicator(),
            _buildInputBar(),
          ],
        ),
      ),
    );
  }

  Widget _buildDisclaimerBanner() {
    return Container(
      key: const Key('health_chat_disclaimer_banner'),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      color: Colors.teal.shade50,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline_rounded, size: 20, color: Colors.teal.shade800),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              _currentLanguage == 'si'
                  ? 'MediConnect AI සෞඛ්‍ය සහායකයා සාමාන්‍ය අධ්‍යාපනික තොරතුරු පමණක් සපයයි. මෙය වෛද්‍ය උපදෙසක් හෝ රෝග විනිශ්චයක් නොවේ. හදිසි අවස්ථාවකදී වහාම 1990 අමතන්න.'
                  : 'MediConnect AI provides general educational health information only. It is not a clinical diagnosis or prescription. In emergencies, call 1990 immediately.',
              style: TextStyle(fontSize: 12, color: Colors.teal.shade900, height: 1.3),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 16),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
            color: Colors.teal.shade700,
            onPressed: () => setState(() => _showDisclaimer = false),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off_rounded, size: 56, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              _errorMessage ?? 'An error occurred.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, color: Colors.black87),

            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _initSession,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primary,
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChatList() {
    final messages = _session?.messages ?? [];
    final hasUserMessage = messages.any((m) => m.isUser);

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      itemCount: messages.length + (!hasUserMessage ? 1 : 0),
      itemBuilder: (context, index) {
        if (!hasUserMessage && index == messages.length) {
          return _buildStarterQuestions();
        }
        final msg = messages[index];
        return _buildMessageTurn(msg);
      },
    );
  }

  Widget _buildStarterQuestions() {
    final starters = _currentLanguage == 'si' ? _starterQuestionsSi : _starterQuestionsEn;
    return Padding(
      key: const Key('health_chat_starter_chips'),
      padding: const EdgeInsets.only(top: 16.0, bottom: 8.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _currentLanguage == 'si'
                ? 'හෝ පහත සඳහන් පොදු ප්‍රශ්නයකින් ආරම්භ කරන්න:'
                : 'Or start with a common health inquiry:',
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.blueGrey),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: starters.map((q) {
              return ActionChip(
                label: Text(q, style: const TextStyle(fontSize: 12.5)),
                backgroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(color: Colors.teal.shade200),
                ),
                onPressed: () => _sendMessage(q),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageTurn(HealthChatMessage msg) {
    if (msg.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(top: 8, bottom: 8, left: 48),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: AppTheme.primary,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(18),
              topRight: Radius.circular(18),
              bottomLeft: Radius.circular(18),
              bottomRight: Radius.circular(4),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.05),
                blurRadius: 4,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                msg.content,
                style: const TextStyle(fontSize: 14.5, color: Colors.white, height: 1.35),
              ),
              const SizedBox(height: 4),
              Text(
                _formatTime(msg.timestamp),
                style: TextStyle(fontSize: 10, color: Colors.white.withValues(alpha: 0.7)),
              ),
            ],
          ),
        ),
      );
    }

    // Assistant Turn
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (msg.isEmergency) _buildEmergencyGuidanceAlert(msg),
        Align(
          alignment: Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.only(top: 6, bottom: 6, right: 40),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(4),
                bottomRight: Radius.circular(18),
              ),
              border: Border.all(color: Colors.grey.shade300, width: 0.8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.medical_services_rounded,
                      size: 15,
                      color: msg.isEmergency ? Colors.red : AppTheme.primary,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'MediConnect Assistant',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: msg.isEmergency ? Colors.red.shade800 : AppTheme.primary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  msg.content,
                  style: const TextStyle(fontSize: 14.5, color: Colors.black87, height: 1.4),
                ),
                if (msg.disclaimer != null) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey.shade300),
                    ),
                    child: Text(
                      msg.disclaimer!,

                      style: TextStyle(fontSize: 11, color: Colors.grey.shade700, fontStyle: FontStyle.italic),
                    ),
                  ),
                ],
                const SizedBox(height: 4),
                Text(
                  _formatTime(msg.timestamp),
                  style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
                ),
              ],
            ),
          ),
        ),
        if (msg.clarifyingQuestions.isNotEmpty) _buildClarifyingChips(msg.clarifyingQuestions),
        if (msg.doctorReferrals.isNotEmpty) _buildDoctorReferralSection(msg.doctorReferrals),
      ],
    );
  }

  Widget _buildEmergencyGuidanceAlert(HealthChatMessage msg) {
    return Container(
      key: const Key('health_chat_emergency_banner'),
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.red.shade400, width: 1.5),
      ),

      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: Colors.red, size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _currentLanguage == 'si'
                      ? 'හදිසි වෛද්‍ය අවධානයක් අවශ්‍ය වේ'
                      : 'Immediate Emergency Care Advised',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.red.shade900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _currentLanguage == 'si'
                ? 'ඔබේ රෝග ලක්ෂණ හදිසි වෛද්‍ය තත්ත්වයක් පෙන්නුම් කරයි. කරුණාකර සාමාන්‍ය සායන වේලාවන් සඳහා ප්‍රමාද නොවී වහාම 1990 ගිලන්රථ සේවය අමතන්න හෝ ළඟම ඇති රෝහල් හදිසි ප්‍රතිකාර ඒකකයට (ETU) යන්න.'
                : 'Your symptoms suggest an acute emergency. Do not wait for a routine appointment. Call 1990 Suwa Seriya ambulance immediately or proceed to the nearest Hospital Emergency Treatment Unit (ETU).',
            style: TextStyle(fontSize: 13.5, color: Colors.red.shade900, height: 1.35),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              key: const Key('health_chat_emergency_call_1990_button'),
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Calling 1990: Sri Lanka National Ambulance Service (Suwa Seriya)'),
                    backgroundColor: Colors.red,
                    duration: Duration(seconds: 4),
                  ),
                );
              },
              icon: const Icon(Icons.phone_in_talk_rounded, color: Colors.white),
              label: const Text(
                'CALL 1990 AMBULANCE NOW',
                style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 0.5, color: Colors.white),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red.shade700,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildClarifyingChips(List<String> questions) {
    return Padding(
      padding: const EdgeInsets.only(left: 6, bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _currentLanguage == 'si' ? 'අදාළ ප්‍රශ්නයක් තෝරන්න:' : 'Helpful context you can share:',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.blueGrey),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: questions.map((q) {
              return ActionChip(
                label: Text(q, style: const TextStyle(fontSize: 12)),
                backgroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: Colors.blueGrey.shade200),
                ),
                onPressed: () => _sendMessage(q),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildDoctorReferralSection(List<DoctorReferralCard> referrals) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.verified_user_rounded, color: AppTheme.primary, size: 18),
              const SizedBox(width: 6),
              Text(
                _currentLanguage == 'si' ? 'නිර්දේශිත පිළිගත් වෛද්‍යවරුන්' : 'Recommended Verified Doctors',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
            ],
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 185,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: referrals.length,
              itemBuilder: (context, idx) {
                final doc = referrals[idx];
                return _buildDoctorReferralCard(doc);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDoctorReferralCard(DoctorReferralCard doc) {
    return Container(
      key: Key('doctor_referral_card_${doc.doctorId}'),
      width: 250,
      margin: const EdgeInsets.only(right: 12, bottom: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.teal.shade200, width: 1.2),
        boxShadow: [

          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 6,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: Colors.teal.shade50,
                child: const Icon(Icons.person, color: AppTheme.primary, size: 22),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      doc.fullName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13.5),
                    ),
                    Text(
                      doc.specialty,
                      style: const TextStyle(fontSize: 11, color: AppTheme.primary, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Fee: LKR ${doc.consultationFee.toStringAsFixed(0)} • ${doc.city ?? "Colombo"}',
            style: const TextStyle(fontSize: 11.5, color: Colors.blueGrey, fontWeight: FontWeight.w500),
          ),
          if (doc.nextAvailableSlot != null) ...[
            const SizedBox(height: 2),
            Text(
              'Next: ${doc.nextAvailableSlot}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 11, color: Colors.green.shade800, fontWeight: FontWeight.w600),
            ),
          ],
          const Spacer(),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  key: Key('doctor_referral_view_button_${doc.doctorId}'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    visualDensity: VisualDensity.compact,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () {
                    Navigator.of(context).pushNamed(
                      '/patient/doctor-detail',
                      arguments: doc.doctorId,
                    );
                  },
                  child: const Text('Profile', style: TextStyle(fontSize: 11)),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: ElevatedButton(
                  key: Key('doctor_referral_book_button_${doc.doctorId}'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    visualDensity: VisualDensity.compact,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () {
                    Navigator.of(context).pushNamed(
                      '/patient/ai-booking',
                      arguments: doc.doctorId,
                    );
                  },
                  child: const Text('Book AI', style: TextStyle(fontSize: 11, color: Colors.white)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      alignment: Alignment.centerLeft,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primary),
          ),
          const SizedBox(width: 8),
          Text(
            _currentLanguage == 'si'
                ? 'සෞඛ්‍ය සහායකයා පිළිතුරු සකසමින් පවතී...'
                : 'Assistant is reviewing your symptoms safely...',
            style: const TextStyle(fontSize: 12, color: Colors.grey, fontStyle: FontStyle.italic),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Colors.grey.shade200)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              key: const Key('health_chat_input_field'),
              controller: _textController,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (val) => _sendMessage(val),
              decoration: InputDecoration(
                hintText: _currentLanguage == 'si'
                    ? 'රෝග ලක්ෂණ විස්තර කරන්න හෝ ප්‍රශ්නයක් අසන්න...'
                    : 'Describe symptoms or ask a health question...',
                hintStyle: TextStyle(fontSize: 13.5, color: Colors.grey.shade500),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                filled: true,
                fillColor: Colors.grey.shade100,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(22),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          CircleAvatar(
            radius: 22,
            backgroundColor: AppTheme.primary,
            child: IconButton(
              key: const Key('health_chat_send_button'),
              icon: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
              onPressed: _isSending ? null : () => _sendMessage(_textController.text),
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}
