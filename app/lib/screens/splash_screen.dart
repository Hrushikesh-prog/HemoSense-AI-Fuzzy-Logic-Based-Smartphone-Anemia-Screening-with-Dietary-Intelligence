import 'package:flutter/material.dart';

import '../theme.dart';
import 'onboarding_screen.dart';
import 'profile_setup_screen.dart';
import 'home_screen.dart';
import '../data/local_store.dart';

/// ① Splash — gradient background, white rounded logo with blood-drop + eye,
/// brand line and a progress bar while the app prepares routing.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    Future<void>.delayed(const Duration(milliseconds: 1600), _next);
  }

  void _next() {
    if (!mounted) return;
    Widget target;
    if (!LocalStore.consented) {
      target = const OnboardingScreen();
    } else if (!LocalStore.profile.isComplete) {
      target = const ProfileSetupScreen(firstRun: true);
    } else {
      target = const HomeScreen();
    }
    Navigator.of(context)
        .pushReplacement(MaterialPageRoute(builder: (_) => target));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFC2304F), Color(0xFF6E1430)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Logo: white rounded square with drop + eye
                      Container(
                        width: 88,
                        height: 88,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(26),
                          boxShadow: const [
                            BoxShadow(
                                color: Color(0x40000000),
                                blurRadius: 20,
                                offset: Offset(0, 8)),
                          ],
                        ),
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            const Icon(Icons.water_drop_rounded,
                                color: C.primary, size: 44),
                            Positioned(
                              bottom: 14,
                              right: 16,
                              child: Icon(Icons.visibility_outlined,
                                  color: C.primaryDark, size: 18),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                      const Text('HemoSense AI',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 25,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.3)),
                      const SizedBox(height: 6),
                      Text(
                        'Anemia screening from a single eye photo',
                        style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.9), fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 20),
                child: Column(
                  children: [
                    Container(
                      width: 120,
                      height: 3,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.25),
                        borderRadius: BorderRadius.circular(2),
                      ),
                      child: const Align(
                        alignment: Alignment.centerLeft,
                        child: FractionallySizedBox(
                          widthFactor: 0.6,
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.all(Radius.circular(2))),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text('Fuzzy-logic powered · v1.0',
                        style: TextStyle(
                            fontSize: 9.5,
                            color: Colors.white.withValues(alpha: 0.75))),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
