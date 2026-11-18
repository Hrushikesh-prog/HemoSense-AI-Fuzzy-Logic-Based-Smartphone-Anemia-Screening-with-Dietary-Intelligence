import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../data/local_store.dart';
import '../theme.dart';
import '../widgets/ui.dart';
import 'camera_screen.dart';

/// One step of the capture tutorial.
class TutorialStep {
  final String title;
  final String body;
  const TutorialStep(this.title, this.body);
}

const kTutorialSteps = <TutorialStep>[
  TutorialStep('Find bright, even light',
      'Face a window or a white light, or turn on the phone torch. Avoid yellow bulbs and shadows.'),
  TutorialStep('Look up',
      'Tilt your eyes up towards the ceiling. This uncovers more of the white of the eye and the lower lid.'),
  TutorialStep('Gently pull the lower eyelid down',
      'Use one clean finger just below the lashes. A pink half-moon of inner eyelid appears.'),
  TutorialStep('Hold the phone 10–15 cm away and keep still',
      'Let the camera focus on the pink area, then tap the shutter. It takes 3 quick photos.'),
  TutorialStep('Then drag the box tightly around just the pink half-moon',
      'On the review screen, cover only the pink inner eyelid: no skin, lashes or white of the eye.'),
];

/// Animated, step-by-step demo of how to photograph the inner eyelid.
/// Drawn entirely with CustomPainter (no images or network).
///
/// Shown automatically before the first capture and always reachable from the
/// capture guide ("How to take the photo"). "Got it, start camera" replaces
/// this screen with the camera.
class CaptureTutorialScreen extends StatefulWidget {
  final List<String> symptoms;
  const CaptureTutorialScreen({super.key, this.symptoms = const []});

  @override
  State<CaptureTutorialScreen> createState() => _CaptureTutorialScreenState();
}

