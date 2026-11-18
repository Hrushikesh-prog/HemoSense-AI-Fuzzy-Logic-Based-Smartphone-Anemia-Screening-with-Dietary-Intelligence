import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../models/roi_box.dart';
import '../theme.dart';
import '../widgets/ui.dart';
import 'analyzing_screen.dart';
import 'camera_screen.dart';

/// Maximum number of photos taken from the gallery.
const kMaxGalleryPhotos = 3;

/// Opens the system photo picker (1-3 photos) and shows them in the review
/// screen. With [replace] the current route is replaced.
Future<void> pickFromGalleryAndReview(BuildContext context,
    {List<String> symptoms = const [], bool replace = false}) async {
  final messenger = ScaffoldMessenger.maybeOf(context);
  List<XFile> picked;
  try {
    picked = await ImagePicker().pickMultiImage(
      limit: kMaxGalleryPhotos,
      maxWidth: 2048,
      maxHeight: 2048,
      imageQuality: 92,
    );
  } catch (e) {
    messenger?.showSnackBar(SnackBar(
        content: Text('Could not open the gallery: $e'),
        backgroundColor: C.severe));
    return;
  }
  if (picked.isEmpty || !context.mounted) return;
  if (picked.length > kMaxGalleryPhotos) {
    picked = picked.sublist(0, kMaxGalleryPhotos);
    messenger?.showSnackBar(const SnackBar(
        content: Text('Using the first $kMaxGalleryPhotos photos.')));
  }
  final route = MaterialPageRoute<void>(
      builder: (_) =>
          ReviewScreen(shots: picked, symptoms: symptoms, fromGallery: true));
  if (replace) {
    await Navigator.of(context).pushReplacement(route);
  } else {
    await Navigator.of(context).push(route);
  }
}

class _Photo {
  final XFile file;
  Uint8List? bytes;
  Size? size; // decoded size, EXIF-rotated (as displayed)
  bool failed = false;
  RoiBox box;
  /// True once the user has moved/resized the box (or it came from a previous attempt).
  /// Analysis is blocked until every photo's box is placed: an unplaced default box
  /// can land on the shirt or cheek instead of the eyelid.
  bool placed;
  _Photo(this.file, this.box, {this.placed = false});
  bool get ready => bytes != null && size != null && !failed;
}

/// ⑧ Review — one photo at its real aspect ratio with a draggable, resizable
/// box marking the pink inner eyelid. The box is sent to the server as
/// fractions of the displayed photo, so it maps exactly to pixels.
///
/// Camera-burst frames are nearly identical, so they share ONE box: moving or
/// resizing it on any frame updates every frame. Gallery photos are different
/// pictures and keep an independent box each.
class ReviewScreen extends StatefulWidget {
  final List<XFile> shots;
  final List<String> symptoms;
  final String eyeSide;
  final bool fromGallery;

  /// Optional boxes to start from (e.g. coming back from an error).
  final List<List<double>>? initialBoxes;

  const ReviewScreen({
    super.key,
    required this.shots,
    this.symptoms = const [],
    this.eyeSide = 'Left eye',
    this.fromGallery = false,
    this.initialBoxes,
  });

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  late final List<_Photo> _photos;
  int _sel = 0;

  /// True when all photos come from one camera burst and share one box.
  late final bool _sharedBox;

  @override
  void initState() {
    super.initState();
    _sharedBox = _decideShared();
    _photos = [
      for (var i = 0; i < widget.shots.length; i++)
        _Photo(widget.shots[i], _initialBox(i),
            placed: widget.initialBoxes != null && i < widget.initialBoxes!.length),
    ];
    _load();
  }

  /// Burst photos share one box. Gallery photos never do. Photos coming back
  /// from an error screen share only if they were all sent with the same box.
  bool _decideShared() {
    if (widget.fromGallery || widget.shots.length < 2) return false;
    final b = widget.initialBoxes;
    if (b == null || b.isEmpty) return true;
    final first = b.first;
    return b.every((x) =>
        x.length == first.length &&
        [for (var k = 0; k < x.length; k++) x[k] == first[k]].every((e) => e));
  }

