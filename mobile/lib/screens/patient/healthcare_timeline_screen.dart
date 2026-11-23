import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/timeline.dart';
import '../../services/patient_timeline_service.dart';
import 'appointment_detail_screen.dart';
import 'medical_record_detail_screen.dart';
import 'patient_care_plans_screen.dart';
import 'patient_visit_detail_screen.dart';
import 'prescription_detail_screen.dart';

/// Patient Healthcare Timeline & Visit History Screen (Phase 58).
class HealthcareTimelineScreen extends StatefulWidget {
  final PatientTimelineService? timelineService;

  const HealthcareTimelineScreen({
    super.key,
    this.timelineService,
  });

  @override
  State<HealthcareTimelineScreen> createState() => _HealthcareTimelineScreenState();
}

class _HealthcareTimelineScreenState extends State<HealthcareTimelineScreen> {
  late final PatientTimelineService _timelineService;

  String _selectedCategory = 'ALL';
  List<TimelineEvent> _events = [];
  TimelineSummary? _summary;
  String? _nextCursor;
  bool _hasMore = false;

  bool _isLoadingInitial = true;
  bool _isLoadingMore = false;
  String? _errorMessage;

  final ScrollController _scrollController = ScrollController();

  static const List<Map<String, String>> _categories = [
    {'id': 'ALL', 'label': 'All Activity'},
    {'id': 'APPOINTMENTS', 'label': 'Appointments'},
    {'id': 'CONSULTATIONS', 'label': 'Consultations'},
    {'id': 'PRESCRIPTIONS', 'label': 'Prescriptions'},
    {'id': 'MEDICAL_RECORDS', 'label': 'Medical Records'},
    {'id': 'FOLLOW_UPS', 'label': 'Follow-ups'},
  ];

