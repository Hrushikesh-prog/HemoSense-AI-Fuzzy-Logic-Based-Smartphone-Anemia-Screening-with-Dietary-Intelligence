import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/local_store.dart';
import '../models/screening.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'why_result_screen.dart';
import 'diet_questionnaire_screen.dart';
import 'diet_screen.dart';
import 'capture_guide_screen.dart';

/// ⑩ Result — 3-zone gauge with the grade and the ANFIS anemia risk score,
/// confidence, verdict, "What this means" card, doctor banner for
/// moderate-to-severe or red-flag symptoms. Never an Hb value.
class ResultScreen extends ConsumerStatefulWidget {
  final BatchScreening result;
  const ResultScreen({super.key, required this.result});

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _saveToHistory();
      _offerDietQuestionnaire();
    });
  }

  /// Offered once, after the first result, when the diet questionnaire has
  /// not been filled in yet.
  Future<void> _offerDietQuestionnaire() async {
    if (!mounted) return;
    if (ref.read(p.profileProvider).hasDietProfile) return;
    if (LocalStore.dietQuestionnaireOffered) return;
    LocalStore.dietQuestionnaireOffered = true;
    final go = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Personalise your diet plan?'),
        content: const Text(
            'Answer a few quick questions about your budget, region, kitchen and foods you dislike, and the AI planner will build meals that fit your life.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Not now')),
          FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Personalise')),
        ],
      ),
    );
    if (go == true && mounted) {
      await Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => const DietQuestionnaireScreen()));
    }
  }

  void _saveToHistory() {
    if (_saved) return;
    final a = widget.result.aggregate;
    ref.read(p.historyProvider.notifier).add(HistoryEntry(
          time: DateTime.now(),
          severityClass: a.severityClass,
          anemic: a.anemic,
          confidence: a.confidence,
          agreement: a.agreement,
          headline: a.verdict.headline,
          severityLabel: a.severityLabel,
          pAnemic: a.pAnemic,
        ));
    // Cache the diet plan so the Diet tab works without re-screening.
    LocalStore.cachedDietPlan = widget.result.dietPlan.toJson();
    _saved = true;
  }

  String _meaning(Aggregate a) {
    if (a.verdict.status == 'inconclusive') {
      return 'The photos disagree, so this result is uncertain. Retake the photos in bright, even light, or get a blood (CBC) test.';
    }
    switch (a.severityLevel) {
      case 0:
        return 'Your eyelid colour shows no visible pallor. Keep eating an iron-rich diet and rescreen if symptoms appear.';
      case 1:
        return 'Your eyelid colour suggests mild pallor. Improve iron intake and get a blood (CBC) test within 2–4 weeks to confirm.';
      default:
        return 'Your eyelid colour suggests moderate-to-severe pallor. See a doctor soon (within a week, sooner if you feel unwell) for a blood test — iron treatment is often needed along with diet.';
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.result;
    final a = r.aggregate;
    final redFlag = r.symptoms.urgent || r.symptoms.redFlags.isNotEmpty;
    final urgent = redFlag || a.needsDoctor;
    final skipped = r.skippedNote;

    return Scaffold(
      appBar: AppBar(title: const Text('Your result')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
              children: [
                // Gauge card
                Card(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(10, 10, 10, 14),
                    child: Column(
                      children: [
                        RiskGauge(
                          severity: a.severityClass,
                          riskScore: a.pAnemic,
                          label: a.severityLabel,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          a.verdict.headline.isEmpty
                              ? (a.anemic ? 'Possible anemia' : 'No sign of anemia')
                              : a.verdict.headline,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w700),
                        ),
                        if (a.verdict.summary.isNotEmpty) ...[
                          const SizedBox(height: 3),
                          Text(
                            a.verdict.summary,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 10.5, color: C.muted, height: 1.4),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // Votes + confidence card
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Photos analysed',
                                style: TextStyle(fontSize: 10, color: C.muted)),
                            Text('${a.nUsed}',
                                style: const TextStyle(
                                    fontSize: 15, fontWeight: FontWeight.w800)),
                          ],
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Anemia votes',
                                style: TextStyle(fontSize: 10, color: C.muted)),
                            Text('${a.anemicVotes} of ${a.nUsed}',
                                style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w800,
                                    color: C.severityColor(a.severityClass))),
                          ],
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            const Text('Confidence',
                                style: TextStyle(fontSize: 10, color: C.muted)),
                            Text(a.confidence,
                                style: const TextStyle(
                                    fontSize: 15, fontWeight: FontWeight.w800)),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                if (a.confidenceDetail?.testingSentence != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.verified_outlined,
                            size: 14, color: C.muted),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(a.confidenceDetail!.testingSentence!,
                              style: const TextStyle(
                                  fontSize: 10.5, color: C.muted, height: 1.35)),
                        ),
                      ],
                    ),
                  ),
                if (skipped != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.info_outline_rounded,
                            size: 14, color: C.muted),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(skipped,
                              style: const TextStyle(
                                  fontSize: 10.5, color: C.muted, height: 1.35)),
                        ),
                      ],
                    ),
                  ),
                // What this means
                Card(
                  color: C.severityBg(a.severityClass),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('What this means',
                            style: TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 12.5,
                                color: C.severityColor(a.severityClass))),
                        const SizedBox(height: 2),
                        Text(_meaning(a),
                            style: const TextStyle(
                                fontSize: 10.5, color: C.muted, height: 1.4)),
                      ],
                    ),
                  ),
                ),
                if (urgent) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(11),
                    decoration: BoxDecoration(
                      color: C.severeBg,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: const Color(0xFFF2C4C4)),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.local_hospital_rounded,
                            color: C.severe, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            redFlag
                                ? 'See a doctor promptly — you reported warning symptoms (such as chest pain, fainting or breathlessness at rest).'
                                : 'See a doctor — the result suggests moderate-to-severe anemia. Confirm with a blood test (CBC).',
                            style: const TextStyle(
                                fontSize: 10.5,
                                color: C.severe,
                                fontWeight: FontWeight.w700),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 8),
                if (r.symptoms.note.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: Text(r.symptoms.note,
                        style: const TextStyle(
                            fontSize: 10, color: C.muted, height: 1.4)),
                  ),
                const SizedBox(height: 10),
                FilledButton.icon(
                  icon: const Icon(Icons.restaurant_rounded, size: 15),
                  label: const Text('View my diet plan'),
                  onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                          builder: (_) => DietScreen(result: r))),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) =>
                                    WhyResultScreen(result: r))),
                        style: OutlinedButton.styleFrom(
                            minimumSize: const Size.fromHeight(38),
                            textStyle: const TextStyle(fontSize: 11)),
                        child: const Text('Why this result?'),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.of(context)
                            .pushAndRemoveUntil(
                                MaterialPageRoute(
                                    builder: (_) =>
                                        const CaptureGuideScreen()),
                                (route) => route.isFirst),
                        style: OutlinedButton.styleFrom(
                            minimumSize: const Size.fromHeight(38),
                            textStyle: const TextStyle(fontSize: 11)),
                        child: const Text('New screening'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          DisclaimerFooter(),
        ],
      ),
    );
  }
}
