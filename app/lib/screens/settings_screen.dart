import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../data/local_store.dart';
import '../models/screening.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'profile_setup_screen.dart';

/// ⑰ Profile & settings — profile card, privacy rows and the Developer
/// section with the backend URL and a live online-status check.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _url;
  bool _checking = false;
  HealthStatus? _health;
  String? _healthError;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: LocalStore.backendUrl);
    _checkHealth(silent: true);
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  void _saveUrl() {
    var value = _url.text.trim();
    if (value.isEmpty) return;
    if (!value.startsWith('http://') && !value.startsWith('https://')) {
      value = 'http://$value';
    }
    if (value.endsWith('/')) value = value.substring(0, value.length - 1);
    LocalStore.backendUrl = value;
    _url.text = value;
    ref.read(p.settingsVersionProvider.notifier).bump();
    _checkHealth();
  }

  Future<void> _checkHealth({bool silent = false}) async {
    if (!silent) setState(() => _checking = true);
    try {
      final h = await ref.read(p.apiClientProvider).health();
      if (!mounted) return;
      setState(() {
        _health = h;
        _healthError = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _health = null;
        _healthError = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _health = null);
    } finally {
      if (mounted && !silent) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = ref.watch(p.profileProvider);
    final online = _health?.modelLoaded ?? false;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile & settings')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
              children: [
                // Profile card
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          alignment: Alignment.center,
                          decoration:
                              const BoxDecoration(color: C.container, shape: BoxShape.circle),
                          child: const Icon(Icons.person_rounded,
                              color: C.primaryDark),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${profile.age ?? '—'} yrs · ${_sexLabel(profile.sex)} · ${_dietLabel(profile.diet)}',
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700, fontSize: 12.5),
                              ),
                              Text(
                                profile.pregnant ? 'Currently pregnant' : 'WHO cut-offs applied automatically',
                                style: const TextStyle(
                                    fontSize: 10.5, color: C.muted),
                              ),
                            ],
                          ),
                        ),
                        GestureDetector(
                          onTap: () => Navigator.of(context).push(MaterialPageRoute(
                              builder: (_) => const ProfileSetupScreen())),
                          child: const Text('Edit',
                              style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: C.primary)),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                const SectionLabel('Privacy'),
                const SizedBox(height: 5),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 2),
                    child: Column(
                      children: [
                        MockListRow(
                          leading: const MiniAvatar(Icons.lock_outline_rounded, size: 22),
                          title: const Text('Delete photos after analysis'),
                          subtitle: const Text('Only results are stored (server default)'),
                          trailing: Toggle(on: true, onChanged: (_) {}),
                        ),
                        const MockListRow(
                          leading: MiniAvatar(Icons.history_rounded, size: 22),
                          title: Text('History stays on this device'),
                          subtitle: Text('No accounts, no cloud sync'),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                const SectionLabel('Developer'),
                const SizedBox(height: 5),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const MiniAvatar(Icons.dns_rounded, size: 22),
                            const SizedBox(width: 10),
                            const Expanded(
                              child: Text('Backend URL',
                                  style: TextStyle(
                                      fontWeight: FontWeight.w700, fontSize: 12.5)),
                            ),
                            if (_checking)
                              const SizedBox(
                                  width: 13,
                                  height: 13,
                                  child: CircularProgressIndicator(strokeWidth: 2))
                            else
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: online ? C.okBg : C.severeBg,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Text(online ? '● Online' : '● Offline',
                                    style: TextStyle(
                                        fontSize: 9.5,
                                        fontWeight: FontWeight.w700,
                                        color: online ? C.ok : C.severe)),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _url,
                          keyboardType: TextInputType.url,
                          onSubmitted: (_) => _saveUrl(),
                          style: const TextStyle(fontSize: 11),
                          decoration: InputDecoration(
                            hintText: 'http://localhost:8000',
                            suffixIcon: IconButton(
                              icon: const Icon(Icons.save_rounded, size: 18),
                              onPressed: _saveUrl,
                            ),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Default: the cloud server. Backup: http://3.111.237.63 or http://<laptop-ip>:8000 on the same Wi-Fi. Tap save to re-check.',
                          style: const TextStyle(fontSize: 9.5, color: C.muted),
                        ),
                        if (_health != null) ...[
                          const SizedBox(height: 6),
                          Text(
                            'Model: ${_health!.modelLoaded ? (_health!.modelName ?? 'loaded') : 'not loaded'}',
                            style: const TextStyle(fontSize: 10, color: C.muted),
                          ),
                        ],
                        if (_healthError != null) ...[
                          const SizedBox(height: 6),
                          Text(_healthError!,
                              style: const TextStyle(
                                  fontSize: 10, color: C.severe)),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SectionLabel('About'),
                        const SizedBox(height: 5),
                        const Text(
                          'HemoSense AI — smartphone anemia screening with dietary intelligence. Capstone project, 2026.',
                          style: TextStyle(fontSize: 10.5, color: C.muted, height: 1.45),
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
            active: 'profile',
            onTab: (t) => _handleTab(context, t),
          ),
        ],
      ),
    );
  }

  String _sexLabel(String s) {
    switch (s) {
      case 'male':
        return 'Male';
      case 'other':
        return 'Other';
      default:
        return 'Female';
    }
  }

  String _dietLabel(String d) {
    switch (d) {
      case 'vegan':
        return 'Vegan';
      case 'vegetarian':
        return 'Vegetarian';
      default:
        return 'Non-veg';
    }
  }

  void _handleTab(BuildContext context, String tab) {
    if (tab == 'profile') return;
    Navigator.of(context).pop();
  }
}
