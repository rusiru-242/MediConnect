import 'package:flutter/material.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/doctor_review.dart';
import '../../services/review_service.dart';

/// Interactive modal dialog for submitting or editing a verified doctor review.
class SubmitReviewDialog extends StatefulWidget {
  final String appointmentId;
  final String? doctorName;
  final DoctorReview? existingReview;
  final ReviewService? reviewService;

  const SubmitReviewDialog({
    super.key,
    required this.appointmentId,
    this.doctorName,
    this.existingReview,
    this.reviewService,
  });

  static Future<DoctorReview?> show(
    BuildContext context, {
    required String appointmentId,
    String? doctorName,
    DoctorReview? existingReview,
    ReviewService? reviewService,
  }) {
    return showDialog<DoctorReview>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => SubmitReviewDialog(
        appointmentId: appointmentId,
        doctorName: doctorName,
        existingReview: existingReview,
        reviewService: reviewService,
      ),
    );
  }

  @override
  State<SubmitReviewDialog> createState() => _SubmitReviewDialogState();
}

class _SubmitReviewDialogState extends State<SubmitReviewDialog> {
  late final ReviewService _reviewService;
  late final TextEditingController _reviewTextController;

  int _selectedRating = 5;
  bool _isSubmitting = false;
  String? _errorMessage;

  final List<String> _ratingLabels = [
    '',
    'Poor (1/5)',
    'Fair (2/5)',
    'Good (3/5)',
    'Very Good (4/5)',
    'Excellent (5/5)',
  ];

  @override
  void initState() {
    super.initState();
    _reviewService = widget.reviewService ?? ReviewService();
    _selectedRating = widget.existingReview?.rating ?? 5;
    _reviewTextController = TextEditingController(
      text: widget.existingReview?.reviewText ?? '',
    );
  }

  @override
  void dispose() {
    _reviewTextController.dispose();
    super.dispose();
  }

  bool get _isEditing => widget.existingReview != null;

  Future<void> _handleSubmit() async {
    if (_isSubmitting) return;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      DoctorReview result;
      if (_isEditing) {
        result = await _reviewService.updateReview(
          reviewId: widget.existingReview!.reviewId,
          rating: _selectedRating,
          reviewText: _reviewTextController.text.trim(),
        );
      } else {
        result = await _reviewService.submitReview(
          appointmentId: widget.appointmentId,
          rating: _selectedRating,
          reviewText: _reviewTextController.text.trim(),
        );
      }

      if (!mounted) return;
      Navigator.of(context).pop(result);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        if (e is ApiException) {
          _errorMessage = e.message;
        } else {
          _errorMessage = 'Unable to submit review. Please try again.';
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _isEditing ? 'Edit Your Review' : 'Rate & Review Doctor';
    final subtitle = widget.doctorName != null
        ? 'Share your verified experience with ${widget.doctorName}'
        : 'Share your verified appointment experience';

    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.1),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.star_rounded, color: AppTheme.primary, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          subtitle,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppTheme.textSecondary),
                    onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              // Interactive Star Rating Selector
              Container(
                padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceVariant.withValues(alpha: 0.25),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.outline.withValues(alpha: 0.15)),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: List.generate(5, (index) {
                        final starNumber = index + 1;
                        final isSelected = starNumber <= _selectedRating;
                        return InkWell(
                          key: Key('rating_star_$starNumber'),
                          onTap: _isSubmitting
                              ? null
                              : () {
                                  setState(() {
                                    _selectedRating = starNumber;
                                  });
                                },
                          borderRadius: BorderRadius.circular(24),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                            child: Icon(
                              isSelected ? Icons.star_rounded : Icons.star_outline_rounded,
                              size: 38,
                              color: isSelected ? Colors.amber[700] : AppTheme.outline,
                            ),
                          ),
                        );
                      }),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _ratingLabels[_selectedRating],
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Colors.amber[900],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 20),

              // Optional Review Text Area
              TextField(
                key: const Key('review_text_field'),
                controller: _reviewTextController,
                maxLength: 1000,
                maxLines: 4,
                enabled: !_isSubmitting,
                decoration: InputDecoration(
                  labelText: 'Written Review (Optional)',
                  hintText: 'Describe your consultation experience, professionalism, and wait time...',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                  contentPadding: const EdgeInsets.all(16),
                ),
              ),

              const SizedBox(height: 8),

              // Privacy Notice Warning Box
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.blue.withValues(alpha: 0.25)),
                ),
                child: const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.shield_outlined, size: 18, color: Colors.blue),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Privacy Notice: Do not include sensitive medical conditions, diagnoses, or prescriptions. Reviews are public to help verified patients.',
                        style: TextStyle(fontSize: 11, color: Colors.blueGrey, height: 1.35),
                      ),
                    ),
                  ],
                ),
              ),

              if (_errorMessage != null) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.error.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: AppTheme.error, size: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(fontSize: 12, color: AppTheme.error),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              const SizedBox(height: 24),

              // Action Buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('Cancel'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      key: const Key('submit_review_button'),
                      onPressed: _isSubmitting ? null : _handleSubmit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _isSubmitting
                          ? const SizedBox(
                              height: 18,
                              width: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Text(
                              _isEditing ? 'Update Review' : 'Submit Review',
                              style: const TextStyle(fontWeight: FontWeight.bold),
                            ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
