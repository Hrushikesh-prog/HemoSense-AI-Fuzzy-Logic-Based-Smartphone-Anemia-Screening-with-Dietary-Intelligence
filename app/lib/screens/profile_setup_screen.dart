import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/local_store.dart';
import '../models/profile.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'home_screen.dart';

/// ④ Profile setup — "Tell us about you" with fields, sex/diet chips and the
/// pregnancy toggle card (only for Female), per the mockup.
class ProfileSetupScreen extends ConsumerStatefulWidget {
  final bool firstRun;
  const ProfileSetupScreen({super.key, this.firstRun = false});

  @override
  ConsumerState<ProfileSetupScreen> createState() => _ProfileSetupScreenState();
}

class _ProfileSetupScreenState extends ConsumerState<ProfileSetupScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _age;
  late final TextEditingController _allergies;
  late String _sex;
  late String _diet;
  bool _pregnant = false;

  static const _sexOptions = ['Female', 'Male', 'Other'];
  static const _dietOptions = ['Omnivore', 'Vegetarian', 'Vegan'];

  @override
  void initState() {
    super.initState();
    final existing = LocalStore.profile;
    _age = TextEditingController(
        text: existing.age == null ? '' : existing.age.toString());
    _allergies = TextEditingController(text: existing.allergies);
    _sex = _sexOptions.contains(_cap(existing.sex)) ? _cap(existing.sex) : 'Female';
    _diet = _dietOptions.contains(_cap(existing.diet)) ? _cap(existing.diet) : 'Omnivore';
    _pregnant = existing.pregnant;
  }

  static String _cap(String s) =>
      s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1).toLowerCase()}';

  @override
  void dispose() {
    _age.dispose();
    _allergies.dispose();
    super.dispose();
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    final sexLower = _sex.toLowerCase() == 'other' ? 'other' : _sex.toLowerCase();
    final profile = UserProfile(
      age: int.tryParse(_age.text.trim()),
      sex: sexLower,
      pregnant: _sex == 'Female' && _pregnant,
      diet: _diet.toLowerCase() == 'vegan'
          ? 'vegan'
          : _diet.toLowerCase() == 'vegetarian'
              ? 'vegetarian'
              : 'omnivore',
      allergies: _allergies.text.trim(),
      // Keep the diet questionnaire answers when editing the basic profile.
      dietProfile: ref.read(p.profileProvider).dietProfile,
    );
    ref.read(p.profileProvider.notifier).save(profile);
    Navigator.of(context)
        .pushReplacement(MaterialPageRoute(builder: (_) => const HomeScreen()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile setup'),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 16),
            child: Center(child: Text('Step 1 of 1', style: TextStyle(fontSize: 10, color: C.muted))),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 4, 14, 16),
          children: [
            const Text('Tell us about you',
                style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
            const SizedBox(height: 3),
            const Text(
              'What counts as anemia depends on age, sex and pregnancy (WHO), so we use these to read your result. Your answers also tailor the diet plan.',
              style: TextStyle(fontSize: 10.5, color: C.muted, height: 1.4),
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _age,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Age', suffixText: 'yrs'),
              validator: (v) =>
                  (int.tryParse(v?.trim() ?? '') ?? 0) <= 0 ? 'Enter your age' : null,
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _allergies,
              decoration: const InputDecoration(
                  labelText: 'Known allergies (optional)', hintText: 'e.g. peanuts, dairy'),
            ),
            const SizedBox(height: 14),
            const SectionLabel('Sex'),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              children: [
                for (final s in _sexOptions)
                  SelectChip(
                    s,
                    selected: _sex == s,
                    onTap: () => setState(() => _sex = s),
                  ),
              ],
            ),
            if (_sex == 'Female') ...[
              const SizedBox(height: 10),
              Card(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Currently pregnant?',
                                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5)),
                            Text('Pregnancy changes what counts as anemia',
                                style: TextStyle(fontSize: 10.5, color: C.muted)),
                          ],
                        ),
                      ),
                      Toggle(
                        on: _pregnant,
                        onChanged: (v) => setState(() => _pregnant = v),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 14),
            const SectionLabel('Diet preference'),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              children: [
                for (final d in _dietOptions)
                  SelectChip(
                    d,
                    selected: _diet == d,
                    onTap: () => setState(() => _diet = d),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            FilledButton(
                onPressed: _save,
                child: Text(widget.firstRun ? 'Continue' : 'Save profile')),
            const SizedBox(height: 6),
            const DisclaimerFooter(),
          ],
        ),
      ),
    );
  }
}
