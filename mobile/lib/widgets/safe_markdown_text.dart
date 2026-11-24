import 'package:flutter/material.dart';

/// Renders the small, safe subset of Markdown used by assistant replies (BUG-024).
///
/// Supported: `# / ## / ###` headings, `**bold**`, `*italic*` / `_italic_`, `- ` / `* ` / `• `
/// bullets and `1. ` numbered items. Everything else is shown as plain text. There is no HTML,
/// link, image or script handling, so assistant output can never inject executable content.
class SafeMarkdownText extends StatelessWidget {
  final String data;
  final TextStyle? style;

  const SafeMarkdownText(this.data, {super.key, this.style});

  static final RegExp _heading = RegExp(r'^(#{1,3})\s+(.*)$');
  static final RegExp _bullet = RegExp(r'^\s*(?:[-*•])\s+(.*)$');
  static final RegExp _numbered = RegExp(r'^\s*(\d{1,2})[.)]\s+(.*)$');
  static final RegExp _inline = RegExp(r'\*\*(.+?)\*\*|__(.+?)__|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)');

  /// Parses inline emphasis into spans. Exposed for tests.
  static List<InlineSpan> inlineSpans(String text, TextStyle base) {
    final spans = <InlineSpan>[];
    var index = 0;
    for (final match in _inline.allMatches(text)) {
      if (match.start > index) {
        spans.add(TextSpan(text: text.substring(index, match.start)));
      }
      final bold = match.group(1) ?? match.group(2);
      final italic = match.group(3) ?? match.group(4);
      if (bold != null) {
        spans.add(TextSpan(text: bold, style: const TextStyle(fontWeight: FontWeight.w700)));
      } else if (italic != null) {
        spans.add(TextSpan(text: italic, style: const TextStyle(fontStyle: FontStyle.italic)));
      }
      index = match.end;
    }
    if (index < text.length) {
      spans.add(TextSpan(text: text.substring(index)));
    }
    return spans;
  }

  /// Plain text with Markdown markers removed (used for accessibility and copy).
  static String toPlainText(String text) {
    return text
        .split('\n')
        .map((line) {
          final heading = _heading.firstMatch(line);
          if (heading != null) return heading.group(2)!;
          final bullet = _bullet.firstMatch(line);
          if (bullet != null) return '• ${bullet.group(1)}';
          return line;
        })
        .join('\n')
        .replaceAllMapped(_inline, (m) => m.group(1) ?? m.group(2) ?? m.group(3) ?? m.group(4) ?? '');
  }

  @override
  Widget build(BuildContext context) {
    final base = style ?? DefaultTextStyle.of(context).style;
    final lines = data.replaceAll('\r\n', '\n').split('\n');
    final hasBlocks = lines.any((line) => _heading.hasMatch(line) || _bullet.hasMatch(line) || _numbered.hasMatch(line));
    if (!hasBlocks) {
      return Text.rich(TextSpan(style: base, children: inlineSpans(data, base)));
    }

    final children = <Widget>[];
    for (final line in lines) {
      if (line.trim().isEmpty) {
        children.add(const SizedBox(height: 6));
        continue;
      }
      final heading = _heading.firstMatch(line);
      final bullet = _bullet.firstMatch(line);
      final numbered = _numbered.firstMatch(line);
      if (heading != null) {
        final level = heading.group(1)!.length;
        final size = (base.fontSize ?? 14) + (level == 1 ? 3 : level == 2 ? 2 : 1);
        children.add(Padding(
          padding: const EdgeInsets.only(top: 2, bottom: 2),
          child: Text.rich(
            TextSpan(children: inlineSpans(heading.group(2)!, base)),
            style: base.copyWith(fontWeight: FontWeight.w700, fontSize: size),
            semanticsLabel: heading.group(2),
          ),
        ));
      } else if (bullet != null || numbered != null) {
        final marker = bullet != null ? '•' : '${numbered!.group(1)}.';
        final content = bullet != null ? bullet.group(1)! : numbered!.group(2)!;
        children.add(Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 2),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(width: 18, child: Text(marker, style: base)),
              Expanded(child: Text.rich(TextSpan(style: base, children: inlineSpans(content, base)))),
            ],
          ),
        ));
      } else {
        children.add(Text.rich(TextSpan(style: base, children: inlineSpans(line, base))));
      }
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: children);
  }
}
