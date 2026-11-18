import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../data/local_store.dart';
import '../models/diet_profile.dart';
import '../models/screening.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'diet_questionnaire_screen.dart';

/// ⑫ Diet plan — "Dietary Intelligence": goal, a one-day meal plan with
/// per-food iron (USDA FoodData Central values from the server), daily totals
/// vs target, AI cost estimates vs budget, dislike replacements, pair/avoid
/// cards, extra tips and the optional LLM "AI tips".
/// Every number shown comes from the server response; sections the server
/// did not fill are hidden.
class DietScreen extends ConsumerStatefulWidget {
  /// Fresh screening result (preferred source).
  final BatchScreening? result;

  /// Fallback: cached plan + severity from the last screening.
  final String? severityOverride;
  const DietScreen({super.key, this.result, this.severityOverride});

  /// Diet tab opened without a fresh screening: use the cached plan.
  const DietScreen.neutral({super.key})
    : result = null,
      severityOverride = null;

  @override
  ConsumerState<DietScreen> createState() => _DietScreenState();
}

class _DietScreenState extends ConsumerState<DietScreen> {
  bool _loadingTips = false;
  String? _tips;
  List<TipSource> _tipSources = const [];
  String? _tipsError;

  /// Plan from `POST /diet/plan` in this session (wins over the others).
  DietPlan? _aiPlan;
  bool _generating = false;
  String? _planError;

  DietPlan? get _plan {
    if (_aiPlan != null) return _aiPlan;
    if (widget.result != null) return widget.result!.dietPlan;
    final cached = LocalStore.cachedDietPlan;
    if (cached != null) return DietPlan.fromJson(cached);
    return null;
  }

  String get _severity =>
      widget.result?.aggregate.severityClass ??
      widget.severityOverride ??
      (LocalStore.history.isEmpty
          ? 'Normal'
          : LocalStore.history.first.severityClass);

  /// Grade + anemic flag for the plan request, from the fresh result or the
  /// latest saved screening. Null when the user has never been screened.
  ({String severity, bool anemic})? get _screening {
    final r = widget.result;
    if (r != null) {
      return (severity: r.aggregate.severityClass, anemic: r.aggregate.anemic);
    }
    final h = LocalStore.history;
    if (h.isEmpty) return null;
    return (severity: h.first.severityClass, anemic: h.first.anemic);
  }

  Future<void> _openQuestionnaire() async {
    await Navigator.of(
      context,
    ).push(MaterialPageRoute(builder: (_) => const DietQuestionnaireScreen()));
    if (mounted) setState(() {});
  }

