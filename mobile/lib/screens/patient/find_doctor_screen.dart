import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/constants/specialties.dart';
import '../../core/constants/api_constants.dart';
import '../../core/theme/app_theme.dart';
import '../../models/doctor.dart';
import '../../services/doctor_service.dart';
import '../../widgets/medical_widgets.dart';

/// Screen allowing patients to discover, search, and filter approved doctors.
/// Redesigned with Google Stitch Clinical Clarity design system (Phase 41).
class FindDoctorScreen extends StatefulWidget {
  final DoctorService? doctorService;

  const FindDoctorScreen({super.key, this.doctorService});

  @override
  State<FindDoctorScreen> createState() => _FindDoctorScreenState();
}

class _FindDoctorScreenState extends State<FindDoctorScreen> {
  late final DoctorService _doctorService;
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Timer? _debounceTimer;

  List<Doctor> _doctors = [];
  bool _isLoading = false;
  bool _isLoadingMore = false;
  String? _errorMessage;

  int _currentPage = 1;
  int _totalPages = 1;
  final int _limit = 20;

  String _selectedSpecialty = 'All';
  String _activeSearchQuery = '';

  // Quick filter toggles
  bool _filterAvailableToday = false;
  bool _filterTopRated = false;
  bool _filterVideoVisit = false;

  final Set<String> _bookmarkedDoctorIds = {};

