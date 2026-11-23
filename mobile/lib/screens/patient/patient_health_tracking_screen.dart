import 'package:flutter/material.dart';

import '../../models/clinical_record.dart';
import '../../services/clinical_api_service.dart';

/// Screen allowing patients to track vital signs (BP, Glucose, Heart Rate, SpO2, Weight, Temp),
/// view deterministic 7-day and 30-day trends, and receive clinical safety alerts.
class PatientHealthTrackingScreen extends StatefulWidget {
  final ClinicalApiService? service;

  const PatientHealthTrackingScreen({super.key, this.service});

  @override
  State<PatientHealthTrackingScreen> createState() => _PatientHealthTrackingScreenState();
}

class _PatientHealthTrackingScreenState extends State<PatientHealthTrackingScreen> {
  late final ClinicalApiService _service;
  HealthTrends? _trends;
  List<HealthMeasurement> _measurements = [];
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? ClinicalApiService();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final trendsFuture = _service.getHealthTrends();
      final measurementsFuture = _service.getMeasurements();
      final results = await Future.wait([trendsFuture, measurementsFuture]);

      if (mounted) {
        setState(() {
          _trends = results[0] as HealthTrends;
          _measurements = results[1] as List<HealthMeasurement>;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Failed to load health tracking data.';
          _isLoading = false;
        });
      }
    }
  }

  void _showAddMeasurementDialog() {
    String selectedMetric = 'blood_pressure';
    final primaryController = TextEditingController();
    final secondaryController = TextEditingController();
    final notesController = TextEditingController();

    showDialog(
      context: context,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            final isBP = selectedMetric == 'blood_pressure';
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Add Health Measurement', style: TextStyle(fontWeight: FontWeight.bold)),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DropdownButtonFormField<String>(
                      initialValue: selectedMetric,
                      decoration: const InputDecoration(labelText: 'Metric'),
                      items: const [
                        DropdownMenuItem(value: 'blood_pressure', child: Text('Blood Pressure (mmHg)')),
                        DropdownMenuItem(value: 'blood_glucose', child: Text('Blood Glucose (mg/dL)')),
                        DropdownMenuItem(value: 'heart_rate', child: Text('Heart Rate (bpm)')),
                        DropdownMenuItem(value: 'oxygen_saturation', child: Text('Oxygen Saturation (SpO2 %)')),
                        DropdownMenuItem(value: 'weight', child: Text('Body Weight (kg)')),
                        DropdownMenuItem(value: 'temperature', child: Text('Temperature (°C)')),
                      ],
                      onChanged: (val) {
                        if (val != null) setDialogState(() => selectedMetric = val);
                      },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: primaryController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                        labelText: isBP ? 'Systolic (mmHg) *' : 'Value *',
                        hintText: isBP ? 'e.g. 120' : 'e.g. 95',
                      ),
                    ),
                    if (isBP) ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: secondaryController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Diastolic (mmHg) *',
                          hintText: 'e.g. 80',
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: notesController,
                      decoration: const InputDecoration(labelText: 'Notes (optional)', hintText: 'e.g. Fasting'),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(dialogCtx), child: const Text('Cancel')),
                ElevatedButton(
                  onPressed: () async {
                    final primary = double.tryParse(primaryController.text.trim());
                    if (primary == null) return;
                    final secondary = isBP ? double.tryParse(secondaryController.text.trim()) : null;
                    if (isBP && secondary == null) return;

                    Navigator.pop(dialogCtx);
                    try {
                      final result = await _service.recordMeasurement(
                        metric: selectedMetric,
                        value: primary,
                        secondary: secondary,
                        notes: notesController.text.trim().isEmpty ? null : notesController.text.trim(),
                      );
                      if (mounted) {
                        if (result.criticalAlert != null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(result.criticalAlert!), backgroundColor: Colors.red, duration: const Duration(seconds: 8)),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Measurement recorded.'), backgroundColor: Colors.green),
                          );
                        }
                        _loadData();
                      }
                    } catch (e) {
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
                      }
                    }
                  },
                  child: const Text('Save'),
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
        title: const Text('My Health Tracking'),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddMeasurementDialog,
        icon: const Icon(Icons.add),
        label: const Text('Add Reading'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : _errorMessage != null
                ? Center(child: Text(_errorMessage!))
                : SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Critical safety alert banner
                        if (_trends != null && _trends!.criticalAlerts.isNotEmpty)
                          Container(
                            margin: const EdgeInsets.only(bottom: 16),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.red.shade50,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: Colors.red.shade300),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Row(
                                  children: [
                                    Icon(Icons.warning, color: Colors.red),
                                    SizedBox(width: 8),
                                    Text('Clinical Safety Alerts', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red)),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                ..._trends!.criticalAlerts.map(
                                  (alert) => Padding(
                                    padding: const EdgeInsets.only(bottom: 4),
                                    child: Text('• $alert', style: TextStyle(color: Colors.red.shade900, fontSize: 12)),
                                  ),
                                ),
                              ],
                            ),
                          ),

                        // Metric Trends Summary Cards
                        const Text('Vitals Summary & Trends (30 Days)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 12),
                        if (_trends != null)
                          GridView.count(
                            crossAxisCount: 2,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 12,
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            children: _trends!.trends.map((t) {
                              return Card(
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                child: Padding(
                                  padding: const EdgeInsets.all(12),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        t.metric.replaceAll('_', ' ').toUpperCase(),
                                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.grey),
                                      ),
                                      if (t.latestValue != null) ...[
                                        Text(
                                          t.latestSecondary != null
                                              ? '${t.latestValue!.toStringAsFixed(0)}/${t.latestSecondary!.toStringAsFixed(0)}'
                                              : t.latestValue!.toStringAsFixed(1),
                                          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                                        ),
                                        Text('${t.unit} (Latest)', style: const TextStyle(fontSize: 10, color: Colors.grey)),
                                      ] else ...[
                                        const Text('No data', style: TextStyle(fontSize: 16, color: Colors.grey)),
                                      ],
                                      Row(
                                        children: [
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(
                                              color: t.trendDirection == 'RISING'
                                                  ? Colors.amber.shade100
                                                  : t.trendDirection == 'FALLING'
                                                      ? Colors.blue.shade100
                                                      : Colors.green.shade100,
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              t.trendDirection,
                                              style: TextStyle(
                                                fontSize: 9,
                                                fontWeight: FontWeight.bold,
                                                color: t.trendDirection == 'RISING' ? Colors.amber.shade900 : Colors.blue.shade900,
                                              ),
                                            ),
                                          ),
                                          const Spacer(),
                                          Text('7d: ${t.sevenDayAverage?.toStringAsFixed(0) ?? '-'}', style: const TextStyle(fontSize: 10, color: Colors.grey)),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            }).toList(),
                          ),

                        const SizedBox(height: 24),
                        const Text('Recent Measurements', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 12),
                        ..._measurements.take(10).map((m) {
                          final isBP = m.metric == 'blood_pressure';
                          return Card(
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              title: Text(
                                isBP && m.secondary != null
                                    ? '${m.value.toStringAsFixed(0)}/${m.secondary!.toStringAsFixed(0)} ${m.unit}'
                                    : '${m.value.toStringAsFixed(1)} ${m.unit}',
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                              subtitle: Text(
                                '${m.metric.replaceAll('_', ' ').toUpperCase()} • ${m.measuredAt.toIso8601String().substring(0, 16).replaceAll('T', ' ')}',
                                style: const TextStyle(fontSize: 11),
                              ),
                              trailing: Text(m.source == 'device_reported' ? 'DEVICE' : 'PATIENT', style: const TextStyle(fontSize: 9, color: Colors.grey)),
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
      ),
    );
  }
}
