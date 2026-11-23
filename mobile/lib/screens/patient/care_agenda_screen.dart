import 'dart:math';

import 'package:flutter/material.dart';

import '../../core/network/api_client.dart';
import 'ai_care_assistant_screen.dart';

const _base = '/care-automation';

class CareAgendaScreen extends StatefulWidget {
  final String? eventId;
  final ApiClient? apiClient;
  const CareAgendaScreen({super.key, this.eventId, this.apiClient});

  @override
  State<CareAgendaScreen> createState() => _CareAgendaScreenState();
}

class _CareAgendaScreenState extends State<CareAgendaScreen> {
  late final _api = widget.apiClient ?? ApiClient();
  late Future<dynamic> _data = _fetch();
  int _days = 1;
  bool _busy = false;
  String? _error;
  String? _lastAction;
  String? _request;

  Future<dynamic> _fetch() => _api.get(
    widget.eventId == null
        ? '$_base/agenda?days=$_days'
        : '$_base/events/${widget.eventId}',
  );
  void _refresh() => setState(() => _data = _fetch());

  Future<void> _action(String action) async {
    if (_busy) return;
    if (_lastAction != action || _request == null) {
      final random = Random.secure();
      _request = List.generate(
        24,
        (_) => random.nextInt(16).toRadixString(16),
      ).join();
      _lastAction = action;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final response = await _api.post(
        '$_base/events/${widget.eventId}/actions',
        body: {'action': action, 'requestId': _request, 'snoozeMinutes': 15},
      );
      if (mounted) {
        setState(() {
          _request = null;
          _data = Future.value(response);
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Could not save this action. Refresh and try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _date(Object? raw) {
    final value = DateTime.tryParse(raw?.toString() ?? '');
    if (value == null) return '';
    final sriLanka = value.toUtc().add(const Duration(hours: 5, minutes: 30));
    final locale = MaterialLocalizations.of(context);
    return '${locale.formatShortDate(sriLanka)} · ${locale.formatTimeOfDay(TimeOfDay.fromDateTime(sriLanka))} (Sri Lanka)';
  }

  Widget _details(Map item) {
    final medication = item['kind'] == 'medication';
    final time = DateTime.tryParse(item['scheduledAt'].toString());
    final action = item['action'];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          item['title'].toString(),
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        Text(_date(item['scheduledAt'])),
        Text(
          item['source'] == 'patient_entered'
              ? 'Patient-entered schedule'
              : 'Clinician record',
        ),
        if (item['location'] != null) Text(item['location'].toString()),
        if (item['instructions'] != null)
          SelectableText(item['instructions'].toString())
        else if (item['kind'] == 'test')
          const Text('No preparation instructions are on file.'),
        if (action != null) Text('Status: $action (patient-reported)'),
        if (_error != null) Text(_error!),
        if (_busy) const LinearProgressIndicator(),
        if (item['appointmentId'] != null)
          TextButton(
            onPressed: () => Navigator.pushNamed(
              context,
              '/patient/appointment-detail',
              arguments: {'appointmentId': item['appointmentId']},
            ),
            child: const Text('View appointment'),
          )
        else
          Wrap(
            spacing: 8,
            children: [
              if (medication &&
                  time != null &&
                  !time.isAfter(DateTime.now())) ...[
                FilledButton(
                  onPressed: _busy ? null : () => _action('taken'),
                  child: const Text('Mark as Taken'),
                ),
                TextButton(
                  onPressed: _busy ? null : () => _action('skipped'),
                  child: const Text('Skip'),
                ),
                TextButton(
                  onPressed: _busy || action == 'taken' || action == 'skipped'
                      ? null
                      : () => _action('snooze'),
                  child: const Text('Snooze 15 minutes'),
                ),
              ],
              if (!medication)
                FilledButton(
                  onPressed: _busy ? null : () => _action('completed'),
                  child: const Text('Mark complete'),
                ),
              if (action != null)
                TextButton(
                  onPressed: _busy ? null : () => _action('reset'),
                  child: const Text('Correct action'),
                ),
            ],
          ),
        if (item['kind'] == 'follow_up')
          TextButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => AiCareAssistantScreen(
                  initialQuery: item['doctorName'] == null
                      ? null
                      : 'Find ${item['doctorName']}',
                ),
              ),
            ),
            child: const Text('Open booking assistant'),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.eventId == null ? 'My Care Plan' : 'Care task'),
      actions: [
        IconButton(
          onPressed: _busy ? null : _refresh,
          icon: const Icon(Icons.refresh),
          tooltip: 'Refresh',
        ),
      ],
    ),
    body: FutureBuilder<dynamic>(
      future: _data,
      builder: (context, result) {
        if (result.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (result.hasError || result.data is! Map) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Care information is unavailable or may have changed.',
                ),
                TextButton(onPressed: _refresh, child: const Text('Retry')),
              ],
            ),
          );
        }
        final data = result.data as Map;
        if (widget.eventId != null) return _details(data);
        final items = (data['items'] as List? ?? []).whereType<Map>();
        return ListView(
          padding: const EdgeInsets.all(14),
          children: [
            Wrap(
              spacing: 8,
              children: [
                ChoiceChip(
                  label: const Text('Today'),
                  selected: _days == 1,
                  onSelected: (_) {
                    _days = 1;
                    _refresh();
                  },
                ),
                ChoiceChip(
                  label: const Text('Next 7 days'),
                  selected: _days == 7,
                  onSelected: (_) {
                    _days = 7;
                    _refresh();
                  },
                ),
                ActionChip(
                  label: const Text('All care plans'),
                  onPressed: () =>
                      Navigator.pushNamed(context, '/patient/care-plans'),
                ),
                ActionChip(
                  label: const Text('Health tracking'),
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => _CareTracking(api: _api)),
                  ),
                ),
                ActionChip(
                  label: const Text('Reminder preferences'),
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => _CarePreferences(api: _api),
                    ),
                  ),
                ),
              ],
            ),
            if (items.isEmpty)
              const ListTile(
                title: Text('No scheduled care tasks for this period.'),
              ),
            for (final row in items)
              ListTile(
                title: Text(row['title'].toString()),
                subtitle: Text(
                  _date(row['scheduledAt']) +
                      (row['action'] == null
                          ? ''
                          : '\n${row['action']} (patient-reported)'),
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () =>
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => CareAgendaScreen(
                          eventId: row['id'] as String,
                          apiClient: _api,
                        ),
                      ),
                    ).then((_) {
                      if (mounted) _refresh();
                    }),
              ),
          ],
        );
      },
    ),
  );
}

