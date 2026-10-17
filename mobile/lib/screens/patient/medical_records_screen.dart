import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/medical_record.dart';
import '../../models/prescription.dart';
import '../../services/medical_record_service.dart';
import 'medical_record_detail_screen.dart';
import 'prescription_detail_screen.dart';

/// Screen allowing patients to review their consultation medical records and digital prescriptions.
class MedicalRecordsScreen extends StatefulWidget {
  final MedicalRecordService? service;

  const MedicalRecordsScreen({super.key, this.service});

  @override
  State<MedicalRecordsScreen> createState() => _MedicalRecordsScreenState();
}

class _MedicalRecordsScreenState extends State<MedicalRecordsScreen> with SingleTickerProviderStateMixin {
  late final MedicalRecordService _service;
  late final TabController _tabController;

  List<MedicalRecord> _records = [];
  List<Prescription> _prescriptions = [];

  bool _isLoadingRecords = false;
  bool _isLoadingPrescriptions = false;
  String? _recordsError;
  String? _prescriptionsError;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? MedicalRecordService();
    _tabController = TabController(length: 2, vsync: this);
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    await Future.wait([_loadRecords(), _loadPrescriptions()]);
  }

  Future<void> _loadRecords() async {
    setState(() {
      _isLoadingRecords = true;
      _recordsError = null;
    });

    try {
      final records = await _service.getPatientMedicalRecords();
      if (mounted) {
        setState(() {
          _records = records;
          _isLoadingRecords = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _recordsError = 'Unable to load consultation records.';
          _isLoadingRecords = false;
        });
      }
    }
  }

  Future<void> _loadPrescriptions() async {
    setState(() {
      _isLoadingPrescriptions = true;
      _prescriptionsError = null;
    });

    try {
      final prescs = await _service.getPatientPrescriptions();
      if (mounted) {
        setState(() {
          _prescriptions = prescs;
          _isLoadingPrescriptions = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _prescriptionsError = 'Unable to load digital prescriptions.';
          _isLoadingPrescriptions = false;
        });
      }
    }
  }

  Future<void> _downloadPdf(Prescription presc) async {
    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Generating PDF for ${presc.prescriptionId}...'),
          duration: const Duration(seconds: 1),
        ),
      );

      final pdfBytes = await _service.downloadPrescriptionPdf(presc.id);
      if (!mounted) return;

      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: const Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 48),
          title: const Text('PDF Download Ready'),
          content: Text(
            'Official Prescription PDF (${presc.prescriptionId}) generated successfully (${pdfBytes.length} bytes).\n\n'
            'Prescribing Physician: ${presc.doctorName ?? "Verified Doctor"}\nSLMC: ${presc.slmcRegistrationNumber ?? "Accredited"}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Close'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Could not download PDF. Please try again.'),
          backgroundColor: AppTheme.error,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Medical Records & Rx'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.tealAccent,
          indicatorWeight: 3,
          tabs: const [
            Tab(icon: Icon(Icons.description_rounded), text: 'Consultations'),
            Tab(icon: Icon(Icons.receipt_long_rounded), text: 'Prescriptions'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildRecordsTab(),
          _buildPrescriptionsTab(),
        ],
      ),
    );
  }

  // -------------------------------------------------------------------------
  // TAB 1: CONSULTATION MEDICAL RECORDS
  // -------------------------------------------------------------------------
  Widget _buildRecordsTab() {
    if (_isLoadingRecords) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_recordsError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(_recordsError!, style: const TextStyle(fontSize: 15)),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _loadRecords, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    if (_records.isEmpty) {
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
                child: const Icon(Icons.medical_information_outlined, size: 64, color: AppTheme.primary),
              ),
              const SizedBox(height: 20),
              const Text(
                'No Consultation Records Yet',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 8),
              const Text(
                'After completing an appointment, your doctor\'s clinical notes and diagnosis will appear here.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadRecords,
      child: ListView.builder(
        padding: const EdgeInsets.all(16.0),
        itemCount: _records.length,
        itemBuilder: (context, index) {
          final rec = _records[index];
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            elevation: 2,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: InkWell(
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (ctx) => MedicalRecordDetailScreen(
                      recordId: rec.id,
                      initialRecord: rec,
                    ),
                  ),
                );
              },
              borderRadius: BorderRadius.circular(16),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: AppTheme.primary.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            rec.consultationDate,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.primary,
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: rec.status == 'AMENDED'
                                ? Colors.orange.withValues(alpha: 0.15)
                                : AppTheme.success.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            rec.status,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              color: rec.status == 'AMENDED' ? Colors.orange[800] : AppTheme.success,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      rec.doctorName ?? 'Verified Doctor',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      rec.doctorSpecialty ?? 'General Physician',
                      style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.background,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.assignment_turned_in_outlined, size: 16, color: AppTheme.primary),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              rec.assessment,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                            ),
                          ),
                        ],
                      ),
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

  // -------------------------------------------------------------------------
  // TAB 2: DIGITAL PRESCRIPTIONS
  // -------------------------------------------------------------------------
  Widget _buildPrescriptionsTab() {
    if (_isLoadingPrescriptions) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_prescriptionsError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.error),
              const SizedBox(height: 12),
              Text(_prescriptionsError!, style: const TextStyle(fontSize: 15)),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _loadPrescriptions, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    if (_prescriptions.isEmpty) {
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
                child: const Icon(Icons.receipt_long_outlined, size: 64, color: AppTheme.primary),
              ),
              const SizedBox(height: 20),
              const Text(
                'No Prescriptions Issued',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 8),
              const Text(
                'When your doctor issues a structured digital prescription, it will appear here for easy viewing and PDF download.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadPrescriptions,
      child: ListView.builder(
        padding: const EdgeInsets.all(16.0),
        itemCount: _prescriptions.length,
        itemBuilder: (context, index) {
          final presc = _prescriptions[index];
          final dateStr = presc.issuedAt.toLocal().toString().substring(0, 10);

          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            elevation: 2,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: InkWell(
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (ctx) => PrescriptionDetailScreen(
                      prescriptionId: presc.id,
                      initialPrescription: presc,
                    ),
                  ),
                );
              },
              borderRadius: BorderRadius.circular(16),
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
                            const Icon(Icons.receipt_long_rounded, color: AppTheme.primary, size: 20),
                            const SizedBox(width: 6),
                            Text(
                              presc.prescriptionId,
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primary,
                              ),
                            ),
                          ],
                        ),
                        Text(
                          dateStr,
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      presc.doctorName ?? 'Prescribing Physician',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${presc.doctorSpecialty ?? "Specialist"} • SLMC: ${presc.slmcRegistrationNumber ?? "Verified"}',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.blue.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '${presc.medicationItems.length} Medications Prescribed',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Colors.blueAccent,
                            ),
                          ),
                        ),
                        IconButton(
                          key: Key('prescription_item_pdf_button_${presc.id}'),
                          icon: const Icon(Icons.picture_as_pdf_rounded, color: AppTheme.primary),
                          tooltip: 'Download PDF',
                          onPressed: () => _downloadPdf(presc),
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
}
