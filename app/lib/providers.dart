import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'data/api_client.dart';
import 'data/local_store.dart';
import 'models/profile.dart';
import 'models/screening.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

/// Bumped whenever settings change (e.g. backend URL edited) so that
/// network-backed providers re-fetch.
class SettingsVersion extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state = state + 1;
}

final settingsVersionProvider =
    NotifierProvider<SettingsVersion, int>(SettingsVersion.new);

final symptomsProvider = FutureProvider<List<SymptomItem>>((ref) async {
  ref.watch(settingsVersionProvider);
  return ref.watch(apiClientProvider).symptoms();
});

/// Foods for the diet questionnaire's dislikes chips (`GET /diet/foods`).
final dietFoodsProvider = FutureProvider<List<DietFood>>((ref) async {
  ref.watch(settingsVersionProvider);
  return ref.watch(apiClientProvider).dietFoods();
});

final healthProvider = FutureProvider<HealthStatus>((ref) async {
  ref.watch(settingsVersionProvider);
  return ref.watch(apiClientProvider).health();
});

class ProfileNotifier extends Notifier<UserProfile> {
  @override
  UserProfile build() => LocalStore.profile;

  void save(UserProfile p) {
    LocalStore.profile = p;
    state = p;
  }
}

final profileProvider =
    NotifierProvider<ProfileNotifier, UserProfile>(ProfileNotifier.new);

class HistoryNotifier extends Notifier<List<HistoryEntry>> {
  @override
  List<HistoryEntry> build() => LocalStore.history;

  void add(HistoryEntry entry) {
    LocalStore.addHistoryEntry(entry);
    state = LocalStore.history;
  }

  void clear() {
    LocalStore.clearHistory();
    state = [];
  }
}

final historyProvider =
    NotifierProvider<HistoryNotifier, List<HistoryEntry>>(HistoryNotifier.new);
