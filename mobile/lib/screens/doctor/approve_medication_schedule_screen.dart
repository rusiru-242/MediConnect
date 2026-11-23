import 'package:flutter/material.dart';

import '../../core/network/api_client.dart';

class ApproveMedicationScheduleScreen extends StatefulWidget {
  final Map<String, dynamic> prescription;
  const ApproveMedicationScheduleScreen({
    super.key,
    required this.prescription,
  });
  @override
  State<ApproveMedicationScheduleScreen> createState() =>
      _ApproveMedicationScheduleScreenState();
}

class _ApproveMedicationScheduleScreenState
    extends State<ApproveMedicationScheduleScreen> {
  final _api = ApiClient();
  final _times = TextEditingController();
  final _start = TextEditingController();
  final _end = TextEditingController();
  late final Future<dynamic> _details = _api.get('/prescriptions/${Uri.encodeComponent(widget.prescription['prescriptionId'].toString())}');
  int _index = 0;
  bool _busy = false;
  String? _message;
  late Future<dynamic> _activity = _api.get('$_path/activity');
  String get _path =>
      '/care-automation/prescriptions/${Uri.encodeComponent(widget.prescription['prescriptionId'].toString())}';

  @override
  void dispose() {
    _times.dispose();
    _start.dispose();
    _end.dispose();
    super.dispose();
  }

  Future<void> _submit(bool approve) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          approve
              ? 'Approve exact reminder times?'
              : 'Stop scheduled reminders?',
        ),
        content: const Text(
          'This changes reminders associated with this prescription.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Back'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      if (approve) {
        await _api.put(
          '$_path/schedule',
          body: {
            'medicationIndex': _index,
            'times': _times.text
                .split(',')
                .map((value) => value.trim())
                .toList(),
            'startDate': _start.text.trim(),
            'endDate': _end.text.trim(),
            'confirm': true,
          },
        );
      } else {
        await _api.delete('$_path/schedule/$_index');
      }
      if (mounted) {
        setState(
          () => _message = approve
              ? 'Schedule approved.'
              : 'Schedule discontinued.',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _message = 'The schedule could not be saved. Check the prescription, dates and exact times.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
    future: _details,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      }
      if (snapshot.hasError || snapshot.data is! Map) {
        return Scaffold(appBar: AppBar(title: const Text('Medication reminders')),
                        body: const Center(child: Text('Could not load the authorized prescription.')));
      }
      return _buildPrescription(snapshot.data as Map);
    },
  );

  Widget _buildPrescription(Map prescription) {
    final items = (prescription['medicationItems'] as List? ?? [])
        .whereType<Map>()
        .toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Medication reminders')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (items.isEmpty)
            const Text('No prescribed medication is available for approval.'),
          if (items.isNotEmpty) ...[
            DropdownButton<int>(
              value: _index,
              items: [
                for (var i = 0; i < items.length; i++)
                  DropdownMenuItem(
                    value: i,
                    child: Text(items[i]['medicationName'].toString()),
                  ),
              ],
              onChanged: _busy
                  ? null
                  : (value) => setState(() => _index = value!),
            ),
            Text(
              '${items[_index]['dose']} · ${items[_index]['frequency']} · ${items[_index]['duration']}',
            ),
            const Text(
              'Enter times in Sri Lanka time. Use one exact time per prescribed daily dose.',
            ),
            TextField(
              controller: _times,
              decoration: const InputDecoration(
                labelText: 'Times separated by commas (HH:mm)',
              ),
            ),
            TextField(
              controller: _start,
              decoration: const InputDecoration(
                labelText: 'Start date (YYYY-MM-DD)',
              ),
            ),
            TextField(
              controller: _end,
              decoration: const InputDecoration(
                labelText: 'Last date (YYYY-MM-DD)',
              ),
            ),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  onPressed: _busy ? null : () => _submit(true),
                  child: const Text('Approve reminders'),
                ),
                TextButton(
                  onPressed: _busy ? null : () => _submit(false),
                  child: const Text('Discontinue'),
                ),
              ],
            ),
          ],
          if (_message != null) Text(_message!),
          const Divider(),
          const Text('Patient-reported activity'),
          FutureBuilder<dynamic>(
            future: _activity,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const LinearProgressIndicator();
              }
              if (snapshot.hasError) {
                return TextButton(
                  onPressed: () =>
                      setState(() => _activity = _api.get('$_path/activity')),
                  child: const Text('Could not load activity. Retry'),
                );
              }
              final rows = (snapshot.data as List).whereType<Map>();
              if (rows.isEmpty) {
                return const Text('No patient actions recorded.');
              }
              return Column(
                children: [
                  for (final row in rows)
                    ListTile(
                      title: Text(row['action']?.toString() ?? 'Corrected'),
                      subtitle: Text(row['scheduledAt'].toString()),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
