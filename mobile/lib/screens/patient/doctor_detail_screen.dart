import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/doctor.dart';
import '../../models/doctor_availability.dart';
import '../../models/doctor_review.dart';
import '../../services/doctor_service.dart';
import '../../services/review_service.dart';
import 'booking_confirmation_screen.dart';

/// Screen displaying public doctor details and patient-facing availability slots.
class DoctorDetailScreen extends StatefulWidget {
  final Doctor? doctor;
  final String? doctorId;
  final DoctorService? doctorService;
  final ReviewService? reviewService;

  const DoctorDetailScreen({
    super.key,
    this.doctor,
    this.doctorId,
    this.doctorService,
    this.reviewService,
  });

  @override
  State<DoctorDetailScreen> createState() => _DoctorDetailScreenState();
}

class _DoctorDetailScreenState extends State<DoctorDetailScreen> {
  late final DoctorService _doctorService;
  late final ReviewService _reviewService;
  Doctor? _doctor;
  String? _effectiveDoctorId;

  bool _isLoadingDoctor = false;
  String? _doctorError;

  bool _isLoadingAvailability = false;
  String? _availabilityError;
  List<DayAvailabilitySlots> _dayAvailabilities = [];

  bool _isLoadingReviews = false;
  DoctorRatingSummary? _ratingSummary;
  List<DoctorReview> _reviews = [];

  String? _selectedDate;
  String? _selectedSlotStartTime;

