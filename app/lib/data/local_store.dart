import 'dart:convert';

import 'package:hive/hive.dart';

import '../models/profile.dart';
import '../models/screening.dart';

/// On-device persistence (Hive). Screenshots/photos are never stored;
/// only settings, the profile and Hb-free history entries.
class LocalStore {
  static late final Box<dynamic> _settings;
  static late final Box<dynamic> _profile;
  static late final Box<dynamic> _history;

  static Future<void> open() async {
    _settings = await Hive.openBox<dynamic>('hs_settings');
    _profile = await Hive.openBox<dynamic>('hs_profile');
    _history = await Hive.openBox<dynamic>('hs_history');
  }

  // --- settings ---
  static String get backendUrl =>
      (_settings.get('backendUrl') as String?) ??
      defaultBackendUrl;

  /// Production backend (AWS EC2 ap-south-1, HTTPS via Caddy + Let's Encrypt).
  /// Fallback during the demo: http://3.111.237.63 or a laptop on the same Wi-Fi.
  static const defaultBackendUrl = 'https://3-111-237-63.sslip.io';
  static set backendUrl(String v) => _settings.put('backendUrl', v);

  static bool get consented => (_settings.get('consented') as bool?) ?? false;
  static set consented(bool v) => _settings.put('consented', v);

  /// Whether the animated capture tutorial has been shown once. Tolerant of
  /// an unopened store (widget tests): reads as not seen, writes are ignored.
  static bool get tutorialSeen {
    try {
      return (_settings.get('tutorialSeen') as bool?) ?? false;
    } catch (_) {
      return false;
    }
  }

  static set tutorialSeen(bool v) {
    try {
      _settings.put('tutorialSeen', v);
    } catch (_) {}
  }

  // --- profile ---
  /// Tolerant of an unopened store (widget tests) and of corrupt JSON:
  /// reads as an empty profile.
  static UserProfile get profile {
    try {
      final raw = _profile.get('json') as String?;
      if (raw == null) return const UserProfile();
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return const UserProfile();
      return UserProfile.fromMap(
          decoded.map((k, v) => MapEntry(k.toString(), v)));
    } catch (_) {
      return const UserProfile();
    }
  }

  static set profile(UserProfile p) {
    try {
      _profile.put('json', jsonEncode(p.toMap()));
    } catch (_) {}
  }

  /// Whether the diet questionnaire was offered after the first result.
  static bool get dietQuestionnaireOffered {
    try {
      return (_settings.get('dietQuestionnaireOffered') as bool?) ?? false;
    } catch (_) {
      return false;
    }
  }

  static set dietQuestionnaireOffered(bool v) {
    try {
      _settings.put('dietQuestionnaireOffered', v);
    } catch (_) {}
  }

  // --- history ---
  static List<HistoryEntry> get history {
    final String? raw;
    try {
      raw = _history.get('entries') as String?;
    } catch (_) {
      return [];
    }
    if (raw == null) return [];
    final list = (jsonDecode(raw) as List).whereType<Map<String, dynamic>>();
    return list.map(HistoryEntry.fromMap).toList()
      ..sort((a, b) => b.time.compareTo(a.time));
  }

  static void addHistoryEntry(HistoryEntry e) {
    final entries = history.map((h) => h.toMap()).toList();
    entries.add(e.toMap());
    _history.put('entries', jsonEncode(entries));
  }

  static void clearHistory() => _history.delete('entries');

  // --- last diet plan cache (for the Diet tab without a fresh screening) ---
  static Map<String, dynamic>? get cachedDietPlan {
    try {
      final raw = _settings.get('dietPlan') as String?;
      if (raw == null) return null;
      final decoded = jsonDecode(raw);
      return decoded is Map<String, dynamic> ? decoded : null;
    } catch (_) {
      return null;
    }
  }

  static set cachedDietPlan(Map<String, dynamic>? plan) {
    try {
      if (plan == null) {
        _settings.delete('dietPlan');
      } else {
        _settings.put('dietPlan', jsonEncode(plan));
      }
    } catch (_) {}
  }
}
