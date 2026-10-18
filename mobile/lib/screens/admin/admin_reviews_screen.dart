import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/doctor_review.dart';
import '../../services/review_service.dart';

/// Screen for administrators to review and moderate reported patient feedback (Phase 26).
class AdminReviewsScreen extends StatefulWidget {
  final ReviewService? reviewService;

  const AdminReviewsScreen({
    super.key,
    this.reviewService,
  });

  @override
  State<AdminReviewsScreen> createState() => _AdminReviewsScreenState();
}

class _AdminReviewsScreenState extends State<AdminReviewsScreen> {
  late final ReviewService _reviewService;
  List<AdminReportedReviewItem> _reviews = [];
  bool _isLoading = true;
  String? _errorMessage;
  String _selectedFilter = 'ALL'; // ALL, REPORTED, HIDDEN

  @override
  void initState() {
    super.initState();
    _reviewService = widget.reviewService ?? ReviewService();
    _loadReportedReviews();
  }

  Future<void> _loadReportedReviews() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final items = await _reviewService.getReportedReviews(pageSize: 50);
      if (mounted) {
        setState(() {
          _reviews = items;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Failed to load reported reviews. Please check connection.';
        });
      }
    }
  }

  Future<void> _moderateReview(String reviewId, String action, {String? reason}) async {
    try {
      await _reviewService.moderateReview(
        reviewId: reviewId,
        action: action,
        reason: reason,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(action == 'HIDE' ? 'Review hidden from public view.' : 'Review restored.'),
            backgroundColor: action == 'HIDE' ? AppTheme.error : AppTheme.success,
          ),
        );
      }
      _loadReportedReviews();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Moderation action failed: ${e.toString().replaceAll("Exception: ", "")}'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }

  List<AdminReportedReviewItem> get _filteredReviews {
    if (_selectedFilter == 'ALL') return _reviews;
    return _reviews.where((r) => r.status.toUpperCase() == _selectedFilter).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Review Moderation'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Filter chips
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
              child: Row(
                children: [
                  _buildFilterChip('ALL', 'All Reported'),
                  const SizedBox(width: 8),
                  _buildFilterChip('REPORTED', 'Pending Decision'),
                  const SizedBox(width: 8),
                  _buildFilterChip('HIDDEN', 'Hidden'),
                ],
              ),
            ),
            Expanded(
              child: _buildBody(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String filterKey, String label) {
    final isSelected = _selectedFilter == filterKey;
    return FilterChip(
      selected: isSelected,
      label: Text(label),
      selectedColor: AppTheme.primaryContainer,
      labelStyle: TextStyle(
        color: isSelected ? AppTheme.primary : AppTheme.textSecondary,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
        fontSize: 13,
      ),
      onSelected: (_) {
        setState(() {
          _selectedFilter = filterKey;
        });
      },
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
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadReportedReviews,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final displayList = _filteredReviews;

    if (displayList.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.rate_review_outlined, size: 56, color: Colors.grey.shade400),
              const SizedBox(height: 16),
              const Text(
                'No reported reviews found',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 8),
              Text(
                'All verified doctor reviews are currently in good standing.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadReportedReviews,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: displayList.length,
        separatorBuilder: (context, index) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final review = displayList[index];
          return _buildReviewCard(review);
        },
      ),
    );
  }

  Widget _buildReviewCard(AdminReportedReviewItem review) {
    final isHidden = review.status.toUpperCase() == 'HIDDEN';

    return Card(
      key: Key('reported_review_card_${review.reviewId}'),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // Star Rating
                Row(
                  children: List.generate(
                    5,
                    (i) => Icon(
                      i < review.rating ? Icons.star_rounded : Icons.star_border_rounded,
                      size: 18,
                      color: Colors.amber.shade700,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${review.rating}/5',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                const Spacer(),
                // Status badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isHidden ? AppTheme.errorContainer : Colors.amber.shade100,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    review.status.toUpperCase(),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: isHidden ? AppTheme.error : Colors.amber.shade900,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            // Review Text
            if (review.reviewText != null && review.reviewText!.isNotEmpty)
              Text(
                '"${review.reviewText}"',
                style: const TextStyle(
                  fontSize: 14,
                  fontStyle: FontStyle.italic,
                  color: AppTheme.textPrimary,
                  height: 1.4,
                ),
              ),
            const SizedBox(height: 12),
            // Doctor and Reviewer info
            Row(
              children: [
                const Icon(Icons.person_outline, size: 16, color: AppTheme.textSecondary),
                const SizedBox(width: 4),
                Text(
                  'Patient: ${review.patientDisplayName ?? "Verified Patient"}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                const SizedBox(width: 16),
                const Icon(Icons.medical_services_outlined, size: 16, color: AppTheme.primary),
                const SizedBox(width: 4),
                Text(
                  review.doctorName ?? 'Doctor: ${review.doctorUserId}',
                  style: const TextStyle(fontSize: 12, color: AppTheme.primary, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            // Report Reason Box
            if (review.reportReason != null && review.reportReason!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red.shade200),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.report_problem_rounded, size: 16, color: Colors.red.shade700),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Report reason: ${review.reportReason}',
                        style: TextStyle(fontSize: 12, color: Colors.red.shade900, fontWeight: FontWeight.w500),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 14),
            // Actions
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                if (!isHidden)
                  ElevatedButton.icon(
                    key: Key('hide_review_button_${review.reviewId}'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.error,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    ),
                    icon: const Icon(Icons.visibility_off_rounded, size: 16),
                    label: const Text('Hide Review'),
                    onPressed: () => _moderateReview(review.reviewId, 'HIDE'),
                  )
                else
                  ElevatedButton.icon(
                    key: Key('restore_review_button_${review.reviewId}'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.success,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    ),
                    icon: const Icon(Icons.visibility_rounded, size: 16),
                    label: const Text('Restore Review'),
                    onPressed: () => _moderateReview(review.reviewId, 'RESTORE'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
