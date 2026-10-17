import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../services/medical_record_service.dart';
import 'create_consultation_record_screen.dart';

/// Screen allowing doctors to view completed appointments eligible for documentation and authored consultation records.
class DoctorConsultationsScreen extends StatefulWidget {
  final MedicalRecordService? service;

  const DoctorConsultationsScreen({super.key, this.service});

  @override
  State<DoctorConsultationsScreen> createState() => _DoctorConsultationsScreenState();
}

class _DoctorConsultationsScreenState extends State<DoctorConsultationsScreen> with SingleTickerProviderStateMixin {
  late final MedicalRecordService _service;
  late final TabController _tabController;

  List<Map<String, dynamic>> _appointments = [];
  bool _isLoadingAppointments = false;
  String? _appointmentsError;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? MedicalRecordService();
    _tabController = TabController(length: 1, vsync: this);
    _loadAppointments();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAppointments() async {
    setState(() {
      _isLoadingAppointments = true;
      _appointmentsError = null;
    });

    try {
      final appts = await _service.getDoctorCompletedAppointments();
      if (mounted) {
        setState(() {
          _appointments = appts;
          _isLoadingAppointments = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _appointmentsError = 'Unable to load appointments for documentation.';
          _isLoadingAppointments = false;
        });
      }
    }
  }

  void _openDocumentation(Map<String, dynamic> appt) async {
    final result = await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (ctx) => CreateConsultationRecordScreen(
          appointment: appt,
          service: _service,
        ),
      ),
    );

    if (result == true) {
      _loadAppointments();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Consultation Documentation'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadAppointments,
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoadingAppointments) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_appointmentsError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(_appointmentsError!, style: const TextStyle(fontSize: 15)),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _loadAppointments, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    if (_appointments.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.assignment_turned_in_outlined, size: 64, color: AppTheme.primary),
              ),
              const SizedBox(height: 20),
              const Text(
                'No Consultations Pending Documentation',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 8),
              const Text(
                'Completed patient appointments requiring clinical notes or digital prescriptions will be listed here.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadAppointments,
      child: ListView.builder(
        padding: const EdgeInsets.all(16.0),
        itemCount: _appointments.length,
        itemBuilder: (context, index) {
          final appt = _appointments[index];
          final patName = appt['patientName'] ?? appt['patient']?['fullName'] ?? 'Patient';
          final apptDate = appt['appointmentDate'] ?? 'Date';
          final timeSlot = '${appt['startTime'] ?? ""} - ${appt['endTime'] ?? ""}';
          final status = appt['status']?.toString() ?? 'CONFIRMED';

          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            elevation: 2,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.calendar_today_rounded, size: 16, color: AppTheme.primary),
                          const SizedBox(width: 6),
                          Text(
                            '$apptDate ($timeSlot)',
                            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.primary),
                          ),
                        ],
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppTheme.success.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          status,
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.success),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '$patName',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  const SizedBox(height: 14),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      key: Key('doctor_document_consultation_button_$index'),
                      onPressed: () => _openDocumentation(appt),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.edit_note_rounded),
                      label: const Text('Document Consultation & Rx'),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