class _CaptureTutorialScreenState extends State<CaptureTutorialScreen>
    with SingleTickerProviderStateMixin {
  /// One animation cycle per step; the action happens in the first ~75 % and
  /// the end pose is held for the rest.
  static const _cycle = Duration(milliseconds: 2800);
  static const _pause = Duration(milliseconds: 500);

  late final AnimationController _anim;
  Timer? _next;
  int _step = 0;
  bool _auto = true;

  @override
  void initState() {
    super.initState();
    LocalStore.tutorialSeen = true;
    _anim = AnimationController(vsync: this, duration: _cycle)
      ..addStatusListener(_onStatus)
      ..forward();
  }

  void _onStatus(AnimationStatus s) {
    if (s != AnimationStatus.completed) return;
    _next?.cancel();
    _next = Timer(_pause, () {
      if (!mounted) return;
      if (_auto && _step < kTutorialSteps.length - 1) {
        _go(_step + 1, manual: false);
      } else {
        _anim.forward(from: 0); // replay the current step
      }
    });
  }

  void _go(int i, {bool manual = true}) {
    if (i < 0 || i >= kTutorialSteps.length) return;
    _next?.cancel();
    setState(() {
      if (manual && i < _step) _auto = false; // going back: let them read
      _step = i;
    });
    _anim.forward(from: 0);
  }

  void _done() {
    LocalStore.tutorialSeen = true;
    Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) => CameraScreen(symptoms: widget.symptoms)));
  }

  @override
  void dispose() {
    _next?.cancel();
    _anim.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final step = kTutorialSteps[_step];
    final last = _step == kTutorialSteps.length - 1;
    return Scaffold(
      appBar: AppBar(title: const Text('How to take the photo')),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
                children: [
                  GestureDetector(
                    onTap: () => _anim.forward(from: 0),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: AspectRatio(
                        aspectRatio: 1.45,
                        child: AnimatedBuilder(
                          animation: _anim,
                          builder: (context, _) => CustomPaint(
                            painter: TutorialPainter(step: _step, t: _anim.value),
                            child: const SizedBox.expand(),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _dots(),
                  const SizedBox(height: 12),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 250),
                    child: Column(
                      key: ValueKey(_step),
                      children: [
                        Text('Step ${_step + 1} of ${kTutorialSteps.length}',
                            style: const TextStyle(
                                fontSize: 10.5,
                                color: C.primary,
                                fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        Text(step.title,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w800)),
                        const SizedBox(height: 6),
                        Text(step.body,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 12, color: C.muted, height: 1.45)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.chevron_left_rounded, size: 18),
                          label: const Text('Back'),
                          onPressed: _step == 0 ? null : () => _go(_step - 1),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.chevron_right_rounded, size: 18),
                          label: const Text('Next'),
                          onPressed: last ? null : () => _go(_step + 1),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  FilledButton.icon(
                    icon: const Icon(Icons.photo_camera_rounded, size: 16),
                    label: const Text('Got it, start camera'),
                    onPressed: _done,
                  ),
                  const SizedBox(height: 4),
                  const DisclaimerFooter(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _dots() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < kTutorialSteps.length; i++)
          GestureDetector(
            onTap: () {
              _auto = false;
              _go(i);
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.symmetric(horizontal: 4),
              width: i == _step ? 22 : 8,
              height: 8,
              decoration: BoxDecoration(
                color: i == _step ? C.primary : C.outline,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Painter
// ---------------------------------------------------------------------------

double _seg(double t, double a, double b) =>
    ((t - a) / (b - a)).clamp(0.0, 1.0).toDouble();
double _ease(double x) => Curves.easeInOut.transform(x.clamp(0.0, 1.0));
Offset _quad(Offset p0, Offset c, Offset p2, double s) {
  final u = 1 - s;
  return p0 * (u * u) + c * (2 * u * s) + p2 * (s * s);
}

/// Draws tutorial step [step] (0..4) at animation progress [t] (0..1).
class TutorialPainter extends CustomPainter {
  final int step;
  final double t;
  TutorialPainter({required this.step, required this.t});

  static const _conj = Color(0xFFD45B68);
  static const _conjLight = Color(0xFFE7868D);
  static const _sclera = Color(0xFFF6F1EC);
  static const _lidLine = Color(0xFFA86C55);
  static const _ok = C.ok;

  @override
  void paint(Canvas canvas, Size size) {
    final r = Offset.zero & size;
    switch (step) {
      case 0:
        _light(canvas, r);
      case 1:
        final look = _ease(_seg(t, 0.05, 0.6));
        _eye(canvas, r, look: look, pull: 0);
        _arrow(canvas, Offset(r.width * 0.5, r.height * 0.09), up: true,
            alpha: math.sin(_seg(t, 0.0, 0.75) * math.pi), scale: r.height);
      case 2:
        final pull = _ease(_seg(t, 0.1, 0.65));
        _eye(canvas, r, look: 1, pull: pull, finger: true);
        _arrow(canvas, Offset(r.width * 0.80, r.height * 0.70), up: false,
            alpha: math.sin(_seg(t, 0.05, 0.7) * math.pi), scale: r.height);
      case 3:
        _distance(canvas, r);
      default:
        _box(canvas, r);
    }
  }

  // ----- eye ---------------------------------------------------------------

  /// Geometry of the eye in [r]: centre, half-width, lid curve peaks.
  ({double cx, double cy, double half, double h}) _geo(Rect r) =>
      (cx: r.center.dx, cy: r.top + 0.42 * r.height, half: 0.34 * r.width, h: r.height);

  /// Lower-lid control point Y for a given pull (0 = resting lid).
  double _lowerCtrl(Rect r, double pull) {
    final g = _geo(r);
    return g.cy + 2 * (0.11 + 0.17 * pull) * g.h;
  }

  void _eye(Canvas canvas, Rect r,
      {required double look, required double pull, bool finger = false, double dim = 0}) {
    final g = _geo(r);
    final cx = g.cx, cy = g.cy, half = g.half, h = g.h;
    final left = Offset(cx - half, cy), right = Offset(cx + half, cy);

    canvas.save();
    canvas.clipRect(r);
    // Skin
    canvas.drawRect(
        r,
        Paint()
          ..shader = const RadialGradient(
            center: Alignment(0, -0.2),
            radius: 0.9,
            colors: [Color(0xFFE9BB9C), Color(0xFFB9805F)],
          ).createShader(r));
    // Brow
    final brow = Path()
      ..moveTo(cx - half * 1.05, cy - 0.26 * h)
      ..quadraticBezierTo(cx, cy - 0.50 * h, cx + half * 1.05, cy - 0.26 * h);
    canvas.drawPath(
        brow,
        Paint()
          ..color = const Color(0xFF5A3A28).withValues(alpha: 0.55)
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round
          ..strokeWidth = 0.05 * h);

    final upperCtrl = Offset(cx, cy - 2 * (0.24 + 0.03 * look) * h);
    final restCtrl = Offset(cx, _lowerCtrl(r, 0));
    final pulledCtrl = Offset(cx, _lowerCtrl(r, pull));

    // Eye opening (sclera) between the upper lid and the resting lower lid.
    final opening = Path()
      ..moveTo(left.dx, left.dy)
      ..quadraticBezierTo(upperCtrl.dx, upperCtrl.dy, right.dx, right.dy)
      ..quadraticBezierTo(restCtrl.dx, restCtrl.dy, left.dx, left.dy)
      ..close();
    canvas.drawPath(opening, Paint()..color = _sclera);

    // Iris + pupil, moving up as the person looks up.
    canvas.save();
    canvas.clipPath(opening);
    final ic = Offset(cx, cy - 0.01 * h - look * 0.12 * h);
    canvas.drawCircle(ic, 0.15 * h, Paint()..color = const Color(0xFF6A4528));
    canvas.drawCircle(ic, 0.10 * h, Paint()..color = const Color(0xFF452B17));
    canvas.drawCircle(ic, 0.06 * h, Paint()..color = const Color(0xFF0D0D0D));
    canvas.drawCircle(ic + Offset(0.035 * h, -0.045 * h), 0.02 * h,
        Paint()..color = Colors.white.withValues(alpha: 0.9));
    canvas.restore();

    // Inner eyelid crescent revealed as the lower lid is pulled down.
    if (pull > 0.01) {
      final crescent = Path()
        ..moveTo(left.dx, left.dy)
        ..quadraticBezierTo(restCtrl.dx, restCtrl.dy, right.dx, right.dy)
        ..quadraticBezierTo(pulledCtrl.dx, pulledCtrl.dy, left.dx, left.dy)
        ..close();
      final bounds = crescent.getBounds();
      canvas.drawPath(
          crescent,
          Paint()
            ..shader = ui.Gradient.linear(bounds.topCenter, bounds.bottomCenter,
                const [_conjLight, _conj]));
      // a few vessels
      final vessel = Paint()
        ..color = const Color(0xFFA8303F).withValues(alpha: 0.6 * pull)
        ..strokeWidth = 1
        ..style = PaintingStyle.stroke;
      for (final (a, b) in const [(0.35, 0.45), (0.55, 0.65), (0.46, 0.52)]) {
        final p0 = _quad(left, restCtrl, right, a);
        final p1 = _quad(left, pulledCtrl, right, b);
        canvas.drawLine(p0, Offset.lerp(p0, p1, 0.8)!, vessel);
      }
    }

    // Upper lid line + lashes
    final upper = Path()
      ..moveTo(left.dx, left.dy)
      ..quadraticBezierTo(upperCtrl.dx, upperCtrl.dy, right.dx, right.dy);
    final lash = Paint()
      ..color = const Color(0xFF2E1D14)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 0.022 * h;
    canvas.drawPath(upper, lash);
    lash.strokeWidth = 0.012 * h;
    for (var i = 1; i < 9; i++) {
      final s = i / 9;
      final p = _quad(left, upperCtrl, right, s);
      canvas.drawLine(p, p + Offset((s - 0.5) * 0.10 * h, -0.06 * h), lash);
    }
    // Lower lid margin (follows the finger)
    final lower = Path()
      ..moveTo(left.dx, left.dy)
      ..quadraticBezierTo(pulledCtrl.dx, pulledCtrl.dy, right.dx, right.dy);
    canvas.drawPath(
        lower,
        Paint()
          ..color = _lidLine
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.025 * h);

    if (finger) {
      final lidBottom = _quad(left, pulledCtrl, right, 0.5);
      _finger(canvas, r, Offset(cx + 0.04 * r.width, lidBottom.dy + 0.05 * h));
    }
    if (dim > 0) {
      canvas.drawRect(r, Paint()..color = Colors.black.withValues(alpha: dim));
    }
    canvas.restore();
  }

  void _finger(Canvas canvas, Rect r, Offset tip) {
    final w = 0.15 * r.width;
    final len = r.height;
    canvas.save();
    canvas.translate(tip.dx, tip.dy);
    canvas.rotate(-0.18);
    final body = RRect.fromRectAndCorners(
      Rect.fromLTWH(-w / 2, 0, w, len),
      topLeft: Radius.circular(w / 2),
      topRight: Radius.circular(w / 2),
    );
    canvas.drawRRect(body.shift(const Offset(3, 3)),
        Paint()..color = Colors.black.withValues(alpha: 0.18));
    canvas.drawRRect(body, Paint()..color = const Color(0xFFE2A988));
    canvas.drawRRect(
        body,
        Paint()
          ..color = const Color(0xFFA9714F)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
    final nail = RRect.fromRectAndRadius(
        Rect.fromLTWH(-w * 0.32, w * 0.12, w * 0.64, w * 0.75),
        Radius.circular(w * 0.3));
    canvas.drawRRect(nail, Paint()..color = const Color(0xFFF5D7C8));
    canvas.drawRRect(
        nail,
        Paint()
          ..color = const Color(0xFFC99580)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1);
    canvas.restore();
  }

  void _arrow(Canvas canvas, Offset at,
      {required bool up, required double alpha, required double scale}) {
    if (alpha <= 0.01) return;
    final s = 0.07 * scale;
    final dir = up ? -1.0 : 1.0;
    final shift = (1 - alpha) * 0.04 * scale * -dir;
    final o = at + Offset(0, shift);
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: alpha)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = 0.022 * scale;
    canvas.drawLine(o - Offset(0, dir * s), o + Offset(0, dir * s), paint);
    final head = o + Offset(0, dir * s);
    canvas.drawPath(
        Path()
          ..moveTo(head.dx - s * 0.6, head.dy - dir * s * 0.6)
          ..lineTo(head.dx, head.dy)
          ..lineTo(head.dx + s * 0.6, head.dy - dir * s * 0.6),
        paint);
  }

  // ----- step 0: light -----------------------------------------------------

  void _light(Canvas canvas, Rect r) {
    final on = _ease(_seg(t, 0.05, 0.35));
    final pulse = 0.85 + 0.15 * math.sin(t * 2 * math.pi * 2);
    final glow = on * pulse;
    final w = r.width, h = r.height;
    canvas.drawRect(
        r,
        Paint()
          ..shader = ui.Gradient.linear(r.topLeft, r.bottomRight, [
            Color.lerp(const Color(0xFF2B1D22), const Color(0xFFFFF4E3), on)!,
            Color.lerp(const Color(0xFF1A1114), const Color(0xFFFCE4EA), on)!,
          ]));

    // Phone (back) with lens + torch
    final phone = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(0.24 * w, 0.52 * h), width: 0.2 * w, height: 0.72 * h),
        Radius.circular(0.035 * w));
    canvas.drawRRect(phone, Paint()..color = const Color(0xFF26262B));
    final lens = Offset(0.20 * w, 0.27 * h);
    canvas.drawCircle(lens, 0.045 * h, Paint()..color = const Color(0xFF0E0E10));
    canvas.drawCircle(lens, 0.025 * h, Paint()..color = const Color(0xFF34405A));
    final torch = Offset(0.28 * w, 0.27 * h);

    // Light beam towards the eye
    final eyeRect = Rect.fromLTWH(0.52 * w, 0.18 * h, 0.44 * w, 0.64 * h);
    if (glow > 0.01) {
      final beam = Path()
        ..moveTo(torch.dx, torch.dy)
        ..lineTo(eyeRect.left, eyeRect.top - 0.06 * h)
        ..lineTo(eyeRect.left, eyeRect.bottom + 0.06 * h)
        ..close();
      canvas.drawPath(
          beam,
          Paint()
            ..shader = ui.Gradient.linear(torch, Offset(eyeRect.left, torch.dy), [
              const Color(0xFFFFE9A8).withValues(alpha: 0.75 * glow),
              const Color(0xFFFFE9A8).withValues(alpha: 0.0),
            ]));
      // Rays around the torch
      final ray = Paint()
        ..color = const Color(0xFFFFC94D).withValues(alpha: glow)
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 0.014 * h;
      for (var i = 0; i < 10; i++) {
        final a = i * 2 * math.pi / 10 + t * 0.6;
        final inner = 0.06 * h, outer = (0.09 + 0.04 * pulse) * h;
        canvas.drawLine(torch + Offset(math.cos(a), math.sin(a)) * inner,
            torch + Offset(math.cos(a), math.sin(a)) * outer, ray);
      }
    }
    canvas.drawCircle(torch, 0.035 * h,
        Paint()..color = Color.lerp(const Color(0xFF55555C), const Color(0xFFFFF6C8), on)!);

    // The eye gets brighter as the light comes on.
    canvas.save();
    canvas.clipRRect(RRect.fromRectAndRadius(eyeRect, Radius.circular(0.03 * w)));
    _eye(canvas, eyeRect, look: 1, pull: 1, dim: 0.6 * (1 - on));
    canvas.restore();
  }

  // ----- step 3: distance --------------------------------------------------

  void _distance(Canvas canvas, Rect r) {
    final w = r.width, h = r.height;
    canvas.drawRect(r, Paint()..color = const Color(0xFFFFF8F9));
    final eyeRect = Rect.fromLTWH(0.03 * w, 0.14 * h, 0.40 * w, 0.58 * h);
    canvas.save();
    canvas.clipRRect(RRect.fromRectAndRadius(eyeRect, Radius.circular(0.03 * w)));
    _eye(canvas, eyeRect, look: 1, pull: 1);
    canvas.restore();

    // Phone side-on, sliding in to the marked distance
    final move = _ease(_seg(t, 0.0, 0.45));
    final phoneX = ui.lerpDouble(0.93 * w, 0.70 * w, move)!;
    final targetL = 0.64 * w, targetR = 0.76 * w;
    final inZone = phoneX >= targetL && phoneX <= targetR && move > 0.98;
    // Target zone marker
    final y = 0.86 * h;
    canvas.drawRRect(
        RRect.fromRectAndRadius(Rect.fromLTRB(targetL, y - 0.035 * h, targetR, y + 0.035 * h),
            Radius.circular(0.02 * h)),
        Paint()..color = (inZone ? _ok : C.primary).withValues(alpha: 0.18));
    // Distance line
    final line = Paint()
      ..color = C.muted
      ..strokeWidth = 1.5;
    canvas.drawLine(Offset(eyeRect.right, y), Offset(phoneX, y), line);
    canvas.drawLine(Offset(eyeRect.right, y - 0.04 * h), Offset(eyeRect.right, y + 0.04 * h), line);
    canvas.drawLine(Offset(phoneX, y - 0.04 * h), Offset(phoneX, y + 0.04 * h), line);
    final tp = TextPainter(
      text: TextSpan(
          text: '10–15 cm',
          style: TextStyle(
              color: inZone ? _ok : C.primaryDark,
              fontSize: 0.065 * h,
              fontWeight: FontWeight.w800)),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset((eyeRect.right + phoneX) / 2 - tp.width / 2, y - 0.04 * h - tp.height));

    // Phone body (side view) with the lens facing the eye
    final phone = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(phoneX + 0.025 * w, 0.43 * h), width: 0.05 * w, height: 0.62 * h),
        Radius.circular(0.015 * w));
    canvas.drawRRect(phone, Paint()..color = const Color(0xFF26262B));
    canvas.drawRect(
        Rect.fromLTWH(phoneX - 0.008 * w, 0.20 * h, 0.012 * w, 0.06 * h),
        Paint()..color = const Color(0xFF34405A));

    // Focus brackets closing in on the pink inner eyelid
    final focus = _ease(_seg(t, 0.45, 0.7));
    if (focus > 0) {
      final g = _geo(eyeRect);
      final target = Rect.fromLTRB(g.cx - g.half * 0.85, g.cy - 0.02 * eyeRect.height,
          g.cx + g.half * 0.85, g.cy + 0.34 * eyeRect.height);
      final rect = Rect.lerp(target.inflate(0.12 * h), target, focus)!;
      final color = Color.lerp(Colors.white, _ok, focus)!;
      _brackets(canvas, rect, color, 0.05 * h, 0.018 * h);
    }
  }

  void _brackets(Canvas canvas, Rect r, Color color, double len, double width) {
    final p = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = width;
    for (final (c, dx, dy) in [
      (r.topLeft, 1.0, 1.0),
      (r.topRight, -1.0, 1.0),
      (r.bottomLeft, 1.0, -1.0),
      (r.bottomRight, -1.0, -1.0),
    ]) {
      canvas.drawLine(c, c + Offset(dx * len, 0), p);
      canvas.drawLine(c, c + Offset(0, dy * len), p);
    }
  }

  // ----- step 4: box -------------------------------------------------------

  void _box(Canvas canvas, Rect r) {
    _eye(canvas, r, look: 1, pull: 1);
    final g = _geo(r);
    final tight = Rect.fromLTRB(g.cx - g.half * 0.78, g.cy + 0.10 * g.h,
        g.cx + g.half * 0.78, _quad(Offset(g.cx - g.half, g.cy), Offset(g.cx, _lowerCtrl(r, 1)),
                Offset(g.cx + g.half, g.cy), 0.5)
            .dy +
            0.02 * g.h);
    final loose = Rect.fromLTRB(0.08 * r.width, 0.10 * r.height, 0.92 * r.width, 0.95 * r.height);
    final k = Curves.easeOutBack.transform(_seg(t, 0.1, 0.6));
    final box = Rect.lerp(loose, tight, k)!;
    final snapped = t >= 0.6;

    if (snapped) {
      final outside = Path()
        ..fillType = PathFillType.evenOdd
        ..addRect(r)
        ..addRect(box);
      canvas.drawPath(outside, Paint()..color = Colors.black.withValues(alpha: 0.40));
    }
    canvas.drawRect(
        box,
        Paint()
          ..color = Colors.white
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.2);
    final fill = Paint()..color = Colors.white;
    final ring = Paint()
      ..color = C.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    for (final c in [box.topLeft, box.topRight, box.bottomLeft, box.bottomRight]) {
      canvas.drawCircle(c, 7, fill);
      canvas.drawCircle(c, 7, ring);
    }
    if (snapped) {
      final pop = _ease(_seg(t, 0.6, 0.72));
      final at = Offset(box.right - 2, box.top - 0.09 * r.height);
      canvas.drawCircle(at, 0.06 * r.height * pop, Paint()..color = _ok);
      if (pop > 0.5) {
        final s = 0.03 * r.height;
        canvas.drawPath(
            Path()
              ..moveTo(at.dx - s, at.dy)
              ..lineTo(at.dx - s * 0.2, at.dy + s * 0.8)
              ..lineTo(at.dx + s * 1.1, at.dy - s * 0.8),
            Paint()
              ..color = Colors.white
              ..style = PaintingStyle.stroke
              ..strokeCap = StrokeCap.round
              ..strokeWidth = 2.5);
      }
    }
  }

  @override
  bool shouldRepaint(TutorialPainter old) => old.step != step || old.t != t;
}
