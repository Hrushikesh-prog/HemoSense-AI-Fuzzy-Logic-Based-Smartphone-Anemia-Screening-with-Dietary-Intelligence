/// The user-drawn region of interest on a photo, as fractions (0..1) of the
/// photo AS DISPLAYED (EXIF-rotated). Sent to the server as `[x, y, w, h]`.
class RoiBox {
  final double x, y, w, h;

  /// Smallest allowed width/height (fraction of the photo).
  static const double minSize = 0.10;

  /// Server default: (0.14, 0.42, 0.72, 0.44).
  static const RoiBox standard = RoiBox(0.14, 0.42, 0.72, 0.44);

  /// Where the editable box starts: small and centred, so the user must move it
  /// onto the eyelid (a large default box can cover cheek or clothing).
  static const RoiBox start = RoiBox(0.3, 0.42, 0.4, 0.16);

  const RoiBox(this.x, this.y, this.w, this.h);

  List<double> toList() => [x, y, w, h];

  /// Moves the box by (dx, dy) fractions, keeping it inside the photo.
  RoiBox moveBy(double dx, double dy) => RoiBox(
        (x + dx).clamp(0.0, 1.0 - w).toDouble(),
        (y + dy).clamp(0.0, 1.0 - h).toDouble(),
        w,
        h,
      );

  /// Drags one corner by (dx, dy). [corner]: 0 = top-left, 1 = top-right,
  /// 2 = bottom-left, 3 = bottom-right. The opposite corner stays fixed; the
  /// box stays inside the photo and at least [minSize] on each side.
  RoiBox resizeCorner(int corner, double dx, double dy) {
    var left = x, top = y, right = x + w, bottom = y + h;
    final moveLeft = corner == 0 || corner == 2;
    final moveTop = corner == 0 || corner == 1;
    if (moveLeft) {
      left = (left + dx).clamp(0.0, right - minSize).toDouble();
    } else {
      right = (right + dx).clamp(left + minSize, 1.0).toDouble();
    }
    if (moveTop) {
      top = (top + dy).clamp(0.0, bottom - minSize).toDouble();
    } else {
      bottom = (bottom + dy).clamp(top + minSize, 1.0).toDouble();
    }
    return RoiBox(left, top, right - left, bottom - top);
  }

  @override
  bool operator ==(Object other) =>
      other is RoiBox && other.x == x && other.y == y && other.w == w && other.h == h;

  @override
  int get hashCode => Object.hash(x, y, w, h);

  @override
  String toString() =>
      'RoiBox(${x.toStringAsFixed(3)}, ${y.toStringAsFixed(3)}, ${w.toStringAsFixed(3)}, ${h.toStringAsFixed(3)})';
}
