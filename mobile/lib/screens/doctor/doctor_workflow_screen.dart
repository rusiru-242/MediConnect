import 'dart:math';

import 'package:flutter/material.dart';

import '../../core/network/api_client.dart';
import 'create_care_plan_screen.dart';

const _base = '/doctor/workflow';

class DoctorWorkflowScreen extends StatefulWidget {
  const DoctorWorkflowScreen({super.key, this.apiClient});

  final ApiClient? apiClient;

  @override
  State<DoctorWorkflowScreen> createState() => _DoctorWorkflowScreenState();
}

class _DoctorWorkflowScreenState extends State<DoctorWorkflowScreen> {
  late final ApiClient _api = widget.apiClient ?? ApiClient();
  final _message = TextEditingController();
  final _random = Random.secure();
  late Future<dynamic> _data = _api.get('$_base/queue');
  Map<String, dynamic>? _selected;
  Map<String, dynamic>? _reply;
  String? _error;
  bool _busy = false;
  bool _week = false;

  DateTime get _today =>
      DateTime.now().toUtc().add(const Duration(hours: 5, minutes: 30));
  String _date(DateTime day) => day.toIso8601String().split('T').first;

  @override
  void dispose() {
    _message.dispose();
    super.dispose();
  }

  void _refresh() => setState(() {
    final start = _date(_today);
    final end = _date(_today.add(const Duration(days: 6)));
    _data = _api.get(
      _week ? '$_base/schedule?start=$start&end=$end' : '$_base/queue',
    );
  });

