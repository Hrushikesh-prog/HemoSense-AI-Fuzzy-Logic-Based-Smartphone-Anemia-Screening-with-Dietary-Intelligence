import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/local_store.dart';
import '../models/screening.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'camera_screen.dart';
import 'capture_tutorial_screen.dart';
import 'review_screen.dart';

/// ⑥ Capture guide — pose illustration + 4 rules, then Open camera.
/// Shows the symptom checklist so the backend can cross-check the result.
class CaptureGuideScreen extends ConsumerStatefulWidget {
  const CaptureGuideScreen({super.key});

  @override
  ConsumerState<CaptureGuideScreen> createState() => _CaptureGuideScreenState();
}

class _CaptureGuideScreenState extends ConsumerState<CaptureGuideScreen> {
  final Set<String> _selectedSymptoms = {};

  static const _rules = [
    (Icons.wb_sunny_rounded, 'Good, even light', 'Daylight or white light. Avoid yellow bulbs.'),
    (Icons.visibility_outlined, 'Show the inner eyelid', 'Gently pull the lower lid down with a clean finger'),
    (Icons.photo_camera_outlined, 'Hold 10–15 cm away', 'Keep the phone steady and let it focus'),
    (Icons.close_rounded, 'No makeup or filters', 'Remove kajal/eyeliner and coloured lenses'),
  ];

  List<String> get _symptoms => _selectedSymptoms.toList(growable: false);

  void _openTutorial() => Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => CaptureTutorialScreen(symptoms: _symptoms)));

  /// The animated tutorial runs before the very first capture; afterwards
  /// "Open camera" goes straight to the camera.
  void _openCamera() {
    if (!LocalStore.tutorialSeen) {
      _openTutorial();
      return;
    }
    Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => CameraScreen(symptoms: _symptoms)));
  }

  @override
  Widget build(BuildContext context) {
    final symptomsAsync = ref.watch(p.symptomsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('How to capture')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
              children: [
                // Pose illustration with hint chip
                Stack(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(14),
                      child: SizedBox(
                          height: 130, child: const EyeArt()),
                    ),
                    Positioned(
                      right: 8,
                      bottom: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(9),
                        ),
                        child: const Text('Pull lower lid down ↓ and look up ↑',
                            style: TextStyle(color: Colors.white, fontSize: 9)),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                OutlinedButton.icon(
                  icon: const Icon(Icons.play_circle_outline_rounded, size: 17),
                  label: const Text('How to take the photo'),
                  onPressed: _openTutorial,
                ),
                const SizedBox(height: 6),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 2),
                    child: Column(
                      children: [
                        for (final (icon, title, sub) in _rules)
                          MockListRow(
                            leading: MiniAvatar(icon, size: 24),
                            title: Text(title),
                            subtitle: Text(sub),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // Symptom checklist
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: symptomsAsync.when(
                      loading: () => const Center(
                          child: Padding(
                        padding: EdgeInsets.all(6),
                        child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2)),
                      )),
                      error: (e, _) => const Text(
                        'Symptom checklist unavailable (backend unreachable?). You can continue without it.',
                        style: TextStyle(fontSize: 10.5, color: C.muted),
                      ),
                      data: (List<SymptomItem> items) => Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SectionLabel('Symptoms right now (optional)'),
                          const SizedBox(height: 7),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: [
                              for (final s in items)
                                SelectChip(
                                  s.label,
                                  selected: _selectedSymptoms.contains(s.id),
                                  onTap: () => setState(() {
                                    _selectedSymptoms.contains(s.id)
                                        ? _selectedSymptoms.remove(s.id)
                                        : _selectedSymptoms.add(s.id);
                                  }),
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
            child: Column(
              children: [
                FilledButton.icon(
                  icon: const Icon(Icons.photo_camera_rounded, size: 16),
                  label: const Text('Open camera'),
                  onPressed: _openCamera,
                ),
                const SizedBox(height: 4),
                OutlinedButton.icon(
                  icon: const Icon(Icons.photo_library_outlined, size: 16),
                  label: const Text('Choose from gallery (1-3 photos)'),
                  onPressed: () =>
                      pickFromGalleryAndReview(context, symptoms: _symptoms),
                ),
                const SizedBox(height: 4),
                DisclaimerFooter(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
