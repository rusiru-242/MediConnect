import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/clinical_record.dart';
import '../../services/clinical_api_service.dart';

/// Screen allowing patients to review their longitudinal medical records,
/// upload external clinical documents (PDF, JPG, PNG), and view AI-grounded medical summaries.
class PatientMedicalRecordsScreen extends StatefulWidget {
  final ClinicalApiService? service;

  const PatientMedicalRecordsScreen({super.key, this.service});

  @override
  State<PatientMedicalRecordsScreen> createState() => _PatientMedicalRecordsScreenState();
}

class _PatientMedicalRecordsScreenState extends State<PatientMedicalRecordsScreen> {
  late final ClinicalApiService _service;
  List<PatientMedicalRecord> _records = [];
  bool _isLoading = false;
  String? _errorMessage;
  String _selectedCategory = 'ALL';

  final List<String> _categories = [
    'ALL',
    'consultation_note',
    'laboratory_result',
    'imaging_report',
    'medical_document',
    'diagnosis',
    'allergy',
  ];

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? ClinicalApiService();
    _loadRecords();
  }

  Future<void> _loadRecords() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final type = _selectedCategory == 'ALL' ? null : _selectedCategory;
      final results = await _service.getMedicalRecords(recordType: type);
      if (mounted) {
        setState(() {
          _records = results;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Failed to load medical records. Pull down to retry.';
          _isLoading = false;
        });
      }
    }
  }

  void _showAiSummarySheet() async {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _AiSummarySheet(service: _service),
    );
  }

  void _showUploadDialog() {
    final titleController = TextEditingController();
    final descController = TextEditingController();
    String selectedType = 'laboratory_result';
    DateTime selectedDate = DateTime.now();

    showDialog(
      context: context,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Row(
                children: [
                  Icon(Icons.upload_file, color: AppTheme.primary),
                  SizedBox(width: 8),
                  Text('Upload Medical Document', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: titleController,
                      decoration: const InputDecoration(
                        labelText: 'Document Title *',
                        hintText: 'e.g. Lipid Profile Lab Report',
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: selectedType,
                      decoration: const InputDecoration(labelText: 'Category *'),
                      items: const [
                        DropdownMenuItem(value: 'laboratory_result', child: Text('Laboratory Result')),
                        DropdownMenuItem(value: 'imaging_report', child: Text('Imaging Report (X-Ray, MRI)')),
                        DropdownMenuItem(value: 'discharge_summary', child: Text('Discharge Summary')),
                        DropdownMenuItem(value: 'medical_document', child: Text('General Medical Document')),
                      ],
                      onChanged: (val) {
                        if (val != null) setDialogState(() => selectedType = val);
                      },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: descController,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Notes / Observations',
                        hintText: 'Optional clinical notes',
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogCtx),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    if (titleController.text.trim().isEmpty) return;
                    Navigator.pop(dialogCtx);
                    // Upload sample PDF document bytes
                    final sampleBytes = '%PDF-1.4 Mock Clinical Report Data'.codeUnits;
                    try {
                      await _service.uploadMedicalDocument(
                        fileBytes: sampleBytes,
                        filename: '${titleController.text.trim().replaceAll(' ', '_')}.pdf',
                        title: titleController.text.trim(),
                        recordType: selectedType,
                        clinicalDate: selectedDate.toIso8601String().substring(0, 10),
                        description: descController.text.trim(),
                      );
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Document uploaded successfully.'), backgroundColor: Colors.green),
                        );
                        _loadRecords();
                      }
                    } catch (e) {
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Upload failed: $e'), backgroundColor: Colors.red),
                        );
                      }
                    }
                  },
                  child: const Text('Upload PDF'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Medical Records'),
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome, color: AppTheme.primary),
            tooltip: 'AI Medical Record Summary',
            onPressed: _showAiSummarySheet,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showUploadDialog,
        icon: const Icon(Icons.add),
        label: const Text('Upload Document'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadRecords,
        child: Column(
          children: [
            // Category filter chips
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: _categories.map((cat) {
                  final isSelected = _selectedCategory == cat;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      selected: isSelected,
                      label: Text(cat.replaceAll('_', ' ').toUpperCase(), style: const TextStyle(fontSize: 11)),
                      onSelected: (selected) {
                        setState(() => _selectedCategory = cat);
                        _loadRecords();
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
                      : _records.isEmpty
                          ? const Center(
                              child: Text('No medical records found in this category.', style: TextStyle(color: Colors.grey)),
                            )
                          : ListView.builder(
                              itemCount: _records.length,
                              padding: const EdgeInsets.all(16),
                              itemBuilder: (ctx, i) {
                                final record = _records[i];
                                final isClinician = record.sourceType == 'clinician_authored';
                                return Card(
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                  margin: const EdgeInsets.only(bottom: 12),
                                  child: ListTile(
                                    contentPadding: const EdgeInsets.all(16),
                                    leading: CircleAvatar(
                                      backgroundColor: isClinician ? Colors.blue.shade50 : Colors.green.shade50,
                                      child: Icon(
                                        record.hasAttachment ? Icons.attach_file : Icons.description,
                                        color: isClinician ? Colors.blue.shade700 : Colors.green.shade700,
                                      ),
                                    ),
                                    title: Text(record.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                                    subtitle: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const SizedBox(height: 4),
                                        Row(
                                          children: [
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                              decoration: BoxDecoration(
                                                color: isClinician ? Colors.blue.shade100 : Colors.green.shade100,
                                                borderRadius: BorderRadius.circular(4),
                                              ),
                                              child: Text(
                                                isClinician ? 'CLINICIAN AUTHORED' : 'PATIENT UPLOADED',
                                                style: TextStyle(
                                                  fontSize: 9,
                                                  fontWeight: FontWeight.bold,
                                                  color: isClinician ? Colors.blue.shade900 : Colors.green.shade900,
                                                ),
                                              ),
                                            ),
                                            const SizedBox(width: 8),
                                            Text(record.clinicalDate, style: const TextStyle(fontSize: 11, color: Colors.grey)),
                                          ],
                                        ),
                                        if (record.description != null) ...[
                                          const SizedBox(height: 6),
                                          Text(record.description!, maxLines: 2, overflow: TextOverflow.ellipsis),
                                        ],
                                      ],
                                    ),
                                    trailing: record.hasAttachment
                                        ? IconButton(
                                            icon: const Icon(Icons.download, color: AppTheme.primary),
                                            onPressed: () async {
                                              final messenger = ScaffoldMessenger.of(context);
                                              try {
                                                await _service.downloadDocumentFile(record.recordId);
                                                if (mounted) {
                                                  messenger.showSnackBar(
                                                    const SnackBar(content: Text('Document downloaded securely.')),
                                                  );
                                                }
                                              } catch (e) {
                                                if (mounted) {
                                                  messenger.showSnackBar(
                                                    SnackBar(content: Text('Download failed: $e')),
                                                  );
                                                }
                                              }
                                            },
                                          )
                                        : null,
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

class _AiSummarySheet extends StatefulWidget {
  final ClinicalApiService service;

  const _AiSummarySheet({required this.service});

  @override
  State<_AiSummarySheet> createState() => _AiSummarySheetState();
}

class _AiSummarySheetState extends State<_AiSummarySheet> {
  MedicalRecordSummary? _summary;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSummary();
  }

  Future<void> _loadSummary() async {
    try {
      final res = await widget.service.getMedicalRecordSummary();
      if (mounted) setState(() { _summary = res; _isLoading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _isLoading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: _isLoading
          ? const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()))
          : _error != null
              ? Center(child: Text('Error loading summary: $_error'))
              : SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.auto_awesome, color: AppTheme.primary),
                          const SizedBox(width: 8),
                          const Text('AI Medical Record Summary', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                          const Spacer(),
                          IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(color: Colors.blue.shade50, borderRadius: BorderRadius.circular(8)),
                        child: Text(_summary!.summary, style: const TextStyle(fontSize: 13, height: 1.4)),
                      ),
                      if (_summary!.diagnoses.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        const Text('Diagnoses:', style: TextStyle(fontWeight: FontWeight.bold)),
                        ..._summary!.diagnoses.map((d) => Text('• $d')),
                      ],
                      if (_summary!.documentedAllergies.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        const Text('Documented Allergies:', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red)),
                        ..._summary!.documentedAllergies.map((a) => Text('• $a', style: const TextStyle(color: Colors.red))),
                      ],
                      if (_summary!.activeMedications.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        const Text('Active Medications:', style: TextStyle(fontWeight: FontWeight.bold)),
                        ..._summary!.activeMedications.map((m) => Text('• $m')),
                      ],
                      const SizedBox(height: 16),
                      Text(
                        _summary!.aiDisclaimer,
                        style: const TextStyle(fontSize: 10, color: Colors.grey, fontStyle: FontStyle.italic),
                      ),
                    ],
                  ),
                ),
    );
  }
}
