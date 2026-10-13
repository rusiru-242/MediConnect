import 'package:flutter/material.dart';

import '../../core/constants/specialties.dart';
import '../../core/theme/app_theme.dart';
import '../../models/doctor_recommendation.dart';
import '../../services/ai_recommendation_service.dart';
import 'booking_confirmation_screen.dart';
import 'doctor_detail_screen.dart';

/// Screen allowing patients to discover verified doctors using natural language (English/Sinhala)
/// and transparent deterministic ranking.
class AiDoctorRecommendationScreen extends StatefulWidget {
  final AiRecommendationService? aiService;

  const AiDoctorRecommendationScreen({super.key, this.aiService});

  @override
  State<AiDoctorRecommendationScreen> createState() => _AiDoctorRecommendationScreenState();
}

class _AiDoctorRecommendationScreenState extends State<AiDoctorRecommendationScreen> {
  late final AiRecommendationService _aiService;
  final TextEditingController _queryController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  bool _isLoading = false;
  String? _errorMessage;
  DoctorRecommendationResponse? _response;

  // Explicit filters toggle
  bool _showFilters = false;
  String _selectedSpecialty = 'All';
  final TextEditingController _cityController = TextEditingController();
  final TextEditingController _maxFeeController = TextEditingController();
  String? _selectedDate;

  final List<String> _samplePrompts = [
    'Cardiologist in Colombo tomorrow',
    'ළමා වෛද්‍යවරයෙක් හෙට උදේට',
    'Skin specialist under 3000 LKR',
    'ENT doctor for severe ear pain',
    'General Physician for high fever and cough',
    'මානසික පීඩනයට වෛද්‍යවරයෙක්',
  ];

  @override
  void initState() {
    super.initState();
    _aiService = widget.aiService ?? AiRecommendationService();
  }

  @override
  void dispose() {
    _queryController.dispose();
    _cityController.dispose();
    _maxFeeController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _applySamplePrompt(String prompt) {
    _queryController.text = prompt;
    _searchRecommendations();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: now,
      lastDate: now.add(const Duration(days: 60)),
    );
    if (picked != null) {
      setState(() {
        _selectedDate =
            '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
      });
    }
  }

  Future<void> _searchRecommendations() async {
    final queryText = _queryController.text.trim();
    if (queryText.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please describe what doctor or health concern you are looking for.')),
      );
      return;
    }

    FocusScope.of(context).unfocus();
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    double? maxFee;
    if (_maxFeeController.text.trim().isNotEmpty) {
      maxFee = double.tryParse(_maxFeeController.text.trim().replaceAll(',', ''));
    }

