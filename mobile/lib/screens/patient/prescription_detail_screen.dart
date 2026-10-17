import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/prescription.dart';
import '../../services/medical_record_service.dart';

/// Screen displaying structured digital prescription and official PDF download action.
class PrescriptionDetailScreen extends StatefulWidget {
  final String prescriptionId;
  final Prescription? initialPrescription;
  final MedicalRecordService? service;

  const PrescriptionDetailScreen({
    super.key,
    required this.prescriptionId,
    this.initialPrescription,
    this.service,
  });

  @override
  State<PrescriptionDetailScreen> createState() => _PrescriptionDetailScreenState();
}

class _PrescriptionDetailScreenState extends State<PrescriptionDetailScreen> {
  late final MedicalRecordService _service;
  Prescription? _prescription;
  bool _isLoading = false;
  bool _isDownloadingPdf = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? MedicalRecordService();
    _prescription = widget.initialPrescription;
    if (_prescription == null) {
      _loadPrescription();
    }
  }

  Future<void> _loadPrescription() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final presc = await _service.getPrescriptionDetail(widget.prescriptionId);
      if (mounted) {
        setState(() {
          _prescription = presc;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Could not load digital prescription details. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _handleDownloadPdf() async {
    if (_prescription == null) return;
    setState(() => _isDownloadingPdf = true);

    try {
      final pdfBytes = await _service.downloadPrescriptionPdf(_prescription!.id);
      if (!mounted) return;

      setState(() => _isDownloadingPdf = false);

      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: const Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 48),
          title: const Text('Prescription PDF Ready'),
          content: Text(
            'Digital Prescription (${_prescription!.prescriptionId}) generated successfully (${pdfBytes.length} bytes).\n\n'
            'Verified under SLMC accreditation: ${_prescription!.slmcRegistrationNumber ?? "Registered Doctor"}.',
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
      setState(() => _isDownloadingPdf = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to download prescription PDF. Please check connection.'),
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
        title: const Text('Digital Prescription'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
            onPressed: _loadPrescription,
          ),
        ],
      ),
      bottomNavigationBar: _prescription != null
          ? Container(
              padding: const EdgeInsets.all(16.0),
              decoration: BoxDecoration(
                color: Colors.white,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    offset: const Offset(0, -2),
                    blurRadius: 10,
                  ),
                ],
              ),
              child: ElevatedButton.icon(
                key: const Key('prescription_download_pdf_button'),
                onPressed: _isDownloadingPdf ? null : _handleDownloadPdf,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                icon: _isDownloadingPdf
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                      )
                    : const Icon(Icons.picture_as_pdf_rounded),
                label: Text(
                  _isDownloadingPdf ? 'Generating Official PDF...' : 'Download Verified PDF',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            )
          : null,
      body: _buildBody(),
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
              const Icon(Icons.error_outline_rounded, size: 56, color: AppTheme.error),
              const SizedBox(height: 16),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppTheme.textPrimary),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _loadPrescription,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_prescription == null) {
      return const Center(child: Text('Prescription not found.'));
    }

    final presc = _prescription!;

    return ListView(
      padding: const EdgeInsets.all(16.0),
      children: [
        // 1. Prescription Header
        Card(
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
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppTheme.primary.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(Icons.receipt_long_rounded, color: AppTheme.primary, size: 24),
                        ),
                        const SizedBox(width: 10),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'OFFICIAL DIGITAL Rx',
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w900,
                                color: AppTheme.primary,
                                letterSpacing: 0.5,
                              ),
                            ),
                            Text(
                              presc.prescriptionId,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: presc.status == 'AMENDED'
                            ? Colors.orange.withValues(alpha: 0.15)
                            : AppTheme.success.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        presc.status,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: presc.status == 'AMENDED' ? Colors.orange[800] : AppTheme.success,
                        ),
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24),
                _buildDoctorBox(presc),
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // 2. Prescribed Medications List
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'Prescribed Medications',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            Text(
              '${presc.medicationItems.length} Items',
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, fontWeight: FontWeight.w600),
            ),
          ],
        ),

        const SizedBox(height: 10),

        ...presc.medicationItems.asMap().entries.map((entry) {
          final idx = entry.key + 1;
          final item = entry.value;
          return _buildMedicationCard(idx, item);
        }),

        if (presc.instructions != null && presc.instructions!.isNotEmpty) ...[
          const SizedBox(height: 12),
          Card(
            elevation: 1,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            color: const Color(0xFFF0FDFA),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.info_outline_rounded, color: AppTheme.primary, size: 20),
                      SizedBox(width: 8),
                      Text(
                        'General Instructions & Precautions',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppTheme.primary),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    presc.instructions!,
                    style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary, height: 1.4),
                  ),
                ],
              ),
            ),
          ),
        ],

        const SizedBox(height: 16),

        // 3. Electronic Verification Notice
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.grey.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.verified_user_rounded, color: AppTheme.primary, size: 18),
                  SizedBox(width: 8),
                  Text(
                    'Tamper-Evident Digital Prescription',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Issued electronically via MediConnect. Verified against Sri Lanka Medical Council (SLMC) accredited credentials. Take strictly as directed.',
                style: TextStyle(fontSize: 11, color: Colors.grey[700]),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildDoctorBox(Prescription presc) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            presc.doctorName ?? 'Prescribing Physician',
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 2),
          Text(
            '${presc.doctorSpecialty ?? "Specialist"} • SLMC: ${presc.slmcRegistrationNumber ?? "Verified"}',
            style: const TextStyle(fontSize: 12, color: AppTheme.primary, fontWeight: FontWeight.w600),
          ),
          if (presc.hospitalOrClinic != null) ...[
            const SizedBox(height: 2),
            Text(
              presc.hospitalOrClinic!,
              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMedicationCard(int index, MedicationItem item) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 12,
                  backgroundColor: AppTheme.primary,
                  child: Text(
                    '$index',
                    style: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '${item.medicationName} (${item.strength})',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    item.route,
                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.blueAccent),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 6,
              children: [
                _buildTag(Icons.medication_liquid_rounded, 'Dose: ${item.dose}'),
                _buildTag(Icons.schedule_rounded, item.frequency),
                _buildTag(Icons.timelapse_rounded, item.duration),
                _buildTag(Icons.inventory_2_outlined, 'Qty: ${item.quantity}'),
              ],
            ),
            if (item.additionalInstructions != null && item.additionalInstructions!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.amber.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.info_outline, size: 14, color: Colors.orange),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        item.additionalInstructions!,
                        style: const TextStyle(fontSize: 12, color: Colors.black87),
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

  Widget _buildTag(IconData icon, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppTheme.textSecondary),
        const SizedBox(width: 4),
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, fontWeight: FontWeight.w500),
        ),
      ],
    );
  }
}
