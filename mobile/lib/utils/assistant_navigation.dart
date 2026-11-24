import 'package:flutter/material.dart';

/// Opens the AI Assistant exactly once (BUG-014 / BUG-015).
///
/// Rapid double taps, or a tap while a previous push is still animating, used to stack two
/// assistant routes, which shows two message composers and can trigger lifecycle assertions when
/// the user presses Back. This helper ignores re-entrant requests until the pushed route closes.
class AssistantNavigation {
  AssistantNavigation._();

  static const String routeName = '/patient/ai-assistant';
  static bool _open = false;

  static bool get isOpen => _open;

  /// Extracts an initial prompt passed as `{'initialPrompt': '...'}` route arguments.
  static String? initialPromptFrom(BuildContext context) {
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map && args['initialPrompt'] is String) {
      final prompt = (args['initialPrompt'] as String).trim();
      return prompt.isEmpty ? null : prompt;
    }
    return null;
  }

  static Future<void> open(BuildContext context, {String? initialPrompt}) async {
    if (_open) return;
    _open = true;
    try {
      await Navigator.of(context).pushNamed(
        routeName,
        arguments: initialPrompt == null ? null : {'initialPrompt': initialPrompt},
      );
    } finally {
      _open = false;
    }
  }

  @visibleForTesting
  static void reset() => _open = false;
}
