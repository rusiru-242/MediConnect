
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../core/network/api_exceptions.dart';
import '../core/theme/app_theme.dart';
import '../services/profile_service.dart';
import 'user_avatar.dart';

/// R02: change or remove the signed-in user's profile picture (patients and doctors).
///
/// Flow: choose gallery / camera / remove -> adjust the square -> confirm -> upload with progress (retry on failure).
/// Cancelling at any step leaves the current picture untouched. Images are picked through the system photo picker or
/// the system camera app, so MediConnect itself requests no storage or camera permission.
class ProfilePictureEditor {
  ProfilePictureEditor._();

  /// Test seam.
  static ImagePicker Function() pickerFactory = ImagePicker.new;

  static Future<void> open(
    BuildContext context, {
    required String? currentUrl,
    required void Function(String? newUrl) onChanged,
    ProfileService? service,
  }) async {
    final choice = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              key: const Key('photo_gallery'),
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choose from gallery'),
              onTap: () => Navigator.pop(ctx, 'gallery'),
            ),
            ListTile(
              key: const Key('photo_camera'),
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('Take a photo'),
              onTap: () => Navigator.pop(ctx, 'camera'),
            ),
            if (currentUrl != null && currentUrl.isNotEmpty)
              ListTile(
                key: const Key('photo_remove'),
                leading: const Icon(Icons.delete_outline, color: AppTheme.error),
                title: const Text('Remove photo', style: TextStyle(color: AppTheme.error)),
                onTap: () => Navigator.pop(ctx, 'remove'),
              ),
            ListTile(
              key: const Key('photo_cancel'),
              leading: const Icon(Icons.close),
              title: const Text('Cancel'),
              onTap: () => Navigator.pop(ctx),
            ),
          ],
        ),
      ),
    );
    if (choice == null || !context.mounted) return;
    final svc = service ?? ProfileService();
    if (choice == 'remove') {
      await _remove(context, svc, currentUrl, onChanged);
      return;
    }
    XFile? picked;
    try {
      picked = await pickerFactory().pickImage(
        source: choice == 'camera' ? ImageSource.camera : ImageSource.gallery,
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 90,
        requestFullMetadata: false,
        preferredCameraDevice: CameraDevice.front,
      );
    } on PlatformException catch (e) {
      if (context.mounted) _snack(context, _pickError(e, choice == 'camera'));
      return;
    } catch (_) {
      if (context.mounted) _snack(context, 'The photo could not be opened. Please try another one.');
      return;
    }
    if (picked == null || !context.mounted) return; // cancelled: nothing changes
    final bytes = await picked.readAsBytes();
    if (!context.mounted) return;
    final newUrl = await Navigator.of(context).push<String>(MaterialPageRoute(
      builder: (_) => AvatarCropScreen(bytes: bytes, filename: picked!.name, service: svc),
    ));
    if (newUrl != null) {
      AvatarCache.evict(currentUrl);
      onChanged(newUrl);
      if (context.mounted) _snack(context, 'Profile photo updated.');
    }
  }

  static String _pickError(PlatformException e, bool camera) {
    final code = e.code.toLowerCase();
    if (code.contains('denied')) {
      return camera
          ? 'Camera access was not allowed. You can allow it in Settings, or choose a photo from the gallery.'
          : 'Photo access was not allowed. You can allow it in Settings.';
    }
    if (code.contains('camera')) return 'No camera is available on this device. Choose a photo from the gallery.';
    return 'The photo could not be opened. Please try another one.';
  }

  static Future<void> _remove(BuildContext context, ProfileService svc, String? currentUrl,
      void Function(String?) onChanged) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove profile photo?'),
        content: const Text('Your photo will be deleted and the default avatar shown instead.'),
        actions: [
          TextButton(key: const Key('photo_remove_cancel'), onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(key: const Key('photo_remove_confirm'), onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    try {
      await svc.removePicture();
      AvatarCache.evict(currentUrl);
      onChanged(null);
      if (context.mounted) _snack(context, 'Profile photo removed.');
    } catch (e) {
      if (context.mounted) _snack(context, _uploadError(e, removing: true));
    }
  }

  static void _snack(BuildContext context, String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
}

String _uploadError(Object e, {bool removing = false}) {
  if (e is ApiException && e.message.isNotEmpty) return e.message;
  if (e is NetworkException) return 'No connection to MediConnect. Check your connection and try again.';
  return removing ? 'The photo could not be removed. Please try again.' : 'The photo could not be uploaded. Please try again.';
}

/// Square preview: drag and pinch to choose the part of the photo to use, then upload it.
class AvatarCropScreen extends StatefulWidget {
  final Uint8List bytes;
  final String filename;
  final ProfileService service;

  const AvatarCropScreen({super.key, required this.bytes, required this.filename, required this.service});

  @override
  State<AvatarCropScreen> createState() => _AvatarCropScreenState();
}

class _AvatarCropScreenState extends State<AvatarCropScreen> {
  final _transform = TransformationController();
  Size? _imageSize;
  bool _decodeFailed = false;
  bool _centered = false;
  bool _uploading = false;
  double _progress = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    decodeImageFromList(widget.bytes).then((img) {
      if (mounted) setState(() => _imageSize = Size(img.width.toDouble(), img.height.toDouble()));
    }).catchError((Object _) {
      if (mounted) setState(() => _decodeFailed = true);
    });
  }

  @override
  void dispose() {
    _transform.dispose();
    super.dispose();
  }

  /// The visible square as fractions of the image: x, y of the top-left corner and the side relative to the short side.
  ({double x, double y, double size}) _crop(double viewport) {
    final size = _imageSize!;
    final base = viewport / size.shortestSide;
    final m = _transform.value;
    final scale = m.getMaxScaleOnAxis();
    final t = m.getTranslation();
    final side = (viewport / (scale * base)) / size.shortestSide;
    final x = (-t.x / (scale * base)) / size.width;
    final y = (-t.y / (scale * base)) / size.height;
    final s = side.clamp(0.01, 1.0);
    return (
      x: x.clamp(0.0, (1 - s * size.shortestSide / size.width).clamp(0.0, 1.0)),
      y: y.clamp(0.0, (1 - s * size.shortestSide / size.height).clamp(0.0, 1.0)),
      size: s,
    );
  }

  Future<void> _upload(double viewport) async {
    final crop = _crop(viewport);
    setState(() {
      _uploading = true;
      _error = null;
      _progress = 0;
    });
    try {
      final url = await widget.service.uploadPicture(
        widget.bytes,
        filename: widget.filename,
        cropX: crop.x,
        cropY: crop.y,
        cropSize: crop.size,
        onProgress: (sent, total) {
          if (mounted && total > 0) setState(() => _progress = sent / total);
        },
      );
      if (mounted) Navigator.of(context).pop(url);
    } catch (e) {
      if (mounted) {
        setState(() {
          _uploading = false;
          _error = _uploadError(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Adjust photo'),
        leading: IconButton(
          key: const Key('avatar_crop_cancel'),
          icon: const Icon(Icons.close),
          tooltip: 'Cancel',
          onPressed: _uploading ? null : () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: LayoutBuilder(builder: (context, constraints) {
          final viewport = (constraints.maxWidth - 32).clamp(160.0, 420.0);
          if (_imageSize != null && !_centered) {
            // Start on the centre of the photo (the same square the server would use without a crop).
            _centered = true;
            final base = viewport / _imageSize!.shortestSide;
            final dx = -(_imageSize!.width * base - viewport) / 2;
            final dy = -(_imageSize!.height * base - viewport) / 2;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) _transform.value = Matrix4.translationValues(dx, dy, 0);
            });
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Text(
                  _imageSize == null ? '' : 'Drag and pinch to choose the part of the photo to use.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                SizedBox.square(
                  dimension: viewport,
                  child: _decodeFailed
                      ? const Center(child: Text('This photo cannot be shown. Choose another one.', key: Key('avatar_decode_error')))
                      : _imageSize == null
                          ? const Center(child: CircularProgressIndicator())
                          : ClipRect(
                              child: Stack(
                                children: [
                                  InteractiveViewer(
                                    key: const Key('avatar_crop_view'),
                                    transformationController: _transform,
                                    constrained: false,
                                    minScale: 1,
                                    maxScale: 5,
                                    boundaryMargin: EdgeInsets.zero,
                                    panEnabled: !_uploading,
                                    scaleEnabled: !_uploading,
                                    child: Image.memory(
                                      widget.bytes,
                                      width: _imageSize!.width * viewport / _imageSize!.shortestSide,
                                      height: _imageSize!.height * viewport / _imageSize!.shortestSide,
                                      fit: BoxFit.fill,
                                    ),
                                  ),
                                  IgnorePointer(
                                    child: Container(
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        border: Border.all(color: Colors.white.withValues(alpha: 0.9), width: 2),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                ),
                const SizedBox(height: 16),
                if (_uploading) ...[
                  LinearProgressIndicator(key: const Key('avatar_upload_progress'), value: _progress > 0 ? _progress : null),
                  const SizedBox(height: 8),
                  Text(_progress >= 1 ? 'Processing...' : 'Uploading ${(100 * _progress).round()}%'),
                ],
                if (_error != null) ...[
                  Text(_error!, key: const Key('avatar_upload_error'), style: const TextStyle(color: AppTheme.error)),
                  const SizedBox(height: 8),
                ],
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    key: Key(_error == null ? 'avatar_crop_confirm' : 'avatar_upload_retry'),
                    onPressed: (_imageSize == null || _uploading) ? null : () => _upload(viewport),
                    icon: Icon(_error == null ? Icons.check : Icons.refresh),
                    label: Text(_error == null ? 'Use this photo' : 'Retry upload'),
                  ),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }
}