  Future<void> _run(Future<void> Function() operation) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await operation();
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'The request could not be completed. Refresh and try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool> _confirm(String title, String body) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          content: Text(body),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirm'),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> _queueAction(
    Map<String, dynamic> row,
    String action,
    String label,
  ) async {
    final position = action == 'reorder'
        ? await showDialog<int>(
            context: context,
            builder: (context) => SimpleDialog(
              title: const Text('Queue priority position'),
              children: [
                for (var i = 1; i <= 10; i++)
                  SimpleDialogOption(
                    onPressed: () => Navigator.pop(context, i),
                    child: Text('$i'),
                  ),
              ],
            ),
          )
        : null;
    if (!mounted || (action == 'reorder' && position == null)) return;
    if (!await _confirm(
      label,
      'Apply this change to ${row['patientName'] ?? 'the selected patient'}?',
    )) {
      return;
    }
    await _run(() async {
      await _api.post(
        '$_base/queue/${row['id']}',
        body: {
          'action': action,
          'version': row['queueVersion'],
          'confirm': true,
          'requestId': List.generate(
            24,
            (_) => _random.nextInt(16).toRadixString(16),
          ).join(),
          if (position != null) 'position': position,
        },
      );
      if (mounted) _refresh();
    });
  }

  Future<void> _ask([String? prompt]) async {
    final message = prompt ?? _message.text.trim();
    if (message.isEmpty) return;
    await _run(() async {
      final response = await _api.post(
        '$_base/assistant',
        body: {
          'message': message,
          if (_selected != null) 'appointmentId': _selected!['id'],
        },
      );
      if (mounted) {
        setState(() => _reply = Map<String, dynamic>.from(response as Map));
      }
    });
  }

  Future<void> _approve(Map draft) async {
    if (!await _confirm(
      'Queue appointment reminders',
      'Send this in-app message to ${draft['count']} eligible bookings?',
    )) {
      return;
    }
    await _run(() async {
      final result = await _api.post(
        '$_base/reminders/${draft['date']}',
        body: {'token': draft['token'], 'confirm': true},
      );
      if (mounted) {
        setState(
          () => _reply = {
            'message': 'Reminder processing status',
            'result': result,
          },
        );
      }
    });
  }

  Future<void> _viewPreparation(Map<String, dynamic> row) async {
    setState(() => _selected = row);
    await _ask('Consultation preparation summary');
  }

  Widget _card(Map<String, dynamic> row) {
    final state = row['queueStatus'];
    final actions = switch (state) {
      'scheduled' => {'checked_in': 'Check in', 'no_show': 'Mark no-show'},
      'checked_in' => {
        'waiting': 'Set waiting',
        'in_consultation': 'Start',
        'reorder': 'Reorder',
        'no_show': 'Mark no-show',
      },
      'waiting' => {
        'in_consultation': 'Start',
        'reorder': 'Reorder',
        'no_show': 'Mark no-show',
      },
      'in_consultation' => {'completed': 'Complete'},
      _ => <String, String>{},
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${row['time']}  ${row['patientName'] ?? 'Patient'}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text('${row['date']} · ${state.toString().replaceAll('_', ' ')}'),
            Text('Booking reference ${row['id']}'),
            if (row['queueOrder'] != null)
              Text('Queue position ${row['queueOrder']}'),
            if (row['estimatedWaitMinutes'] != null)
              Text('Estimated wait ${row['estimatedWaitMinutes']} min'),
            Wrap(
              children: [
                if (state != 'cancelled')
                  TextButton(
                    onPressed: _busy ? null : () => _viewPreparation(row),
                    child: const Text('Preparation'),
                  ),
                if (row['date'] == _date(_today))
                  for (final action in actions.entries)
                    TextButton(
                      onPressed: _busy
                          ? null
                          : () => _queueAction(row, action.key, action.value),
                      child: Text(action.value),
                    ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _result(Map<String, dynamic> reply) {
    final draft = reply['reminder'] as Map?;
    final result = reply['result'] as Map?;
    final sources = result?['sources'] as Map?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(reply['message'].toString()),
            if (draft != null) ...[
              Text(draft['title'].toString()),
              Text(draft['body'].toString()),
              Text('${draft['count']} recipients · In-app'),
              if (draft['statuses'] case final Map statuses) _fields(statuses),
              FilledButton(
                onPressed: _busy || draft['count'] == 0
                    ? null
                    : () => _approve(draft),
                child: const Text('Approve reminder'),
              ),
            ],
            if (reply['followUpDate'] != null)
              FilledButton(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => CreateCarePlanScreen(
                      appointmentId: reply['appointmentId'] as String,
                      patientName: _selected?['patientName'] as String?,
                      initialFollowUpDate: DateTime.tryParse(
                        reply['followUpDate'] as String,
                      ),
                    ),
                  ),
                ),
                child: Text('Review follow-up for ${reply['followUpDate']}'),
              ),
            if (sources != null) ...[
              Text(result!['label'].toString()),
              if (result['appointment'] case final Map appointment)
                _fields(appointment),
              if (result['patientReportedReason'] != null)
                Text(
                  'Patient-reported reason: ${result['patientReportedReason']}',
                ),
              for (final section in sources.entries) ...[
                const SizedBox(height: 8),
                Text(switch (section.key) {
                  'priorRecords' => 'Prior clinician records',
                  'prescriptions' => 'Prescription records',
                  _ => 'Follow-up plans',
                }),
                if ((section.value as List).isEmpty)
                  const Text('No accessible records found.'),
                for (final record in section.value as List)
                  _fields(record as Map),
              ],
            ] else if (result?['followUps'] case final List plans) ...[
              for (final plan in plans.cast<Map>())
                ListTile(
                  title: Text('Follow-up ${plan['followUpDate']}'),
                  subtitle: Text(plan['status'].toString()),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () =>
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => CreateCarePlanScreen(
                            appointmentId: plan['appointmentId'] as String?,
                            planId: plan['id'] as String,
                          ),
                        ),
                      ).then((_) {
                        if (mounted) _ask('List my follow-ups');
                      }),
                ),
            ] else if (result != null)
              _fields(result),
          ],
        ),
      ),
    );
  }

  Widget _fields(Map fields) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final entry in fields.entries)
          if (entry.value case final List rows)
            for (final row in rows)
              if (row is Map) _fields(row) else Text(row.toString())
          else if (entry.value case final Map value)
            _fields(value)
          else if (entry.value != null)
            Text('${entry.key}: ${entry.value}'),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Clinic workflow'),
      actions: [
        IconButton(
          tooltip: 'Refresh',
          onPressed: _busy ? null : _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            ChoiceChip(
              label: const Text('Today’s queue'),
              selected: !_week,
              onSelected: (_) {
                _week = false;
                _refresh();
              },
            ),
            ChoiceChip(
              label: const Text('Next 7 days'),
              selected: _week,
              onSelected: (_) {
                _week = true;
                _refresh();
              },
            ),
            ActionChip(
              label: const Text('Follow-ups'),
              onPressed: _busy ? null : () => _ask('List my follow-ups'),
            ),
            ActionChip(
              label: const Text('Analytics'),
              onPressed: _busy ? null : () => _ask('Week analytics'),
            ),
            ActionChip(
              label: const Text('Tomorrow’s reminders'),
              onPressed: _busy
                  ? null
                  : () => _ask('Tomorrow appointment reminder'),
            ),
            ActionChip(
              label: const Text('Manage availability'),
              onPressed: () =>
                  Navigator.pushNamed(context, '/doctor/manage-availability'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _message,
          decoration: InputDecoration(
            labelText: 'Ask the doctor assistant',
            helperText: _selected == null
                ? null
                : 'Selected: ${_selected!['patientName'] ?? 'appointment'}',
            suffixIcon: IconButton(
              tooltip: 'Ask',
              onPressed: _busy ? null : () => _ask(),
              icon: const Icon(Icons.send),
            ),
          ),
          onSubmitted: (_) => _ask(),
        ),
        if (_busy) const LinearProgressIndicator(),
        if (_error != null)
          Text(
            _error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        if (_reply != null) _result(_reply!),
        FutureBuilder<dynamic>(
          future: _data,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return TextButton(
                onPressed: _refresh,
                child: const Text('Could not load appointments. Retry'),
              );
            }
            final rows =
                (snapshot.data as Map?)?['appointments'] as List? ?? [];
            if (rows.isEmpty) {
              return const Padding(
                padding: EdgeInsets.all(16),
                child: Text('No appointments in this period.'),
              );
            }
            return Column(
              children: [
                for (final row in rows)
                  _card(Map<String, dynamic>.from(row as Map)),
              ],
            );
          },
        ),
      ],
    ),
  );
}
