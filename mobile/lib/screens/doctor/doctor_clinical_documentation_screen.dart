import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/clinical_record.dart';
import '../../services/clinical_api_service.dart';

/// Screen allowing doctors to draft, AI-structure, edit, review, and digitally sign clinical SOAP notes.
class DoctorClinicalDocumentationScreen extends StatefulWidget {
  final String patientUserId;
  final String? patientName;
  final String? appointmentId;
  final ClinicalApiService? service;

  const DoctorClinicalDocumentationScreen({
    super.key,
    required this.patientUserId,
    this.patientName,
    this.appointmentId,
    this.service,
  });

  @override
  State<DoctorClinicalDocumentationScreen> createState() => _DoctorClinicalDocumentationScreenState();
}

class _DoctorClinicalDocumentationScreenState extends State<DoctorClinicalDocumentationScreen> {
  late final ClinicalApiService _service;
  ClinicalNote? _activeNote;
  bool _isLoading = false;

  final _chiefComplaintController = TextEditingController();
  final _hpiController = TextEditingController();
  final _pastHistoryController = TextEditingController();
  final _examController = TextEditingController();
  final _assessmentController = TextEditingController();
  final _planController = TextEditingController();
  final _followUpController = TextEditingController();
  final _rawNotesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? ClinicalApiService();
  }

  void _organizeWithAi() async {
    final raw = _rawNotesController.text.trim();
    if (raw.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter consultation notes to organize.')),
      );
      return;
    }

    setState(() => _isLoading = true);
    try {
      final draft = await _service.createClinicalNoteDraft(
        patientUserId: widget.patientUserId,
        appointmentId: widget.appointmentId,
        rawNotes: raw,
      );
      _populateFromNote(draft);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('AI SOAP draft generated. Review and edit before signing.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to generate draft: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _populateFromNote(ClinicalNote note) {
    setState(() {
      _activeNote = note;
      _chiefComplaintController.text = note.content.chiefComplaint;
      _hpiController.text = note.content.historyOfPresentIllness;
      _pastHistoryController.text = note.content.pastMedicalHistory ?? '';
      _examController.text = note.content.examinationFindings;
      _assessmentController.text = note.content.assessment;
      _planController.text = note.content.plan;
      _followUpController.text = note.content.followUpInstructions ?? '';
    });
  }

  void _signNote() async {
    if (_activeNote == null) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Digitally Sign Clinical Note'),
        content: const Text(
          'I certify that this consultation note accurately reflects my clinical evaluation and findings. '
          'Once signed, the note becomes immutable and any corrections will require a documented amendment.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sign Note'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      setState(() => _isLoading = true);
      try {
        final signed = await _service.signClinicalNote(_activeNote!.noteId);
        _populateFromNote(signed);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Clinical note digitally signed (SLMC: ${signed.slmcRegistrationNumber}).'),
              backgroundColor: Colors.green,
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Signing failed: $e'), backgroundColor: Colors.red),
          );
        }
      } finally {
        if (mounted) setState(() => _isLoading = false);
      }
    }
  }

  void _amendNote() async {
    if (_activeNote == null) return;
    final justificationCtrl = TextEditingController();
    final addendumCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Amend Signed Note'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: justificationCtrl,
              decoration: const InputDecoration(labelText: 'Clinical Justification *', hintText: 'Reason for amendment'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: addendumCtrl,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Addendum Content *', hintText: 'Updated notes or corrections'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              if (justificationCtrl.text.trim().isEmpty || addendumCtrl.text.trim().isEmpty) return;
              Navigator.pop(ctx);
              try {
                final amended = await _service.amendClinicalNote(
                  noteId: _activeNote!.noteId,
                  justification: justificationCtrl.text.trim(),
                  addendum: addendumCtrl.text.trim(),
                );
                _populateFromNote(amended);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Clinical note amended successfully.')),
                  );
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Amendment failed: $e'), backgroundColor: Colors.red),
                  );
                }
              }
            },
            child: const Text('Submit Amendment'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isSigned = _activeNote?.status == 'signed' || _activeNote?.status == 'amended';

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.patientName != null ? 'SOAP Note: ${widget.patientName}' : 'Clinical Documentation'),
        actions: [
          if (isSigned)
            IconButton(icon: const Icon(Icons.edit_note), tooltip: 'Amend Note', onPressed: _amendNote),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Status Banner
                  if (_activeNote != null)
                    Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isSigned ? Colors.green.shade50 : Colors.amber.shade50,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: isSigned ? Colors.green.shade300 : Colors.amber.shade300),
                      ),
                      child: Row(
                        children: [
                          Icon(isSigned ? Icons.verified : Icons.edit, color: isSigned ? Colors.green : Colors.amber.shade800),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              isSigned
                                  ? 'SIGNED by Dr. ${_activeNote!.doctorName ?? ''} (SLMC: ${_activeNote!.slmcRegistrationNumber ?? ''}) on ${_activeNote!.signedAt?.toIso8601String().substring(0, 16) ?? ''}'
                                  : 'DRAFT (Under Review) • Not yet signed',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: isSigned ? Colors.green.shade900 : Colors.amber.shade900,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                  // AI Fast Draft Input
                  if (!isSigned) ...[
                    Card(
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      color: Colors.blue.shade50.withValues(alpha: 0.5),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Row(
                              children: [
                                Icon(Icons.auto_awesome, color: AppTheme.primary, size: 20),
                                SizedBox(width: 8),
                                Text('AI Clinical Documentation Assistant', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                              ],
                            ),
                            const SizedBox(height: 8),
                            TextField(
                              controller: _rawNotesController,
                              maxLines: 3,
                              decoration: const InputDecoration(
                                hintText: 'Enter shorthand consultation observations, symptoms, or findings...',
                                fillColor: Colors.white,
                                filled: true,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Align(
                              alignment: Alignment.centerRight,
                              child: ElevatedButton.icon(
                                onPressed: _organizeWithAi,
                                icon: const Icon(Icons.auto_awesome, size: 16),
                                label: const Text('Organize into SOAP Draft'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Structured SOAP Inputs
                  const Text('Subjective', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _chiefComplaintController,
                    enabled: !isSigned,
                    decoration: const InputDecoration(labelText: 'Chief Complaint *'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _hpiController,
                    enabled: !isSigned,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'History of Present Illness (HPI) *'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _pastHistoryController,
                    enabled: !isSigned,
                    decoration: const InputDecoration(labelText: 'Past Medical History'),
                  ),

                  const SizedBox(height: 20),
                  const Text('Objective', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _examController,
                    enabled: !isSigned,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Physical Examination Findings *'),
                  ),

                  const SizedBox(height: 20),
                  const Text('Assessment', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _assessmentController,
                    enabled: !isSigned,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Clinical Impression / Assessment *'),
                  ),

                  const SizedBox(height: 20),
                  const Text('Plan', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _planController,
                    enabled: !isSigned,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Management & Treatment Plan *'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _followUpController,
                    enabled: !isSigned,
                    decoration: const InputDecoration(labelText: 'Follow-up Instructions'),
                  ),

                  const SizedBox(height: 24),
                  if (!isSigned)
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          backgroundColor: Colors.green,
                        ),
                        onPressed: _activeNote != null ? _signNote : null,
                        icon: const Icon(Icons.check_circle),
                        label: const Text('Review & Sign Clinical Note', style: TextStyle(fontWeight: FontWeight.bold)),
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}
