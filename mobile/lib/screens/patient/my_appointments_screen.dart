import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/appointment.dart';
import '../../services/appointment_service.dart';
import 'appointment_detail_screen.dart';

/// Screen listing patient's appointments with tabs for Upcoming, Completed, and Cancelled.
class MyAppointmentsScreen extends StatefulWidget {
  final AppointmentService? appointmentService;

  const MyAppointmentsScreen({
    super.key,
    this.appointmentService,
  });

  @override
  State<MyAppointmentsScreen> createState() => _MyAppointmentsScreenState();
}

class _MyAppointmentsScreenState extends State<MyAppointmentsScreen>
    with SingleTickerProviderStateMixin {
  late final AppointmentService _appointmentService;
  late final TabController _tabController;

  bool _isLoading = false;
  String? _errorMessage;
  List<Appointment> _allAppointments = [];

  @override
  void initState() {
    super.initState();
    _appointmentService = widget.appointmentService ?? AppointmentService();
    _tabController = TabController(length: 3, vsync: this);
    _loadAppointments();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAppointments() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await _appointmentService.getMyAppointments(limit: 50);
      if (!mounted) return;
      setState(() {
        _allAppointments = res.items;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Failed to load appointments. Please check connection.';
        _isLoading = false;
      });
    }
  }

  List<Appointment> _filterAppointments(int tabIndex) {
    switch (tabIndex) {
      case 0: // Upcoming: PENDING or CONFIRMED
        return _allAppointments
            .where((a) => a.isPending || a.isConfirmed)
            .toList();
      case 1: // Completed
        return _allAppointments.where((a) => a.isCompleted).toList();
      case 2: // Cancelled
        return _allAppointments.where((a) => a.isCancelled).toList();
      default:
        return _allAppointments;
    }
  }

  Widget _buildStatusChip(String status) {
    Color bg;
    Color fg;

    switch (status.toUpperCase()) {
      case 'PENDING':
        bg = Colors.amber.shade100;
        fg = Colors.amber.shade900;
        break;
      case 'CONFIRMED':
        bg = Colors.green.shade100;
        fg = Colors.green.shade800;
        break;
      case 'COMPLETED':
        bg = Colors.blue.shade100;
        fg = Colors.blue.shade800;
        break;
      case 'CANCELLED':
        bg = Colors.red.shade100;
        fg = Colors.red.shade800;
        break;
      default:
        bg = Colors.grey.shade200;
        fg = Colors.grey.shade800;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        status.toUpperCase(),
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: fg,
        ),
      ),
    );
  }

  Widget _buildAppointmentList(List<Appointment> appointments) {
    if (appointments.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.event_busy,
                size: 56,
                color: AppTheme.textSecondary.withValues(alpha: 0.5),
              ),
              const SizedBox(height: 12),
              const Text(
                'No appointments found.',
                style: TextStyle(
                  fontSize: 15,
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
      onRefresh: _loadAppointments,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: appointments.length,
        separatorBuilder: (_, index) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final appt = appointments[index];
          return Card(
            key: Key('appointment_card_${appt.id}'),
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
              side: BorderSide(
                color: AppTheme.outline.withValues(alpha: 0.2),
              ),
            ),
            child: InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AppointmentDetailScreen(
                      appointment: appt,
                      appointmentId: appt.id,
                      appointmentService: _appointmentService,
                    ),
                  ),
                );
                // Refresh list on return to reflect cancellations
                _loadAppointments();
              },
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CircleAvatar(
                          radius: 22,
                          backgroundColor:
                              AppTheme.primary.withValues(alpha: 0.1),
                          child: const Icon(
                            Icons.medical_services_outlined,
                            color: AppTheme.primary,
                            size: 22,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                appt.doctorName ?? 'Doctor Profile',
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                appt.specialty ?? 'General',
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.primary,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        ),
                        _buildStatusChip(appt.status),
                      ],
                    ),
                    const Divider(height: 20),
                    Row(
                      children: [
                        const Icon(
                          Icons.calendar_today,
                          size: 15,
                          color: AppTheme.textSecondary,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          appt.appointmentDate,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const SizedBox(width: 16),
                        const Icon(
                          Icons.access_time,
                          size: 15,
                          color: AppTheme.textSecondary,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '${appt.startTime} - ${appt.endTime}',
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const Spacer(),
                        const Icon(
                          Icons.chevron_right,
                          color: AppTheme.textSecondary,
                          size: 20,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Appointments'),
        centerTitle: true,
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppTheme.primary,
          unselectedLabelColor: AppTheme.textSecondary,
          indicatorColor: AppTheme.primary,
          tabs: const [
            Tab(text: 'Upcoming'),
            Tab(text: 'Completed'),
            Tab(text: 'Cancelled'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline,
                            color: AppTheme.error, size: 48),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 15),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadAppointments,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildAppointmentList(_filterAppointments(0)),
                    _buildAppointmentList(_filterAppointments(1)),
                    _buildAppointmentList(_filterAppointments(2)),
                  ],
                ),
    );
  }
}