    try {
      final result = await _aiService.getDoctorRecommendations(
        query: queryText,
        specialty: _selectedSpecialty != 'All' ? _selectedSpecialty : null,
        city: _cityController.text.trim().isNotEmpty ? _cityController.text.trim() : null,
        date: _selectedDate,
        maxFee: maxFee,
      );

      if (!mounted) return;
      setState(() {
        _response = result;
        _isLoading = false;
      });

      // Smooth scroll down to results
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            180,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to complete AI doctor search. Please verify your connection and try again.';
        _isLoading = false;
      });
    }
  }

  void _callEmergencyHotline() {
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.auto_awesome_rounded, color: Colors.amber, size: 22),
            SizedBox(width: 8),
            Text('AI Doctor Finder'),
          ],
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          controller: _scrollController,
          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeaderBanner(),
              const SizedBox(height: 14),
              _buildInputCard(),
              const SizedBox(height: 12),
              _buildSamplePromptsSection(),
              const SizedBox(height: 16),
              if (_isLoading) _buildLoadingState(),
              if (_errorMessage != null) _buildErrorState(),
              if (_response != null && !_isLoading) ...[
                if (_response!.isUrgent) _buildUrgencyBanner(),
                if (_response!.clarificationQuestion != null) _buildClarificationCard(),
                _buildInterpretedPreferencesChips(),
                const SizedBox(height: 12),
                _buildRecommendationsList(),
                const SizedBox(height: 20),
                _buildDisclaimerCard(),
                const SizedBox(height: 24),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderBanner() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primary.withValues(alpha: 0.15),
            Colors.teal.shade50.withValues(alpha: 0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.15),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.psychology_alt_rounded, color: AppTheme.primary, size: 28),
          ),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Intelligent Doctor Matching',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
                SizedBox(height: 3),
                Text(
                  'Describe your needs in English or Sinhala. We will find verified specialists with real availability.',
                  style: TextStyle(
                    fontSize: 12.5,
                    color: AppTheme.textSecondary,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputCard() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              key: const Key('ai_doctor_search_input'),
              controller: _queryController,
              maxLines: 3,
              minLines: 2,
              decoration: InputDecoration(
                hintText:
                    'Example: "I need an experienced cardiologist in Colombo for chest discomfort tomorrow evening under 3000 LKR"',
                hintStyle: TextStyle(fontSize: 13.5, color: Colors.grey.shade500),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide(color: AppTheme.outline.withValues(alpha: 0.3)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.primary, width: 1.5),
                ),
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.all(14),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                TextButton.icon(
                  onPressed: () {
                    setState(() {
                      _showFilters = !_showFilters;
                    });
                  },
                  icon: Icon(
                    _showFilters ? Icons.tune_rounded : Icons.filter_list_rounded,
                    size: 18,
                    color: AppTheme.primary,
                  ),
                  label: Text(
                    _showFilters ? 'Hide Filters' : 'More Filters',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),
                const Spacer(),
                if (_queryController.text.isNotEmpty)
                  IconButton(
                    tooltip: 'Clear',
                    icon: const Icon(Icons.clear_rounded, size: 20, color: AppTheme.textSecondary),
                    onPressed: () {
                      setState(() {
                        _queryController.clear();
                      });
                    },
                  ),
                ElevatedButton.icon(
                  key: const Key('ai_doctor_search_submit_button'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  onPressed: _isLoading ? null : _searchRecommendations,
                  icon: const Icon(Icons.search_rounded, size: 18),
                  label: const Text('Find Doctors', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ],
            ),
            if (_showFilters) ...[
              const Divider(height: 24),
              _buildExplicitFiltersSection(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildExplicitFiltersSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Optional Explicit Criteria',
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
        ),
        const SizedBox(height: 10),
        // Specialty Dropdown
        DropdownButtonFormField<String>(
          initialValue: _selectedSpecialty,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: 'Specialty',
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
          ),
          items: [
            const DropdownMenuItem(value: 'All', child: Text('All Specialties')),
            ...Specialties.list.map((s) => DropdownMenuItem(value: s, child: Text(s))),
          ],
          onChanged: (val) {
            if (val != null) setState(() => _selectedSpecialty = val);
          },
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _cityController,
                decoration: InputDecoration(
                  labelText: 'City / Hospital',
                  hintText: 'e.g. Colombo, Asiri',
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _maxFeeController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: 'Max Fee (LKR)',
                  hintText: 'e.g. 3000',
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _pickDate,
                icon: const Icon(Icons.calendar_month_outlined, size: 16),
                label: Text(
                  _selectedDate ?? 'Select Preferred Date',
                  style: const TextStyle(fontSize: 12.5),
                ),
                style: OutlinedButton.styleFrom(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
            if (_selectedDate != null)
              IconButton(
                icon: const Icon(Icons.close_rounded, size: 18),
                onPressed: () => setState(() => _selectedDate = null),
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildSamplePromptsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Example Inquiries:',
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 38,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: _samplePrompts.length,
            separatorBuilder: (_, index) => const SizedBox(width: 8),
            itemBuilder: (context, idx) {
              final prompt = _samplePrompts[idx];
              return ActionChip(
                label: Text(prompt, style: const TextStyle(fontSize: 12)),
                backgroundColor: Colors.white,
                elevation: 1,
                side: BorderSide(color: AppTheme.outline.withValues(alpha: 0.25)),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                onPressed: () => _applySamplePrompt(prompt),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildLoadingState() {
    return Container(
      padding: const EdgeInsets.all(32),
      alignment: Alignment.center,
      child: Column(
        children: [
          const CircularProgressIndicator(color: AppTheme.primary),
          const SizedBox(height: 16),
          const Text(
            'Analyzing request & checking doctor availability...',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 6),
          Text(
            'Scanning verified doctors and real-time scheduling slots',
            style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Card(
      color: Colors.red.shade50,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 36),
            const SizedBox(height: 8),
            Text(
              _errorMessage ?? 'An error occurred.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppTheme.error, fontSize: 13.5, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.error,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: _searchRecommendations,
              child: const Text('Try Again'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUrgencyBanner() {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3CD),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFFFEEBA), width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: Color(0xFF856404), size: 24),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Potential Emergency Caution',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF856404),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _response?.safetyGuidance ??
                'If you are experiencing acute chest pain, severe shortness of breath, or sudden weakness, seek emergency care immediately.',
            style: const TextStyle(fontSize: 13, color: Color(0xFF533F03), height: 1.35),
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFD32F2F),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: _callEmergencyHotline,
            icon: const Icon(Icons.phone_in_talk_rounded, size: 18),
            label: const Text('Call Ambulance (1990)', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildClarificationCard() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue.shade100),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.help_outline_rounded, color: Colors.blue.shade700, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              _response!.clarificationQuestion!,
              style: TextStyle(fontSize: 13, color: Colors.blue.shade900, height: 1.3),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInterpretedPreferencesChips() {
    final prefs = _response!.interpretedPreferences;
    final chips = <Widget>[];

    if (prefs.specialty != null) {
      chips.add(_buildInfoChip(Icons.medical_services_outlined, 'Specialty: ${prefs.specialty}'));
    }
    if (prefs.city != null) {
      chips.add(_buildInfoChip(Icons.location_on_outlined, 'Location: ${prefs.city}'));
    }
    if (prefs.date != null) {
      chips.add(_buildInfoChip(Icons.calendar_today_outlined, 'Date: ${prefs.date}'));
    }
    if (prefs.timeRange != null) {
      chips.add(_buildInfoChip(Icons.schedule_outlined, 'Time: ${prefs.timeRange}'));
    }
    if (prefs.maxFee != null) {
      chips.add(_buildInfoChip(Icons.payments_outlined, 'Max Fee: LKR ${prefs.maxFee!.toStringAsFixed(0)}'));
    }

    if (chips.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Interpreted Search Criteria:',
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: chips,
        ),
      ],
    );
  }

  Widget _buildInfoChip(IconData icon, String text) {
    return Chip(
      avatar: Icon(icon, size: 14, color: AppTheme.primary),
      label: Text(text, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w500)),
      backgroundColor: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 4),
      side: BorderSide(color: AppTheme.outline.withValues(alpha: 0.2)),
    );
  }

  Widget _buildRecommendationsList() {
    final recs = _response!.recommendations;
    if (recs.isEmpty) {
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(28.0),
          child: Column(
            children: [
              const Icon(Icons.person_search_outlined, size: 48, color: AppTheme.textSecondary),
              const SizedBox(height: 12),
              const Text(
                'No Verified Doctors Matched',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 6),
              const Text(
                'Try broadening your query, removing the fee limit, or browsing all available doctors.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: () {
                  Navigator.of(context).pushNamed('/patient/find-doctor');
                },
                child: const Text('Browse All Doctors'),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Recommended Doctors (${recs.length})',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.green.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green.shade200),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.verified_rounded, size: 14, color: Colors.green),
                  SizedBox(width: 4),
                  Text('Verified Doctors', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.green)),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: recs.length,
          separatorBuilder: (_, index) => const SizedBox(height: 12),
          itemBuilder: (context, idx) => _buildDoctorCard(recs[idx]),
        ),
      ],
    );
  }

  Widget _buildDoctorCard(DoctorRecommendation rec) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top Row: Avatar, Name, Score Badge
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 26,
                  backgroundColor: AppTheme.primary.withValues(alpha: 0.12),
                  child: Text(
                    rec.fullName.isNotEmpty ? rec.fullName[0].toUpperCase() : 'D',
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primary,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              rec.fullName,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ),
                          const Icon(Icons.verified_rounded, size: 16, color: AppTheme.primary),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          rec.specialty,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.primary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.teal.shade50,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: Colors.teal.shade200),
                  ),
                  child: Text(
                    '${rec.score.toStringAsFixed(0)}% Match',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Colors.teal.shade800,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 12),

            // Metadata Row: Hospital, Experience, Fee
            Wrap(
              spacing: 12,
              runSpacing: 6,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.local_hospital_outlined, size: 14, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(
                      rec.hospitalOrClinic,
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.work_history_outlined, size: 14, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(
                      '${rec.experienceYears} Years Exp.',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.payments_outlined, size: 14, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(
                      'LKR ${rec.consultationFee.toStringAsFixed(0)}',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    ),
                  ],
                ),
              ],
            ),

            // Match Reasons
            if (rec.matchReasons.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceVariant.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Why Recommended:',
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    ),
                    const SizedBox(height: 4),
                    ...rec.matchReasons.map(
                      (r) => Padding(
                        padding: const EdgeInsets.only(bottom: 2),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('• ', style: TextStyle(fontSize: 11, color: AppTheme.primary, fontWeight: FontWeight.bold)),
                            Expanded(
                              child: Text(
                                r,
                                style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary, height: 1.25),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            // Real Available Slots section
            const SizedBox(height: 12),
            if (rec.availableSlots.isNotEmpty) ...[
              Row(
                children: [
                  const Icon(Icons.event_available_rounded, size: 15, color: Colors.green),
                  const SizedBox(width: 4),
                  const Text(
                    'Real Available Slots:',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  const Spacer(),
                  Text(
                    '${rec.availableSlots.length} open',
                    style: const TextStyle(fontSize: 11, color: Colors.green, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              SizedBox(
                height: 38,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: rec.availableSlots.length,
                  separatorBuilder: (_, index) => const SizedBox(width: 6),
                  itemBuilder: (context, sIdx) {
                    final slot = rec.availableSlots[sIdx];
                    return ActionChip(
                      avatar: const Icon(Icons.schedule, size: 14, color: AppTheme.primary),
                      label: Text(
                        '${slot.date} ${slot.startTime}',
                        style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
                      ),
                      backgroundColor: Colors.white,
                      side: BorderSide(color: AppTheme.primary.withValues(alpha: 0.3)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      onPressed: () {
                        // Open existing booking confirmation screen
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => BookingConfirmationScreen(
                              doctor: rec.toDoctor(),
                              date: slot.date,
                              slot: slot.toTimeSlot(),
                            ),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ] else ...[
              Row(
                children: [
                  Icon(Icons.event_busy_rounded, size: 15, color: Colors.grey.shade500),
                  const SizedBox(width: 4),
                  Text(
                    'No open slots on selected date. View profile for upcoming days.',
                    style: TextStyle(fontSize: 11.5, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ],

            const SizedBox(height: 14),

            // Actions: View Profile & Book
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.primary,
                      side: const BorderSide(color: AppTheme.primary),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => DoctorDetailScreen(doctor: rec.toDoctor()),
                        ),
                      );
                    },
                    child: const Text('View Profile', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onPressed: () {
                      if (rec.availableSlots.isNotEmpty) {
                        final firstSlot = rec.availableSlots.first;
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => BookingConfirmationScreen(
                              doctor: rec.toDoctor(),
                              date: firstSlot.date,
                              slot: firstSlot.toTimeSlot(),
                            ),
                          ),
                        );
                      } else {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => DoctorDetailScreen(doctor: rec.toDoctor()),
                          ),
                        );
                      }
                    },
                    child: const Text('Book Slot', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDisclaimerCard() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline_rounded, size: 16, color: Colors.grey.shade600),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _response?.disclaimer ??
                  'MediConnect Doctor Discovery Assistant is an informational matching tool, not a diagnostic or prescribing service.',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade700, height: 1.3),
            ),
          ),
        ],
      ),
    );
  }
}
