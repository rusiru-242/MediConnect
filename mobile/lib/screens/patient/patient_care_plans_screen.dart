import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../models/care_plan.dart';
import '../../services/care_plan_service.dart';
import 'doctor_detail_screen.dart';

/// Screen allowing patients to review their smart follow-up care plans and complete tasks (Phase 56).
class PatientCarePlansScreen extends StatefulWidget {
  final CarePlanService? carePlanService;

  const PatientCarePlansScreen({super.key, this.carePlanService});

  @override
  State<PatientCarePlansScreen> createState() => _PatientCarePlansScreenState();
}

class _PatientCarePlansScreenState extends State<PatientCarePlansScreen>
    with SingleTickerProviderStateMixin {
  late final CarePlanService _carePlanService;
  late final TabController _tabController;

  List<CarePlan> _allPlans = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _carePlanService = widget.carePlanService ?? CarePlanService();
    _tabController = TabController(length: 2, vsync: this);
    _loadCarePlans();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadCarePlans() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final plans = await _carePlanService.getPatientCarePlans();
      if (!mounted) return;
      setState(() {
        _allPlans = plans;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load follow-up care plans.';
      });
    }
  }

  Future<void> _toggleTaskStatus(CarePlan plan, CareTask task, bool newStatus) async {
    try {
      final updated = await _carePlanService.updateTaskStatus(
        plan.id,
        task.taskId,
        isCompleted: newStatus,
      );
      if (!mounted) return;
      setState(() {
        final index = _allPlans.indexWhere((p) => p.id == plan.id);
        if (index != -1) {
          _allPlans[index] = updated;
        }
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not update task status: $e'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  void _navigateToBookFollowUp(CarePlan plan) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DoctorDetailScreen(doctorId: plan.doctorUserId),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return const Color(0xFF1565C0);
      case 'FOLLOW_UP_BOOKED':
        return Colors.green.shade700;
      case 'OVERDUE':
        return Colors.amber.shade800;
      case 'COMPLETED':
        return Colors.purple.shade700;
      case 'CANCELLED':
        return Colors.grey.shade600;
      default:
        return const Color(0xFF1565C0);
    }
  }

  Widget _buildStatusBadge(String status) {
    final color = _getStatusColor(status);
    final text = status.replaceAll('_', ' ');

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildCarePlanCard(CarePlan plan) {
    const navy = Color(0xFF0D1B2A);

    return Card(
      key: Key('care_plan_card_${plan.id}'),
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      elevation: 1,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: AppTheme.outline.withValues(alpha: 0.2)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Doctor header & status badge
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: const Color(0xFF1565C0).withValues(alpha: 0.1),
                  child: const Icon(Icons.medical_services_rounded, color: Color(0xFF1565C0)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        plan.doctorName,
                        style: const TextStyle(
                          fontSize: 16.5,
                          fontWeight: FontWeight.bold,
                          color: navy,
                        ),
                      ),
                      if (plan.doctorSpecialty != null)
                        Text(
                          plan.doctorSpecialty!,
                          style: const TextStyle(
                            fontSize: 13,
                            color: Color(0xFF1565C0),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                    ],
                  ),
                ),
                _buildStatusBadge(plan.status),
              ],
            ),
            const Divider(height: 24),

            // Schedule info
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F8FC),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.event_repeat_rounded, color: Color(0xFF1565C0), size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Recommended Follow-up',
                          style: TextStyle(fontSize: 11.5, color: AppTheme.textSecondary),
                        ),
                        Text(
                          plan.followUpDateEnd != null
                              ? '${plan.followUpDate} to ${plan.followUpDateEnd}'
                              : plan.followUpDate,
                          style: const TextStyle(
                            fontSize: 14.5,
                            fontWeight: FontWeight.bold,
                            color: navy,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (plan.consultationDate != null)
                    Text(
                      'Visit: ${plan.consultationDate}',
                      style: const TextStyle(fontSize: 11.5, color: AppTheme.textSecondary),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Reason
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.notes_rounded, size: 16, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    plan.reason,
                    style: const TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: navy,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Instructions
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.blue.shade100),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.info_outline_rounded, size: 15, color: Color(0xFF1565C0)),
                      SizedBox(width: 6),
                      Text(
                        'Care Instructions',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF1565C0),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    plan.instructions,
                    style: const TextStyle(fontSize: 13, height: 1.35, color: navy),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),

            // Tasks Checklist
            if (plan.tasks.isNotEmpty) ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Care Tasks (${plan.completedTaskCount}/${plan.totalTaskCount})',
                    style: const TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.bold,
                      color: navy,
                    ),
                  ),
                  Text(
                    '${(plan.progressPercentage * 100).toInt()}% Done',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF1565C0),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: plan.progressPercentage,
                  backgroundColor: Colors.grey.shade200,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    plan.progressPercentage == 1.0 ? Colors.green : const Color(0xFF1565C0),
                  ),
                  minHeight: 6,
                ),
              ),
              const SizedBox(height: 8),
              ...plan.tasks.map((task) {
                return CheckboxListTile(
                  key: Key('task_checkbox_${task.taskId}'),
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  activeColor: const Color(0xFF1565C0),
                  value: task.isCompleted,
                  onChanged: plan.isActive || plan.isFollowUpBooked || plan.isOverdue
                      ? (v) => _toggleTaskStatus(plan, task, v ?? false)
                      : null,
                  title: Text(
                    task.title,
                    style: TextStyle(
                      fontSize: 13,
                      decoration: task.isCompleted ? TextDecoration.lineThrough : null,
                      color: task.isCompleted ? AppTheme.textSecondary : navy,
                    ),
                  ),
                  subtitle: task.isCompleted && task.completedAt != null
                      ? Text(
                          'Completed on ${task.completedAt!.toString().substring(0, 16)}',
                          style: TextStyle(fontSize: 11, color: Colors.green.shade700),
                        )
                      : (task.description != null
                          ? Text(task.description!, style: const TextStyle(fontSize: 11))
                          : null),
                );
              }),
            ],

            const SizedBox(height: 8),

            // Book Follow-up Action
            if (plan.isActive || plan.isOverdue) ...[
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  key: Key('book_follow_up_button_${plan.id}'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1565C0),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: () => _navigateToBookFollowUp(plan),
                  icon: const Icon(Icons.calendar_month_rounded, size: 18),
                  label: const Text(
                    'Book Follow-up Appointment',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                ),
              ),
            ] else if (plan.isFollowUpBooked) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.check_circle_rounded, color: Colors.green.shade700, size: 18),
                    const SizedBox(width: 8),
                    Text(
                      'Follow-up Appointment Booked',
                      style: TextStyle(
                        color: Colors.green.shade800,
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
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

  Widget _buildEmptyState(String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.assignment_outlined, size: 64, color: Colors.grey.shade400),
            const SizedBox(height: 16),
            Text(
              message,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: Color(0xFF0D1B2A),
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            const Text(
              'Follow-up plans created by your doctor after a consultation will appear here.',
              style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final activePlans = _allPlans.where((p) => p.isActive || p.isFollowUpBooked || p.isOverdue).toList();
    final completedPlans = _allPlans.where((p) => p.isCompleted || p.isCancelled).toList();

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FC),
      appBar: AppBar(
        title: const Text(
          'My Care Plans',
          style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: Color(0xFF0D1B2A)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF1565C0),
          unselectedLabelColor: AppTheme.textSecondary,
          indicatorColor: const Color(0xFF1565C0),
          indicatorWeight: 3,
          tabs: [
            Tab(text: 'Active (${activePlans.length})'),
            Tab(text: 'History (${completedPlans.length})'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 48),
                      const SizedBox(height: 12),
                      Text(_errorMessage!, style: const TextStyle(fontSize: 15)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadCarePlans,
                        child: const Text('Try Again'),
                      ),
                    ],
                  ),
                )
              : TabBarView(
                  controller: _tabController,
                  children: [
                    // Tab 1: Active Plans
                    RefreshIndicator(
                      onRefresh: _loadCarePlans,
                      child: activePlans.isEmpty
                          ? _buildEmptyState('No active follow-up care plans')
                          : ListView.builder(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              itemCount: activePlans.length,
                              itemBuilder: (_, i) => _buildCarePlanCard(activePlans[i]),
                            ),
                    ),
                    // Tab 2: Completed / Cancelled
                    RefreshIndicator(
                      onRefresh: _loadCarePlans,
                      child: completedPlans.isEmpty
                          ? _buildEmptyState('No completed follow-up plans')
                          : ListView.builder(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              itemCount: completedPlans.length,
                              itemBuilder: (_, i) => _buildCarePlanCard(completedPlans[i]),
                            ),
                    ),
                  ],
                ),
    );
  }
}
