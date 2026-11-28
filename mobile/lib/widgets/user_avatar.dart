import 'dart:collection';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../core/network/api_client.dart';

/// R02: in-memory cache of profile pictures, keyed by the versioned URL the backend returns
/// (`/api/profile/pictures/<userId>?v=<version>`). A replaced picture has a new version, so its URL - and cache key -
/// changes and the old bytes are never shown again. Nothing is written to disk, and [clear] runs on login and logout
/// so a second account on the same device never sees the previous account's cached private picture.
class AvatarCache {
  AvatarCache._();

  static const int _maxEntries = 60;
  static final LinkedHashMap<String, Uint8List> _bytes = LinkedHashMap();
  static final Map<String, Future<Uint8List?>> _inFlight = {};
  static int _generation = 0;

  /// Test seam: replaces the network fetch.
  static Future<List<int>> Function(String endpoint)? fetchOverride;

  static Uint8List? peek(String url) => _bytes[url];

  static Future<Uint8List?> load(String url, ApiClient client) {
    final hit = _bytes[url];
    if (hit != null) return Future.value(hit);
    final pending = _inFlight[url];
    if (pending != null) return pending;
    final generation = _generation;
    final endpoint = url.startsWith('/api/') ? url.substring(4) : url;
    final future = (fetchOverride != null ? fetchOverride!(endpoint) : client.getBytes(endpoint)).then((data) {
      final bytes = Uint8List.fromList(data);
      if (generation == _generation && bytes.isNotEmpty) {
        _bytes[url] = bytes;
        while (_bytes.length > _maxEntries) {
          _bytes.remove(_bytes.keys.first);
        }
      }
      return bytes.isEmpty ? null : bytes;
    }).catchError((Object _) => null).whenComplete(() {
      // Block body on purpose: returning the removed Future (this one) would make whenComplete wait on itself.
      _inFlight.remove(url);
    });
    _inFlight[url] = future;
    return future;
  }

  /// Drops every cached picture (logout, login, account switch). Fetches already in flight are discarded.
  static void clear() {
    _generation++;
    _bytes.clear();
    _inFlight.clear();
    PaintingBinding.instance.imageCache.clear();
    PaintingBinding.instance.imageCache.clearLiveImages();
  }

  /// Forgets one picture (after the owner removes or replaces it).
  static void evict(String? url) {
    if (url != null) _bytes.remove(url);
  }
}

/// A user's profile picture with a neutral fallback.
///
/// * `/api/...` paths are MediConnect pictures: fetched with the signed-in session (the backend decides who may see
///   them) through [AvatarCache].
/// * `http(s)://` URLs are external pictures already on the account (for example a Google account photo); they are
///   loaded without MediConnect credentials.
/// * Anything else, a missing picture, a refused request or a broken image shows [fallback]. Errors never throw.
class UserAvatar extends StatefulWidget {
  final String? imageUrl;
  final double size;

  /// null = circle; otherwise a rounded square with this radius.
  final double? borderRadius;
  final Widget fallback;
  final String? semanticLabel;
  final ApiClient? client;

  const UserAvatar({
    super.key,
    required this.imageUrl,
    required this.size,
    required this.fallback,
    this.borderRadius,
    this.semanticLabel,
    this.client,
  });

  @override
  State<UserAvatar> createState() => _UserAvatarState();
}

class _UserAvatarState extends State<UserAvatar> {
  Uint8List? _bytes;
  String? _loadedFor;
  static final ApiClient _sharedClient = ApiClient();

  bool get _isApiPicture => (widget.imageUrl ?? '').startsWith('/api/');

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant UserAvatar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.imageUrl != widget.imageUrl) _load();
  }

  void _load() {
    final url = widget.imageUrl;
    _loadedFor = url;
    if (url == null || !_isApiPicture) {
      if (_bytes != null) setState(() => _bytes = null);
      return;
    }
    final cached = AvatarCache.peek(url);
    if (cached != null) {
      _bytes = cached;
      return;
    }
    _bytes = null;
    AvatarCache.load(url, widget.client ?? _sharedClient).then((bytes) {
      if (!mounted || _loadedFor != url) return;
      setState(() => _bytes = bytes);
    });
  }

  @override
  Widget build(BuildContext context) {
    final url = widget.imageUrl;
    Widget child;
    if (url != null && _isApiPicture && _bytes != null) {
      child = Image.memory(
        _bytes!,
        key: ValueKey('avatar_image_$url'),
        width: widget.size,
        height: widget.size,
        fit: BoxFit.cover,
        gaplessPlayback: true,
        cacheWidth: (widget.size * 3).round(),
        errorBuilder: (_, _, _) => widget.fallback,
      );
    } else if (url != null && (url.startsWith('https://') || url.startsWith('http://'))) {
      child = Image.network(
        url,
        width: widget.size,
        height: widget.size,
        fit: BoxFit.cover,
        cacheWidth: (widget.size * 3).round(),
        errorBuilder: (_, _, _) => widget.fallback,
      );
    } else {
      child = widget.fallback;
    }
    final clipped = widget.borderRadius == null
        ? ClipOval(child: SizedBox.square(dimension: widget.size, child: child))
        : ClipRRect(
            borderRadius: BorderRadius.circular(widget.borderRadius!),
            child: SizedBox.square(dimension: widget.size, child: child),
          );
    return Semantics(
      image: true,
      label: widget.semanticLabel,
      excludeSemantics: widget.semanticLabel != null,
      child: clipped,
    );
  }
}