class _CarePreferences extends StatefulWidget {
  final ApiClient api;
  const _CarePreferences({required this.api});

  @override
  State<_CarePreferences> createState() => _CarePreferencesState();
}

class _CarePreferencesState extends State<_CarePreferences> {
  late final Future<dynamic> _loaded = widget.api.get('$_base/preferences');
  late Map<String, dynamic> _values;
  bool _ready = false;
  bool _busy = false;
  String? _error;
  static const _labels = {
    'careReminders': 'Care reminders',
    'reminder24h': 'Appointment reminder 24 hours before',
    'reminder2h': 'Appointment reminder 2 hours before',
    'careEmail': 'Email important reminders to my verified address',
    'careSms': 'Authorize SMS to my saved mobile number',
  };

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.api.put('$_base/preferences', body: _values);
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Could not save settings. Check your verified email or saved mobile number.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Reminder preferences')),
    body: FutureBuilder<dynamic>(
      future: _loaded,
      builder: (context, state) {
        if (state.hasError) {
          return const Center(child: Text('Could not load preferences.'));
        }
        if (state.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (!_ready) {
          _values = Map<String, dynamic>.from(state.data as Map);
          _ready = true;
        }
        return ListView(
          children: [
            for (final entry in _labels.entries)
              SwitchListTile(
                title: Text(entry.value),
                value: _values[entry.key] == true,
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _values[entry.key] = value),
              ),
            if (_error != null) ListTile(title: Text(_error!)),
            FilledButton(
              onPressed: _busy ? null : _save,
              child: const Text('Save preferences'),
            ),
          ],
        );
      },
    ),
  );
}

class _CareTracking extends StatefulWidget {
  final ApiClient api;
  const _CareTracking({required this.api});
  @override
  State<_CareTracking> createState() => _CareTrackingState();
}