  RoiBox _initialBox(int i) {
    final b = widget.initialBoxes;
    if (b != null && i < b.length && b[i].length == 4) {
      final r = RoiBox(b[i][0], b[i][1], b[i][2], b[i][3]);
      // Re-validate through the clamping logic.
      return r.moveBy(0, 0);
    }
    return RoiBox.start;
  }

  bool get _allPlaced => _photos.where((p) => p.ready).every((p) => p.placed);

  Future<void> _load() async {
    for (final p in _photos) {
      try {
        final bytes = await p.file.readAsBytes();
        final img = await decodeImageFromList(bytes);
        final size = Size(img.width.toDouble(), img.height.toDouble());
        img.dispose();
        if (!mounted) return;
        setState(() {
          p.bytes = bytes;
          p.size = size;
        });
      } catch (_) {
        if (mounted) setState(() => p.failed = true);
      }
    }
  }

  void _remove(int i) {
    if (_photos.length <= 1) return;
    setState(() {
      _photos.removeAt(i);
      if (_sel >= _photos.length) _sel = _photos.length - 1;
    });
  }

  void _analyse() {
    final usable = _photos.where((p) => p.ready).toList();
    if (usable.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('No usable photo. Retake or choose another photo.'),
          backgroundColor: C.severe));
      return;
    }
    Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) => AnalyzingScreen(
              shots: [for (final p in usable) p.file],
              roiBoxes: [for (final p in usable) p.box.toList()],
              symptoms: widget.symptoms,
              eyeSide: widget.eyeSide,
            )));
  }

  void _retake() {
    if (widget.fromGallery) {
      pickFromGalleryAndReview(context, symptoms: widget.symptoms, replace: true);
    } else {
      Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => CameraScreen(symptoms: widget.symptoms)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final failedCount = _photos.where((p) => p.failed).length;
    final current = _photos.isEmpty ? null : _photos[_sel];
    return Scaffold(
      appBar: AppBar(title: const Text('Review photo')),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(14, 2, 14, 6),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.crop_free_rounded, size: 16, color: C.primary),
                      SizedBox(width: 6),
                      Flexible(
                        child: Text('Drag the box onto the pink half-moon under the eye',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                                fontSize: 13, fontWeight: FontWeight.w800)),
                      ),
                    ],
                  ),
                  SizedBox(height: 2),
                  Text('Keep it small: just the pink inner eyelid, not skin or clothes · drag a corner to resize',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 10, color: C.muted)),
                ],
              ),
            ),
            if (_photos.length > 1)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 0, 14, 6),
                child: Text(
                  _sharedBox
                      ? 'One box is used for all ${_photos.length} burst photos'
                      : 'Place the box on each photo',
                  key: const ValueKey('boxModeHint'),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      fontSize: 11,
                      color: C.primary,
                      fontWeight: FontWeight.w700),
                ),
              ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: LayoutBuilder(builder: (context, c) {
                  if (current == null) return const SizedBox();
                  return Center(child: _editor(current, c.maxWidth, c.maxHeight));
                }),
              ),
            ),
            const SizedBox(height: 8),
            // Thumbnails (tap to switch photo; burst photos share one box,
            // gallery photos keep their own)
            SizedBox(
              height: 64,
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                scrollDirection: Axis.horizontal,
                itemCount: _photos.length,
                separatorBuilder: (_, _) => const SizedBox(width: 6),
                itemBuilder: (context, i) => _thumb(i),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 6, 14, 6),
              child: Text(
                '${_photos.length} photo${_photos.length == 1 ? '' : 's'} · ${widget.fromGallery ? 'from gallery' : widget.eyeSide}'
                '${failedCount > 0 ? ' · $failedCount could not be opened and will be skipped' : ''}',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: 10.5, color: failedCount > 0 ? C.severe : C.muted),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: Icon(
                          widget.fromGallery
                              ? Icons.photo_library_outlined
                              : Icons.refresh_rounded,
                          size: 15),
                      label: Text(widget.fromGallery ? 'Choose again' : 'Retake'),
                      onPressed: _retake,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    flex: 2,
                    child: FilledButton(
                      onPressed: _photos.any((p) => p.ready) && _allPlaced ? _analyse : null,
                      child: Text(_allPlaced
                          ? 'Analyse'
                          : _photos.length > 1 && !_sharedBox
                              ? 'Place the box on every photo'
                              : 'Place the box first'),
                    ),
                  ),
                ],
              ),
            ),
            DisclaimerFooter(),
          ],
        ),
      ),
    );
  }

  Widget _editor(_Photo p, double maxW, double maxH) {
    if (p.failed) {
      return Container(
        height: math.min(maxH, 220),
        decoration: BoxDecoration(
          color: const Color(0xFF2A2A2A),
          borderRadius: BorderRadius.circular(14),
        ),
        alignment: Alignment.center,
        padding: const EdgeInsets.all(16),
        child: const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.broken_image_rounded, color: Colors.white54, size: 36),
            SizedBox(height: 6),
            Text('This photo could not be opened.',
                style: TextStyle(color: Colors.white70, fontSize: 11)),
          ],
        ),
      );
    }
    if (!p.ready) {
      return const SizedBox(
          width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2));
    }
    final s = p.size!;
    final scale = math.min(maxW / s.width, maxH / s.height);
    final dw = s.width * scale, dh = s.height * scale;
    return RoiEditor(
      key: ValueKey(p),
      bytes: p.bytes!,
      displaySize: Size(dw, dh),
      box: p.box,
      onChanged: (b) => setState(() {
        if (_sharedBox) {
          for (final q in _photos) {
            q.box = b;
            q.placed = true;
          }
        } else {
          p.box = b;
          p.placed = true;
        }
      }),
    );
  }

  Widget _thumb(int i) {
    final p = _photos[i];
    final selected = i == _sel;
    Widget img;
    if (p.bytes != null && !p.failed) {
      img = Image.memory(p.bytes!, fit: BoxFit.cover, cacheWidth: 240, gaplessPlayback: true);
    } else if (p.failed) {
      img = Container(
          color: const Color(0xFF2A2A2A),
          child: const Icon(Icons.broken_image_rounded, color: Colors.white24));
    } else {
      img = Container(color: const Color(0xFFF1E6EA));
    }
    return GestureDetector(
      onTap: () => setState(() => _sel = i),
      child: Stack(
        children: [
          Container(
            width: 72,
            height: 64,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: selected ? C.primary : Colors.transparent, width: 2.5),
            ),
            child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox.expand(child: img)),
          ),
          if (!_sharedBox && _photos.length > 1 && p.ready)
            Positioned(
              left: 4,
              bottom: 4,
              child: Container(
                width: 18,
                height: 18,
                decoration: BoxDecoration(
                    color: p.placed ? C.ok : Colors.black54,
                    shape: BoxShape.circle),
                child: Icon(
                    p.placed ? Icons.check_rounded : Icons.crop_free_rounded,
                    size: 12,
                    color: Colors.white),
              ),
            ),
          if (_photos.length > 1)
            Positioned(
              right: 2,
              top: 2,
              child: GestureDetector(
                onTap: () => _remove(i),
                child: Container(
                  width: 20,
                  height: 20,
                  decoration: const BoxDecoration(
                      color: Colors.black54, shape: BoxShape.circle),
                  child: const Icon(Icons.close_rounded,
                      size: 13, color: Colors.white),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Photo shown at exactly [displaySize] (its real aspect ratio) with a
/// movable / resizable ROI box on top.
class RoiEditor extends StatefulWidget {
  final Uint8List bytes;
  final Size displaySize;
  final RoiBox box;
  final ValueChanged<RoiBox> onChanged;

  const RoiEditor({
    super.key,
    required this.bytes,
    required this.displaySize,
    required this.box,
    required this.onChanged,
  });

  @override
  State<RoiEditor> createState() => _RoiEditorState();
}

class _RoiEditorState extends State<RoiEditor> {
  static const double _handleHit = 30; // px touch radius for corners
  int? _corner; // 0 TL, 1 TR, 2 BL, 3 BR
  bool _moving = false;
  // Absolute tracking: the box follows the finger exactly (no slop lag).
  Offset _startPos = Offset.zero;
  RoiBox _startBox = RoiBox.standard;

  Rect _rectPx(RoiBox b, Size s) =>
      Rect.fromLTWH(b.x * s.width, b.y * s.height, b.w * s.width, b.h * s.height);

  void _onStart(DragStartDetails d) {
    final s = widget.displaySize;
    final r = _rectPx(widget.box, s);
    final pos = d.localPosition;
    final corners = [r.topLeft, r.topRight, r.bottomLeft, r.bottomRight];
    int? best;
    var bestDist = double.infinity;
    for (var i = 0; i < 4; i++) {
      final dist = (corners[i] - pos).distance;
      if (dist < _handleHit && dist < bestDist) {
        best = i;
        bestDist = dist;
      }
    }
    _corner = best;
    _moving = best == null && r.inflate(6).contains(pos);
    _startPos = pos;
    _startBox = widget.box;
  }

  void _onUpdate(DragUpdateDetails d) {
    final s = widget.displaySize;
    final total = d.localPosition - _startPos;
    final dx = total.dx / s.width, dy = total.dy / s.height;
    if (_corner != null) {
      widget.onChanged(_startBox.resizeCorner(_corner!, dx, dy));
    } else if (_moving) {
      widget.onChanged(_startBox.moveBy(dx, dy));
    }
  }

  void _onEnd([Object? _]) {
    _corner = null;
    _moving = false;
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.displaySize;
    return SizedBox(
      width: s.width,
      height: s.height,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Stack(
          children: [
            Positioned.fill(
              child: Image.memory(widget.bytes,
                  fit: BoxFit.fill, gaplessPlayback: true),
            ),
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                dragStartBehavior: DragStartBehavior.down,
                onPanStart: _onStart,
                onPanUpdate: _onUpdate,
                onPanEnd: _onEnd,
                onPanCancel: _onEnd,
                child: CustomPaint(
                  painter: _RoiPainter(_rectPx(widget.box, s)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoiPainter extends CustomPainter {
  final Rect box;
  _RoiPainter(this.box);

  @override
  void paint(Canvas canvas, Size size) {
    // Dim everything outside the box.
    final outside = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size)
      ..addRect(box);
    canvas.drawPath(outside, Paint()..color = Colors.black.withValues(alpha: 0.40));
    // Box outline.
    canvas.drawRect(
        box,
        Paint()
          ..color = Colors.white
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.2);
    // Corner handles.
    final fill = Paint()..color = Colors.white;
    final ring = Paint()
      ..color = C.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    for (final c in [box.topLeft, box.topRight, box.bottomLeft, box.bottomRight]) {
      canvas.drawCircle(c, 9, fill);
      canvas.drawCircle(c, 9, ring);
    }
    // Label above (or inside if no room) the box.
    final tp = TextPainter(
      text: const TextSpan(
          text: 'Inner eyelid',
          style: TextStyle(
              color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
      textDirection: ui.TextDirection.ltr,
    )..layout();
    final ty = box.top - tp.height - 6 >= 0 ? box.top - tp.height - 6 : box.top + 6;
    final tx = (box.left + 12).clamp(0.0, math.max(0.0, size.width - tp.width)).toDouble();
    tp.paint(canvas, Offset(tx, ty));
  }

  @override
  bool shouldRepaint(_RoiPainter old) => old.box != box;
}
