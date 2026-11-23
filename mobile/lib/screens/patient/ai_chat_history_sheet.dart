import 'package:flutter/material.dart';

import '../../services/ai_booking_service.dart';

class AiHistorySelection {
  final String? id;
  final bool activeDeleted;
  final bool open;

  const AiHistorySelection({
    this.id,
    this.activeDeleted = false,
    this.open = true,
  });
}

class AiChatHistorySheet extends StatefulWidget {
  final AiBookingService service;
  final String? activeId;

  const AiChatHistorySheet({super.key, required this.service, this.activeId});

  @override
  State<AiChatHistorySheet> createState() => _AiChatHistorySheetState();
}

class _AiChatHistorySheetState extends State<AiChatHistorySheet> {
  final _items = <Map<String, dynamic>>[];
  bool _loading = false;
  bool _hasMore = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool refresh = false}) async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.service.listConversations(
        offset: refresh ? 0 : _items.length,
      );
      if (!mounted) return;
      setState(() {
        if (refresh) _items.clear();
        _items.addAll(page);
        _hasMore = page.length == 30;
      });
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load chat history.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit(Map<String, dynamic> item, String action) async {
    final id = item['id'] as String;
    try {
      if (action == 'delete') {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Delete conversation?'),
            content: const Text(
              'This permanently removes the chat and its messages.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Delete'),
              ),
            ],
          ),
        );
        if (confirmed != true || !mounted) return;
        await widget.service.deleteConversation(id);
        if (!mounted) return;
        if (id == widget.activeId) {
          Navigator.pop(context, const AiHistorySelection(activeDeleted: true));
          return;
        }
      } else {
        var title = item['title'] as String;
        final updated = await showDialog<String>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Rename conversation'),
            content: TextFormField(
              autofocus: true,
              initialValue: title,
              maxLength: 100,
              onChanged: (value) => title = value,
              onFieldSubmitted: (value) => Navigator.pop(context, value.trim()),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, title.trim()),
                child: const Text('Save'),
              ),
            ],
          ),
        );
        if (updated == null || updated.isEmpty || !mounted) return;
        await widget.service.renameConversation(id, updated);
      }
      if (mounted) await _load(refresh: true);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not update the conversation.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: FractionallySizedBox(
        heightFactor: 0.75,
        child: Column(
          children: [
            ListTile(
              title: Text(
                'Chat History',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              trailing: TextButton.icon(
                onPressed: () =>
                    Navigator.pop(context, const AiHistorySelection()),
                icon: const Icon(Icons.add),
                label: const Text('New Chat'),
              ),
            ),
            if (_loading) const LinearProgressIndicator(),
            if (_error != null)
              ListTile(
                title: Text(_error!),
                trailing: TextButton(
                  onPressed: () => _load(refresh: true),
                  child: const Text('Retry'),
                ),
              ),
            if (!_loading && _error == null && _items.isEmpty)
              const Expanded(
                child: Center(child: Text('No conversations yet.')),
              )
            else
              Expanded(
                child: ListView(
                  children: [
                    for (final item in _items) _tile(context, item),
                    if (_hasMore && !_loading && _error == null)
                      TextButton(
                        onPressed: _load,
                        child: const Text('Load more'),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _tile(BuildContext context, Map<String, dynamic> item) {
    final id = item['id'] as String;
    final updatedAt = DateTime.tryParse(item['updatedAt'] as String? ?? '')
        ?.toLocal();
    final locale = MaterialLocalizations.of(context);
    return ListTile(
      selected: id == widget.activeId,
      title: Text(
        item['title'] as String,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item['preview'] as String? ?? '',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          if (updatedAt != null)
            Text(
              '${locale.formatShortDate(updatedAt)} ${locale.formatTimeOfDay(TimeOfDay.fromDateTime(updatedAt))}',
            ),
        ],
      ),
      onTap: () => Navigator.pop(context, AiHistorySelection(id: id)),
      trailing: PopupMenuButton<String>(
        tooltip: 'Conversation options',
        onSelected: (action) => _edit(item, action),
        itemBuilder: (_) => const [
          PopupMenuItem(value: 'rename', child: Text('Rename')),
          PopupMenuItem(value: 'delete', child: Text('Delete')),
        ],
      ),
    );
  }
}
