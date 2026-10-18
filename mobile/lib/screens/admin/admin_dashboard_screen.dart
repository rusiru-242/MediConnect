import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../models/analytics_data.dart';
import '../../providers/admin_provider.dart';
import '../../providers/auth_provider.dart';
import '../../services/analytics_service.dart';
import '../../widgets/mediconnect_logo.dart';
import 'admin_article_editor_screen.dart';
import 'admin_articles_screen.dart';
import 'doctor_applications_screen.dart';

/// Administrative dashboard for MediConnect doctor verification, analytics, and content operations (Phase 24).
class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> with SingleTickerProviderStateMixin {
  final AnalyticsService _analyticsService = AnalyticsService();
  late TabController _tabController;

  AnalyticsOverviewData? _overviewData;
  DoctorAnalyticsData? _doctorAnalyticsData;
  bool _isLoadingAnalytics = true;
  String? _analyticsError;

  String _dateFilter = 'ALL'; // ALL, 7D, 30D

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AdminProvider>().fetchApplications(status: 'PENDING');
      _loadAnalytics();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAnalytics() async {
    setState(() {
      _isLoadingAnalytics = true;
      _analyticsError = null;
    });

    String? startDate;
    String? endDate;
    final now = DateTime.now();

    if (_dateFilter == '7D') {
      final start = now.subtract(const Duration(days: 7));
      startDate = '${start.year}-${start.month.toString().padLeft(2, '0')}-${start.day.toString().padLeft(2, '0')}';
      endDate = '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    } else if (_dateFilter == '30D') {
      final start = now.subtract(const Duration(days: 30));
      startDate = '${start.year}-${start.month.toString().padLeft(2, '0')}-${start.day.toString().padLeft(2, '0')}';
      endDate = '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
    }

    try {
      final ov = await _analyticsService.fetchOverview(startDate: startDate, endDate: endDate);
      final docStats = await _analyticsService.fetchDoctorAnalytics();
      if (mounted) {
        setState(() {
          _overviewData = ov;
          _doctorAnalyticsData = docStats;
          _isLoadingAnalytics = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoadingAnalytics = false;
          _analyticsError = 'Failed to load analytics: ${e.toString().replaceAll("Exception: ", "")}';
        });
      }
    }
  }

  Future<void> _handleLogout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Logout'),
        content: const Text('Are you sure you want to log out of the Admin Portal?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirm != true) return;
    if (!mounted) return;

    final authProvider = context.read<AuthProvider>();
    await authProvider.logout();

    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/welcome', (route) => false);
  }