  Future<void> _generatePlan() async {
    final s = _screening;
    final profile = ref.read(p.profileProvider);
    if (s == null || !profile.hasDietProfile) return;
    setState(() {
      _generating = true;
      _planError = null;
    });
    try {
      final plan = await ref
          .read(p.apiClientProvider)
          .dietPlan(profile: profile, severity: s.severity, anemic: s.anemic);
      if (!mounted) return;
      if (plan.meals.isEmpty && plan.goal.isEmpty && plan.sampleDay.isEmpty) {
        setState(
          () => _planError =
              'The server returned an empty plan. Please try again.',
        );
        return;
      }
      LocalStore.cachedDietPlan = plan.toJson();
      setState(() => _aiPlan = plan);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _planError = e.message);
    } catch (_) {
      if (!mounted) return;
      setState(
        () => _planError =
            'The diet plan could not be created. Please try again.',
      );
    } finally {
      if (mounted) setState(() => _generating = false);
    }
  }

  Future<void> _loadTips() async {
    if (widget.result == null) {
      setState(() {
        _tipsError =
            'AI tips need a screening result with a plan. Take a scan first.';
      });
      return;
    }
    setState(() {
      _loadingTips = true;
      _tipsError = null;
    });
    try {
      final a = widget.result!.aggregate;
      final res = await ref
          .read(p.apiClientProvider)
          .dietRecommendations(
            severity: a.severityClass,
            anemic: a.anemic,
            profile: ref.read(p.profileProvider),
          );
      if (!mounted) return;
      setState(() {
        _tips = res.text.isEmpty ? null : res.text;
        _tipSources = res.text.isEmpty ? const [] : res.sources;
        if (res.text.isEmpty) {
          _tipsError = 'The AI tips service returned nothing. The plan below still applies.';
        }
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _tips = null;
        _tipsError = 'AI tips unavailable: ${e.message}';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _tips = null;
        _tipsError = 'AI tips unavailable right now.';
      });
    } finally {
      if (mounted) setState(() => _loadingTips = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final plan = _plan;
    final severity = _severity;
    final dp = ref.watch(p.profileProvider).dietProfile;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Your diet plan'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 14),
            child: SeverityPill(severity),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
              children: [
                _personaliseCard(dp),
                const SizedBox(height: 10),
                if (plan == null)
                  const _NoPlanView()
                else
                  ..._planSections(plan, severity),
              ],
            ),
          ),
          const DisclaimerFooter(),
        ],
      ),
    );
  }

  /// Questionnaire status + "Generate my AI diet plan".
  Widget _personaliseCard(DietProfile? dp) {
    final screening = _screening;
    final canGenerate = dp != null && screening != null && !_generating;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.tune_rounded, size: 16, color: C.primary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    dp == null
                        ? 'Personalise my diet'
                        : 'Your diet preferences',
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 12.5,
                    ),
                  ),
                ),
                if (dp != null)
                  TextButton(
                    onPressed: _generating ? null : _openQuestionnaire,
                    child: const Text('Edit diet preferences'),
                  ),
              ],
            ),
            const SizedBox(height: 3),
            if (dp == null) ...[
              const Text(
                'Answer a few questions about your budget, region, kitchen and the foods you dislike to get an AI-planned diet that fits your life.',
                style: TextStyle(fontSize: 10.5, color: C.muted, height: 1.4),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                icon: const Icon(Icons.edit_note_rounded, size: 16),
                label: const Text('Personalise my diet'),
                onPressed: _openQuestionnaire,
              ),
            ] else
              Text(
                _summary(dp),
                style: const TextStyle(
                  fontSize: 10.5,
                  color: C.muted,
                  height: 1.4,
                ),
              ),
            const SizedBox(height: 8),
            FilledButton.icon(
              icon: const Icon(Icons.auto_awesome_rounded, size: 16),
              label: const Text('Generate my AI diet plan'),
              onPressed: canGenerate ? _generatePlan : null,
            ),
            if (dp == null)
              const Padding(
                padding: EdgeInsets.only(top: 5),
                child: Text(
                  'Fill in your diet preferences first.',
                  style: TextStyle(fontSize: 10, color: C.muted),
                ),
              )
            else if (screening == null)
              const Padding(
                padding: EdgeInsets.only(top: 5),
                child: Text(
                  'Take a screening first so the plan matches your result.',
                  style: TextStyle(fontSize: 10, color: C.muted),
                ),
              ),
            if (_generating && dp != null) ...[
              const SizedBox(height: 10),
              const LinearProgressIndicator(minHeight: 3),
              const SizedBox(height: 6),
              Text(
                'Planning meals for ${dp.state} within ${dp.budgetLabel}…',
                style: const TextStyle(fontSize: 10.5, color: C.muted),
              ),
            ],
            if (_planError != null && !_generating) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: C.severeBg,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        _planError!,
                        style: const TextStyle(
                          fontSize: 10.5,
                          color: C.severe,
                          height: 1.4,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: canGenerate ? _generatePlan : null,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _summary(DietProfile dp) {
    final parts = <String>[
      '${dp.budgetLabel}/day',
      dp.city.isEmpty ? dp.state : '${dp.city}, ${dp.state}',
      kAreaTypes[dp.areaType] ?? dp.areaType,
      kKitchenTypes[dp.kitchen] ?? dp.kitchen,
      if (dp.dislikes.isNotEmpty)
        '${dp.dislikes.length} dislike${dp.dislikes.length == 1 ? '' : 's'}',
    ];
    return parts.join(' · ');
  }

  List<Widget> _planSections(DietPlan plan, String severity) {
    return [
      // Who planned it
      if (plan.isAiPlanned || plan.isRulesPlanned) ...[
        _SourceBadge(plan),
        const SizedBox(height: 8),
      ],
      // Context chips
      Wrap(
        spacing: 6,
        children: [
          SelectChip(_dietLabel(plan.dietType), selected: true),
          SelectChip(severityDisplayLabel(severity), selected: true),
        ],
      ),
      const SizedBox(height: 8),
      if (plan.warnings.isNotEmpty) ...[
        _WarningsNote(plan.warnings),
        const SizedBox(height: 8),
      ],
      // Goal
      if (plan.goal.isNotEmpty) ...[
        Card(
          child: Padding(
            padding: const EdgeInsets.all(11),
            child: Text(
              plan.goal,
              style: const TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
                height: 1.4,
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
      ],
      // Real meal plan (new servers) or the sample day (older).
      if (plan.meals.isNotEmpty) ...[
        const SectionLabel('Your meal plan for one day'),
        const SizedBox(height: 5),
        for (final m in plan.meals) _MealCard(m),
        if (plan.daily != null) _DailySummary(plan.daily!, plan.costBasis),
        const SizedBox(height: 10),
      ] else if (plan.sampleDay.isNotEmpty) ...[
        SectionLabel('Sample day (${_dietLabel(plan.dietType)})'),
        const SizedBox(height: 5),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 2),
            child: Column(
              children: [
                for (final e in plan.sampleDay.entries)
                  MockListRow(
                    leading: SizedBox(
                      width: 62,
                      child: Text(
                        e.key,
                        style: const TextStyle(
                          fontSize: 10.5,
                          color: C.muted,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    title: Text(e.value),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
      ],
      if (plan.replacements.isNotEmpty) ...[
        _ReplacementsCard(plan.replacements),
        const SizedBox(height: 10),
      ],
      if (plan.ironRichFoods.isNotEmpty) ...[
        const SectionLabel('Iron-rich foods for you'),
        const SizedBox(height: 5),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 2),
            child: Column(
              children: [
                for (final f in plan.ironRichFoods)
                  MockListRow(
                    leading: const MiniAvatar(
                      Icons.emoji_food_beverage_rounded,
                      bg: Color(0xFFE6F2E2),
                      fg: C.ok,
                    ),
                    title: Text(f),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
      ],
      // Pair with / avoid
      if (plan.pairWithVitaminC.isNotEmpty || plan.avoidOrLimit.isNotEmpty)
        Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (plan.pairWithVitaminC.isNotEmpty)
              Expanded(
                child: _listCard(
                  title: '✓ Pair with',
                  items: plan.pairWithVitaminC,
                  bg: const Color(0xFFEEF7EC),
                  border: const Color(0xFFCFE6CA),
                  fg: C.ok,
                ),
              ),
            if (plan.pairWithVitaminC.isNotEmpty &&
                plan.avoidOrLimit.isNotEmpty)
              const SizedBox(width: 7),
            if (plan.avoidOrLimit.isNotEmpty)
              Expanded(
                child: _listCard(
                  title: '✕ Avoid with meals',
                  items: plan.avoidOrLimit,
                  bg: const Color(0xFFFDECEC),
                  border: const Color(0xFFF3CACA),
                  fg: C.severe,
                ),
              ),
          ],
        ),
      if (plan.extraTips.isNotEmpty) ...[
        const SizedBox(height: 10),
        const SectionLabel('Tips for you'),
        const SizedBox(height: 5),
        Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 4),
            child: Column(
              children: [
                for (final t in plan.extraTips)
                  MockListRow(
                    leading: const MiniAvatar(
                      Icons.lightbulb_outline_rounded,
                      size: 22,
                    ),
                    title: Text(t),
                  ),
              ],
            ),
          ),
        ),
      ],
      const SizedBox(height: 10),
      // Clinician guidance
      if (plan.whenToSeeClinician.isNotEmpty ||
          plan.recoveryOutlook.isNotEmpty) ...[
        Card(
          child: Padding(
            padding: const EdgeInsets.all(11),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionLabel('When to see a clinician'),
                const SizedBox(height: 5),
                if (plan.whenToSeeClinician.isNotEmpty)
                  Text(
                    plan.whenToSeeClinician,
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: C.muted,
                      height: 1.4,
                    ),
                  ),
                if (plan.whenToSeeClinician.isNotEmpty &&
                    plan.recoveryOutlook.isNotEmpty)
                  const SizedBox(height: 6),
                if (plan.recoveryOutlook.isNotEmpty)
                  Text(
                    plan.recoveryOutlook,
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: C.muted,
                      height: 1.4,
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
      ],
      if (widget.result != null) ...[
        OutlinedButton.icon(
          icon: _loadingTips
              ? const SizedBox(
                  width: 15,
                  height: 15,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.lightbulb_outline_rounded, size: 15),
          label: Text(_tips == null ? 'Get AI tips' : 'Refresh AI tips'),
          onPressed: _loadingTips ? null : _loadTips,
        ),
        if (_tipsError != null) ...[
          const SizedBox(height: 6),
          Text(
            _tipsError!,
            style: const TextStyle(fontSize: 10, color: C.muted),
          ),
        ],
        if (_tips != null) ...[
          const SizedBox(height: 10),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(11),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(
                        Icons.auto_awesome_rounded,
                        size: 14,
                        color: C.primary,
                      ),
                      SizedBox(width: 6),
                      Text(
                        'AI dietary tips',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 12.5,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  SelectableText(
                    _tips!,
                    style: const TextStyle(fontSize: 10.5, height: 1.45),
                  ),
                  if (_tipSources.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    const Divider(height: 1),
                    const SizedBox(height: 8),
                    const Row(
                      children: [
                        Icon(Icons.menu_book_rounded, size: 13, color: C.muted),
                        SizedBox(width: 6),
                        Text(
                          'Sources',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 11,
                            color: C.muted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    for (final s in _tipSources)
                      Padding(
                        padding: const EdgeInsets.only(top: 3),
                        child: Text(
                          '[${s.ref}] ${s.source}${s.page != null ? ', p. ${s.page}' : ''}',
                          style: const TextStyle(
                            fontSize: 9.5,
                            color: C.muted,
                            height: 1.35,
                          ),
                        ),
                      ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ],
      if (plan.dataSource.isNotEmpty)
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 8, 4, 0),
          child: Text(
            'Nutrient data: ${plan.dataSource}',
            style: const TextStyle(fontSize: 9.5, color: C.muted),
          ),
        ),
      const SizedBox(height: 6),
    ];
  }

  Widget _listCard({
    required String title,
    required List<String> items,
    required Color bg,
    required Color border,
    required Color fg,
  }) {
    return Card(
      color: bg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(9),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 11,
                color: fg,
              ),
            ),
            const SizedBox(height: 3),
            for (final f in items)
              Text('· $f', style: const TextStyle(fontSize: 10, height: 1.35)),
          ],
        ),
      ),
    );
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
}

/// mg with sensible precision: 0.35 mg, 3.2 mg, 18.0 mg.
String _mg(double v) => v < 1 ? v.toStringAsFixed(2) : v.toStringAsFixed(1);

/// AI-estimated rupee amount, e.g. "≈ ₹45 (AI estimate)".
String costEstimateLabel(double v) =>
    '≈ ₹${formatInr(v.roundToDouble())} (AI estimate)';

/// "1 serving", "1.5 servings".
String _servings(double v) {
  final n = v == v.roundToDouble()
      ? v.round().toString()
      : v.toStringAsFixed(1);
  return '$n serving${v == 1 ? '' : 's'}';
}

/// "AI-planned · nutrients from USDA data" or "Data-driven plan (AI unavailable)".
class _SourceBadge extends StatelessWidget {
  final DietPlan plan;
  const _SourceBadge(this.plan);

  @override
  Widget build(BuildContext context) {
    final ai = plan.isAiPlanned;
    final fg = ai ? C.primaryDark : C.muted;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
          color: ai ? C.container : const Color(0xFFF1E6EA),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              ai ? Icons.auto_awesome_rounded : Icons.rule_rounded,
              size: 13,
              color: fg,
            ),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                ai
                    ? 'AI-planned · nutrients from USDA data'
                    : 'Data-driven plan (AI unavailable)',
                style: TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w700,
                  color: fg,
                ),
              ),
            ),
            if (ai && plan.aiModel != null) ...[
              const SizedBox(width: 6),
              Text(
                plan.aiModel!,
                style: const TextStyle(fontSize: 9, color: C.muted),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Server warnings as a small amber note.
class _WarningsNote extends StatelessWidget {
  final List<String> warnings;
  const _WarningsNote(this.warnings);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(9),
      decoration: BoxDecoration(
        color: C.mildBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFF0D68A)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline_rounded, size: 14, color: C.mildDark),
          const SizedBox(width: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final w in warnings)
                  Text(
                    w,
                    style: const TextStyle(
                      fontSize: 10,
                      color: C.mildDark,
                      height: 1.4,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// "Your dislikes → replacements".
class _ReplacementsCard extends StatelessWidget {
  final List<DietReplacement> items;
  const _ReplacementsCard(this.items);

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SectionLabel('Your dislikes → replacements'),
            const SizedBox(height: 6),
            for (final r in items)
              Padding(
                padding: const EdgeInsets.only(bottom: 7),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${r.disliked} → ${r.replacement}',
                      style: const TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (r.reason.isNotEmpty)
                      Text(
                        r.reason,
                        style: const TextStyle(
                          fontSize: 10,
                          color: C.muted,
                          height: 1.4,
                        ),
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

/// One meal from `diet_plan.meals`: time, dish, each food with portion,
/// servings, iron and absorbable iron (all values from the server), the
/// AI cost estimate and the meal's note.
class _MealCard extends StatelessWidget {
  final Meal meal;
  const _MealCard(this.meal);

  @override
  Widget build(BuildContext context) {
    final totals = <String>[
      if (meal.ironMg != null) 'Iron ${_mg(meal.ironMg!)} mg',
      if (meal.absorbableIronMg != null)
        'absorbable ${_mg(meal.absorbableIronMg!)} mg',
    ];
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(11, 9, 11, 9),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (meal.time.isNotEmpty)
                        Text(
                          meal.time,
                          style: const TextStyle(
                            fontSize: 9.5,
                            color: C.muted,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      Text(
                        meal.meal.isEmpty ? 'Meal' : meal.meal,
                        style: const TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
                if (totals.isNotEmpty)
                  Flexible(
                    child: Text(
                      totals.join(' · '),
                      textAlign: TextAlign.right,
                      style: const TextStyle(
                        fontSize: 10,
                        color: C.primaryDark,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
              ],
            ),
            if (meal.dish.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                meal.dish,
                style: const TextStyle(
                  fontSize: 11.5,
                  fontStyle: FontStyle.italic,
                  color: C.text,
                ),
              ),
            ],
            const SizedBox(height: 4),
            for (final it in meal.items) _itemRow(it),
            if (meal.estCostInr != null) ...[
              const SizedBox(height: 6),
              Text(
                costEstimateLabel(meal.estCostInr!),
                style: const TextStyle(
                  fontSize: 10.5,
                  color: C.primaryDark,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            if (meal.note.isNotEmpty) ...[
              const SizedBox(height: 6),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.lightbulb_outline_rounded,
                    size: 13,
                    color: C.muted,
                  ),
                  const SizedBox(width: 5),
                  Expanded(
                    child: Text(
                      meal.note,
                      style: const TextStyle(
                        fontSize: 10,
                        color: C.muted,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _itemRow(MealItem it) {
    final facts = <String>[
      if (it.servings != null && it.servings! > 0) _servings(it.servings!),
      if (it.grams != null) '${it.grams!.round()} g',
      if (it.ironMg != null) 'iron ${_mg(it.ironMg!)} mg',
      if (it.absorbableIronMg != null)
        'absorbable ${_mg(it.absorbableIronMg!)} mg',
      if (it.vitaminCMg != null && it.vitaminCMg! >= 1)
        'vit C ${it.vitaminCMg!.round()} mg',
    ];
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 5),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFF1E7EA))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Flexible(
                child: Text(
                  it.food,
                  style: const TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              if (it.heme) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 5,
                    vertical: 1,
                  ),
                  decoration: BoxDecoration(
                    color: C.container,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    'heme',
                    style: TextStyle(
                      fontSize: 9,
                      color: C.primaryDark,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ],
          ),
          if (facts.isNotEmpty)
            Text(
              facts.join(' · '),
              style: const TextStyle(fontSize: 10, color: C.muted),
            ),
        ],
      ),
    );
  }
}

/// Daily totals vs targets from `diet_plan.daily`, plus the AI cost
/// estimate vs budget (only when both are present).
class _DailySummary extends StatelessWidget {
  final DailyIron daily;
  final String? costBasis;
  const _DailySummary(this.daily, this.costBasis);

  @override
  Widget build(BuildContext context) {
    final cost = daily.estCostInr;
    final budget = daily.budgetInr;
    final hasCost = cost != null && budget != null && budget > 0;
    final rows = <Widget>[
      if (daily.ironMg != null)
        _row('Total iron', daily.ironMg!, daily.targetIronMg),
      if (daily.absorbableIronMg != null)
        _row(
          'Absorbable iron',
          daily.absorbableIronMg!,
          daily.absorbedTargetMg,
        ),
      if (hasCost) _costRow(cost, budget),
    ];
    if (rows.isEmpty && daily.targetBasis.isEmpty) return const SizedBox();
    return Card(
      color: C.container,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFF2C6D2)),
      ),
      margin: const EdgeInsets.only(bottom: 4),
      child: Padding(
        padding: const EdgeInsets.all(11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SectionLabel('Daily total'),
            const SizedBox(height: 7),
            ...rows,
            if (daily.targetBasis.isNotEmpty)
              Text(
                daily.targetBasis,
                style: const TextStyle(
                  fontSize: 9.5,
                  color: C.muted,
                  height: 1.4,
                ),
              ),
            if (hasCost && costBasis != null) ...[
              const SizedBox(height: 4),
              Text(
                costBasis!,
                style: const TextStyle(
                  fontSize: 9,
                  color: C.muted,
                  height: 1.4,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _costRow(double cost, double budget) {
    final within = cost <= budget;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Est. cost (AI estimate)',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                '≈ ₹${formatInr(cost.roundToDouble())} of ₹${formatInr(budget)} budget',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: within ? C.ok : C.severe,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          HBar(cost / budget, color: within ? C.ok : C.severe, height: 7),
        ],
      ),
    );
  }

  Widget _row(String label, double value, double? target) {
    final hasTarget = target != null && target > 0;
    final share = hasTarget ? value / target : 0.0;
    final met = hasTarget && value >= target;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                hasTarget
                    ? '${_mg(value)} of ${_mg(target)} mg'
                    : '${_mg(value)} mg',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: met ? C.ok : C.primaryDark,
                ),
              ),
            ],
          ),
          if (hasTarget) ...[
            const SizedBox(height: 4),
            HBar(share, color: met ? C.ok : C.primary, height: 7),
          ],
        ],
      ),
    );
  }
}

class _NoPlanView extends StatelessWidget {
  const _NoPlanView();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.fromLTRB(24, 24, 24, 24),
      child: Column(
        children: [
          Icon(
            Icons.restaurant_menu_rounded,
            size: 56,
            color: Color(0xFFDCCBD1),
          ),
          SizedBox(height: 12),
          Text(
            'No diet plan yet',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          ),
          SizedBox(height: 4),
          Text(
            'Take a screening and your personalised iron-aware plan will appear here.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11, color: C.muted, height: 1.4),
          ),
        ],
      ),
    );
  }
}
