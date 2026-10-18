import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/health_content.dart';
import '../../services/health_content_service.dart';
import 'admin_article_editor_screen.dart';

/// Admin Content Management Screen: search, filter, publish, archive, and edit articles (Phase 24).
class AdminArticlesScreen extends StatefulWidget {
  const AdminArticlesScreen({super.key});

  @override
  State<AdminArticlesScreen> createState() => _AdminArticlesScreenState();
}

class _AdminArticlesScreenState extends State<AdminArticlesScreen> {
  final HealthContentService _service = HealthContentService();
  final TextEditingController _searchController = TextEditingController();

  final List<String> _statusFilters = ['ALL', 'PUBLISHED', 'DRAFT', 'ARCHIVED'];
  String _selectedStatus = 'ALL';
  String _searchQuery = '';

  List<HealthArticle> _articles = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadArticles();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadArticles() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await _service.fetchAdminArticles(
        status: _selectedStatus == 'ALL' ? null : _selectedStatus,
        search: _searchQuery.trim().isEmpty ? null : _searchQuery.trim(),
        pageSize: 50,
      );
      if (mounted) {
        setState(() {
          _articles = res.items;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Failed to load articles. Please try again.';
        });
      }
    }
  }

  Future<void> _publishArticle(HealthArticle article) async {
    try {
      await _service.publishArticle(article.contentId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Published "${article.title}"'),
            backgroundColor: AppTheme.primary,
          ),
        );
      }
      _loadArticles();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to publish: $e'), backgroundColor: AppTheme.error),
        );
      }
    }
  }

  Future<void> _archiveArticle(HealthArticle article) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Archive Article'),
        content: Text('Are you sure you want to archive "${article.title}"? It will no longer be visible to patients.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await _service.archiveArticle(article.contentId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Archived "${article.title}"')),
        );
      }
      _loadArticles();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to archive: $e'), backgroundColor: AppTheme.error),
        );
      }
    }
  }

  void _openEditor([HealthArticle? article]) async {
    final result = await Navigator.of(context).push<HealthArticle>(
      MaterialPageRoute(
        builder: (_) => AdminArticleEditorScreen(articleToEdit: article),
      ),
    );
    if (result != null && mounted) {
      _loadArticles();
    }
  }

  Color _getStatusColor(String status) {
    switch (status.toUpperCase()) {
      case 'PUBLISHED':
        return Colors.green.shade700;
      case 'DRAFT':
        return Colors.amber.shade800;
      case 'ARCHIVED':
        return Colors.grey.shade600;
      default:
        return AppTheme.textSecondary;
    }
  }

  Color _getStatusBg(String status) {
    switch (status.toUpperCase()) {
      case 'PUBLISHED':
        return Colors.green.shade50;
      case 'DRAFT':
        return Colors.amber.shade50;
      case 'ARCHIVED':
        return Colors.grey.shade200;
      default:
        return Colors.grey.shade100;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Health Content Management'),
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('admin_create_article_fab'),
        onPressed: () => _openEditor(),
        backgroundColor: AppTheme.primary,
        icon: const Icon(Icons.add_rounded, color: Colors.white),
        label: const Text('New Article', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Search and Status filters
            Container(
              padding: const EdgeInsets.all(16),
              color: Colors.white,
              child: Column(
                children: [
                  // Search
                  TextField(
                    key: const Key('admin_articles_search_input'),
                    controller: _searchController,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (val) {
                      setState(() => _searchQuery = val);
                      _loadArticles();
                    },
                    decoration: InputDecoration(
                      hintText: 'Search articles by title, tag, or ID...',
                      prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.primary),
                      suffixIcon: _searchController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded),
                              onPressed: () {
                                _searchController.clear();
                                setState(() => _searchQuery = '');
                                _loadArticles();
                              },
                            )
                          : null,
                      filled: true,
                      fillColor: AppTheme.background,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Status chips
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: _statusFilters.map((st) {
                        final isSelected = _selectedStatus == st;
                        return Padding(
                          padding: const EdgeInsets.only(right: 8.0),
                          child: ChoiceChip(
                            key: Key('admin_status_filter_$st'),
                            label: Text(st),
                            selected: isSelected,
                            selectedColor: AppTheme.primary,
                            labelStyle: TextStyle(
                              color: isSelected ? Colors.white : AppTheme.textPrimary,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              fontSize: 12,
                            ),
                            onSelected: (_) {
                              setState(() => _selectedStatus = st);
                              _loadArticles();
                            },
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                ],
              ),
            ),

            // Articles list
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
                  : _errorMessage != null
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(_errorMessage!),
                              const SizedBox(height: 12),
                              ElevatedButton(onPressed: _loadArticles, child: const Text('Retry')),
                            ],
                          ),
                        )
                      : _articles.isEmpty
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.article_outlined, size: 48, color: Colors.grey.shade400),
                                  const SizedBox(height: 12),
                                  const Text('No articles found.', style: TextStyle(color: AppTheme.textSecondary)),
                                ],
                              ),
                            )
                          : RefreshIndicator(
                              onRefresh: _loadArticles,
                              color: AppTheme.primary,
                              child: ListView.builder(
                                padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
                                itemCount: _articles.length,
                                itemBuilder: (context, index) {
                                  final article = _articles[index];
                                  return _buildAdminArticleCard(article);
                                },
                              ),
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAdminArticleCard(HealthArticle article) {
    final statusColor = _getStatusColor(article.status);
    final statusBg = _getStatusBg(article.status);

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top Row: Category and Status Pill
          Row(
            children: [
              Text(
                article.category.toUpperCase(),
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primary,
                  letterSpacing: 0.5,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: statusColor.withValues(alpha: 0.3)),
                ),
                child: Text(
                  article.status,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Title
          Text(
            article.title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 4),

          // Summary
          Text(
            article.summary,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary, height: 1.3),
          ),
          const SizedBox(height: 10),

          // ID and reading time
          Row(
            children: [
              Text(
                article.contentId,
                style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: AppTheme.textSecondary),
              ),
              const SizedBox(width: 12),
              Text(
                '${article.readingTimeMinutes} min read',
                style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
              ),
            ],
          ),
          const Divider(height: 24),

          // Action Buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              // Edit button
              TextButton.icon(
                key: Key('edit_article_${article.contentId}'),
                onPressed: () => _openEditor(article),
                icon: const Icon(Icons.edit_outlined, size: 16),
                label: const Text('Edit'),
              ),
              const SizedBox(width: 8),

              // Publish button (if draft or archived)
              if (article.status != 'PUBLISHED')
                ElevatedButton.icon(
                  key: Key('publish_article_${article.contentId}'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green.shade700,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  onPressed: () => _publishArticle(article),
                  icon: const Icon(Icons.publish_rounded, size: 16),
                  label: const Text('Publish'),
                ),

              // Archive button (if published or draft)
              if (article.status != 'ARCHIVED') ...[
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  key: Key('archive_article_${article.contentId}'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.error,
                    side: const BorderSide(color: AppTheme.error),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  onPressed: () => _archiveArticle(article),
                  icon: const Icon(Icons.archive_outlined, size: 16),
                  label: const Text('Archive'),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
