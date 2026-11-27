import 'package:flutter/material.dart';

import '../../core/network/api_error_mapper.dart';
import '../../core/theme/app_theme.dart';
import '../../models/support_ticket.dart';
import '../../services/support_service.dart';

/// A05 (Agent 26): Help & Support. The patient creates tickets, reads replies from MediConnect Support and answers
/// them. Messages are shown as plain text. Nothing here changes an appointment, payment, refund or account.
class SupportTicketsScreen extends StatefulWidget {
  final SupportService? service;

  const SupportTicketsScreen({super.key, this.service});

  @override
  State<SupportTicketsScreen> createState() => _SupportTicketsScreenState();
}

class _SupportTicketsScreenState extends State<SupportTicketsScreen> {
  late final SupportService _service = widget.service ?? SupportService();
  List<SupportTicket> _tickets = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final tickets = await _service.myTickets();
      if (!mounted) return;
      setState(() {
        _tickets = tickets;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ApiErrorMapper.mapException(e);
        _loading = false;
      });
    }
  }

  Future<void> _create() async {
    final created = await Navigator.of(context).push<SupportTicket>(
      MaterialPageRoute(builder: (_) => CreateSupportTicketScreen(service: _service)),
    );
    if (created != null && mounted) {
      await _load();
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => SupportTicketDetailScreen(ticketId: created.ticketId, service: _service, initial: created),
      ));
      if (mounted) _load();
    }
  }

  Future<void> _open(SupportTicket t) async {
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => SupportTicketDetailScreen(ticketId: t.ticketId, service: _service),
    ));
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Help & Support')),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('support_create_button'),
        onPressed: _create,
        icon: const Icon(Icons.add_comment_outlined),
        label: const Text('Create ticket'),
      ),
      body: RefreshIndicator(onRefresh: _load, child: _body()),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(key: Key('support_loading')));
    }
    if (_error != null) {
      return ListView(padding: const EdgeInsets.all(24), children: [
        Text(_error!, key: const Key('support_error'), textAlign: TextAlign.center),
        const SizedBox(height: 12),
        Center(
          child: OutlinedButton(key: const Key('support_retry'), onPressed: _load, child: const Text('Try again')),
        ),
      ]);
    }
    if (_tickets.isEmpty) {
      return ListView(padding: const EdgeInsets.all(24), children: const [
        SizedBox(height: 40),
        Icon(Icons.support_agent_rounded, size: 48, color: AppTheme.textSecondary),
        SizedBox(height: 12),
        Text('No support tickets yet', key: Key('support_empty'), textAlign: TextAlign.center,
            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        SizedBox(height: 8),
        Text(
          'Ask MediConnect Support about bookings, payments, your account or a problem with the app. '
          'Support cannot give medical advice. In an emergency call 1990.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppTheme.textSecondary),
        ),
      ]);
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
      itemCount: _tickets.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, i) {
        final t = _tickets[i];
        return Card(
          child: ListTile(
            key: Key('support_ticket_${t.ticketId}'),
            title: Text(t.subject, maxLines: 2, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text('${t.ticketId} · ${supportCategoryLabel(t.category)}'),
            trailing: _StatusChip(status: t.status, highlight: t.supportReplied),
            onTap: () => _open(t),
          ),
        );
      },
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String status;
  final bool highlight;

  const _StatusChip({required this.status, required this.highlight});

  @override
  Widget build(BuildContext context) {
    final color = highlight ? AppTheme.primary : AppTheme.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.4)),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(supportStatusLabel(status), style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
    );
  }
}

class CreateSupportTicketScreen extends StatefulWidget {
  final SupportService service;

  const CreateSupportTicketScreen({super.key, required this.service});

  @override
  State<CreateSupportTicketScreen> createState() => _CreateSupportTicketScreenState();
}

class _CreateSupportTicketScreenState extends State<CreateSupportTicketScreen> {
  final _formKey = GlobalKey<FormState>();
  final _subject = TextEditingController();
  final _message = TextEditingController();
  String _category = 'general_support';
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _subject.dispose();
    _message.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_sending || !(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final ticket = await widget.service.create(
          category: _category, subject: _subject.text.trim(), message: _message.text.trim());
      if (mounted) Navigator.of(context).pop(ticket);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ApiErrorMapper.mapException(e);
        _sending = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create support ticket')),
      body: Form(
        key: _formKey,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          const Text(
            'MediConnect Support helps with bookings, payments, your account and app problems. It cannot give '
            'medical advice, approve refunds or change appointments from a ticket. In an emergency call 1990.',
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            key: const Key('support_category'),
            initialValue: _category,
            decoration: const InputDecoration(labelText: 'Category'),
            items: supportCategories.entries
                .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                .toList(),
            onChanged: _sending ? null : (v) => setState(() => _category = v ?? 'general_support'),
          ),
          const SizedBox(height: 12),
          TextFormField(
            key: const Key('support_subject'),
            controller: _subject,
            maxLength: 200,
            decoration: const InputDecoration(labelText: 'Subject', hintText: 'Short summary of the problem'),
            validator: (v) => (v ?? '').trim().length < 3 ? 'Enter a subject of at least 3 characters.' : null,
          ),
          const SizedBox(height: 8),
          TextFormField(
            key: const Key('support_message'),
            controller: _message,
            maxLength: 4000,
            minLines: 4,
            maxLines: 8,
            decoration: const InputDecoration(labelText: 'Message', hintText: 'Describe what happened'),
            validator: (v) => (v ?? '').trim().length < 5 ? 'Enter a message of at least 5 characters.' : null,
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, key: const Key('support_create_error'), style: const TextStyle(color: AppTheme.error)),
          ],
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('support_submit'),
            onPressed: _sending ? null : _submit,
            icon: _sending
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.send_rounded),
            label: Text(_sending ? 'Sending…' : 'Send to support'),
          ),
        ]),
      ),
    );
  }
}

