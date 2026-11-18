import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/screening.dart';
import '../theme.dart';

const kDisclaimer = 'Screening only, not a diagnosis. Confirm with a blood test (CBC) and a doctor.';

// ---------------------------------------------------------------------------
// Severity pill  (mockup: .pill.p-ok/.p-mi/.p-mo/.p-se)
// ---------------------------------------------------------------------------
class SeverityPill extends StatelessWidget {
  final String severity;
  const SeverityPill(this.severity, {super.key});

  @override
  Widget build(BuildContext context) {
    final color = C.severityColor(severity);
    final bg = C.severityBg(severity);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(10)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle, size: 7, color: color),
          const SizedBox(width: 4),
          Text(severityDisplayLabel(severity),
              style: TextStyle(
                  color: color, fontSize: 10, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Selectable chip (mockup: .chip/.chip.on)
// ---------------------------------------------------------------------------
class SelectChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  const SelectChip(this.label, {super.key, required this.selected, this.onTap});

  @override
  Widget build(BuildContext context) {
    final bg = selected ? C.container : Colors.white;
    final bc = selected ? C.primary : const Color(0xFFD8C8CE);
    final fg = selected ? C.primaryDark : C.text;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: bc, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (selected) ...[
              const Icon(Icons.check, size: 13, color: C.primaryDark),
              const SizedBox(width: 4),
            ],
            Text(label,
                style: TextStyle(
                    fontSize: 11,
                    color: fg,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400)),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Toggle (mockup: .tog)
// ---------------------------------------------------------------------------
class Toggle extends StatelessWidget {
  final bool on;
  final ValueChanged<bool> onChanged;
  const Toggle({super.key, required this.on, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged(!on),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 34,
        height: 20,
        padding: const EdgeInsets.all(2),
        decoration: BoxDecoration(
          color: on ? C.primary : const Color(0xFFCFC3C7),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Align(
          alignment: on ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            width: 16,
            height: 16,
            decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Progress bar (mockup: .bar)
// ---------------------------------------------------------------------------
class HBar extends StatelessWidget {
  final double value; // 0..1
  final Color color;
  final double height;
  const HBar(this.value, {super.key, required this.color, this.height = 6});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: const Color(0xFFEFE6E9),
        borderRadius: BorderRadius.circular(height / 2),
      ),
      child: Align(
        alignment: Alignment.centerLeft,
        child: FractionallySizedBox(
          widthFactor: value.clamp(0.0, 1.0),
          child: Container(
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(height / 2),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Section label (mockup: .lbl)
// ---------------------------------------------------------------------------
class SectionLabel extends StatelessWidget {
  final String text;
  const SectionLabel(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: const TextStyle(
          fontSize: 9.5,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.6,
          color: C.muted),
    );
  }
}

// ---------------------------------------------------------------------------
// Small avatar box (mockup: .av)
// ---------------------------------------------------------------------------
class MiniAvatar extends StatelessWidget {
  final IconData icon;
  final Color bg;
  final Color fg;
  final double size;
  const MiniAvatar(this.icon,
      {super.key, this.bg = C.container, this.fg = C.primaryDark, this.size = 28});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(9)),
      child: Icon(icon, size: size * 0.55, color: fg),
    );
  }
}

// ---------------------------------------------------------------------------
// Disclaimer footer (mockup: always-visible info row)
// ---------------------------------------------------------------------------
class DisclaimerFooter extends StatelessWidget {
  const DisclaimerFooter({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(14, 8, 14, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, size: 14, color: C.muted),
          const SizedBox(width: 6),
          Expanded(
            child: Text(kDisclaimer,
                style: const TextStyle(fontSize: 9.5, color: C.muted)),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Eye illustration (simplified custom-painted version of the mockup SVG)
// ---------------------------------------------------------------------------
class EyeArt extends StatelessWidget {
  final bool pale;
  const EyeArt({super.key, this.pale = false});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _EyePainter(pale: pale), child: const SizedBox.expand());
  }
}

class _EyePainter extends CustomPainter {
  final bool pale;
  _EyePainter({required this.pale});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    // Skin background
    final skin = Paint()
      ..shader = const RadialGradient(
        center: Alignment(0, -0.2),
        colors: [Color(0xFFE7B596), Color(0xFFB9805F)],
      ).createShader(Rect.fromLTWH(0, 0, w, h));
    canvas.drawRect(Rect.fromLTWH(0, 0, w, h), skin);

    // Upper eye opening (sclera)
    final upper = Path()
      ..moveTo(0.05 * w, 0.43 * h)
      ..quadraticBezierTo(0.5 * w, 0.02 * h, 0.95 * w, 0.43 * h)
      ..quadraticBezierTo(0.5 * w, 0.68 * h, 0.05 * w, 0.43 * h)
      ..close();
    canvas.drawPath(upper, Paint()..color = const Color(0xFFF6F1EC));
    // Iris
    final clipUpper = Path.from(upper);
    canvas.save();
    canvas.clipPath(clipUpper);
    final cy = 0.38 * h;
    canvas.drawCircle(Offset(0.5 * w, cy), 0.17 * h, Paint()..color = const Color(0xFF5A3A22));
    canvas.drawCircle(Offset(0.5 * w, cy), 0.11 * h, Paint()..color = const Color(0xFF3E2716));
    canvas.drawCircle(Offset(0.5 * w, cy), 0.065 * h, Paint()..color = const Color(0xFF0D0D0D));
    canvas.drawCircle(Offset(0.53 * w, cy - 0.05 * h), 0.022 * h,
        Paint()..color = Colors.white.withValues(alpha: 0.9));
    // Upper lid shadow line
    final lid = Path()
      ..moveTo(0.05 * w, 0.43 * h)
      ..quadraticBezierTo(0.5 * w, 0.02 * h, 0.95 * w, 0.43 * h);
    canvas.drawPath(
        lid, Paint()..color = const Color(0xFF4A2E22)..style = PaintingStyle.stroke..strokeWidth = 2.5);
    canvas.restore();

    // Lower conjunctiva fold (the screening target)
    final foldColor = pale ? const Color(0xFFEDBAB5) : const Color(0xFFD45B68);
    final fold = Path()
      ..moveTo(0.07 * w, 0.47 * h)
      ..quadraticBezierTo(0.5 * w, 0.72 * h, 0.93 * w, 0.47 * h)
      ..quadraticBezierTo(0.5 * w, 0.97 * h, 0.07 * w, 0.47 * h)
      ..close();
    canvas.drawPath(fold, Paint()..color = foldColor);
    if (!pale) {
      final inner = Path()
        ..moveTo(0.15 * w, 0.53 * h)
        ..quadraticBezierTo(0.5 * w, 0.69 * h, 0.85 * w, 0.53 * h)
        ..quadraticBezierTo(0.5 * w, 0.86 * h, 0.15 * w, 0.53 * h)
        ..close();
      canvas.drawPath(
          inner, Paint()..color = const Color(0xFFE7868D).withValues(alpha: 0.75));
      // small vessels
      final vessel = Paint()
        ..color = const Color(0xFFA8303F)
        ..strokeWidth = 1
        ..style = PaintingStyle.stroke;
      canvas.drawLine(const Offset(0, 0), const Offset(0, 0), vessel);
      for (final (a, b, c, d) in const [
        (0.3, 0.62, 0.4, 0.66),
        (0.62, 0.64, 0.72, 0.58),
        (0.45, 0.68, 0.52, 0.74),
      ]) {
        final p = Path()
          ..moveTo(a * w, b * h)
          ..quadraticBezierTo(((a + c) / 2) * w, (b + 0.05) * h, c * w, d * h);
        canvas.drawPath(p, vessel);
      }
    }
    // Lower lid outline
    final lowerLine = Path()
      ..moveTo(0.07 * w, 0.47 * h)
      ..quadraticBezierTo(0.5 * w, 0.97 * h, 0.93 * w, 0.47 * h);
    canvas.drawPath(lowerLine,
        Paint()..color = const Color(0xFFA86C55)..strokeWidth = 2.5..style = PaintingStyle.stroke);
    // Upper lid brow line
    final brow = Path()
      ..moveTo(0.02 * w, 0.4 * h)
      ..quadraticBezierTo(0.5 * w, -0.05 * h, 0.98 * w, 0.4 * h);
    canvas.drawPath(brow,
        Paint()..color = const Color(0xFF6B4632).withValues(alpha: 0.5)..strokeWidth = 3..style = PaintingStyle.stroke);
    // Nose base hint
    final nose = Path()
      ..moveTo(0.28 * w, h)
      ..quadraticBezierTo(0.33 * w, 0.86 * h, 0.42 * w, 0.87 * h)
      ..quadraticBezierTo(0.5 * w, 0.9 * h, 0.58 * w, 0.87 * h)
      ..quadraticBezierTo(0.67 * w, 0.86 * h, 0.72 * w, h);
    canvas.drawPath(nose, Paint()..color = const Color(0xFFC88A6E));
  }

  @override
  bool shouldRepaint(_EyePainter old) => old.pale != pale;
}

// ---------------------------------------------------------------------------
// Result gauge: 3-zone semicircle (Normal / Mild / Moderate-to-Severe) with a
// needle, the grade and the ANFIS anemia risk score. Never an Hb value.
// ---------------------------------------------------------------------------
class RiskGauge extends StatelessWidget {
  final String severity; // severity_class: Normal | Mild | Moderate
  final double riskScore; // p_anemic 0..1
  final String? label; // severity_label from the server (optional)
  const RiskGauge(
      {super.key, required this.severity, required this.riskScore, this.label});

  static const zoneColors = [C.ok, C.mild, C.moderate];
  static const zones = ['Normal', 'Mild', 'Moderate-to-Severe'];

  @override
  Widget build(BuildContext context) {
    final level = severityLevelOf(severity);
    final needleAngle = -180.0 + (level + 0.5) * 60.0; // 3 zones over 180 deg
    final text = label ?? severityDisplayLabel(severity);
    return SizedBox(
      width: 230,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CustomPaint(
            size: const Size(210, 112),
            painter: _GaugeZonesPainter(needleAngle: needleAngle),
          ),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
                level == 0 ? 'No Anemia Detected' : '$text Anemia Risk',
                style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: C.severityColor(severity))),
          ),
          Text(
            'Anemia risk score ${(riskScore.clamp(0.0, 1.0) * 100).round()}%',
            style: const TextStyle(fontSize: 11, color: C.muted),
          ),
          const SizedBox(height: 6),
          Wrap(
            alignment: WrapAlignment.center,
            runSpacing: 2,
            children: [
              for (var i = 0; i < zones.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 5),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.circle, size: 7, color: zoneColors[i]),
                      const SizedBox(width: 3),
                      Text(zones[i],
                          style: TextStyle(
                              fontSize: 8.5,
                              color: i == level ? C.text : C.muted,
                              fontWeight:
                                  i == level ? FontWeight.w800 : FontWeight.w400)),
                    ],
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _GaugeZonesPainter extends CustomPainter {
  final double needleAngle;
  _GaugeZonesPainter({required this.needleAngle});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height - 6);
    final radius = size.width / 2 - 16;
    const n = 3;
    const zoneSweep = math.pi / n;
    const start = math.pi; // from left
    for (var i = 0; i < n; i++) {
      final paint = Paint()
        ..color = RiskGauge.zoneColors[i]
        ..style = PaintingStyle.stroke
        ..strokeWidth = 14
        ..strokeCap = StrokeCap.butt;
      canvas.drawArc(
          Rect.fromCircle(center: center, radius: radius),
          start + i * zoneSweep + 0.01,
          zoneSweep - 0.02,
          false,
          paint);
    }
    // Needle
    final rad = needleAngle * math.pi / 180;
    final tip = Offset(center.dx + math.cos(rad) * (radius - 12),
        center.dy + math.sin(rad) * (radius - 12));
    canvas.drawLine(center, tip,
        Paint()..color = C.text..strokeWidth = 3.5..strokeCap = StrokeCap.round);
    canvas.drawCircle(center, 6, Paint()..color = C.text);
  }

  @override
  bool shouldRepaint(_GaugeZonesPainter old) => old.needleAngle != needleAngle;
}

// ---------------------------------------------------------------------------
// Bottom navigation (mockup: .bn with 5 tabs)
// ---------------------------------------------------------------------------
class HemoBottomNav extends StatelessWidget {
  final String active; // home | scan | history | diet | profile
  final ValueChanged<String>? onTab;
  const HemoBottomNav({super.key, required this.active, this.onTab});

  @override
  Widget build(BuildContext context) {
    final tabs = const [
      ('home', Icons.home_outlined, 'Home'),
      ('scan', Icons.camera_alt_outlined, 'Scan'),
      ('history', Icons.history_rounded, 'History'),
      ('diet', Icons.restaurant_outlined, 'Diet'),
      ('profile', Icons.person_outline_rounded, 'Profile'),
    ];
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: C.outline)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 58,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              for (final (id, icon, label) in tabs)
                _tab(context, id, icon, label, active == id),
            ],
          ),
        ),
      ),
    );
  }

  Widget _tab(BuildContext context, String id, IconData icon, String label, bool selected) {
    final color = selected ? C.primaryDark : C.muted;
    return InkWell(
      onTap: selected ? null : () => onTab?.call(id),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 44,
              height: 24,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selected ? C.container : Colors.transparent,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, size: 17, color: color),
            ),
            Text(label,
                style: TextStyle(
                    fontSize: 9,
                    color: color,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400)),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Reusable list row (mockup: .li)
// ---------------------------------------------------------------------------
class MockListRow extends StatelessWidget {
  final Widget leading;
  final Widget title;
  final Widget? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  const MockListRow(
      {super.key,
      required this.leading,
      required this.title,
      this.subtitle,
      this.trailing,
      this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: Color(0xFFF1E7EA))),
        ),
        child: Row(
          children: [
            leading,
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  DefaultTextStyle.merge(style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5), child: title),
                  if (subtitle != null)
                    DefaultTextStyle.merge(
                        style: const TextStyle(fontSize: 10.5, color: C.muted),
                        child: subtitle!),
                ],
              ),
            ),
            ?trailing,
          ],
        ),
      ),
    );
  }
}

/// History entry → severity pill helper.
SeverityPill pillFor(HistoryEntry e) => SeverityPill(e.severityClass);
