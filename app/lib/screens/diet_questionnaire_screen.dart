import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../models/diet_profile.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';

/// Diet questionnaire: budget, region, living situation, kitchen, dislikes
/// and routine. Saved in the profile (Hive) and sent as
/// `user_context.diet_profile` with every screening and diet-plan request.
/// Pops with the saved [DietProfile].
class DietQuestionnaireScreen extends ConsumerStatefulWidget {
  const DietQuestionnaireScreen({super.key});

  @override
  ConsumerState<DietQuestionnaireScreen> createState() =>
      _DietQuestionnaireScreenState();
}

class _DietQuestionnaireScreenState
    extends ConsumerState<DietQuestionnaireScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _budget;
  late final TextEditingController _city;
  final _search = TextEditingController();
  final _custom = TextEditingController();

  String? _state;
  String? _area;
  String? _kitchen;
  bool _fridge = false;
  bool _skipsBreakfast = false;
  bool _nightShift = false;
  final List<String> _dislikes = [];
  String _query = '';
  bool _triedSave = false;

  @override
  void initState() {
    super.initState();
    final existing = ref.read(p.profileProvider).dietProfile;
    _budget = TextEditingController(
      text: existing == null ? '' : formatInr(existing.budgetInrPerDay),
    );
    _city = TextEditingController(text: existing?.city ?? '');
    if (existing != null) {
      _state = kIndianStatesAndUts.contains(existing.state)
          ? existing.state
          : null;
      _area = existing.areaType;
      _kitchen = existing.kitchen;
      _fridge = existing.fridge;
      _skipsBreakfast = existing.skipsBreakfast;
      _nightShift = existing.nightShift;
      _dislikes.addAll(existing.dislikes);
    }
  }

  @override
  void dispose() {
    _budget.dispose();
    _city.dispose();
    _search.dispose();
    _custom.dispose();
    super.dispose();
  }

  double? get _budgetValue => double.tryParse(_budget.text.trim());

  bool _hasDislike(String name) =>
      _dislikes.any((d) => d.toLowerCase() == name.toLowerCase());

  void _toggleDislike(String name) {
    setState(() {
      if (_hasDislike(name)) {
        _dislikes.removeWhere((d) => d.toLowerCase() == name.toLowerCase());
      } else {
        _dislikes.add(name);
      }
    });
  }

  void _addCustom() {
    final t = _custom.text.trim();
    if (t.isEmpty) return;
    if (!_hasDislike(t)) setState(() => _dislikes.add(t));
    _custom.clear();
  }

  void _save() {
    setState(() => _triedSave = true);
    final formOk = _formKey.currentState!.validate();
    if (!formOk || _area == null || _kitchen == null) return;
    final dp = DietProfile(
      budgetInrPerDay: _budgetValue!,
      state: _state!,
      city: _city.text.trim(),
      areaType: _area!,
      kitchen: _kitchen!,
      fridge: _fridge,
      dislikes: List.of(_dislikes),
      skipsBreakfast: _skipsBreakfast,
      nightShift: _nightShift,
    );
    final notifier = ref.read(p.profileProvider.notifier);
    notifier.save(ref.read(p.profileProvider).copyWith(dietProfile: dp));
    Navigator.of(context).pop(dp);
  }

  @override
  Widget build(BuildContext context) {
    final slider = (_budgetValue ?? kBudgetMin).clamp(kBudgetMin, kBudgetMax);
    return Scaffold(
      appBar: AppBar(title: const Text('Diet preferences')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 4, 14, 16),
          children: [
            const Text(
              'Personalise my diet',
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 3),
            const Text(
              'Your answers let the AI planner pick local dishes you can afford, cook and enjoy. They stay on this phone and are only sent with your diet-plan requests.',
              style: TextStyle(fontSize: 10.5, color: C.muted, height: 1.4),
            ),
            const SizedBox(height: 14),
            // --- Budget ---
            const SectionLabel('Daily food budget'),
            const SizedBox(height: 6),
            TextFormField(
              key: const Key('dq_budget'),
              controller: _budget,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: false,
              ),
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(
                labelText: 'Budget per day',
                prefixText: '₹ ',
                helperText:
                    'Between ₹${formatInr(kBudgetMin)} and ₹${formatInr(kBudgetMax)}',
              ),
              onChanged: (_) => setState(() {}),
              validator: (v) {
                final b = double.tryParse(v?.trim() ?? '');
                if (b == null) return 'Enter your daily food budget';
                if (b < kBudgetMin || b > kBudgetMax) {
                  return 'Enter an amount from ₹${formatInr(kBudgetMin)} to ₹${formatInr(kBudgetMax)}';
                }
                return null;
              },
            ),
            Slider(
              value: slider.toDouble(),
              min: kBudgetMin,
              max: kBudgetMax,
              divisions: ((kBudgetMax - kBudgetMin) / kBudgetStep).round(),
              label: _budgetValue == null ? null : '₹${formatInr(slider)}',
              onChanged: (v) {
                final snapped = (v / kBudgetStep).round() * kBudgetStep;
                setState(() => _budget.text = formatInr(snapped));
              },
            ),
            const SizedBox(height: 8),
            // --- Region ---
            const SectionLabel('Where you live'),
            const SizedBox(height: 6),
            DropdownButtonFormField<String>(
              key: const Key('dq_state'),
              initialValue: _state,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'State / union territory',
              ),
              items: [
                for (final s in kIndianStatesAndUts)
                  DropdownMenuItem(value: s, child: Text(s)),
              ],
              onChanged: (v) => setState(() => _state = v),
              validator: (v) =>
                  v == null ? 'Choose your state or union territory' : null,
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _city,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'City / district (optional)',
              ),
            ),
            const SizedBox(height: 14),
            const SectionLabel('Living situation'),
            const SizedBox(height: 6),
            _choiceChips(kAreaTypes, _area, (v) => setState(() => _area = v)),
            if (_triedSave && _area == null) _errorText('Choose one'),
            const SizedBox(height: 14),
            const SectionLabel('Kitchen'),
            const SizedBox(height: 6),
            _choiceChips(
              kKitchenTypes,
              _kitchen,
              (v) => setState(() => _kitchen = v),
            ),
            if (_triedSave && _kitchen == null) _errorText('Choose one'),
            const SizedBox(height: 8),
            _switchCard(
              'Fridge available',
              'Lets the plan use leftovers and fresh produce kept cold',
              _fridge,
              (v) => setState(() => _fridge = v),
            ),
            const SizedBox(height: 14),
            // --- Dislikes ---
            const SectionLabel('Foods you dislike'),
            const SizedBox(height: 3),
            const Text(
              "We'll suggest a replacement for each.",
              style: TextStyle(fontSize: 10.5, color: C.muted),
            ),
            const SizedBox(height: 6),
            if (_dislikes.isNotEmpty) ...[
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final d in _dislikes)
                    InputChip(
                      label: Text(d, style: const TextStyle(fontSize: 11)),
                      onDeleted: () => _toggleDislike(d),
                    ),
                ],
              ),
              const SizedBox(height: 8),
            ],
            _foodPicker(),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('dq_custom_dislike'),
                    controller: _custom,
                    decoration: const InputDecoration(
                      labelText: 'Add another food',
                      hintText: 'Not in the list? Type it here',
                    ),
                    onSubmitted: (_) => _addCustom(),
                  ),
                ),
                const SizedBox(width: 6),
                OutlinedButton(
                  onPressed: _addCustom,
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(64, 44),
                  ),
                  child: const Text('Add'),
                ),
              ],
            ),
            const SizedBox(height: 14),
            // --- Routine ---
            const SectionLabel('Routine'),
            const SizedBox(height: 6),
            _switchCard(
              'I usually skip breakfast',
              null,
              _skipsBreakfast,
              (v) => setState(() => _skipsBreakfast = v),
            ),
            const SizedBox(height: 6),
            _switchCard(
              'I work night shifts',
              null,
              _nightShift,
              (v) => setState(() => _nightShift = v),
            ),
            const SizedBox(height: 20),
            FilledButton(
              key: const Key('dq_save'),
              onPressed: _save,
              child: const Text('Save diet preferences'),
            ),
            const SizedBox(height: 6),
            const DisclaimerFooter(),
          ],
        ),
      ),
    );
  }

  Widget _foodPicker() {
    final foods = ref.watch(p.dietFoodsProvider);
    return foods.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 8),
            Text(
              'Loading foods…',
              style: TextStyle(fontSize: 10.5, color: C.muted),
            ),
          ],
        ),
      ),
      error: (e, _) => Row(
        children: [
          Expanded(
            child: Text(
              'Could not load the food list: ${e is ApiException ? e.message : 'server error'}. You can still type foods below.',
              style: const TextStyle(fontSize: 10.5, color: C.muted),
            ),
          ),
          TextButton(
            onPressed: () => ref.invalidate(p.dietFoodsProvider),
            child: const Text('Retry'),
          ),
        ],
      ),
      data: (list) {
        if (list.isEmpty) {
          return const Text(
            'The server has no food list. Type foods below.',
            style: TextStyle(fontSize: 10.5, color: C.muted),
          );
        }
        final q = _query.trim().toLowerCase();
        final matches = list
            .where(
              (f) =>
                  q.isEmpty ||
                  f.name.toLowerCase().contains(q) ||
                  f.group.toLowerCase().contains(q),
            )
            .take(40)
            .toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _search,
              decoration: const InputDecoration(
                labelText: 'Search foods',
                prefixIcon: Icon(Icons.search_rounded, size: 18),
              ),
              onChanged: (v) => setState(() => _query = v),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final f in matches)
                  SelectChip(
                    f.name,
                    selected: _hasDislike(f.name),
                    onTap: () => _toggleDislike(f.name),
                  ),
              ],
            ),
            if (matches.isEmpty)
              const Text(
                'No food matches. Add it below.',
                style: TextStyle(fontSize: 10.5, color: C.muted),
              ),
          ],
        );
      },
    );
  }

  Widget _choiceChips(
    Map<String, String> options,
    String? value,
    ValueChanged<String> onPick,
  ) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final e in options.entries)
          SelectChip(
            e.value,
            selected: value == e.key,
            onTap: () => onPick(e.key),
          ),
      ],
    );
  }

  Widget _errorText(String t) => Padding(
    padding: const EdgeInsets.only(top: 4, left: 4),
    child: Text(
      t,
      style: TextStyle(
        fontSize: 11,
        color: Theme.of(context).colorScheme.error,
      ),
    ),
  );

  Widget _switchCard(
    String title,
    String? sub,
    bool on,
    ValueChanged<bool> onChanged,
  ) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 12.5,
                    ),
                  ),
                  if (sub != null)
                    Text(
                      sub,
                      style: const TextStyle(fontSize: 10.5, color: C.muted),
                    ),
                ],
              ),
            ),
            Toggle(on: on, onChanged: onChanged),
          ],
        ),
      ),
    );
  }
}