  @override
  void initState() {
    super.initState();
    _timelineService = widget.timelineService ?? PatientTimelineService();
    _scrollController.addListener(_onScroll);
    _loadInitialData();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      if (!_isLoadingMore && _hasMore && _nextCursor != null) {
        _loadMoreEvents();
      }
    }
  }

  Future<void> _loadInitialData() async {
    setState(() {
      _isLoadingInitial = true;
      _errorMessage = null;
    });

    try {
      final futures = await Future.wait([
        _timelineService.getHealthcareTimeline(
          category: _selectedCategory,
          limit: 20,
        ),
        _timelineService.getHealthcareTimelineSummary(),
      ]);

      final timelineRes = futures[0] as TimelineResponse;
      final summaryRes = futures[1] as TimelineSummary;

      if (!mounted) return;
      setState(() {
        _events = timelineRes.events;
        _nextCursor = timelineRes.nextCursor;
        _hasMore = timelineRes.hasMore;
        _summary = summaryRes;
        _isLoadingInitial = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e.toString().replaceAll("Exception:", "").trim();
        _isLoadingInitial = false;
      });
    }
  }

  Future<void> _filterCategory(String category) async {
    if (_selectedCategory == category && !_isLoadingInitial) return;
    setState(() {
      _selectedCategory = category;
      _isLoadingInitial = true;
      _errorMessage = null;
    });

    try {
      final timelineRes = await _timelineService.getHealthcareTimeline(
        category: category,
        limit: 20,
      );
      if (!mounted) return;
      setState(() {
        _events = timelineRes.events;
        _nextCursor = timelineRes.nextCursor;
        _hasMore = timelineRes.hasMore;
        _isLoadingInitial = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e.toString().replaceAll("Exception:", "").trim();
        _isLoadingInitial = false;
      });
    }
  }

  Future<void> _loadMoreEvents() async {
    if (_isLoadingMore || !_hasMore || _nextCursor == null) return;
    setState(() => _isLoadingMore = true);

    try {
      final timelineRes = await _timelineService.getHealthcareTimeline(
        category: _selectedCategory,
        cursor: _nextCursor,
        limit: 20,
      );

      if (!mounted) return;
      setState(() {
        // Avoid duplicate events when appending
        final existingIds = _events.map((e) => e.eventId).toSet();
        final newItems = timelineRes.events.where((e) => !existingIds.contains(e.eventId)).toList();
        _events.addAll(newItems);
        _nextCursor = timelineRes.nextCursor;
        _hasMore = timelineRes.hasMore;
        _isLoadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0D1B2A);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FC),
      appBar: AppBar(
        title: const Text(
          'Healthcare Timeline',
          style: TextStyle(fontWeight: FontWeight.bold, color: navy),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: navy),
        actions: [
          IconButton(
            key: const Key('timeline_refresh_button'),
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _loadInitialData,
          ),
        ],
      ),
      body: Column(
        children: [
          // 1. Category Filter Selector Bar
          _buildCategoryFilterBar(),

          // 2. Main Content Area
          Expanded(
            child: _isLoadingInitial
                ? const Center(child: CircularProgressIndicator())
                : _errorMessage != null
                    ? _buildErrorView()
                    : RefreshIndicator(
                        onRefresh: _loadInitialData,
                        child: ListView(
                          controller: _scrollController,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          children: [
                            // Summary Metrics Hero Card
                            if (_summary != null) _buildSummaryMetricsCard(),
                            const SizedBox(height: 16),

                            // Timeline Content or Empty State
                            if (_events.isEmpty)
                              _buildEmptyState()
                            else
                              ..._buildGroupedTimelineWidgets(),

                            // Pagination indicator
                            if (_isLoadingMore)
                              const Padding(
                                padding: EdgeInsets.symmetric(vertical: 16),
                                child: Center(child: CircularProgressIndicator()),
                              ),
                            if (_hasMore && !_isLoadingMore)
                              Padding(
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                child: Center(
                                  child: OutlinedButton(
                                    key: const Key('timeline_load_more_button'),
                                    onPressed: _loadMoreEvents,
                                    child: const Text('Load More Events'),
                                  ),
                                ),
                              ),
                            const SizedBox(height: 24),
                          ],
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryFilterBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(
          children: _categories.map((c) {
            final isSelected = _selectedCategory == c['id'];
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: ChoiceChip(
                key: Key('category_chip_${c['id']}'),
                label: Text(
                  c['label']!,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                    color: isSelected ? Colors.white : const Color(0xFF0D1B2A),
                  ),
                ),
                selected: isSelected,
                selectedColor: const Color(0xFF1565C0),
                backgroundColor: const Color(0xFFF0F4F8),
                onSelected: (selected) {
                  if (selected) _filterCategory(c['id']!);
                },
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildSummaryMetricsCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1565C0), Color(0xFF1976D2)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF1565C0).withValues(alpha: 0.25),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text(
                'YOUR CARE JOURNEY',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Colors.white70, letterSpacing: 0.8),
              ),
              Icon(Icons.health_and_safety_rounded, color: Colors.white, size: 20),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildSummaryItem('Upcoming', _summary!.upcomingAppointmentsCount.toString(), Icons.event_available_rounded),
              _buildSummaryItem('Completed', _summary!.completedConsultationsCount.toString(), Icons.verified_rounded),
              _buildSummaryItem('Prescriptions', _summary!.prescriptionsCount.toString(), Icons.receipt_long_rounded),
              _buildSummaryItem('Care Plans', _summary!.activeCarePlansCount.toString(), Icons.assignment_turned_in_rounded),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryItem(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: Colors.white.withValues(alpha: 0.85), size: 18),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
        Text(label, style: const TextStyle(fontSize: 10, color: Colors.white70)),
      ],
    );
  }

  List<Widget> _buildGroupedTimelineWidgets() {
    // Group events by displayDate
    final groups = <String, List<TimelineEvent>>{};
    for (final ev in _events) {
      final dateKey = ev.displayDate.isNotEmpty ? ev.displayDate : 'Recent';
      groups.putIfAbsent(dateKey, () => []).add(ev);
    }

    final widgets = <Widget>[];

    groups.forEach((dateStr, eventList) {
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(top: 14, bottom: 6),
          child: Row(
            children: [
              const Icon(Icons.calendar_today_rounded, size: 14, color: Color(0xFF1565C0)),
              const SizedBox(width: 6),
              Text(
                dateStr,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                  color: Color(0xFF0D1B2A),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Divider(color: AppTheme.outline.withValues(alpha: 0.2)),
              ),
            ],
          ),
        ),
      );

      for (int i = 0; i < eventList.length; i++) {
        widgets.add(_buildTimelineEventCard(eventList[i], isLast: i == eventList.length - 1));
      }
    });

    return widgets;
  }

  Widget _buildTimelineEventCard(TimelineEvent event, {required bool isLast}) {
    const navy = Color(0xFF0D1B2A);
    final themeConfig = _getEventThemeConfig(event.eventType, event.category);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.outline.withValues(alpha: 0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.02),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Row: Icon, Title & Status Chip
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: themeConfig.color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(themeConfig.icon, color: themeConfig.color, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        event.title,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                          color: navy,
                        ),
                      ),
                      if (event.displayTime != null && event.displayTime!.isNotEmpty)
                        Text(
                          event.displayTime!,
                          style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                        ),
                    ],
                  ),
                ),
                if (event.status != null && event.status!.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: themeConfig.color.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: themeConfig.color.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      event.status!,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: themeConfig.color,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),

            // Doctor and Specialty Row
            if (event.doctorDisplayName != null && event.doctorDisplayName!.isNotEmpty) ...[
              Row(
                children: [
                  const Icon(Icons.person_outline, size: 14, color: Color(0xFF1565C0)),
                  const SizedBox(width: 4),
                  Text(
                    event.doctorDisplayName!,
                    style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12, color: Color(0xFF1565C0)),
                  ),
                  if (event.doctorSpecialty != null && event.doctorSpecialty!.isNotEmpty) ...[
                    const Text(' • ', style: TextStyle(color: AppTheme.textSecondary)),
                    Text(
                      event.doctorSpecialty!,
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 6),
            ],

            // Patient-safe Description
            Text(
              event.description,
              style: const TextStyle(fontSize: 13, color: Color(0xFF334155)),
            ),

            // Available Action Buttons
            if (event.availableActions.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: event.availableActions.map((action) => _buildActionButton(event, action)).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton(TimelineEvent event, String action) {
    switch (action) {
      case 'VIEW_VISIT':
        return OutlinedButton.icon(
          key: Key('view_visit_${event.eventId}'),
          style: OutlinedButton.styleFrom(
            foregroundColor: const Color(0xFF1565C0),
            side: const BorderSide(color: Color(0xFF1565C0)),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            visualDensity: VisualDensity.compact,
          ),
          icon: const Icon(Icons.remove_red_eye_outlined, size: 14),
          label: const Text('View Visit Details', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          onPressed: () {
            if (event.appointmentId != null && event.appointmentId!.isNotEmpty) {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => PatientVisitDetailScreen(
                    appointmentId: event.appointmentId!,
                    timelineService: _timelineService,
                  ),
                ),
              );
            }
          },
        );

      case 'VIEW_APPOINTMENT':
        return OutlinedButton.icon(
          key: Key('view_appointment_${event.eventId}'),
          style: OutlinedButton.styleFrom(
            foregroundColor: const Color(0xFF0288D1),
            side: const BorderSide(color: Color(0xFF0288D1)),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            visualDensity: VisualDensity.compact,
          ),
          icon: const Icon(Icons.event_outlined, size: 14),
          label: const Text('View Appointment', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          onPressed: () {
            if (event.appointmentId != null && event.appointmentId!.isNotEmpty) {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => AppointmentDetailScreen(appointmentId: event.appointmentId!),
                ),
              );
            }
          },
        );

      case 'VIEW_PRESCRIPTION':
        return ElevatedButton.icon(
          key: Key('view_prescription_${event.eventId}'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.teal,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            visualDensity: VisualDensity.compact,
          ),
          icon: const Icon(Icons.receipt_long_rounded, size: 14),
          label: const Text('View Prescription', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => PrescriptionDetailScreen(prescriptionId: event.sourceId),
              ),
            );
          },
        );

      case 'VIEW_MEDICAL_RECORD':
        return ElevatedButton.icon(
          key: Key('view_record_${event.eventId}'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.indigo,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            visualDensity: VisualDensity.compact,
          ),
          icon: const Icon(Icons.description_outlined, size: 14),
          label: const Text('View Record', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => MedicalRecordDetailScreen(recordId: event.sourceId),
              ),
            );
          },
        );

      case 'VIEW_CARE_PLAN':
        return ElevatedButton.icon(
          key: Key('view_care_plan_${event.eventId}'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.purple,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            visualDensity: VisualDensity.compact,
          ),
          icon: const Icon(Icons.assignment_turned_in_rounded, size: 14),
          label: const Text('View Care Plan', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => const PatientCarePlansScreen(),
              ),
            );
          },
        );

      default:
        return const SizedBox.shrink();
    }
  }

  _EventThemeConfig _getEventThemeConfig(String eventType, String category) {
    switch (eventType) {
      case 'APPOINTMENT_CANCELLED':
        return _EventThemeConfig(icon: Icons.cancel_outlined, color: Colors.red.shade700);
      case 'APPOINTMENT_RESCHEDULED':
        return _EventThemeConfig(icon: Icons.update_rounded, color: Colors.orange.shade800);
      case 'APPOINTMENT_COMPLETED':
      case 'CONSULTATION_COMPLETED':
        return _EventThemeConfig(icon: Icons.task_alt_rounded, color: Colors.green.shade700);
      case 'PRESCRIPTION_ISSUED':
        return _EventThemeConfig(icon: Icons.medication_rounded, color: Colors.teal);
      case 'MEDICAL_RECORD_ADDED':
        return _EventThemeConfig(icon: Icons.description_outlined, color: Colors.indigo);
      case 'FOLLOW_UP_PLAN_CREATED':
      case 'FOLLOW_UP_BOOKED':
        return _EventThemeConfig(icon: Icons.assignment_turned_in_rounded, color: Colors.purple);
      default:
        return _EventThemeConfig(icon: Icons.calendar_today_rounded, color: const Color(0xFF1565C0));
    }
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF1565C0).withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.timeline_rounded, size: 56, color: Color(0xFF1565C0)),
            ),
            const SizedBox(height: 18),
            Text(
              _selectedCategory == 'ALL'
                  ? 'No Healthcare History Yet'
                  : 'No ${_categories.firstWhere((c) => c["id"] == _selectedCategory)["label"]} Found',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)),
            ),
            const SizedBox(height: 8),
            Text(
              _selectedCategory == 'ALL'
                  ? 'Your appointments, completed doctor visits, prescriptions, and follow-up care plans will appear here in chronological order.'
                  : 'There are no events recorded under this category.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
            if (_selectedCategory != 'ALL') ...[
              const SizedBox(height: 16),
              OutlinedButton(
                key: const Key('timeline_reset_filter_button'),
                onPressed: () => _filterCategory('ALL'),
                child: const Text('View All Activity'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 48),
            const SizedBox(height: 12),
            Text(
              _errorMessage ?? 'Failed to load timeline.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, color: Color(0xFF0D1B2A)),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              key: const Key('timeline_error_retry_button'),
              onPressed: _loadInitialData,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

class _EventThemeConfig {
  final IconData icon;
  final Color color;

  const _EventThemeConfig({
    required this.icon,
    required this.color,
  });
}