class SupportTicketDetailScreen extends StatefulWidget {
  final String ticketId;
  final SupportService? service;
  final SupportTicket? initial;

  const SupportTicketDetailScreen({super.key, required this.ticketId, this.service, this.initial});

  @override
  State<SupportTicketDetailScreen> createState() => _SupportTicketDetailScreenState();
}

class _SupportTicketDetailScreenState extends State<SupportTicketDetailScreen> {
  late final SupportService _service = widget.service ?? SupportService();
  final _reply = TextEditingController();
  SupportTicket? _ticket;
  bool _loading = true;
  bool _sending = false;
  String? _error;
  String? _sendError;

  @override
  void initState() {
    super.initState();
    _ticket = widget.initial;
    _load();
  }

  @override
  void dispose() {
    _reply.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = _ticket == null;
      _error = null;
    });
    try {
      final t = await _service.ticket(widget.ticketId);
      if (!mounted) return;
      setState(() {
        _ticket = t;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = ApiErrorMapper.mapException(e);
        _loading = false;
      });
    }
  }

  Future<void> _send() async {
    final text = _reply.text.trim();
    if (_sending || text.isEmpty) return;
    setState(() {
      _sending = true;
      _sendError = null;
    });
    try {
      final t = await _service.reply(widget.ticketId, text);
      if (!mounted) return;
      _reply.clear();
      setState(() {
        _ticket = t;
        _sending = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sendError = ApiErrorMapper.mapException(e);
        _sending = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = _ticket;
    return Scaffold(
      appBar: AppBar(title: Text(t?.ticketId ?? 'Support ticket')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : t == null
              ? ListView(padding: const EdgeInsets.all(24), children: [
                  Text(_error ?? 'This ticket could not be loaded.', key: const Key('support_detail_error'),
                      textAlign: TextAlign.center),
                  const SizedBox(height: 12),
                  Center(child: OutlinedButton(onPressed: _load, child: const Text('Try again'))),
                ])
              : Column(children: [
                  Expanded(
                    child: RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(padding: const EdgeInsets.all(16), children: [
                        Text(t.subject, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        Text('${supportCategoryLabel(t.category)} · ${supportStatusLabel(t.status)}',
                            key: const Key('support_detail_status'),
                            style: const TextStyle(color: AppTheme.textSecondary)),
                        if (t.safetyNotice != null) ...[
                          const SizedBox(height: 12),
                          Container(
                            key: const Key('support_safety_notice'),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppTheme.errorContainer,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(t.safetyNotice!, style: const TextStyle(color: AppTheme.error)),
                          ),
                        ],
                        const SizedBox(height: 12),
                        for (final m in t.messages) _MessageBubble(message: m),
                      ]),
                    ),
                  ),
                  SafeArea(top: false, child: _composer(t)),
                ]),
    );
  }

  Widget _composer(SupportTicket t) {
    if (t.isClosed) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('This ticket is closed. Create a new ticket if you need more help.',
            key: Key('support_closed_notice'), textAlign: TextAlign.center),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        if (_sendError != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(_sendError!, key: const Key('support_reply_error'),
                style: const TextStyle(color: AppTheme.error)),
          ),
        Row(children: [
          Expanded(
            child: TextField(
              key: const Key('support_reply_field'),
              controller: _reply,
              minLines: 1,
              maxLines: 4,
              maxLength: 4000,
              decoration: const InputDecoration(hintText: 'Write a reply to support', counterText: ''),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            key: const Key('support_reply_send'),
            onPressed: _sending ? null : _send,
            icon: _sending
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.send_rounded),
            tooltip: 'Send reply',
          ),
        ]),
      ]),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final SupportMessage message;

  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final support = message.fromSupport;
    final time = message.sentAt;
    final stamp = time == null
        ? ''
        : '${time.day}/${time.month}/${time.year} ${time.hour.toString().padLeft(2, '0')}:'
            '${time.minute.toString().padLeft(2, '0')}';
    return Align(
      alignment: support ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        key: Key('support_message_${message.messageId}'),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        constraints: const BoxConstraints(maxWidth: 320),
        decoration: BoxDecoration(
          color: support ? AppTheme.primaryContainer : const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(support ? 'MediConnect Support' : 'You',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.textSecondary)),
          const SizedBox(height: 4),
          // Plain Text: message content is never interpreted as markup or links.
          Text(message.message),
          if (stamp.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(stamp, style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
          ],
        ]),
      ),
    );
  }
}