  @override
  void initState() {
    super.initState();
    _doctorService = widget.doctorService ?? DoctorService();
    _scrollController.addListener(_onScroll);
    _fetchDoctors(initial: true);
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      if (!_isLoading && !_isLoadingMore && _currentPage < _totalPages) {
        _loadMoreDoctors();
      }
    }
  }

  void _onSearchChanged(String value) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 400), () {
      if (mounted) {
        setState(() {
          _activeSearchQuery = value.trim();
        });
        _fetchDoctors(initial: true);
      }
    });
  }

  void _selectSpecialty(String specialty) {
    if (_selectedSpecialty == specialty) return;
    setState(() {
      _selectedSpecialty = specialty;
    });
    _fetchDoctors(initial: true);
  }

  Future<void> _fetchDoctors({bool initial = false}) async {
    if (initial) {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
        _currentPage = 1;
      });
    }

    try {
      final response = await _doctorService.getDoctors(
        page: 1,
        limit: _limit,
        search: _activeSearchQuery.isNotEmpty ? _activeSearchQuery : null,
        specialty: _selectedSpecialty != 'All' ? _selectedSpecialty : null,
      );

      if (!mounted) return;
      setState(() {
        _doctors = response.items;
        _currentPage = response.page;
        _totalPages = response.totalPages;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to connect to MediConnect. Please try again.';
        _isLoading = false;
      });
    }
  }

  Future<void> _loadMoreDoctors() async {
    setState(() {
      _isLoadingMore = true;
    });

    try {
      final nextPage = _currentPage + 1;
      final response = await _doctorService.getDoctors(
        page: nextPage,
        limit: _limit,
        search: _activeSearchQuery.isNotEmpty ? _activeSearchQuery : null,
        specialty: _selectedSpecialty != 'All' ? _selectedSpecialty : null,
      );

      if (!mounted) return;
      setState(() {
        _doctors.addAll(response.items);
        _currentPage = response.page;
        _totalPages = response.totalPages;
        _isLoadingMore = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isLoadingMore = false;
      });
    }
  }

  String _getSpecialtyEmoji(String specialty) {
    final lower = specialty.toLowerCase();
    if (lower.contains('cardio')) return '🫀';
    if (lower.contains('derm')) return '🧴';
    if (lower.contains('neuro')) return '🧠';
    if (lower.contains('pediat')) return '👶';
    if (lower.contains('ortho')) return '🦴';
    if (lower.contains('eye') || lower.contains('ophthal')) return '👁️';
    if (lower.contains('psych')) return '🧘';
    if (lower.contains('dent')) return '🦷';
    if (lower.contains('oncol')) return '🎗️';
    return '🩺';
  }

  void _toggleBookmark(String doctorId) {
    setState(() {
      if (_bookmarkedDoctorIds.contains(doctorId)) {
        _bookmarkedDoctorIds.remove(doctorId);
      } else {
        _bookmarkedDoctorIds.add(doctorId);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 1,
        title: const Text(
          'Doctor Directory',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: AppTheme.textPrimary,
          ),
        ),
        actions: [
          // Preserved for automated integration & screen tests
          IconButton(
            key: const Key('find_doctor_ai_health_chat_icon_button'),
            icon: const Icon(
              Icons.health_and_safety_rounded,
              color: AppTheme.primaryBlue,
            ),
            tooltip: 'AI Health Assistant',
            onPressed: () {
              Navigator.of(context).pushNamed('/patient/ai-health-chat');
            },
          ),
          IconButton(
            key: const Key('find_doctor_ai_booking_icon_button'),
            icon: const Icon(
              Icons.chat_bubble_outline_rounded,
              color: AppTheme.primaryBlue,
            ),
            tooltip: 'AI Booking Assistant',
            onPressed: () {
              Navigator.of(context).pushNamed('/patient/ai-booking');
            },
          ),
          IconButton(
            key: const Key('find_doctor_ai_assistant_icon_button'),
            icon: const Icon(Icons.auto_awesome_rounded, color: Colors.amber),
            tooltip: 'AI Doctor Finder',
            onPressed: () {
              Navigator.of(context).pushNamed('/patient/ai-assistant');
            },
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 1. Search Bar & Filter Action Row
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Container(
                      height: 48,
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceContainerLow,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.border),
                      ),
                      child: TextField(
                        key: const Key('find_doctor_search_field'),
                        controller: _searchController,
                        onChanged: _onSearchChanged,
                        decoration: InputDecoration(
                          hintText: 'Search doctor, specialty, hospital...',
                          hintStyle: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.textMuted,
                          ),
                          prefixIcon: const Icon(
                            Icons.search_rounded,
                            color: AppTheme.textMuted,
                            size: 20,
                          ),
                          suffixIcon: _searchController.text.isNotEmpty
                              ? IconButton(
                                  icon: const Icon(
                                    Icons.close_rounded,
                                    size: 18,
                                    color: AppTheme.textSecondary,
                                  ),
                                  onPressed: () {
                                    _searchController.clear();
                                    _onSearchChanged('');
                                  },
                                )
                              : null,
                          filled: false,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 12,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: IconButton(
                      icon: const Icon(
                        Icons.tune_rounded,
                        color: AppTheme.primaryBlue,
                        size: 22,
                      ),
                      tooltip: 'Filter Options',
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Filter options: Use specialty carousel & toggles below.',
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),

            // 2. Specialty Quick Filter Carousel
            SizedBox(
              height: 44,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 14),
                children: [
                  _buildSpecialtyChip('All'),
                  ...Specialties.list.map((s) => _buildSpecialtyChip(s)),
                ],
              ),
            ),
            const SizedBox(height: 6),

            // 3. Secondary Quick Toggles Bar
            SizedBox(
              height: 36,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 14),
                children: [
                  _buildQuickToggle(
                    label: 'Available Today',
                    isActive: _filterAvailableToday,
                    leadingDot: AppTheme.success,
                    onTap: () {
                      setState(
                        () => _filterAvailableToday = !_filterAvailableToday,
                      );
                    },
                  ),
                  _buildQuickToggle(
                    label: 'Top Rated 4.5+',
                    isActive: _filterTopRated,
                    icon: Icons.star_rounded,
                    iconColor: Colors.amber,
                    onTap: () {
                      setState(() => _filterTopRated = !_filterTopRated);
                    },
                  ),
                  _buildQuickToggle(
                    label: 'Video Visit',
                    isActive: _filterVideoVisit,
                    icon: Icons.videocam_rounded,
                    iconColor: AppTheme.secondaryBlue,
                    onTap: () {
                      setState(() => _filterVideoVisit = !_filterVideoVisit);
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),

            // 4. Results Count & Sort Context Bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Text(
                        _selectedSpecialty == 'All'
                            ? 'All Specialists'
                            : _selectedSpecialty,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceContainerLow,
                          borderRadius: BorderRadius.circular(9999),
                        ),
                        child: Text(
                          '${_doctors.length} found',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.primaryBlue,
                          ),
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: const [
                      Text(
                        'Sorted: ',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      Text(
                        'Recommended',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.primaryBlue,
                        ),
                      ),
                      Icon(
                        Icons.expand_more_rounded,
                        size: 16,
                        color: AppTheme.primaryBlue,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 4),

            // 5. Doctor List Content
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickToggle({
    required String label,
    required bool isActive,
    Color? leadingDot,
    IconData? icon,
    Color? iconColor,
    required VoidCallback onTap,
  }) {
    return Padding(
      padding: const EdgeInsets.only(right: 8.0),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: isActive ? AppTheme.primaryContainer : Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isActive ? AppTheme.primaryBlue : AppTheme.border,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (leadingDot != null) ...[
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: leadingDot,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
              ],
              if (icon != null) ...[
                Icon(icon, size: 14, color: iconColor ?? AppTheme.primaryBlue),
                const SizedBox(width: 4),
              ],
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                  color: isActive ? AppTheme.primaryBlue : AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSpecialtyChip(String specialty) {
    final isSelected = _selectedSpecialty == specialty;
    final emoji = specialty == 'All' ? '🌟' : _getSpecialtyEmoji(specialty);

    return Padding(
      padding: const EdgeInsets.only(right: 8.0),
      child: InkWell(
        key: Key('specialty_chip_$specialty'),
        onTap: () => _selectSpecialty(specialty),
        borderRadius: BorderRadius.circular(9999),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: isSelected
                ? AppTheme.primaryBlue
                : AppTheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(9999),
            border: Border.all(
              color: isSelected ? AppTheme.primaryBlue : AppTheme.border,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(emoji, style: const TextStyle(fontSize: 13)),
              const SizedBox(width: 6),
              Text(
                specialty,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppTheme.textPrimary,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_rounded,
                size: 54,
                color: AppTheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 15,
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: () async {
                  await ApiConstants.autoDetectBaseUrl(force: true);
                  _fetchDoctors(initial: true);
                },
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Try Again'),
              ),
            ],
          ),
        ),
      );
    }

    if (_doctors.isEmpty) {
      final isFiltered =
          _activeSearchQuery.isNotEmpty || _selectedSpecialty != 'All';
      final emptyText = isFiltered
          ? 'No doctors match your search.'
          : 'No doctors found.';

      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.person_search_rounded,
                size: 56,
                color: AppTheme.textSecondary.withValues(alpha: 0.6),
              ),
              const SizedBox(height: 16),
              Text(
                emptyText,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => _fetchDoctors(initial: true),
      child: ListView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
        itemCount: _doctors.length + (_isLoadingMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == _doctors.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            );
          }

          final doctor = _doctors[index];
          return _buildDoctorCard(doctor);
        },
      ),
    );
  }

  Widget _buildDoctorCard(Doctor doctor) {
    final isBookmarked = _bookmarkedDoctorIds.contains(doctor.doctorId);

    return StitchCard(
      key: Key('doctor_card_${doctor.doctorId}'),
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Avatar with verified badge
              Stack(
                clipBehavior: Clip.none,
                children: [
                  Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      color: AppTheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppTheme.border),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      doctor.fullName.isNotEmpty
                          ? doctor.fullName
                                .replaceFirst('Dr. ', '')
                                .split(' ')
                                .map((n) => n.isNotEmpty ? n[0] : '')
                                .take(2)
                                .join()
                          : 'DR',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                  ),
                  Positioned(
                    bottom: -3,
                    right: -3,
                    child: Container(
                      width: 18,
                      height: 18,
                      decoration: const BoxDecoration(
                        color: AppTheme.primaryBlue,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.verified_rounded,
                        color: Colors.white,
                        size: 12,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 14),

              // Doctor Info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            doctor.fullName,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textPrimary,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        InkWell(
                          onTap: () => _toggleBookmark(doctor.doctorId),
                          child: Icon(
                            isBookmarked
                                ? Icons.favorite_rounded
                                : Icons.favorite_border_rounded,
                            size: 20,
                            color: isBookmarked
                                ? AppTheme.error
                                : AppTheme.textMuted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      doctor.specialty,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.secondaryBlue,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${doctor.hospitalOrClinic.isNotEmpty ? doctor.hospitalOrClinic : "General Hospital"} • ${doctor.experienceYears} yrs exp',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(9999),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.location_on_outlined,
                                size: 12,
                                color: AppTheme.textMuted,
                              ),
                              SizedBox(width: 2),
                              Text(
                                'Nearby',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Row(
                          children: const [
                            Icon(
                              Icons.star_rounded,
                              size: 15,
                              color: Colors.amber,
                            ),
                            SizedBox(width: 2),
                            Text(
                              '4.9',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            SizedBox(width: 2),
                            Text(
                              '(120+)',
                              style: TextStyle(
                                fontSize: 10,
                                color: AppTheme.textMuted,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Metadata Slot (Next slot & Consultation Fee)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppTheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Container(
                      width: 26,
                      height: 26,
                      decoration: BoxDecoration(
                        color: AppTheme.successContainer,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Icon(
                        Icons.schedule_rounded,
                        size: 16,
                        color: AppTheme.success,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: const [
                        Text(
                          'Next Slot',
                          style: TextStyle(
                            fontSize: 10,
                            color: AppTheme.textMuted,
                          ),
                        ),
                        Text(
                          'Today, 2:00 PM',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    const Text(
                      'Consultation',
                      style: TextStyle(fontSize: 10, color: AppTheme.textMuted),
                    ),
                    Text(
                      doctor.consultationFee > 0
                          ? 'Rs. ${doctor.consultationFee.toInt()}'
                          : 'Rs. 2,500',
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

          // Actions
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: AppTheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: IconButton(
                  icon: const Icon(
                    Icons.videocam_rounded,
                    size: 20,
                    color: AppTheme.primaryBlue,
                  ),
                  tooltip: 'Video Consultation',
                  onPressed: () {
                    Navigator.of(context)
                        .pushNamed('/patient/doctor-detail', arguments: doctor);
                  },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ElevatedButton(
                  key: Key('view_profile_button_${doctor.doctorId}'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    minimumSize: const Size(0, 42),
                  ),
                  onPressed: () {
                    Navigator.of(context)
                        .pushNamed('/patient/doctor-detail', arguments: doctor);
                  },
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'Book Now',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      SizedBox(width: 6),
                      Icon(Icons.arrow_forward_rounded, size: 16),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
