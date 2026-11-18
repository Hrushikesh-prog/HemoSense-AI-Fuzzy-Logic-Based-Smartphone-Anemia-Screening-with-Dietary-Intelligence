import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';

import '../data/api_client.dart';
import '../theme.dart';
import '../widgets/ui.dart';
import 'analyzing_screen.dart';
import 'capture_guide_screen.dart';
import 'review_screen.dart';

/// ⑯ Error state — tinted "couldn't analyze" card with the specific problem
/// and how to fix it, plus Retake / View capture guide actions.
class ErrorScreen extends StatelessWidget {
  final ApiException failure;

  /// The photos/boxes that failed, so the user can adjust the box or retry
  /// without retaking (optional).
  final List<XFile>? shots;
  final List<List<double>>? roiBoxes;
  final List<String> symptoms;
  final String eyeSide;

  const ErrorScreen({
    super.key,
    required this.failure,
    this.shots,
    this.roiBoxes,
    this.symptoms = const [],
    this.eyeSide = 'Left eye',
  });

  bool get _isPhotoProblem =>
      failure.code == 'image_quality' || failure.code == 'bad_image';

  static String _qualityTitle(String? reason) {
    switch (reason) {
      case 'too_dark':
        return 'The photo is too dark';
      case 'overexposed':
        return 'The photo has too much glare';
      case 'blurry':
        return 'The photo is blurry';
      case 'no_conjunctiva':
        return 'Inner eyelid not found in the box';
      case 'no_eye':
        return 'No eye found above the box';
      case 'not_crescent':
        return "That isn't the inner eyelid";
      case 'too_far':
        return 'The eyelid is too small in the photo';
      default:
        return "We couldn't analyse this photo";
    }
  }

  static String _qualityTip(String? reason) {
    switch (reason) {
      case 'too_dark':
        return 'Turn on the torch (lightning icon) or move to daylight / bright white light.';
      case 'overexposed':
        return 'Move the light slightly to the side so it does not reflect straight off the eye.';
      case 'blurry':
        return 'Hold the phone 10-15 cm away, keep it steady and tap the eyelid to focus.';
      case 'no_conjunctiva':
        return 'Gently pull the lower eyelid down so the pink area shows, then drag the box over it.';
      case 'no_eye':
        return 'Place the box on the pink inner eyelid directly under the white of the eye.';
      case 'not_crescent':
        return 'The pink inner eyelid is a thin half-moon. Move closer and draw a small box around just that half-moon, not the cheek, nose or clothes.';
      case 'too_far':
        return 'Hold the phone 10-15 cm from the eye so the pink eyelid fills the oval, then retake.';
      default:
        return 'Use bright, even light, pull the lower eyelid down and place the box over the pink inner eyelid.';
    }
  }

  (String, IconData, List<(String, String)>) get _content {
    switch (failure.code) {
      case 'network':
        return (
          'No connection to the server',
          Icons.wifi_off_rounded,
          [
            ('Could not reach the server', failure.message),
            ('Check the backend URL in Settings', 'Phone and laptop must be on the same Wi-Fi'),
            ('Make sure the FastAPI server is running', 'uvicorn api.main:app --host 0.0.0.0 --port 8000'),
          ],
        );
      case 'timeout':
        return (
          'The server took too long',
          Icons.hourglass_bottom_rounded,
          [('No answer in time', failure.message)],
        );
      case 'model_unavailable':
        return (
          'Service temporarily unavailable',
          Icons.cloud_off_rounded,
          [('The screening model is not loaded on the server', failure.message)],
        );
      case 'image_quality':
        final perPhoto = failure.photoErrors.length > 1
            ? [
                for (var i = 0; i < failure.photoErrors.length; i++)
                  ('Photo ${i + 1}', failure.photoErrors[i]),
              ]
            : const <(String, String)>[];
        return (
          _qualityTitle(failure.reason),
          Icons.image_not_supported_rounded,
          [
            ('What went wrong', failure.message),
            ('How to fix it', _qualityTip(failure.reason)),
            ...perPhoto,
          ],
        );
      case 'bad_image':
        return (
          "We couldn't analyse these photos",
          Icons.image_not_supported_rounded,
          [('The photos could not be processed', failure.message)],
        );
      default:
        return ('Something went wrong', Icons.error_outline_rounded,
            [('Unexpected problem', failure.message)]);
    }
  }

  @override
  Widget build(BuildContext context) {
    final (title, icon, problems) = _content;
    return Scaffold(
      appBar: AppBar(title: const Text('Screening problem')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
              children: [
                // Dimmed photo stand-in with "not usable" pill
                Stack(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(14),
                      child: ColorFiltered(
                        colorFilter: const ColorFilter.mode(
                            Colors.black54, BlendMode.saturation),
                        child: SizedBox(
                            height: 120, child: const EyeArt(pale: true)),
                      ),
                    ),
                    Positioned.fill(
                      child: Center(
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: C.severeBg,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.warning_amber_rounded,
                                  size: 13, color: C.severe),
                              SizedBox(width: 5),
                              Text('Not usable',
                                  style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w800,
                                      color: C.severe)),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Card(
                  color: C.severeBg,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                    side: const BorderSide(color: Color(0xFFF2C4C4)),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title,
                            style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w800,
                                color: C.severe)),
                        const SizedBox(height: 2),
                        const Text(
                          'Results from a poor photo can be wrong, so please retake or fix the setup.',
                          style: TextStyle(fontSize: 10.5, color: Color(0xFF6B2B2B)),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 11, vertical: 2),
                    child: Column(
                      children: [
                        for (final (label, detail) in problems)
                          MockListRow(
                            leading: const SeverityPill('✕'),
                            title: Text(label),
                            subtitle: Text(detail),
                          ),
                      ],
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
                  icon: const Icon(Icons.photo_camera_rounded, size: 15),
                  label: const Text('Retake photo'),
                  onPressed: () => Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(
                          builder: (_) => const CaptureGuideScreen()),
                      (route) => route.isFirst),
                ),
                if (shots != null && shots!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  OutlinedButton.icon(
                    icon: Icon(
                        _isPhotoProblem
                            ? Icons.crop_free_rounded
                            : Icons.refresh_rounded,
                        size: 15),
                    label: Text(_isPhotoProblem
                        ? 'Adjust the box and try again'
                        : 'Try again'),
                    onPressed: () => Navigator.of(context).pushReplacement(
                        MaterialPageRoute(
                            builder: (_) => _isPhotoProblem
                                ? ReviewScreen(
                                    shots: shots!,
                                    initialBoxes: roiBoxes,
                                    symptoms: symptoms,
                                    eyeSide: eyeSide)
                                : AnalyzingScreen(
                                    shots: shots!,
                                    roiBoxes: roiBoxes,
                                    symptoms: symptoms,
                                    eyeSide: eyeSide))),
                  ),
                ],
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
