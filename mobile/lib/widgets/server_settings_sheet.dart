import 'package:flutter/material.dart';

import '../core/constants/api_constants.dart';
import '../core/network/api_client.dart';
import '../core/storage/secure_storage_service.dart';
import '../core/theme/app_theme.dart';

/// Modal bottom sheet allowing users to view, test, and reconfigure the backend
/// server IP address on physical devices, emulators, or local networks.
class ServerSettingsSheet extends StatefulWidget {
  const ServerSettingsSheet({super.key});

  /// Static helper to display the sheet from any screen.
  static Future<bool?> show(BuildContext context) {
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const ServerSettingsSheet(),
    );
  }

  @override
  State<ServerSettingsSheet> createState() => _ServerSettingsSheetState();
}

class _ServerSettingsSheetState extends State<ServerSettingsSheet> {
  late final TextEditingController _urlController;
  final SecureStorageService _storageService = SecureStorageService();
  final ApiClient _apiClient = ApiClient();

  bool _isTesting = false;
  bool? _testSuccess;
  String? _testMessage;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: ApiConstants.hostBaseUrl);
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _testConnection([String? testUrl]) async {
    final target = testUrl ?? _urlController.text.trim();
    if (target.isEmpty) return;

    setState(() {
      _isTesting = true;
      _testSuccess = null;
      _testMessage = null;
    });

    final previousHost = ApiConstants.hostBaseUrl;
    ApiConstants.setBaseUrl(target);

    try {
      final isHealthy = await _apiClient.checkHealth();
      if (!mounted) return;

      setState(() {
        _isTesting = false;
        _testSuccess = isHealthy;
        _testMessage = isHealthy
            ? 'Connected successfully to backend!'
            : 'Could not connect. Please verify server is running.';
      });

      if (!isHealthy) {
        // Revert temporary test host if failed
        ApiConstants.setBaseUrl(previousHost);
      }
    } catch (e) {
      if (!mounted) return;
      ApiConstants.setBaseUrl(previousHost);
      setState(() {
        _isTesting = false;
        _testSuccess = false;
        _testMessage = 'Connection failed: $e';
      });
    }
  }

  Future<void> _autoDetect() async {
    setState(() {
      _isTesting = true;
      _testSuccess = null;
      _testMessage = 'Scanning candidate host endpoints...';
    });

    final detected = await ApiConstants.autoDetectBaseUrl(force: true);
    if (!mounted) return;

    setState(() {
      _isTesting = false;
      if (detected != null) {
        _urlController.text = ApiConstants.hostBaseUrl;
        _testSuccess = true;
        _testMessage = 'Detected active server at ${ApiConstants.hostBaseUrl}!';
      } else {
        _testSuccess = false;
        _testMessage = 'No active server detected on standard candidate ports.';
      }
    });
  }

  Future<void> _saveAndApply() async {
    final host = _urlController.text.trim();
    if (host.isEmpty) return;

    ApiConstants.setBaseUrl(host);
    await _storageService.saveServerUrl(host);

    if (mounted) {
      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Server connected to: ${ApiConstants.baseUrl}'),
          backgroundColor: AppTheme.primary,
        ),
      );
    }
  }

  Future<void> _resetDefault() async {
    ApiConstants.resetToDefault();
    await _storageService.clearServerUrl();
    setState(() {
      _urlController.text = ApiConstants.hostBaseUrl;
      _testSuccess = null;
      _testMessage = null;
    });
  }

  void _selectPreset(String presetHost) {
    setState(() {
      _urlController.text = presetHost;
      _testSuccess = null;
      _testMessage = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      padding: EdgeInsets.fromLTRB(24, 16, 24, 24 + bottomInset),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Drag handle
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: AppTheme.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryLight,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.dns_rounded, color: AppTheme.primary),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Backend Server Settings',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Text(
                        'Configure host IP for physical device or emulator',
                        style: TextStyle(
                          fontSize: 12,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded, size: 20),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Current Active Base URL badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.background,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.border),
              ),
              child: Row(
                children: [
                  const Text(
                    'Active API:',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      ApiConstants.baseUrl,
                      style: const TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                        color: AppTheme.primary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Quick preset chips
            const Text(
              'Quick Presets',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildPresetChip(
                  label: 'USB Cable (127.0.0.1:8000)',
                  value: 'http://127.0.0.1:8000',
                  icon: Icons.usb_rounded,
                ),
                _buildPresetChip(
                  label: 'Local Wi-Fi (192.168.248.238:8000)',
                  value: 'http://192.168.248.238:8000',
                  icon: Icons.wifi_rounded,
                ),
                _buildPresetChip(
                  label: 'Emulator (10.0.2.2:8000)',
                  value: 'http://10.0.2.2:8000',
                  icon: Icons.phone_android_rounded,
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Server Host Input
            TextField(
              controller: _urlController,
              decoration: InputDecoration(
                labelText: 'Server Host URL',
                hintText: 'http://192.168.x.x:8000',
                prefixIcon: const Icon(Icons.link_rounded),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.clear_rounded, size: 18),
                  onPressed: () => _urlController.clear(),
                ),
              ),
              keyboardType: TextInputType.url,
            ),
            const SizedBox(height: 12),

            // Test Feedback Banner
            if (_testMessage != null) ...[
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: _testSuccess == true
                      ? AppTheme.success.withValues(alpha: 0.1)
                      : AppTheme.error.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: _testSuccess == true
                        ? AppTheme.success.withValues(alpha: 0.3)
                        : AppTheme.error.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      _testSuccess == true ? Icons.check_circle_rounded : Icons.error_rounded,
                      color: _testSuccess == true ? AppTheme.success : AppTheme.error,
                      size: 18,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _testMessage!,
                        style: TextStyle(
                          fontSize: 13,
                          color: _testSuccess == true ? AppTheme.success : AppTheme.error,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
            ],

            // Action Buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: _isTesting
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.radar_rounded, size: 16),
                    label: const Text('Auto-Detect'),
                    onPressed: _isTesting ? null : _autoDetect,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.network_check_rounded, size: 16),
                    label: const Text('Test Connection'),
                    onPressed: _isTesting ? null : () => _testConnection(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            Row(
              children: [
                TextButton(
                  onPressed: _resetDefault,
                  child: const Text('Reset Default'),
                ),
                const Spacer(),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(0, 44),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  icon: const Icon(Icons.save_rounded, size: 18),
                  label: const Text('Save & Connect'),
                  onPressed: _saveAndApply,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPresetChip({
    required String label,
    required String value,
    required IconData icon,
  }) {
    final isSelected = _urlController.text.trim() == value;
    return ChoiceChip(
      avatar: Icon(
        icon,
        size: 16,
        color: isSelected ? AppTheme.primary : AppTheme.textSecondary,
      ),
      label: Text(label),
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        color: isSelected ? AppTheme.primary : AppTheme.textPrimary,
      ),
      selected: isSelected,
      onSelected: (_) => _selectPreset(value),
      selectedColor: AppTheme.primaryLight,
      backgroundColor: AppTheme.background,
    );
  }
}
