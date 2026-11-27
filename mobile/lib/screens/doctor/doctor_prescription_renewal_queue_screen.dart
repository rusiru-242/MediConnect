import 'package:flutter/material.dart';

import '../../models/clinical_record.dart';
import '../../services/clinical_api_service.dart';

/// Screen allowing clinicians to review pending patient prescription renewal requests,
/// approve new prescriptions, request follow-up consultations, or reject with documented reasons.
class DoctorPrescriptionRenewalQueueScreen extends StatefulWidget {
  final ClinicalApiService? service;

  const DoctorPrescriptionRenewalQueueScreen({super.key, this.service});

  @override
  State<DoctorPrescriptionRenewalQueueScreen> createState() => _DoctorPrescriptionRenewalQueueScreenState();
}

class _DoctorPrescriptionRenewalQueueScreenState extends State<DoctorPrescriptionRenewalQueueScreen> {
  late final ClinicalApiService _service;
  List<PrescriptionRenewal> _renewals = [];
  bool _isLoading = false;
  String? _errorMessage;
  String _selectedStatus = 'requested';

  final List<String> _statuses = ['requested', 'approved', 'rejected', 'needs_consultation', 'ALL'];

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? ClinicalApiService();
    _loadQueue();
  }

  Future<void> _loadQueue() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final list = await _service.getPrescriptionRenewals(
        statusFilter: _selectedStatus == 'ALL' ? null : _selectedStatus,
      );
      if (mounted) {
        setState(() {
          _renewals = list;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Failed to load renewal queue.';
          _isLoading = false;
        });
      }
    }
  }

  void _handleReviewDecision(PrescriptionRenewal renewal, String decision) async {
    final reasonController = TextEditingController(
      text: decision == 'approve' ? 'Medication renewal approved following clinical review.' : '',
    );
    final consultDetailsController = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          decision == 'approve'
              ? 'Approve Prescription Renewal'
              : decision == 'reject'
                  ? 'Reject Prescription Renewal'
                  : 'Request Follow-up Consultation',
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Medication: ${renewal.medicationName}', style: const TextStyle(fontWeight: FontWeight.bold)),
              // A04: the doctor sees what an approval will issue. The renewal copies the original instructions
              // exactly; nothing is filled in or changed by the app.
              for (final field in const ['strength', 'dose', 'route', 'frequency', 'duration', 'quantity'])
                Text(
                  '${field[0].toUpperCase()}${field.substring(1)}: '
                  '${(renewal.medicationDetails[field]?.toString().trim().isNotEmpty ?? false) ? renewal.medicationDetails[field] : 'not stated'}',
                  key: Key('renewal_detail_$field'),
                  style: const TextStyle(fontSize: 13),
                ),
              if (decision == 'approve')
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: Text('Approving issues a new prescription with exactly these instructions from the original.',
                      style: TextStyle(fontSize: 12, color: Colors.grey)),
                ),
              const SizedBox(height: 12),
              TextField(
                controller: reasonController,
                decoration: InputDecoration(
                  labelText: decision == 'approve' ? 'Approval Notes' : 'Clinical Justification *',
                ),
              ),
              if (decision == 'needs_consultation') ...[
                const SizedBox(height: 12),
                TextField(
                  controller: consultDetailsController,
                  decoration: const InputDecoration(
                    labelText: 'Consultation Instructions *',
                    hintText: 'e.g. Please book a blood test and appointment before next refill',
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: decision == 'approve'
                  ? Colors.green
                  : decision == 'reject'
                      ? Colors.red
                      : Colors.orange,
            ),
            onPressed: () {
              if (reasonController.text.trim().isEmpty) return;
              Navigator.pop(ctx, true);
            },
            child: Text(
              decision == 'approve' ? 'Approve & Issue Rx' : decision == 'reject' ? 'Confirm Reject' : 'Request Consult',
            ),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _service.reviewPrescriptionRenewal(
          renewalId: renewal.renewalId,
          decision: decision,
          reason: reasonController.text.trim(),
          consultationDetails: consultDetailsController.text.trim().isEmpty ? null : consultDetailsController.text.trim(),
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Prescription renewal updated ($decision).'), backgroundColor: Colors.green),
          );
          _loadQueue();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Action failed: $e'), backgroundColor: Colors.red),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Prescription Renewal Queue'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadQueue,
        child: Column(
          children: [
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: _statuses.map((st) {
                  final isSelected = _selectedStatus == st;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      selected: isSelected,
                      label: Text(st.replaceAll('_', ' ').toUpperCase(), style: const TextStyle(fontSize: 11)),
                      onSelected: (val) {
                        setState(() => _selectedStatus = st);
                        _loadQueue();
                      },
                    ),
                  );
                }).toList(),
              ),
            ),
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _errorMessage != null
                      ? Center(child: Text(_errorMessage!))
                      : _renewals.isEmpty
                          ? const Center(
                              child: Text('No renewal requests in this category.', style: TextStyle(color: Colors.grey)),
                            )
                          : ListView.builder(
                              itemCount: _renewals.length,
                              padding: const EdgeInsets.all(16),
                              itemBuilder: (ctx, i) {
                                final r = _renewals[i];
                                final isPending = r.status == 'requested' || r.status == 'awaiting_review';
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
                                            Text(
                                              r.status.toUpperCase(),
                                              style: TextStyle(
                                                fontSize: 10,
                                                fontWeight: FontWeight.bold,
                                                color: r.status == 'approved' ? Colors.green : Colors.blue,
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 6),
                                        Text('Patient: ${r.patientName ?? r.patientUserId} • Requested: ${r.requestedAt.toIso8601String().substring(0, 10)}',
                                            style: const TextStyle(fontSize: 11, color: Colors.grey)),
                                        if (r.patientReason != null) ...[
                                          const SizedBox(height: 8),
                                          Text('Patient Reason: ${r.patientReason!}', style: const TextStyle(fontSize: 13)),
                                        ],
                                        if (isPending) ...[
                                          const SizedBox(height: 16),
                                          // A04-BUG-014: a Row overflowed by ~200 px on a phone (Approve was
                                          // cut off in release builds and the list failed to draw in debug).
                                          Wrap(
                                            alignment: WrapAlignment.end,
                                            spacing: 8,
                                            runSpacing: 8,
                                            children: [
                                              OutlinedButton(
                                                onPressed: () => _handleReviewDecision(r, 'reject'),
                                                child: const Text('Reject', style: TextStyle(color: Colors.red)),
                                              ),
                                              OutlinedButton(
                                                onPressed: () => _handleReviewDecision(r, 'needs_consultation'),
                                                child: const Text('Require Consult'),
                                              ),
                                              ElevatedButton(
                                                style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                                                onPressed: () => _handleReviewDecision(r, 'approve'),
                                                child: const Text('Approve'),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
            ),
          ],
        ),
      ),
    );
  }
}
