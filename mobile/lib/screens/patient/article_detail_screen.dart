import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/health_content.dart';
import '../../services/health_content_service.dart';

/// Article detail screen displaying educational health content and medical disclaimer (Phase 24).
class ArticleDetailScreen extends StatefulWidget {
  final String articleIdentifier;
  final HealthArticle? initialArticle;

  const ArticleDetailScreen({
    super.key,
    required this.articleIdentifier,
    this.initialArticle,
  });

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  final HealthContentService _service = HealthContentService();

  late HealthArticle _article;
  bool _isLoading = false;
  String? _errorMessage;
  bool _hasToggledBookmark = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialArticle != null) {
      _article = widget.initialArticle!;
    }
    _fetchFullArticle();
  }

  Future<void> _fetchFullArticle() async {
    if (widget.initialArticle == null) {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });
    }

    try {
      final res = await _service.fetchArticleDetail(widget.articleIdentifier);
      if (mounted) {
        setState(() {
          _article = res;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted && widget.initialArticle == null) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Failed to load article details. Please try again.';
        });
      }
    }
  }

  Future<void> _handleToggleBookmark() async {
    final originalState = _article.isBookmarked;
    setState(() {
      _article = _article.copyWith(isBookmarked: !originalState);
      _hasToggledBookmark = true;
    });

    try {
      final newState = await _service.toggleBookmark(_article.contentId);
      if (mounted) {
        setState(() {
          _article = _article.copyWith(isBookmarked: newState);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(newState ? 'Saved to bookmarks' : 'Removed from bookmarks'),
            duration: const Duration(seconds: 2),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _article = _article.copyWith(isBookmarked: originalState);
        });
      }
    }
  }

  String _formatDate(DateTime? dt) {
    if (dt == null) return '';
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }

  Widget _buildFormattedBody(String text) {
    final lines = text.split('\n');
    final widgets = <Widget>[];

    for (final rawLine in lines) {
      final line = rawLine.trim();
      if (line.isEmpty) {
        widgets.add(const SizedBox(height: 10));
      } else if (line.startsWith('### ')) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(top: 14.0, bottom: 6.0),
            child: Text(
              line.substring(4),
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
        );
      } else if (line.startsWith('## ')) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(top: 18.0, bottom: 8.0),
            child: Text(
              line.substring(3),
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppTheme.primary,
              ),
            ),
          ),
        );
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 6.0, left: 8.0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('• ', style: TextStyle(fontSize: 16, color: AppTheme.primary, fontWeight: FontWeight.bold)),
                Expanded(
                  child: Text(
                    line.substring(2).replaceAll('**', ''),
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppTheme.textPrimary,
                      height: 1.45,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      } else if (line.startsWith('*Disclaimer:')) {
        // Handled specially in footer disclaimer box
        continue;
      } else {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 8.0),
            child: Text(
              line.replaceAll('**', ''),
              style: const TextStyle(
                fontSize: 14,
                color: AppTheme.textPrimary,
                height: 1.5,
              ),
            ),
          ),
        );
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: true,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop && _hasToggledBookmark) {
          // Handled via will pop or Navigator result
        }
      },
      child: Scaffold(
        backgroundColor: Colors.white,
        body: _isLoading
            ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
            : _errorMessage != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.error),
                          const SizedBox(height: 16),
                          Text(_errorMessage!, textAlign: TextAlign.center),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _fetchFullArticle,
                            child: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  )
                : CustomScrollView(
                    slivers: [
                      // Sliver App Bar with Image
                      SliverAppBar(
                        expandedHeight: 240,
                        pinned: true,
                        leading: IconButton(
                          icon: Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.4),
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.arrow_back_rounded, color: Colors.white, size: 20),
                          ),
                          onPressed: () => Navigator.of(context).pop(_article),
                        ),
                        actions: [
                          IconButton(
                            key: const Key('article_detail_bookmark_icon_button'),
                            icon: Container(
                              padding: const EdgeInsets.all(6),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.4),
                                shape: BoxShape.circle,
                              ),
                              child: Icon(
                                _article.isBookmarked ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                                color: _article.isBookmarked ? Colors.amberAccent : Colors.white,
                                size: 20,
                              ),
                            ),
                            onPressed: _handleToggleBookmark,
                          ),
                        ],
                        flexibleSpace: FlexibleSpaceBar(
                          background: Stack(
                            fit: StackFit.expand,
                            children: [
                              if (_article.coverImage != null && _article.coverImage!.startsWith('http'))
                                Image.network(
                                  _article.coverImage!,
                                  fit: BoxFit.cover,
                                  errorBuilder: (context, error, stackTrace) => _buildHeaderFallback(),
                                )
                              else
                                _buildHeaderFallback(),
                              Container(
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    colors: [
                                      Colors.black.withValues(alpha: 0.6),
                                      Colors.transparent,
                                      Colors.black.withValues(alpha: 0.5),
                                    ],
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                      // Article Content
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.all(20.0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Category and Reading time badge
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: AppTheme.primary.withValues(alpha: 0.1),
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      _article.category,
                                      style: const TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.primary,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  const Icon(Icons.timer_outlined, size: 14, color: AppTheme.textSecondary),
                                  const SizedBox(width: 4),
                                  Text(
                                    '${_article.readingTimeMinutes} min read',
                                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                                  ),
                                  if (_article.publishedAt != null) ...[
                                    const Spacer(),
                                    Text(
                                      _formatDate(_article.publishedAt),
                                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                                    ),
                                  ],
                                ],
                              ),
                              const SizedBox(height: 16),

                              // Title
                              Text(
                                _article.title,
                                style: const TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.textPrimary,
                                  height: 1.25,
                                ),
                              ),
                              const SizedBox(height: 10),

                              // Author & Editorial info
                              Row(
                                children: [
                                  CircleAvatar(
                                    radius: 14,
                                    backgroundColor: AppTheme.primary.withValues(alpha: 0.15),
                                    child: const Icon(Icons.verified_user_rounded, size: 16, color: AppTheme.primary),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      'Reviewed by ${_article.authorName}',
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w500,
                                        color: AppTheme.textSecondary,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),

                              // Summary Callout
                              Container(
                                padding: const EdgeInsets.all(16),
                                decoration: BoxDecoration(
                                  color: AppTheme.primary.withValues(alpha: 0.05),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
                                ),
                                child: Text(
                                  _article.summary,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontStyle: FontStyle.italic,
                                    color: AppTheme.textPrimary,
                                    height: 1.45,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 20),

                              // Article Body
                              _buildFormattedBody(_article.body),
                              const SizedBox(height: 24),

                              // Tags
                              if (_article.tags.isNotEmpty) ...[
                                const Text(
                                  'Tags',
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  children: _article.tags
                                      .map(
                                        (tag) => Chip(
                                          label: Text(tag),
                                          labelStyle: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
                                          backgroundColor: AppTheme.background,
                                          side: const BorderSide(color: AppTheme.border),
                                          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                                        ),
                                      )
                                      .toList(),
                                ),
                                const SizedBox(height: 20),
                              ],

                              // Sources & Citations
                              if (_article.sources != null && _article.sources!.isNotEmpty) ...[
                                Container(
                                  padding: const EdgeInsets.all(14),
                                  decoration: BoxDecoration(
                                    color: Colors.grey.shade50,
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(color: Colors.grey.shade200),
                                  ),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Row(
                                        children: [
                                          Icon(Icons.menu_book_rounded, size: 16, color: AppTheme.primary),
                                          SizedBox(width: 6),
                                          Text(
                                            'Sources & References',
                                            style: TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.bold,
                                              color: AppTheme.textPrimary,
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      Text(
                                        _article.sources!,
                                        style: TextStyle(fontSize: 12, color: Colors.grey.shade700, height: 1.4),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 24),
                              ],

                              // Medical Disclaimer Box (Requirement 5 & 11)
                              Container(
                                padding: const EdgeInsets.all(16),
                                decoration: BoxDecoration(
                                  color: Colors.amber.shade50,
                                  borderRadius: BorderRadius.circular(14),
                                  border: Border.all(color: Colors.amber.shade200),
                                ),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Icon(Icons.shield_outlined, color: Colors.amber.shade900, size: 24),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            'Medical Disclaimer',
                                            style: TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.bold,
                                              color: Colors.amber.shade900,
                                            ),
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            'This article is strictly for educational and informational purposes. It is not intended to be a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or qualified health provider with any questions you may have regarding a medical condition.',
                                            style: TextStyle(
                                              fontSize: 12,
                                              height: 1.4,
                                              color: Colors.amber.shade900,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 40),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }

  Widget _buildHeaderFallback() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0F766E), Color(0xFF14B8A6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: const Center(
        child: Icon(Icons.spa_rounded, size: 72, color: Colors.white30),
      ),
    );
  }
}
