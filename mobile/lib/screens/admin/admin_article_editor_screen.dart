import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/health_content.dart';
import '../../services/health_content_service.dart';

/// Admin Article Creation & Editing Screen with Live Preview (Phase 24).
class AdminArticleEditorScreen extends StatefulWidget {
  final HealthArticle? articleToEdit;

  const AdminArticleEditorScreen({super.key, this.articleToEdit});

  @override
  State<AdminArticleEditorScreen> createState() => _AdminArticleEditorScreenState();
}

class _AdminArticleEditorScreenState extends State<AdminArticleEditorScreen> with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final HealthContentService _service = HealthContentService();

  late TabController _tabController;

  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _summaryController = TextEditingController();
  final TextEditingController _bodyController = TextEditingController();
  final TextEditingController _coverImageController = TextEditingController();
  final TextEditingController _tagsController = TextEditingController();
  final TextEditingController _sourcesController = TextEditingController();

  static const List<String> _categories = [
    'Healthy Food',
    'Exercise',
    'Nutrition',
    'Mental Wellness',
    'Preventive Healthcare',
    'General Health Tips',
    'Health News',
  ];

  String _selectedCategory = 'Healthy Food';
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);

    if (widget.articleToEdit != null) {
      final a = widget.articleToEdit!;
      _titleController.text = a.title;
      _summaryController.text = a.summary;
      _bodyController.text = a.body;
      _coverImageController.text = a.coverImage ?? '';
      _tagsController.text = a.tags.join(', ');
      _sourcesController.text = a.sources ?? '';
      if (_categories.contains(a.category)) {
        _selectedCategory = a.category;
      }
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _titleController.dispose();
    _summaryController.dispose();
    _bodyController.dispose();
    _coverImageController.dispose();
    _tagsController.dispose();
    _sourcesController.dispose();
    super.dispose();
  }

  List<String> _parseTags() {
    return _tagsController.text
        .split(',')
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .toList();
  }

  Future<void> _handleSave({required bool publishImmediately}) async {
    if (!_formKey.currentState!.validate()) {
      _tabController.animateTo(0);
      return;
    }

    setState(() {
      _isSaving = true;
    });

    final targetStatus = publishImmediately ? 'PUBLISHED' : 'DRAFT';
    final tags = _parseTags();
    final coverImage = _coverImageController.text.trim().isEmpty ? null : _coverImageController.text.trim();
    final sources = _sourcesController.text.trim().isEmpty ? null : _sourcesController.text.trim();

    try {
      HealthArticle result;
      if (widget.articleToEdit != null) {
        final updateData = <String, dynamic>{
          'title': _titleController.text.trim(),
          'summary': _summaryController.text.trim(),
          'body': _bodyController.text.trim(),
          'category': _selectedCategory,
          'coverImage': ?coverImage,
          'tags': tags,
          'sources': ?sources,
          'status': targetStatus,
        };
        result = await _service.updateArticle(widget.articleToEdit!.contentId, updateData);
      } else {
        result = await _service.createArticle(
          title: _titleController.text.trim(),
          summary: _summaryController.text.trim(),
          body: _bodyController.text.trim(),
          category: _selectedCategory,
          coverImage: coverImage,
          tags: tags,
          sources: sources,
          status: targetStatus,
        );
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              publishImmediately
                  ? 'Article published successfully!'
                  : 'Article draft saved successfully.',
            ),
            backgroundColor: AppTheme.primary,
          ),
        );
        Navigator.of(context).pop(result);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save article: ${e.toString().replaceAll("Exception: ", "")}'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEditing = widget.articleToEdit != null;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text(isEditing ? 'Edit Health Article' : 'New Health Article'),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: const [
            Tab(icon: Icon(Icons.edit_note_rounded), text: 'Editor'),
            Tab(icon: Icon(Icons.preview_rounded), text: 'Preview'),
          ],
        ),
      ),
      body: _isSaving
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildEditorTab(),
                _buildPreviewTab(),
              ],
            ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, -3),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton(
                key: const Key('admin_save_draft_button'),
                onPressed: _isSaving ? null : () => _handleSave(publishImmediately: false),
                child: const Text('Save Draft'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                key: const Key('admin_publish_article_button'),
                onPressed: _isSaving ? null : () => _handleSave(publishImmediately: true),
                child: const Text('Publish Article'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEditorTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20.0),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Category Dropdown
            const Text(
              'Topic Category *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            DropdownButtonFormField<String>(
              key: const Key('admin_article_category_dropdown'),
              initialValue: _selectedCategory,
              decoration: InputDecoration(
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
              items: _categories.map((cat) {
                return DropdownMenuItem(value: cat, child: Text(cat));
              }).toList(),
              onChanged: (val) {
                if (val != null) setState(() => _selectedCategory = val);
              },
            ),
            const SizedBox(height: 16),

            // Title
            const Text(
              'Article Title *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('admin_article_title_input'),
              controller: _titleController,
              decoration: InputDecoration(
                hintText: 'e.g. The Power of Everyday Hydration',
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
              validator: (v) {
                if (v == null || v.trim().length < 3) return 'Title must be at least 3 characters.';
                if (v.trim().length > 250) return 'Title must not exceed 250 characters.';
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Summary
            const Text(
              'Brief Summary *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('admin_article_summary_input'),
              controller: _summaryController,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: 'One or two sentences summarizing the key educational takeaway.',
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
              validator: (v) {
                if (v == null || v.trim().length < 10) return 'Summary must be at least 10 characters.';
                if (v.trim().length > 600) return 'Summary must not exceed 600 characters.';
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Cover Image URL
            const Text(
              'Cover Image URL (optional)',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('admin_article_image_input'),
              controller: _coverImageController,
              decoration: InputDecoration(
                hintText: 'https://images.unsplash.com/...',
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Tags
            const Text(
              'Tags (comma separated)',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('admin_article_tags_input'),
              controller: _tagsController,
              decoration: InputDecoration(
                hintText: 'nutrition, hydration, wellness, habits',
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Full Article Body
            const Text(
              'Article Body (Markdown supported) *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('admin_article_body_input'),
              controller: _bodyController,
              maxLines: 12,
              decoration: InputDecoration(
                hintText: 'Write the educational content here. Use ## for headings and - for bullet points.',
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
              validator: (v) {
                if (v == null || v.trim().length < 20) return 'Article body must be at least 20 characters.';
                return null;
              },
            ),
            const SizedBox(height: 16),

            // Sources
            const Text(
              'Sources & Medical References (optional)',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('admin_article_sources_input'),
              controller: _sourcesController,
              maxLines: 2,
              decoration: InputDecoration(
                hintText: 'e.g. World Health Organization Healthy Diet Guidelines.',
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.border),
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildPreviewTab() {
    final title = _titleController.text.trim().isEmpty ? 'Article Title Preview' : _titleController.text.trim();
    final summary = _summaryController.text.trim().isEmpty ? 'Article summary will appear here.' : _summaryController.text.trim();
    final body = _bodyController.text.trim().isEmpty ? 'Full article body will appear here.' : _bodyController.text.trim();
    final tags = _parseTags();
    final coverImage = _coverImageController.text.trim();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Category pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              _selectedCategory,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.primary),
            ),
          ),
          const SizedBox(height: 12),

          // Title
          Text(
            title,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
          ),
          const SizedBox(height: 12),

          // Cover Image Preview if given
          if (coverImage.startsWith('http')) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Image.network(
                coverImage,
                height: 180,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Summary Callout
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
            ),
            child: Text(
              summary,
              style: const TextStyle(fontSize: 14, fontStyle: FontStyle.italic, color: AppTheme.textPrimary),
            ),
          ),
          const SizedBox(height: 16),

          // Body Preview
          Text(
            body,
            style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary, height: 1.5),
          ),
          const SizedBox(height: 20),

          // Tags
          if (tags.isNotEmpty)
            Wrap(
              spacing: 8,
              children: tags.map((t) => Chip(label: Text(t))).toList(),
            ),
        ],
      ),
    );
  }
}
