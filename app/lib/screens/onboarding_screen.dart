import 'package:flutter/material.dart';

import '../theme.dart';
import '../widgets/ui.dart';
import 'profile_setup_screen.dart';

/// ② Onboarding — 3 swipeable slides with the eye illustration, dots and a
/// Skip action; the last slide carries the consent checkbox + disclaimer.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _Slide {
  final IconData icon;
  final String title;
  final String body;
  final bool showEye;
  const _Slide(this.icon, this.title, this.body, {this.showEye = false});
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _controller = PageController();
  bool _consented = false;
  int _page = 0;

  static const _slides = [
    _Slide(Icons.camera_alt_rounded, 'Snap your inner eyelid',
        'Gently pull down your lower eyelid and take a clear photo. The colour of this area can show signs of anemia.',
        showEye: true),
    _Slide(Icons.auto_awesome_rounded, 'Smart screening analysis',
        'A fuzzy-logic (ANFIS) model analyses the colour of the inner eyelid and gives an anemia risk score with a confidence level.'),
    _Slide(Icons.restaurant_rounded, 'Eat right, recover faster',
        'Get a personalised iron-rich diet plan with vitamin-C pairings matched to your profile.'),
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _finish() {
    Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const ProfileSetupScreen(firstRun: true)));
  }

  @override
  Widget build(BuildContext context) {
    final last = _page == _slides.length - 1;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.topRight,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
                child: TextButton(
                  onPressed: _finish,
                  style: TextButton.styleFrom(
                      foregroundColor: C.primary,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      textStyle: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600)),
                  child: const Text('Skip'),
                ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: _slides.length,
                onPageChanged: (i) => setState(() => _page = i),
                itemBuilder: (context, i) {
                  final s = _slides[i];
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 18),
                    child: Column(
                      children: [
                        const Spacer(),
                        if (s.showEye)
                          Expanded(
                            flex: 4,
                            child: Stack(
                              fit: StackFit.expand,
                              children: [
                                Container(
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(14),
                                    boxShadow: const [
                                      BoxShadow(
                                          color: Color(0x2E781E3C),
                                          blurRadius: 16,
                                          offset: Offset(0, 6)),
                                    ],
                                  ),
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(14),
                                    child: const EyeArt(),
                                  ),
                                ),
                                // dashed oval target hint
                                Center(
                                  child: Container(
                                    width: double.infinity,
                                    margin: const EdgeInsets.symmetric(
                                        horizontal: 44),
                                    height: 120,
                                    decoration: BoxDecoration(
                                      border: Border.all(
                                          color: Colors.white,
                                          width: 2,
                                          style: BorderStyle.solid),
                                      borderRadius: BorderRadius.circular(60),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          )
                        else
                          Expanded(
                            flex: 3,
                            child: Center(
                              child: Container(
                                width: 110,
                                height: 110,
                                decoration: const BoxDecoration(
                                    color: C.container, shape: BoxShape.circle),
                                child: Icon(s.icon, size: 52, color: C.primary),
                              ),
                            ),
                          ),
                        const Spacer(),
                        Text(s.title,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w800,
                                color: C.text)),
                        const SizedBox(height: 6),
                        Text(s.body,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 12, color: C.muted, height: 1.45)),
                        const Spacer(),
                      ],
                    ),
                  );
                },
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < _slides.length; i++)
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    margin: const EdgeInsets.symmetric(horizontal: 2.5),
                    width: i == _page ? 16 : 6,
                    height: 6,
                    decoration: BoxDecoration(
                      color: i == _page ? C.primary : const Color(0xFFDCCBD1),
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
              child: Column(
                children: [
                  if (last) ...[
                    Row(
                      children: [
                        SizedBox(
                          width: 24,
                          height: 24,
                          child: Checkbox(
                            value: _consented,
                            onChanged: (v) => setState(() => _consented = v ?? false),
                            activeColor: C.primary,
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(5)),
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: Text(
                            'I understand this is a screening tool, not a diagnosis, and consent to analysing my photos.',
                            style: TextStyle(fontSize: 10.5, color: C.muted, height: 1.35),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                  ],
                  FilledButton(
                    onPressed: _consented
                        ? () => last
                            ? _finish()
                            : _controller.nextPage(
                                duration: const Duration(milliseconds: 300),
                                curve: Curves.easeOut)
                        : null,
                    child: Text(last ? 'Get started' : 'Next'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
