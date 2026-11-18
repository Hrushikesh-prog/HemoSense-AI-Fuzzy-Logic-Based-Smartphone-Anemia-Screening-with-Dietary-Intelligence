import 'package:flutter/material.dart';

/// Design tokens taken from docs/ui_mockups.html (Material 3, page 2).
class C {
  static const primary = Color(0xFFB4264A);
  static const primaryDark = Color(0xFF7A1734);
  static const primaryLight = Color(0xFFC2304F);
  static const container = Color(0xFFFCE4EA);
  static const background = Color(0xFFFFF8F9);
  static const outline = Color(0xFFE8D9DE);
  static const text = Color(0xFF1F1A1C);
  static const muted = Color(0xFF6F6267);

  // Risk colours (always shown with text labels)
  static const ok = Color(0xFF2E7D32);
  static const okBg = Color(0xFFE3F3E4);
  static const mild = Color(0xFFC98F00);
  static const mildDark = Color(0xFF8A6200);
  static const mildBg = Color(0xFFFFF3D1);
  static const moderate = Color(0xFFE0620B);
  static const moderateDark = Color(0xFFA64300);
  static const moderateBg = Color(0xFFFFE7D4);
  static const severe = Color(0xFFC62828);
  static const severeBg = Color(0xFFFBDEDE);

  static Color severityColor(String severity) {
    switch (severity) {
      case 'Normal':
        return ok;
      case 'Mild':
        return mildDark;
      case 'Moderate':
      case 'Moderate-to-Severe':
        return moderateDark;
      case 'Severe':
        return severe;
      default:
        return muted;
    }
  }

  static Color severityBg(String severity) {
    switch (severity) {
      case 'Normal':
        return okBg;
      case 'Mild':
        return mildBg;
      case 'Moderate':
      case 'Moderate-to-Severe':
        return moderateBg;
      case 'Severe':
        return severeBg;
      default:
        return const Color(0xFFF1E6EA);
    }
  }
}

ThemeData buildHemoSenseTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: C.primary).copyWith(
    primary: C.primary,
    onPrimary: Colors.white,
    primaryContainer: C.container,
    onPrimaryContainer: C.primaryDark,
    secondary: C.moderate,
    error: C.severe,
    surface: Colors.white,
  );
  const side = BorderSide(color: C.outline);
  final shape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(14),
    side: side,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: C.background,
    textTheme: const TextTheme(
      bodyMedium: TextStyle(color: C.text, height: 1.35),
      bodySmall: TextStyle(color: C.muted, fontSize: 11),
      titleLarge: TextStyle(color: C.text, fontWeight: FontWeight.w700, fontSize: 20),
      titleMedium: TextStyle(color: C.text, fontWeight: FontWeight.w700, fontSize: 14),
      titleSmall: TextStyle(color: C.text, fontWeight: FontWeight.w600, fontSize: 12.5),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: C.text,
      centerTitle: false,
      titleTextStyle: TextStyle(
          color: C.text, fontSize: 15, fontWeight: FontWeight.w700, height: 1),
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      shape: shape,
      margin: EdgeInsets.zero,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: C.primary,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(44),
        shape: const StadiumBorder(),
        textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: C.primary,
        minimumSize: const Size.fromHeight(44),
        side: const BorderSide(color: C.primary, width: 1.3),
        shape: const StadiumBorder(),
        textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      floatingLabelStyle: const TextStyle(color: C.muted, fontSize: 11),
      labelStyle: const TextStyle(color: C.muted, fontSize: 12),
      hintStyle: const TextStyle(color: C.muted, fontSize: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(9),
        borderSide: const BorderSide(color: Color(0xFFCBBEC3)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(9),
        borderSide: const BorderSide(color: Color(0xFFCBBEC3)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(9),
        borderSide: const BorderSide(color: C.primary, width: 1.4),
      ),
    ),
    dividerTheme: const DividerThemeData(color: Color(0xFFF1E7EA), thickness: 1),
  );
}
