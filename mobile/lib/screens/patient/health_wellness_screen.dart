import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/health_content.dart';
import '../../services/health_content_service.dart';
import 'article_detail_screen.dart';

/// Patient Health & Wellness Educational Content Feed (Phase 24).
class HealthWellnessScreen extends StatefulWidget {
  const HealthWellnessScreen({super.key});

  @override
  State<HealthWellnessScreen> createState() => _HealthWellnessScreenState();
}

class _HealthWellnessScreenState extends State<HealthWellnessScreen> {
  final HealthContentService _service = HealthContentService();
  final TextEditingController _searchController = TextEditingController();

  final List<String> _categories = const [
    'All',
    'Healthy Food',
    'Exercise',
    'Nutrition',
    'Mental Wellness',
    'Preventive Healthcare',
    'General Health Tips',
    'Bookmarks',
  ];

  String _selectedCategory = 'All';
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
      if (_selectedCategory == 'Bookmarks') {
        final res = await _service.fetchBookmarks(pageSize: 30);
        if (mounted) {
          setState(() {
            _articles = res.items;
            _isLoading = false;
          });
        }
      } else {
        final catFilter = _selectedCategory == 'All' ? null : _selectedCategory;
        final res = await _service.fetchPublishedArticles(
          category: catFilter,
          search: _searchQuery.trim().isEmpty ? null : _searchQuery.trim(),
          pageSize: 30,
        );
        if (mounted) {
          setState(() {
            _articles = res.items;
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Failed to load health articles. Please check your network and try again.';
        });
      }
    }
  }

  Future<void> _handleToggleBookmark(HealthArticle article) async {
    final originalState = article.isBookmarked;
    setState(() {
      final index = _articles.indexWhere((a) => a.contentId == article.contentId);
      if (index != -1) {
        _articles[index] = article.copyWith(isBookmarked: !originalState);
      }
    });

    try {
      final newState = await _service.toggleBookmark(article.contentId);
      if (mounted) {
        setState(() {
          final index = _articles.indexWhere((a) => a.contentId == article.contentId);
          if (index != -1) {
            _articles[index] = article.copyWith(isBookmarked: newState);
          }
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
      // Revert on error
      if (mounted) {
        setState(() {
          final index = _articles.indexWhere((a) => a.contentId == article.contentId);
          if (index != -1) {
            _articles[index] = article.copyWith(isBookmarked: originalState);
          }
        });
      }
    }
  }

  void _onCategorySelected(String category) {
    if (_selectedCategory == category) return;
    setState(() {
      _selectedCategory = category;
    });
    _loadArticles();
  }

  void _onSearchSubmitted(String query) {
    setState(() {
      _searchQuery = query;
    });
    _loadArticles();
  }

  void _clearSearch() {
    _searchController.clear();
    setState(() {
      _searchQuery = '';
    });
    _loadArticles();
  }

  void _openArticleDetail(HealthArticle article) async {
    final updated = await Navigator.of(context).push<HealthArticle>(
      MaterialPageRoute(
        builder: (_) => ArticleDetailScreen(
          articleIdentifier: article.contentId,
          initialArticle: article,
        ),
      ),
    );
    if (updated != null && mounted) {
      setState(() {
        final idx = _articles.indexWhere((a) => a.contentId == updated.contentId);
        if (idx != -1) {
          _articles[idx] = updated;
        }
      });
    }
  }

  IconData _getCategoryIcon(String category) {
    switch (category) {
      case 'Healthy Food':
        return Icons.restaurant_rounded;
      case 'Nutrition':
        return Icons.local_dining_rounded;
      case 'Exercise':
        return Icons.fitness_center_rounded;
      case 'Mental Wellness':
        return Icons.self_improvement_rounded;
      case 'Preventive Healthcare':
        return Icons.health_and_safety_rounded;
      case 'Health News':
        return Icons.newspaper_rounded;
      default:
        return Icons.spa_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final featuredArticle = _articles.isNotEmpty ? _articles.first : null;
    final otherArticles = _articles.length > 1 ? _articles.sublist(1) : <HealthArticle>[];

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Health & Wellness'),
        actions: [
          IconButton(
            key: const Key('health_feed_bookmarks_icon_button'),
            tooltip: 'My Bookmarks',
            icon: Icon(
              _selectedCategory == 'Bookmarks' ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
              color: _selectedCategory == 'Bookmarks' ? Colors.amberAccent : null,
            ),
            onPressed: () => _onCategorySelected('Bookmarks'),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadArticles,
          color: AppTheme.primary,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // Search & Header
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Search Bar
                      Container(
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppTheme.border),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.03),
                              blurRadius: 10,
                              offset: const Offset(0, 3),
                            ),
                          ],
                        ),
                        child: TextField(
                          key: const Key('health_feed_search_input'),
                          controller: _searchController,
                          textInputAction: TextInputAction.search,
                          onSubmitted: _onSearchSubmitted,
                          decoration: InputDecoration(
                            hintText: 'Search food, exercises, wellness tips...',
                            hintStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 14),
                            prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.primary),
                            suffixIcon: _searchController.text.isNotEmpty
                                ? IconButton(
                                    icon: const Icon(Icons.clear_rounded, size: 20),
                                    onPressed: _clearSearch,
                                  )
                                : null,
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Category Tabs
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: _categories.map((cat) {
                            final isSelected = _selectedCategory == cat;
                            return Padding(
                              padding: const EdgeInsets.only(right: 8.0),
                              child: FilterChip(
                                key: Key('category_chip_${cat.replaceAll(" ", "_")}'),
                                label: Text(cat),
                                selected: isSelected,
                                onSelected: (_) => _onCategorySelected(cat),
                                backgroundColor: Colors.white,
                                selectedColor: AppTheme.primary,
                                checkmarkColor: Colors.white,
                                labelStyle: TextStyle(
                                  fontSize: 13,
                                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                  color: isSelected ? Colors.white : AppTheme.textPrimary,
                                ),
                                side: BorderSide(
                                  color: isSelected ? AppTheme.primary : AppTheme.border,
                                ),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Content Body
              if (_isLoading)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(
                    child: CircularProgressIndicator(color: AppTheme.primary),
                  ),
                )
              else if (_errorMessage != null)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.wifi_off_rounded, size: 48, color: Colors.grey.shade400),
                          const SizedBox(height: 16),
                          Text(
                            _errorMessage!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton.icon(
                            onPressed: _loadArticles,
                            icon: const Icon(Icons.refresh_rounded, size: 18),
                            label: const Text('Try Again'),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
              else if (_articles.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            _selectedCategory == 'Bookmarks'
                                ? Icons.bookmark_border_rounded
                                : Icons.article_outlined,
                            size: 56,
                            color: Colors.grey.shade400,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            _selectedCategory == 'Bookmarks'
                                ? 'No bookmarked articles yet'
                                : 'No articles found',
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _selectedCategory == 'Bookmarks'
                                ? 'Tap the bookmark icon on any article to save it for quick reading later.'
                                : 'Try searching for other wellness topics or select another category.',
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
              else ...[
                // Featured Article (First article in list when not searching)
                if (featuredArticle != null && _searchQuery.isEmpty && _selectedCategory != 'Bookmarks')
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                      child: _buildFeaturedCard(featuredArticle),
                    ),
                  ),

                // Section Title for Remaining Articles
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                    child: Text(
                      _selectedCategory == 'Bookmarks'
                          ? 'Saved Articles (${_articles.length})'
                          : _searchQuery.isNotEmpty
                              ? 'Search Results (${_articles.length})'
                              : 'Recommended Articles',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ),
                ),

                // Article Cards List
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                  sliver: SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final article = (_searchQuery.isNotEmpty || _selectedCategory == 'Bookmarks')
                            ? _articles[index]
                            : otherArticles[index];
                        return _buildArticleCard(article);
                      },
                      childCount: (_searchQuery.isNotEmpty || _selectedCategory == 'Bookmarks')
                          ? _articles.length
                          : otherArticles.length,
                    ),
                  ),
                ),

                // Educational Disclaimer Footer
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.blueGrey.shade50,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.blueGrey.shade100),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.info_outline_rounded, size: 20, color: Colors.blueGrey.shade700),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Educational Disclaimer: MediConnect health articles are for informational purposes only. Do not rely on them as medical diagnosis or treatment. Consult a licensed physician for personal health concerns.',
                              style: TextStyle(
                                fontSize: 11,
                                height: 1.4,
                                color: Colors.blueGrey.shade800,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFeaturedCard(HealthArticle article) {
    return InkWell(
      key: Key('featured_article_${article.contentId}'),
      onTap: () => _openArticleDetail(article),
      borderRadius: BorderRadius.circular(20),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.border),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 14,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Cover Image or Fallback Gradient
            Stack(
              children: [
                if (article.coverImage != null && article.coverImage!.startsWith('http'))
                  Image.network(
                    article.coverImage!,
                    height: 180,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => _buildFallbackBanner(article),
                  )
                else
                  _buildFallbackBanner(article),

                // Category Badge
                Positioned(
                  top: 14,
                  left: 14,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.7),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(_getCategoryIcon(article.category), size: 14, color: Colors.white),
                        const SizedBox(width: 6),
                        Text(
                          article.category,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                // Bookmark Button
                Positioned(
                  top: 10,
                  right: 10,
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(20),
                      onTap: () => _handleToggleBookmark(article),
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.5),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          article.isBookmarked ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                          size: 20,
                          color: article.isBookmarked ? Colors.amberAccent : Colors.white,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),

            // Content Body
            Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.timer_outlined, size: 14, color: AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        '${article.readingTimeMinutes} min read',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                      const Spacer(),
                      const Text(
                        'FEATURED',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 0.8,
                          color: AppTheme.primary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    article.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimary,
                      height: 1.25,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    article.summary,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildArticleCard(HealthArticle article) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: InkWell(
        key: Key('article_card_${article.contentId}'),
        onTap: () => _openArticleDetail(article),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppTheme.border),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.02),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Thumbnail
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: article.coverImage != null && article.coverImage!.startsWith('http')
                    ? Image.network(
                        article.coverImage!,
                        width: 90,
                        height: 90,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => _buildThumbFallback(article),
                      )
                    : _buildThumbFallback(article),
              ),
              const SizedBox(width: 14),

              // Title and Summary
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          article.category.toUpperCase(),
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primary,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${article.readingTimeMinutes} min',
                          style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      article.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                        height: 1.25,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      article.summary,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),

              // Bookmark icon
              IconButton(
                key: Key('bookmark_btn_${article.contentId}'),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                icon: Icon(
                  article.isBookmarked ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                  size: 22,
                  color: article.isBookmarked ? Colors.amber.shade700 : Colors.grey.shade400,
                ),
                onPressed: () => _handleToggleBookmark(article),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFallbackBanner(HealthArticle article) {
    return Container(
      height: 180,
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0D5C56), Color(0xFF14B8A6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Center(
        child: Icon(
          _getCategoryIcon(article.category),
          size: 64,
          color: Colors.white.withValues(alpha: 0.4),
        ),
      ),
    );
  }

  Widget _buildThumbFallback(HealthArticle article) {
    return Container(
      width: 90,
      height: 90,
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        _getCategoryIcon(article.category),
        size: 36,
        color: AppTheme.primary,
      ),
    );
  }
}