  void _navigateToApplications({String filter = 'PENDING'}) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DoctorApplicationsScreen(initialFilter: filter),
      ),
    );
  }

  void _navigateToArticles() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const AdminArticlesScreen(),
      ),
    );
  }

  void _navigateToNewArticle() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const AdminArticleEditorScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final adminProvider = context.watch<AdminProvider>();
    final user = authProvider.user;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('MediConnect Admin'),
        actions: [
          IconButton(
            tooltip: 'Logout',
            icon: const Icon(Icons.logout_rounded),
            onPressed: _handleLogout,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: const [
            Tab(icon: Icon(Icons.verified_user_rounded), text: 'Doctors'),
            Tab(icon: Icon(Icons.insights_rounded), text: 'Analytics'),
            Tab(icon: Icon(Icons.article_rounded), text: 'Content'),
          ],
        ),
      ),
      body: SafeArea(
        child: TabBarView(
          controller: _tabController,
          children: [
            // Tab 0: Doctor Verification
            _buildDoctorVerificationTab(user, adminProvider),

            // Tab 1: Analytics & Trends
            _buildAnalyticsTab(user),

            // Tab 2: Health Content
            _buildContentTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildAdminHeader(dynamic user) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          const MediConnectLogo(size: 48),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user?.fullName ?? 'System Administrator',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  user?.email ?? 'admin@mediconnect.lk',
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text(
              'ADMIN',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: AppTheme.primary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // --------------------------------------------------------------------------
  // Tab 1: Analytics & Platform Overview
  // --------------------------------------------------------------------------
  Widget _buildAnalyticsTab(dynamic user) {
    return RefreshIndicator(
      onRefresh: _loadAnalytics,
      color: AppTheme.primary,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildAdminHeader(user),
            const SizedBox(height: 20),

            // Date Range Filters
            Row(
              children: [
                const Text(
                  'Platform Analytics',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const Spacer(),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'ALL', label: Text('All')),
                    ButtonSegment(value: '7D', label: Text('7d')),
                    ButtonSegment(value: '30D', label: Text('30d')),
                  ],
                  selected: {_dateFilter},
                  onSelectionChanged: (val) {
                    setState(() => _dateFilter = val.first);
                    _loadAnalytics();
                  },
                  style: const ButtonStyle(
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            if (_isLoadingAnalytics)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 40.0),
                child: Center(child: CircularProgressIndicator(color: AppTheme.primary)),
              )
            else if (_analyticsError != null)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.errorContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline_rounded, color: AppTheme.error),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(_analyticsError!, style: const TextStyle(color: AppTheme.error)),
                    ),
                    IconButton(
                      icon: const Icon(Icons.refresh_rounded, color: AppTheme.error),
                      onPressed: _loadAnalytics,
                    ),
                  ],
                ),
              )
            else if (_overviewData != null) ...[
              // Metric cards grid
              Row(
                children: [
                  Expanded(
                    child: _buildMetricCard(
                      title: 'Patients',
                      subtitle: 'Registered',
                      count: _overviewData!.totalPatients,
                      color: Colors.blue.shade700,
                      backgroundColor: Colors.blue.shade50,
                      icon: Icons.people_alt_rounded,
                      onTap: () {},
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildMetricCard(
                      title: 'Doctors',
                      subtitle: 'Verified',
                      count: _overviewData!.totalVerifiedDoctors,
                      color: Colors.green.shade700,
                      backgroundColor: Colors.green.shade50,
                      icon: Icons.medical_services_rounded,
                      onTap: () => _tabController.animateTo(1),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              Row(
                children: [
                  Expanded(
                    child: _buildMetricCard(
                      title: 'Appointments',
                      subtitle: '${_overviewData!.completedAppointments} Completed',
                      count: _overviewData!.totalAppointments,
                      color: AppTheme.primary,
                      backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                      icon: Icons.calendar_today_rounded,
                      onTap: () {},
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildMetricCard(
                      title: 'Cancelled',
                      subtitle: 'Patient or Doctor',
                      count: _overviewData!.cancelledAppointments,
                      color: Colors.orange.shade800,
                      backgroundColor: Colors.orange.shade50,
                      icon: Icons.event_busy_rounded,
                      onTap: () {},
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Revenue Card (Gross, Net, Refunded with Stripe Test Mode indicator)
              _buildRevenueCard(_overviewData!),
              const SizedBox(height: 16),

              // Doctor Specialty Breakdown
              if (_doctorAnalyticsData != null && _doctorAnalyticsData!.specialtyDistribution.isNotEmpty) ...[
                _buildSpecialtiesCard(_doctorAnalyticsData!),
                const SizedBox(height: 16),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildRevenueCard(AnalyticsOverviewData data) {
    final lkrRevenue = data.totalRevenueByCurrency.firstWhere(
      (r) => r.currency == 'LKR',
      orElse: () => const CurrencyRevenueData(currency: 'LKR', grossAmount: 0.0, refundedAmount: 0.0, netAmount: 0.0, paymentCount: 0),
    );

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.teal.shade50,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.account_balance_wallet_rounded, color: Colors.teal.shade700, size: 22),
              ),
              const SizedBox(width: 12),
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Net Earned Revenue',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  Text(
                    'Excludes holds, failed & refunded payments',
                    style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                  ),
                ],
              ),
              const Spacer(),
              // Stripe Test Indicator
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: Colors.purple.shade50,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Colors.purple.shade200),
                ),
                child: Text(
                  'STRIPE TEST',
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.purple.shade800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Net Total Display
          Text(
            'LKR ${lkrRevenue.netAmount.toStringAsFixed(2)}',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.bold,
              color: Colors.teal.shade800,
            ),
          ),
          const SizedBox(height: 12),

          // Breakdown Row
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Gross Paid', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    Text('LKR ${lkrRevenue.grossAmount.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                  ],
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Refunded', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    Text('LKR ${lkrRevenue.refundedAmount.toStringAsFixed(0)}', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: Colors.red.shade700)),
                  ],
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Transactions', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    Text('${data.successfulPaymentsCount} paid', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSpecialtiesCard(DoctorAnalyticsData docData) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.category_rounded, size: 20, color: AppTheme.primary),
              SizedBox(width: 10),
              Text(
                'Doctor Specialties Distribution',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ...docData.specialtyDistribution.map((spec) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      spec.specialty,
                      style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '${spec.count} doctors',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.primary),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // --------------------------------------------------------------------------
  // Tab 2: Doctor Verification Overview
  // --------------------------------------------------------------------------
  Widget _buildDoctorVerificationTab(dynamic user, AdminProvider adminProvider) {
    return RefreshIndicator(
      onRefresh: () => adminProvider.fetchApplications(status: 'PENDING'),
      color: AppTheme.primary,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildAdminHeader(user),
            const SizedBox(height: 24),

            // Section Title
            const Text(
              'Doctor Verification Overview',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Manage medical credentials and approve qualified practitioners.',
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 16),

            // Summary Metric Cards
            Row(
              children: [
                Expanded(
                  child: _buildMetricCard(
                    title: 'Pending',
                    subtitle: 'Needs Review',
                    count: adminProvider.pendingCount,
                    color: Colors.amber.shade700,
                    backgroundColor: Colors.amber.shade50,
                    icon: Icons.hourglass_top_rounded,
                    onTap: () => _navigateToApplications(filter: 'PENDING'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildMetricCard(
                    title: 'Approved',
                    subtitle: 'Active Doctors',
                    count: adminProvider.approvedCount,
                    color: Colors.green.shade700,
                    backgroundColor: Colors.green.shade50,
                    icon: Icons.check_circle_rounded,
                    onTap: () => _navigateToApplications(filter: 'APPROVED'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildMetricCard(
                    title: 'Rejected',
                    subtitle: 'Declined Applications',
                    count: adminProvider.rejectedCount,
                    color: AppTheme.error,
                    backgroundColor: AppTheme.errorContainer,
                    icon: Icons.cancel_rounded,
                    onTap: () => _navigateToApplications(filter: 'REJECTED'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 28),

            // Quick Navigation: Doctor Applications
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.assignment_ind_rounded, color: AppTheme.primary, size: 24),
                      SizedBox(width: 12),
                      Text(
                        'Doctor Applications',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Inspect submitted identity documents, medical council registration, and qualifications to verify doctor accounts.',
                    style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    key: const Key('open_doctor_applications_button'),
                    onPressed: () => _navigateToApplications(filter: 'PENDING'),
                    icon: const Icon(Icons.arrow_forward_rounded, size: 18),
                    label: const Text('View Doctor Applications'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // --------------------------------------------------------------------------
  // Tab 3: Health Content Management
  // --------------------------------------------------------------------------
  Widget _buildContentTab() {
    final publishedCount = _overviewData?.publishedArticles ?? 0;
    final draftCount = _overviewData?.draftArticles ?? 0;
    final totalArticles = _overviewData?.totalArticles ?? 0;
    final totalBookmarks = _overviewData?.totalBookmarks ?? 0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Health & Wellness Content',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Publish reliable, educational health advice and nutritional guidelines for patients.',
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 16),

          // Content Metric Cards
          Row(
            children: [
              Expanded(
                child: _buildMetricCard(
                  title: 'Published',
                  subtitle: 'Live in Patient Feed',
                  count: publishedCount,
                  color: Colors.green.shade700,
                  backgroundColor: Colors.green.shade50,
                  icon: Icons.check_circle_outline_rounded,
                  onTap: _navigateToArticles,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetricCard(
                  title: 'Drafts',
                  subtitle: 'In Review',
                  count: draftCount,
                  color: Colors.amber.shade800,
                  backgroundColor: Colors.amber.shade50,
                  icon: Icons.edit_note_rounded,
                  onTap: _navigateToArticles,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          Row(
            children: [
              Expanded(
                child: _buildMetricCard(
                  title: 'Total Articles',
                  subtitle: 'All statuses',
                  count: totalArticles,
                  color: AppTheme.primary,
                  backgroundColor: AppTheme.primary.withValues(alpha: 0.1),
                  icon: Icons.menu_book_rounded,
                  onTap: _navigateToArticles,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetricCard(
                  title: 'Saved Bookmarks',
                  subtitle: 'Patient engagement',
                  count: totalBookmarks,
                  color: Colors.purple.shade700,
                  backgroundColor: Colors.purple.shade50,
                  icon: Icons.bookmark_added_rounded,
                  onTap: _navigateToArticles,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Actions Card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.library_books_rounded, color: AppTheme.primary, size: 24),
                    SizedBox(width: 12),
                    Text(
                      'Content Management Actions',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                const Text(
                  'Write, edit, preview, and organize evidence-based articles for the MediConnect community.',
                  style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.4),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton.icon(
                        key: const Key('admin_create_new_article_shortcut'),
                        onPressed: _navigateToNewArticle,
                        icon: const Icon(Icons.add_rounded, size: 18),
                        label: const Text('New Article'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        key: const Key('admin_manage_articles_shortcut'),
                        onPressed: _navigateToArticles,
                        icon: const Icon(Icons.list_alt_rounded, size: 18),
                        label: const Text('Manage All'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String subtitle,
    required int count,
    required Color color,
    required Color backgroundColor,
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppTheme.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: backgroundColor,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 20),
                ),
                const Spacer(),
                Text(
                  '$count',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: const TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
