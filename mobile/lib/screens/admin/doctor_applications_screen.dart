import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../models/admin_doctor_application.dart';
import '../../providers/admin_provider.dart';
import 'doctor_application_detail_screen.dart';

/// Screen listing doctor applications categorized by Pending, Approved, and Rejected status.
class DoctorApplicationsScreen extends StatefulWidget {
  final String initialFilter;

  const DoctorApplicationsScreen({
    super.key,
    this.initialFilter = 'PENDING',
  });

  @override
  State<DoctorApplicationsScreen> createState() =>
      _DoctorApplicationsScreenState();
}

class _DoctorApplicationsScreenState extends State<DoctorApplicationsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final List<String> _statuses = ['PENDING', 'APPROVED', 'REJECTED'];

  @override
  void initState() {
    super.initState();
    final initialIndex = _statuses.indexOf(widget.initialFilter.toUpperCase());
    _tabController = TabController(
      length: _statuses.length,
      vsync: this,
      initialIndex: initialIndex >= 0 ? initialIndex : 0,
    );

    _tabController.addListener(() {
      if (_tabController.indexIsChanging) return;
      final selectedStatus = _statuses[_tabController.index];
      context.read<AdminProvider>().fetchApplications(status: selectedStatus);
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final selectedStatus = _statuses[_tabController.index];
      context.read<AdminProvider>().fetchApplications(status: selectedStatus);
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final status = _statuses[_tabController.index];
    await context.read<AdminProvider>().fetchApplications(status: status);
  }

  void _openDetail(AdminDoctorApplicationSummary app) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DoctorApplicationDetailScreen(
          doctorProfileId: app.doctorProfileId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final adminProvider = context.watch<AdminProvider>();
    final applications = adminProvider.applications;
    final isLoading = adminProvider.isLoading;
    final errorMessage = adminProvider.errorMessage;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Doctor Applications'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primary,
          unselectedLabelColor: AppTheme.textSecondary,
          indicatorColor: AppTheme.primary,
          indicatorWeight: 3,
          tabs: const [
            Tab(text: 'Pending'),
            Tab(text: 'Approved'),
            Tab(text: 'Rejected'),
          ],
        ),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _refresh,
          color: AppTheme.primary,
          child: isLoading
              ? const Center(child: CircularProgressIndicator())
              : errorMessage != null
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24.0),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.error_outline, size: 48, color: AppTheme.error),
                            const SizedBox(height: 16),
                            Text(
                              errorMessage,
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: AppTheme.error, fontSize: 14),
                            ),
                            const SizedBox(height: 16),
                            ElevatedButton(
                              onPressed: _refresh,
                              child: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    )
                  : applications.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.inbox_rounded,
                                size: 56,
                                color: AppTheme.textMuted.withValues(alpha: 0.5),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'No ${_statuses[_tabController.index].toLowerCase()} applications.',
                                style: const TextStyle(
                                  fontSize: 16,
                                  color: AppTheme.textSecondary,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                          itemCount: applications.length,
                          separatorBuilder: (_, _) => const SizedBox(height: 12),
                          itemBuilder: (context, index) {
                            final app = applications[index];
                            return _buildApplicationCard(app);
                          },
                        ),
        ),
      ),
    );
  }

  Widget _buildApplicationCard(AdminDoctorApplicationSummary app) {
    Color badgeColor;
    Color textColor;
    IconData statusIcon;

    if (app.isApproved) {
      badgeColor = Colors.green.shade50;
      textColor = Colors.green.shade800;
      statusIcon = Icons.check_circle_outline;
    } else if (app.isRejected) {
      badgeColor = AppTheme.errorContainer;
      textColor = AppTheme.error;
      statusIcon = Icons.cancel_outlined;
    } else {
      badgeColor = Colors.amber.shade50;
      textColor = Colors.amber.shade900;
      statusIcon = Icons.schedule_rounded;
    }

    final formattedDate =
        '${app.submittedAt.year}-${app.submittedAt.month.toString().padLeft(2, '0')}-${app.submittedAt.day.toString().padLeft(2, '0')}';

    return Card(
      key: Key('doctor_app_card_${app.doctorProfileId}'),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppTheme.border),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _openDetail(app),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                    child: const Icon(
                      Icons.person,
                      color: AppTheme.primary,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          app.fullName,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          app.specialty,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: badgeColor,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(statusIcon, size: 12, color: textColor),
                        const SizedBox(width: 4),
                        Text(
                          app.verificationStatus,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: textColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Icon(Icons.badge_outlined, size: 16, color: AppTheme.textSecondary),
                  const SizedBox(width: 6),
                  Text(
                    'SLMC: ${app.medicalRegistrationNumber}',
                    style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                  ),
                  const Spacer(),
                  const Icon(Icons.business_outlined, size: 16, color: AppTheme.textSecondary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      app.hospitalOrClinic,
                      style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.end,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.calendar_today_outlined, size: 14, color: AppTheme.textMuted),
                  const SizedBox(width: 6),
                  Text(
                    'Submitted: $formattedDate',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
                  ),
                  const Spacer(),
                  const Text(
                    'Review Details',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.primary,
                    ),
                  ),
                  const Icon(
                    Icons.arrow_forward_ios_rounded,
                    size: 12,
                    color: AppTheme.primary,
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
