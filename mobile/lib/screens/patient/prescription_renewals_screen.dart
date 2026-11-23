import 'package:flutter/material.dart';

import '../../models/clinical_record.dart';
import '../../services/clinical_api_service.dart';

/// Screen allowing patients to track prescription renewal requests and submit new requests.
class PrescriptionRenewalsScreen extends StatefulWidget {
  final ClinicalApiService? service;

  const PrescriptionRenewalsScreen({super.key, this.service});

  @override
  State<PrescriptionRenewalsScreen> createState() => _PrescriptionRenewalsScreenState();
}

class _PrescriptionRenewalsScreenState extends State<PrescriptionRenewalsScreen> {
  late final ClinicalApiService _service;
  List<PrescriptionRenewal> _renewals = [];
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? ClinicalApiService();
    _loadRenewals();
  }

  Future<void> _loadRenewals() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final list = await _service.getPrescriptionRenewals();
      if (mounted) {
        setState(() {
          _renewals = list;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Failed to load renewal requests.';
          _isLoading = false;
        });
      }
    }
  }

  void _showRequestRenewalDialog() {
    final rxIdController = TextEditingController();
    final medNameController = TextEditingController();
    final reasonController = TextEditingController();

    showDialog(
      context: context,
      builder: (dialogCtx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Request Prescription Renewal', style: TextStyle(fontWeight: FontWeight.bold)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: rxIdController,
                  decoration: const InputDecoration(
                    labelText: 'Original Prescription ID *',
                    hintText: 'e.g. RX-20261018-XXXX',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: medNameController,
                  decoration: const InputDecoration(
                    labelText: 'Medication Name *',
                    hintText: 'e.g. Losartan 50mg',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: reasonController,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Reason for Renewal',
                    hintText: 'e.g. Regular monthly maintenance supply',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogCtx), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () async {
                final rxId = rxIdController.text.trim();
                final med = medNameController.text.trim();
                if (rxId.isEmpty || med.isEmpty) return;
                Navigator.pop(dialogCtx);

                try {
                  await _service.requestPrescriptionRenewal(
                    originalPrescriptionId: rxId,
                    medicationName: med,
                    patientReason: reasonController.text.trim().isEmpty ? null : reasonController.text.trim(),
                  );
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Renewal request submitted for clinician review.'), backgroundColor: Colors.green),
                    );
                    _loadRenewals();
                  }
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Failed: $e'), backgroundColor: Colors.red),
                    );
                  }
                }
              },
              child: const Text('Submit Request'),
            ),
          ],
        );
      },
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'approved':
        return Colors.green;
      case 'rejected':
        return Colors.red;
      case 'needs_consultation':
        return Colors.orange;
      case 'awaiting_review':
      case 'requested':
      default:
        return Colors.blue;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Prescription Renewals'),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showRequestRenewalDialog,
        icon: const Icon(Icons.add),
        label: const Text('Request Renewal'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadRenewals,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _errorMessage != null
                ? Center(child: Text(_errorMessage!))
                : _renewals.isEmpty
                    ? const Center(
                        child: Text('No prescription renewal requests on record.', style: TextStyle(color: Colors.grey)),
                      )
                    : ListView.builder(
                        itemCount: _renewals.length,
                        padding: const EdgeInsets.all(16),
                        itemBuilder: (ctx, i) {
                          final r = _renewals[i];
                          final statusColor = _getStatusColor(r.status);
                          return Card(
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            margin: const EdgeInsets.only(bottom: 12),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          r.medicationName,
                                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                        decoration: BoxDecoration(
                                          color: statusColor.withValues(alpha: 0.1),
                                          borderRadius: BorderRadius.circular(6),
                                          border: Border.all(color: statusColor.withValues(alpha: 0.4)),
                                        ),
                                        child: Text(
                                          r.status.replaceAll('_', ' ').toUpperCase(),
                                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: statusColor),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    'Original Rx: ${r.originalPrescriptionId} • Requested: ${r.requestedAt.toIso8601String().substring(0, 10)}',
                                    style: const TextStyle(fontSize: 11, color: Colors.grey),
                                  ),
                                  if (r.patientReason != null) ...[
                                    const SizedBox(height: 8),
                                    Text('Reason: ${r.patientReason!}', style: const TextStyle(fontSize: 13)),
                                  ],
                                  if (r.doctorDecisionReason != null) ...[
                                    const SizedBox(height: 8),
                                    Container(
                                      padding: const EdgeInsets.all(8),
                                      decoration: BoxDecoration(
                                        color: Colors.grey.shade100,
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        'Doctor Response: ${r.doctorDecisionReason!}',
                                        style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic),
                                      ),
                                    ),
                                  ],
                                  if (r.resultingPrescriptionId != null) ...[
                                    const SizedBox(height: 6),
                                    Text(
                                      'Issued Prescription ID: ${r.resultingPrescriptionId}',
                                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.green),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          );
                        },
                      ),
      ),
    );
  }
}
