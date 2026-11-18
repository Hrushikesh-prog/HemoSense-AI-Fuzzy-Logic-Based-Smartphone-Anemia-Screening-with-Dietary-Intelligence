import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'data/local_store.dart';
import 'screens/splash_screen.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();
  await LocalStore.open();
  runApp(const ProviderScope(child: HemoSenseApp()));
}

/// Root widget. The splash decides the first route:
/// onboarding (no consent yet) -> profile setup -> home.
class HemoSenseApp extends StatelessWidget {
  const HemoSenseApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'HemoSense AI',
      debugShowCheckedModeBanner: false,
      theme: buildHemoSenseTheme(),
      home: const SplashScreen(),
    );
  }
}