class _CareTrackingState extends State<_CareTracking> {
  final _value = TextEditingController();
  final _secondary = TextEditingController();
  late Future<dynamic> _items = widget.api.get('$_base/measurements');
  static const _units = {
    'blood_pressure': 'mmHg',
    'blood_glucose': 'mg/dL',
    'weight': 'kg',
    'temperature': '°C',
  };
  String _metric = 'weight';
  String? _message;
  bool _busy = false;

  @override
  void dispose() {
    _value.dispose();
    _secondary.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final value = double.tryParse(_value.text);
    final second = double.tryParse(_secondary.text);
    if (value == null ||
        !value.isFinite ||
        _metric == 'blood_pressure' && (second == null || !second.isFinite)) {
      setState(() => _message = 'Enter a numeric reading.');
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.api.post(
        '$_base/measurements',
        body: {
          'metric': _metric,
          'value': value,
          if (_metric == 'blood_pressure') 'secondary': second,
        },
      );
      if (mounted) {
        setState(() {
          _message = 'Reading saved.';
          _value.clear();
          _secondary.clear();
          _items = widget.api.get('$_base/measurements');
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _message =
              'Could not save this reading. Check the unit and value.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _schedule(bool enabled) async {
    final at = enabled
        ? await showTimePicker(
            context: context,
            initialTime: const TimeOfDay(hour: 8, minute: 0),
            helpText: 'Daily reminder in Sri Lanka time',
          )
        : const TimeOfDay(hour: 0, minute: 0);
    if (!mounted || at == null) return;
    try {
      await widget.api.put(
        '$_base/tracking-schedule',
        body: {
          'metric': _metric,
          'enabled': enabled,
          'time':
              '${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}',
        },
      );
      if (mounted) {
        setState(
          () => _message = enabled
              ? 'Daily reminder saved.'
              : 'Daily reminder stopped.',
        );
      }
    } catch (_) {
      if (mounted) setState(() => _message = 'Could not update the reminder.');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Health Tracking')),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Patient-reported readings'),
        DropdownButton<String>(
          value: _metric,
          onChanged: (value) => setState(() => _metric = value!),
          items: [
            for (final key in _units.keys)
              DropdownMenuItem(
                value: key,
                child: Text(key.replaceAll('_', ' ')),
              ),
          ],
        ),
        TextField(
          controller: _value,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(
            labelText:
                '${_metric == 'blood_pressure' ? 'Systolic' : 'Reading'} (${_units[_metric]})',
          ),
        ),
        if (_metric == 'blood_pressure')
          TextField(
            controller: _secondary,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Diastolic (mmHg)'),
          ),
        if (_message != null) Text(_message!),
        Wrap(
          spacing: 8,
          children: [
            FilledButton(
              onPressed: _busy ? null : _save,
              child: const Text('Save reading'),
            ),
            TextButton(
              onPressed: () => _schedule(true),
              child: const Text('Set daily reminder'),
            ),
            TextButton(
              onPressed: () => _schedule(false),
              child: const Text('Stop reminder'),
            ),
          ],
        ),
        FutureBuilder<dynamic>(
          future: _items,
          builder: (context, result) {
            if (result.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (result.hasError) {
              return TextButton(
                onPressed: () => setState(
                  () => _items = widget.api.get('$_base/measurements'),
                ),
                child: const Text('Could not load readings. Retry'),
              );
            }
            final items = ((result.data as Map)['items'] as List? ?? [])
                .whereType<Map>()
                .where((r) => r['metric'] == _metric)
                .toList();
            if (items.isEmpty) {
              return const Text('No readings for this measurement.');
            }
            return Column(
              children: [
                if (items.length > 1)
                  Text(
                    'Change from previous reading: '
                    '${((items[0]['value'] as num) - (items[1]['value'] as num)).toStringAsFixed(1)} ${items[0]['unit']}'
                    '${_metric == 'blood_pressure' ? ' systolic' : ''}',
                  ),
                for (final row in items)
                  ListTile(
                    title: Text(
                      '${row['value']}${row['secondary'] == null ? '' : '/${row['secondary']}'} ${row['unit']}',
                    ),
                    subtitle: Text(row['recordedAt'].toString()),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}
