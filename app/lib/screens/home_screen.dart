import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'capture_guide_screen.dart';
import 'history_screen.dart';
import 'diet_screen.dart';
import 'settings_screen.dart';

/// ⑤ Home dashboard — greeting header, gradient hero "Check for anemia",
/// last screening card, quick links and the tip of the day.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(p.profileProvider);
    final history = ref.watch(p.historyProvider);
    final last = history.isEmpty ? null : history.first;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
                children: [
                  // Header
                  Row(
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(DateFormat('EEEE, d MMM').format(DateTime.now()),
                              style: const TextStyle(fontSize: 10, color: C.muted)),
                          Text('Hi, ${profile.age != null ? 'friend' : 'there'}',
                              style: const TextStyle(
                                  fontSize: 15, fontWeight: FontWeight.w700)),
                        ],
                      ),
                      const Spacer(),
                      const Icon(Icons.notifications_none_rounded, color: C.text, size: 20),
                      const SizedBox(width: 10),
                      Container(
                        width: 30,
                        height: 30,
                        decoration: const BoxDecoration(
                            color: C.container, shape: BoxShape.circle),
                        child: const Icon(Icons.person_rounded,
                            size: 17, color: C.primaryDark),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  // Hero gradient card
                  Container(
                    padding: const EdgeInsets.all(13),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [Color(0xFFC2304F), Color(0xFF7A1734)],
                      ),
                    ),
                    child: Stack(
                      children: [
                        Positioned(
                          right: -18,
                          top: -18,
                          child: Container(
                            width: 90,
                            height: 90,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.08),
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Check for anemia',
                                style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 14,
                                    fontWeight: FontWeight.w800)),
                            const SizedBox(height: 3),
                            Text(
                              'Takes about 30 seconds with just your phone camera',
                              style: TextStyle(
                                  color: Colors.white.withValues(alpha: 0.9), fontSize: 10),
                            ),
                            const SizedBox(height: 10),
                            FilledButton.icon(
                              icon: const Icon(Icons.camera_alt_rounded, size: 14),
                              label: const Text('Start scan'),
                              style: FilledButton.styleFrom(
                                backgroundColor: Colors.white,
                                foregroundColor: C.primaryDark,
                                minimumSize: const Size(128, 34),
                                textStyle: const TextStyle(
                                    fontSize: 11.5, fontWeight: FontWeight.w700),
                              ),
                              onPressed: () => _goScan(context),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  // Last screening
                  if (last != null)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(11),
                        child: Column(
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                    'Last screening · '
                                    '${DateFormat('d MMM').format(last.time)}',
                                    style:
                                        const TextStyle(fontSize: 10, color: C.muted)),
                                SeverityPill(last.severityClass),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                          last.headline.isEmpty
                                              ? last.label
                                              : last.headline,
                                          style: const TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.w700)),
                                      Text(
                                          last.riskPercent != null
                                              ? 'Anemia risk score ${last.riskPercent}% · ${last.confidence} confidence'
                                              : '${last.confidence} confidence',
                                          style: const TextStyle(
                                              fontSize: 10, color: C.muted)),
                                    ],
                                  ),
                                ),
                                Icon(Icons.trending_up_rounded,
                                    color: C.ok, size: 20),
                              ],
                            ),
                          ],
                        ),
                      ),
                    )
                  else
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(
                          'No screenings yet — your first result will appear here.',
                          style: const TextStyle(fontSize: 11, color: C.muted),
                        ),
                      ),
                    ),
                  const SizedBox(height: 8),
                  // Quick links
                  Row(
                    children: [
                      Expanded(
                          child: _quick(context, Icons.restaurant_rounded, 'Diet plan',
                              "Today's meals", () => _goTab(context, 'diet'))),
                      const SizedBox(width: 7),
                      Expanded(
                          child: _quick(context, Icons.history_rounded, 'History',
                              history.isEmpty ? '0 scans' : '${history.length} scans',
                              () => _goTab(context, 'history'))),
                    ],
                  ),
                  const SizedBox(height: 7),
                  Row(
                    children: [
                      Expanded(
                          child: _quick(context, Icons.psychology_alt_outlined,
                              'Why result?', 'Last explanation', () => _goTab(context, 'why'))),
                      const SizedBox(width: 7),
                      Expanded(
                          child: _quick(context, Icons.person_outline_rounded,
                              'Profile', 'Edit details',
                              () => _goTab(context, 'profile'))),
                    ],
                  ),
                  const SizedBox(height: 10),
                  // Tip of the day
                  Card(
                    color: const Color(0xFFFFF6E3),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                      side: const BorderSide(color: Color(0xFFF4DFAE)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(11),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.emoji_food_beverage_rounded,
                              color: Color(0xFFA06C00), size: 18),
                          const SizedBox(width: 9),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('Tip of the day',
                                    style: TextStyle(
                                        fontWeight: FontWeight.w700, fontSize: 12)),
                                const SizedBox(height: 2),
                                Text(
                                  _tip(),
                                  style: const TextStyle(
                                      fontSize: 10.5, color: C.muted, height: 1.4),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            DisclaimerFooter(),
            HemoBottomNav(
              active: 'home',
              onTab: (t) => _goTab(context, t),
            ),
          ],
        ),
      ),
    );
  }

  String _tip() {
    final tips = const [
      'Squeeze lemon on your dal — vitamin C can boost iron absorption.',
      'Avoid tea or coffee within an hour of iron-rich meals.',
      'Cook in a cast-iron pan for a small iron boost.',
      'Pair greens with tomatoes or amla for better absorption.',
    ];
    return tips[DateTime.now().day % tips.length];
  }

  void _goScan(BuildContext context) {
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => const CaptureGuideScreen()));
  }

  Widget _quick(BuildContext context, IconData icon, String title, String sub,
      VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(9),
          child: Row(
            children: [
              MiniAvatar(icon, size: 28),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 12)),
                    Text(sub,
                        style:
                            const TextStyle(fontSize: 10, color: C.muted)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _goTab(BuildContext context, String tab) {
    switch (tab) {
      case 'scan':
        _goScan(context);
      case 'history':
        Navigator.of(context)
            .push(MaterialPageRoute(builder: (_) => const HistoryScreen()));
      case 'diet':
        Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const DietScreen.neutral()));
      case 'profile':
        Navigator.of(context)
            .push(MaterialPageRoute(builder: (_) => const SettingsScreen()));
      case 'why':
        Navigator.of(context)
            .push(MaterialPageRoute(builder: (_) => const HistoryScreen()));
    }
  }
}