  @override
  void initState() {
    super.initState();
    _doctorService = widget.doctorService ?? DoctorService();
    _reviewService = widget.reviewService ?? ReviewService();
    _doctor = widget.doctor;
    _effectiveDoctorId = widget.doctor?.doctorId ?? widget.doctorId;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_doctor == null && _effectiveDoctorId == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Doctor) {
        _doctor = args;
        _effectiveDoctorId = args.doctorId;
      } else if (args is Map<String, dynamic> && args.containsKey('doctorId')) {
        _effectiveDoctorId = args['doctorId'].toString();
      } else if (args is String) {
        _effectiveDoctorId = args;
      }
    }

    if (_doctor == null && _effectiveDoctorId != null && !_isLoadingDoctor) {
      _loadDoctorDetail();
    } else if (_doctor != null && _dayAvailabilities.isEmpty && !_isLoadingAvailability) {
      _loadAvailability();
      _loadReviews();
    }
  }

  Future<void> _loadDoctorDetail() async {
    if (_effectiveDoctorId == null) return;
    setState(() {
      _isLoadingDoctor = true;
      _doctorError = null;
    });

    try {
      final doc = await _doctorService.getDoctorDetail(_effectiveDoctorId!);
      if (!mounted) return;
      setState(() {
        _doctor = doc;
        _isLoadingDoctor = false;
      });
      _loadAvailability();
      _loadReviews();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _doctorError = 'Unable to connect to MediConnect. Please try again.';
        _isLoadingDoctor = false;
      });
    }
  }

  Future<void> _loadReviews() async {
    final docId = _doctor?.doctorId ?? _effectiveDoctorId;
    if (docId == null) return;

    setState(() {
      _isLoadingReviews = true;
    });

    try {
      final summary = await _reviewService.getDoctorRatingSummary(docId);
      final page = await _reviewService.getDoctorReviews(docId, page: 1, pageSize: 20);
      if (!mounted) return;
      setState(() {
        _ratingSummary = summary;
        _reviews = page.items;
        _isLoadingReviews = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isLoadingReviews = false;
      });
    }
  }

  Future<void> _loadAvailability() async {
    final docId = _doctor?.doctorId ?? _effectiveDoctorId;
    if (docId == null) return;

    setState(() {
      _isLoadingAvailability = true;
      _availabilityError = null;
    });

    try {
      final slots = await _doctorService.getDoctorAvailability(docId);
      if (!mounted) return;
      setState(() {
        _dayAvailabilities = slots;
        _isLoadingAvailability = false;
        if (_dayAvailabilities.isNotEmpty) {
          _selectedDate = _dayAvailabilities.first.date;
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _availabilityError = 'Unable to connect to MediConnect. Please try again.';
        _isLoadingAvailability = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Doctor Profile'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoadingDoctor) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_doctorError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 54, color: AppTheme.error),
              const SizedBox(height: 16),
              Text(
                _doctorError!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppTheme.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _loadDoctorDetail,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final doctor = _doctor;
    if (doctor == null) {
      return const Center(child: Text('Doctor not found.'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Doctor Header Card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            elevation: 1,
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 40,
                    backgroundColor: AppTheme.primaryContainer,
                    child: Text(
                      doctor.fullName.isNotEmpty
                          ? doctor.fullName.replaceFirst('Dr. ', '').split(' ').map((n) => n.isNotEmpty ? n[0] : '').take(2).join()
                          : 'DR',
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    doctor.fullName,
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    doctor.specialty,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.primary),
                  ),
                  const SizedBox(height: 10),
                  // Verified Doctor Indicator
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.success.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.success.withValues(alpha: 0.3)),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.verified_rounded, size: 16, color: AppTheme.success),
                        SizedBox(width: 6),
                        Text(
                          'Verified Doctor',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.success),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Qualifications & Practice Details
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            elevation: 1,
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Professional Details', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 14),
                  if (doctor.qualifications != null && doctor.qualifications!.isNotEmpty) ...[
                    _buildDetailRow(Icons.school_outlined, 'Qualifications', doctor.qualifications!),
                    const Divider(height: 20),
                  ],
                  _buildDetailRow(Icons.local_hospital_outlined, 'Hospital / Clinic', doctor.hospitalOrClinic),
                  const Divider(height: 20),
                  _buildDetailRow(Icons.work_history_outlined, 'Experience', '${doctor.experienceYears} Years'),
                  const Divider(height: 20),
                  _buildDetailRow(
                    Icons.payments_outlined,
                    'Consultation Fee',
                    'LKR ${doctor.consultationFee.toStringAsFixed(2)}',
                  ),
                  if (doctor.bio != null && doctor.bio!.isNotEmpty) ...[
                    const Divider(height: 20),
                    _buildDetailRow(Icons.info_outline, 'About', doctor.bio!),
                  ],
                ],
              ),
            ),
          ),

          const SizedBox(height: 20),

          // Availability Section
          const Text(
            'Available Dates & Times',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 12),

          _buildAvailabilitySection(),

          const SizedBox(height: 24),

          // Verified Reviews & Ratings Section (Phase 23)
          _buildReviewsAndRatingsSection(),
        ],
      ),
    );
  }

  Widget _buildDetailRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: AppTheme.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: AppTheme.textPrimary)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAvailabilitySection() {
    if (_isLoadingAvailability) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(32.0),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (_availabilityError != null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            children: [
              Text(_availabilityError!, style: const TextStyle(color: AppTheme.textSecondary)),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                onPressed: _loadAvailability,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_dayAvailabilities.isEmpty) {
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: const Padding(
          padding: EdgeInsets.all(24.0),
          child: Center(
            child: Column(
              children: [
                Icon(Icons.event_busy_rounded, size: 48, color: AppTheme.textSecondary),
                SizedBox(height: 12),
                Text(
                  'No available time slots currently.',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final selectedDay = _dayAvailabilities.firstWhere(
      (d) => d.date == _selectedDate,
      orElse: () => _dayAvailabilities.first,
    );

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Select Date',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 10),

            // Available Dates Selector
            SizedBox(
              height: 48,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _dayAvailabilities.length,
                itemBuilder: (context, index) {
                  final day = _dayAvailabilities[index];
                  final isSelected = day.date == _selectedDate;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8.0),
                    child: ChoiceChip(
                      key: Key('date_chip_${day.date}'),
                      selected: isSelected,
                      label: Text(
                        day.date,
                        style: TextStyle(
                          color: isSelected ? Colors.white : AppTheme.textPrimary,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                      selectedColor: AppTheme.primary,
                      backgroundColor: Colors.white,
                      onSelected: (selected) {
                        if (selected) {
                          setState(() {
                            _selectedDate = day.date;
                            _selectedSlotStartTime = null;
                          });
                        }
                      },
                    ),
                  );
                },
              ),
            ),

            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 10),

            Text(
              'Available Slots for ${selectedDay.date}',
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 12),

            // Time Slots Wrap
            if (selectedDay.slots.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Text('No slots remaining on this date.', style: TextStyle(color: AppTheme.textSecondary)),
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: selectedDay.slots.map((slot) {
                  final isSelected = _selectedSlotStartTime == slot.startTime;
                  return ChoiceChip(
                    key: Key('slot_chip_${slot.startTime}'),
                    selected: isSelected,
                    label: Text(
                      '${slot.startTime} - ${slot.endTime}',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                        color: isSelected ? Colors.white : AppTheme.textPrimary,
                      ),
                    ),
                    selectedColor: AppTheme.primary,
                    backgroundColor: AppTheme.surfaceVariant.withValues(alpha: 0.4),
                    side: BorderSide(
                      color: isSelected ? AppTheme.primary : AppTheme.outline.withValues(alpha: 0.3),
                    ),
                    onSelected: (selected) {
                      setState(() {
                        _selectedSlotStartTime = selected ? slot.startTime : null;
                      });
                    },
                  );
                }).toList(),
              ),

            const SizedBox(height: 20),

            // Functional Booking Action Button
            Builder(
              builder: (context) {
                TimeSlot? selectedSlot;
                if (_selectedSlotStartTime != null) {
                  try {
                    selectedSlot = selectedDay.slots.firstWhere(
                      (s) => s.startTime == _selectedSlotStartTime,
                    );
                  } catch (_) {}
                }

                final isEnabled = _selectedSlotStartTime != null &&
                    _doctor != null &&
                    selectedSlot != null;

                return SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    key: const Key('book_appointment_button'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isEnabled
                          ? AppTheme.primary
                          : AppTheme.outline.withValues(alpha: 0.3),
                      foregroundColor: isEnabled
                          ? Colors.white
                          : AppTheme.textSecondary,
                      elevation: isEnabled ? 2 : 0,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: isEnabled
                        ? () async {
                            final shouldRefresh = await Navigator.push<bool>(
                              context,
                              MaterialPageRoute(
                                builder: (_) => BookingConfirmationScreen(
                                  doctor: _doctor!,
                                  date: selectedDay.date,
                                  slot: selectedSlot!,
                                ),
                              ),
                            );
                            if (shouldRefresh == true) {
                              setState(() {
                                _selectedSlotStartTime = null;
                              });
                              _loadAvailability();
                            }
                          }
                        : null,
                    child: Text(
                      _selectedSlotStartTime != null
                          ? 'Continue to Booking ($_selectedSlotStartTime)'
                          : 'Select a Time Slot',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildReviewsAndRatingsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.rate_review_outlined, color: AppTheme.primary, size: 22),
            SizedBox(width: 8),
            Text(
              'Patient Reviews & Ratings',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
          ],
        ),
        const SizedBox(height: 12),
        _buildRatingSummaryCard(),
        const SizedBox(height: 16),
        if (_reviews.isNotEmpty) ...[
          const Text(
            'Verified Patient Feedback',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 10),
          ..._reviews.map((r) => _buildReviewCard(r)),
        ],
      ],
    );
  }

  Widget _buildRatingSummaryCard() {
    if (_isLoadingReviews) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(24.0),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    if (_ratingSummary == null || !_ratingSummary!.hasReviews) {
      return Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 1,
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.amber.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.star_outline_rounded, color: Colors.amber, size: 30),
              ),
              const SizedBox(width: 16),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'No reviews yet',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Reviews appear after verified patients complete their scheduled appointments.',
                      style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.3),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    }

    final summary = _ratingSummary!;
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Overall Rating Column
            Expanded(
              flex: 4,
              child: Column(
                children: [
                  Text(
                    summary.averageRating?.toStringAsFixed(1) ?? '0.0',
                    style: const TextStyle(fontSize: 38, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(5, (i) {
                      final starValue = i + 1;
                      final rating = summary.averageRating ?? 0.0;
                      return Icon(
                        rating >= starValue
                            ? Icons.star_rounded
                            : (rating >= starValue - 0.5 ? Icons.star_half_rounded : Icons.star_outline_rounded),
                        color: Colors.amber[700],
                        size: 18,
                      );
                    }),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '${summary.totalReviews} verified review${summary.totalReviews > 1 ? "s" : ""}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),
            // Breakdown bars (5 down to 1)
            Expanded(
              flex: 6,
              child: Column(
                children: [5, 4, 3, 2, 1].map((star) {
                  final pct = summary.getStarPercentage(star);
                  final count = summary.ratingDistribution[star.toString()] ?? 0;
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      children: [
                        Text('$star', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                        const SizedBox(width: 4),
                        const Icon(Icons.star_rounded, size: 12, color: Colors.amber),
                        const SizedBox(width: 6),
                        Expanded(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: pct,
                              minHeight: 6,
                              backgroundColor: AppTheme.outline.withValues(alpha: 0.15),
                              valueColor: AlwaysStoppedAnimation<Color>(Colors.amber[700]!),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 20,
                          child: Text(
                            '$count',
                            textAlign: TextAlign.right,
                            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildReviewCard(DoctorReview review) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      elevation: 0.5,
      color: AppTheme.surfaceVariant.withValues(alpha: 0.2),
      child: Padding(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: AppTheme.primary.withValues(alpha: 0.12),
                  child: const Icon(Icons.person, size: 16, color: AppTheme.primary),
                ),
                const SizedBox(width: 8),
                Text(
                  review.patientDisplayName,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.success.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.check_circle_rounded, size: 12, color: AppTheme.success),
                      SizedBox(width: 3),
                      Text('Verified', style: TextStyle(fontSize: 10, color: AppTheme.success, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
                const Spacer(),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: List.generate(5, (i) {
                    return Icon(
                      i < review.rating ? Icons.star_rounded : Icons.star_outline_rounded,
                      size: 16,
                      color: Colors.amber[700],
                    );
                  }),
                ),
              ],
            ),
            if (review.reviewText != null && review.reviewText!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                review.reviewText!,
                style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary, height: 1.35),
              ),
            ],
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                InkWell(
                  onTap: () => _promptReportReview(review.reviewId),
                  child: const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.flag_outlined, size: 13, color: AppTheme.textSecondary),
                        SizedBox(width: 4),
                        Text('Report', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _promptReportReview(String reviewId) async {
    final reasonController = TextEditingController();
    final reported = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Report Review'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Please provide a reason why this review violates guidelines:',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: reasonController,
              maxLength: 500,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: 'Enter reason...',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              if (reasonController.text.trim().length >= 5) {
                Navigator.of(ctx).pop(true);
              }
            },
            child: const Text('Report'),
          ),
        ],
      ),
    );

    if (reported == true && mounted) {
      try {
        await _reviewService.reportReview(
          reviewId: reviewId,
          reason: reasonController.text.trim(),
        );
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Review reported for administrative moderation.'),
            backgroundColor: AppTheme.success,
          ),
        );
      } catch (e) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Failed to report review.'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }
}
