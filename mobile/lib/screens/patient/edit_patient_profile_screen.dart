import 'package:flutter/material.dart';

import '../../core/network/api_exceptions.dart';
import '../../core/theme/app_theme.dart';
import '../../models/patient_profile.dart';
import '../../services/profile_service.dart';

/// R02: the patient edits their own name and patient-reported health details. Every value is optional; an empty
/// field clears it. "Not provided", "No known allergies" and "I have allergies" are separate, explicit choices.
/// The server re-validates everything (ranges, phone format, allergy consistency).
class EditPatientProfileScreen extends StatefulWidget {
  final PatientProfile profile;
  final ProfileService service;

  const EditPatientProfileScreen({
    super.key,
    required this.profile,
    required this.service,
  });

  @override
  State<EditPatientProfileScreen> createState() =>
      _EditPatientProfileScreenState();
}

class _EditPatientProfileScreenState extends State<EditPatientProfileScreen> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.profile.fullName);
  late final _height = TextEditingController(
    text: _num(widget.profile.heightCm),
  );
  late final _weight = TextEditingController(
    text: _num(widget.profile.weightKg),
  );
  late final _allergies = TextEditingController(
    text: widget.profile.allergies.join(', '),
  );
  late final _contactName = TextEditingController(
    text: widget.profile.emergencyContact?.name ?? '',
  );
  late final _contactRel = TextEditingController(
    text: widget.profile.emergencyContact?.relationship ?? '',
  );
  late final _contactPhone = TextEditingController(
    text: widget.profile.emergencyContact?.phone ?? '',
  );
  late String _allergyStatus = widget.profile.allergyStatus;
  bool _saving = false;
  String? _error;

  static String _num(double? v) =>
      v == null
          ? ''
          : (v == v.roundToDouble()
              ? v.toStringAsFixed(0)
              : v.toStringAsFixed(1));

  @override
  void dispose() {
    for (final c in [
      _name,
      _height,
      _weight,
      _allergies,
      _contactName,
      _contactRel,
      _contactPhone,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _range(String? v, double min, double max, String label) {
    final text = (v ?? '').trim();
    if (text.isEmpty) return null;
    final n = double.tryParse(text);
    if (n == null || n < min || n > max) {
      return '$label must be between ${min.toStringAsFixed(0)} and ${max.toStringAsFixed(0)}';
    }
    return null;
  }

  List<String> get _allergyItems =>
      _allergies.text
          .split(',')
          .map((e) => e.trim())
          .where((e) => e.isNotEmpty)
          .toList();

  Future<void> _save() async {
    setState(() => _error = null);
    if (!_form.currentState!.validate()) return;
    final p = widget.profile;
    final changes = <String, dynamic>{};
    final name = _name.text.trim();
    if (name != p.fullName) changes['fullName'] = name;
    final h = double.tryParse(_height.text.trim());
    if (h != p.heightCm) changes['heightCm'] = h;
    final w = double.tryParse(_weight.text.trim());
    if (w != p.weightKg) changes['weightKg'] = w;
    final items =
        _allergyStatus == PatientProfile.hasAllergies
            ? _allergyItems
            : <String>[];
    if (_allergyStatus != p.allergyStatus ||
        items.join('|') != p.allergies.join('|')) {
      changes['allergyStatus'] = _allergyStatus;
      changes['allergies'] = items;
    }
    final cName = _contactName.text.trim(),
        cPhone = _contactPhone.text.trim(),
        cRel = _contactRel.text.trim();
    final contact =
        cName.isEmpty && cPhone.isEmpty
            ? null
            : EmergencyContact(
              name: cName,
              relationship: cRel.isEmpty ? null : cRel,
              phone: cPhone,
            );
    final before = p.emergencyContact;
    if ((contact == null) != (before == null) ||
        (contact != null &&
            (contact.name != before!.name ||
                contact.phone != before.phone ||
                (contact.relationship ?? '') != (before.relationship ?? '')))) {
      changes['emergencyContact'] = contact?.toJson();
    }
    if (changes.isEmpty) {
      Navigator.of(context).pop();
      return;
    }
    setState(() => _saving = true);
    try {
      final updated = await widget.service.updateProfile(changes);
      if (mounted) Navigator.of(context).pop(updated);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error =
            e is ApiException && e.message.isNotEmpty
                ? e.message
                : 'Your changes could not be saved. Please try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Profile')),
      body: SafeArea(
        child: Form(
          key: _form,
          // A Column (not a lazy ListView) so every field exists and is validated, even when scrolled off screen.
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextFormField(
                  key: const Key('edit_full_name'),
                  controller: _name,
                  decoration: const InputDecoration(labelText: 'Full name'),
                  validator:
                      (v) =>
                          (v ?? '').trim().length < 2
                              ? 'Enter your full name'
                              : null,
                ),
                const SizedBox(height: 20),
                const Text(
                  'Health details (optional, entered by you)',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Leave a field empty if you prefer not to say. Your doctor confirms clinical details separately.',
                  style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        key: const Key('edit_height'),
                        controller: _height,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Height (cm)',
                        ),
                        validator: (v) => _range(v, 50, 250, 'Height'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        key: const Key('edit_weight'),
                        controller: _weight,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Weight (kg)',
                        ),
                        validator: (v) => _range(v, 2, 350, 'Weight'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                const Text(
                  'Allergies',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                RadioGroup<String>(
                  groupValue: _allergyStatus,
                  onChanged:
                      (v) => setState(
                        () => _allergyStatus = v ?? PatientProfile.notProvided,
                      ),
                  child: const Column(
                    children: [
                      RadioListTile<String>(
                        key: Key('allergy_not_provided'),
                        value: PatientProfile.notProvided,
                        title: Text('Not provided'),
                        contentPadding: EdgeInsets.zero,
                      ),
                      RadioListTile<String>(
                        key: Key('allergy_none_known'),
                        value: PatientProfile.noneKnown,
                        title: Text('No known allergies'),
                        contentPadding: EdgeInsets.zero,
                      ),
                      RadioListTile<String>(
                        key: Key('allergy_has'),
                        value: PatientProfile.hasAllergies,
                        title: Text('I have allergies'),
                        contentPadding: EdgeInsets.zero,
                      ),
                    ],
                  ),
                ),
                if (_allergyStatus == PatientProfile.hasAllergies)
                  TextFormField(
                    key: const Key('edit_allergies'),
                    controller: _allergies,
                    decoration: const InputDecoration(
                      labelText: 'Allergies (separate with commas)',
                    ),
                    validator: (_) {
                      final items = _allergyItems;
                      if (items.isEmpty) return 'List at least one allergy';
                      if (items.length > 20) return 'List at most 20 allergies';
                      if (items.any((e) => e.length > 80)) {
                        return 'Each allergy must be 80 characters or fewer';
                      }
                      return null;
                    },
                  ),
                const SizedBox(height: 20),
                const Text(
                  'Emergency contact',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                TextFormField(
                  key: const Key('edit_contact_name'),
                  controller: _contactName,
                  decoration: const InputDecoration(labelText: 'Name'),
                  validator:
                      (v) =>
                          (v ?? '').trim().isEmpty &&
                                  _contactPhone.text.trim().isNotEmpty
                              ? 'Enter a name'
                              : null,
                ),
                TextFormField(
                  key: const Key('edit_contact_relationship'),
                  controller: _contactRel,
                  decoration: const InputDecoration(
                    labelText: 'Relationship (optional)',
                  ),
                  validator:
                      (v) =>
                          (v ?? '').trim().length > 40
                              ? 'Use 40 characters or fewer'
                              : null,
                ),
                TextFormField(
                  key: const Key('edit_contact_phone'),
                  controller: _contactPhone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Phone'),
                  validator: (v) {
                    final text = (v ?? '').trim();
                    if (text.isEmpty) {
                      return _contactName.text.trim().isNotEmpty
                          ? 'Enter a phone number'
                          : null;
                    }
                    return RegExp(r'^\+?[0-9][0-9 ()\-]{6,19}$').hasMatch(text)
                        ? null
                        : 'Enter a valid phone number';
                  },
                ),
                const SizedBox(height: 20),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(
                      _error!,
                      key: const Key('edit_error'),
                      style: const TextStyle(color: AppTheme.error),
                    ),
                  ),
                FilledButton(
                  key: const Key('edit_save'),
                  onPressed: _saving ? null : _save,
                  child: Text(_saving ? 'Saving...' : 'Save'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
