import 'package:flutter/material.dart';

import '../models/screening.dart';
import '../theme.dart';
import '../widgets/ui.dart';

/// ⑪ Why this result? — what the ANFIS fuzzy model looked at for the first
/// valid photo: the detected inner eyelid, the three input colour features
/// with their Low / Medium / High memberships, and the top fuzzy rules.
/// All values come from the backend JSON. Never an Hb value.
class WhyResultScreen extends StatelessWidget {
  final BatchScreening result;
  const WhyResultScreen({super.key, required this.result});

  static const _termColors = {
    'Low': C.mild,
    'Medium': C.primary,
    'High': C.ok,
  };

  @override
  Widget build(BuildContext context) {
    final a = result.aggregate;
    final valid = result.validImages;
    final first = valid.isEmpty ? null : valid.first;
    final thumb = decodeDataUrl(first?.roiThumbnail);
    final exp = first?.explanation ?? const AnfisExplanation();
    final anemiaShare = a.nUsed == 0 ? 0.0 : a.anemicVotes / a.nUsed;

    return Scaffold(
      appBar: AppBar(title: const Text('Why this result?')),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 12),
              children: [
                const Padding(
                  padding: EdgeInsets.fromLTRB(4, 0, 4, 8),
                  child: Text(
                    'The model is an ANFIS fuzzy system; it screens, it does not diagnose.',
                    style: TextStyle(fontSize: 11, color: C.muted, height: 1.4),
                  ),
                ),
                // 1 · Detected inner eyelid
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SectionLabel(valid.length > 1
                            ? '1 · Detected inner eyelid (photo ${first!.index + 1})'
                            : '1 · Detected inner eyelid'),
                        const SizedBox(height: 8),
                        if (thumb != null)
                          Center(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(10),
                              child: ConstrainedBox(
                                constraints: const BoxConstraints(maxHeight: 220),
                                child: Image.memory(thumb,
                                    fit: BoxFit.contain,
                                    errorBuilder: (_, _, _) => const Text(
                                        'Preview unavailable.',
                                        style: TextStyle(
                                            fontSize: 10.5, color: C.muted))),
                              ),
                            ),
                          )
                        else
                          const Text('Preview unavailable for this scan.',
                              style: TextStyle(fontSize: 10.5, color: C.muted)),
                        const SizedBox(height: 6),
                        const Text(
                          'The green tint marks the pink inner-eyelid pixels the model analysed. If it covers skin or the eye itself, retake and move the box.',
                          style: TextStyle(fontSize: 10, color: C.muted, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // 2 · Fuzzy inputs
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SectionLabel('2 · Colour features (fuzzy inputs)'),
                        const SizedBox(height: 8),
                        if (exp.inputs.isEmpty)
                          const Text('Feature values unavailable for this scan.',
                              style: TextStyle(fontSize: 10.5, color: C.muted))
                        else
                          for (final f in exp.inputs)
                            _featureBlock(f, exp.memberships[f] ?? const {},
                                first?.features[f]),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // 3 · Top rules
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(11),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SectionLabel('3 · Fuzzy rules that fired most'),
                        const SizedBox(height: 8),
                        if (exp.topRules.isEmpty)
                          const Text('Rule details unavailable for this scan.',
                              style: TextStyle(fontSize: 10.5, color: C.muted))
                        else
                          for (final (i, rule) in exp.topRules.take(3).indexed)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 7),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('${i + 1}.',
                                      style: const TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700)),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(rule.sentence,
                                        style: const TextStyle(
                                            fontSize: 11, height: 1.35)),
                                  ),
                                ],
                              ),
                            ),
                        const SizedBox(height: 2),
                        const Text(
                          'Weight = how strongly the rule matched this photo. Risk = the rule\'s anemia risk. The final score blends all rules by weight.',
                          style: TextStyle(fontSize: 9.5, color: C.muted, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // 4 · Photo agreement
                if (a.nUsed > 1) ...[
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(11),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SectionLabel('4 · Photo agreement'),
                          const SizedBox(height: 8),
                          _barRow('Normal', '${a.nUsed - a.anemicVotes}',
                              1 - anemiaShare, C.ok),
                          _barRow('Anemia', '${a.anemicVotes}', anemiaShare,
                              C.moderate),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                // Symptoms
                if (result.symptoms.note.isNotEmpty ||
                    result.symptoms.redFlags.isNotEmpty)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(11),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SectionLabel('Your symptoms'),
                          const SizedBox(height: 6),
                          if (result.symptoms.note.isNotEmpty)
                            Text(result.symptoms.note,
                                style: const TextStyle(
                                    fontSize: 10.5, color: C.muted, height: 1.45)),
                          if (result.symptoms.redFlags.isNotEmpty) ...[
                            const SizedBox(height: 6),
                            const Text(
                              'Red-flag symptoms reported — see a doctor promptly.',
                              style: TextStyle(
                                  fontSize: 10.5,
                                  color: C.severe,
                                  fontWeight: FontWeight.w700),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 8),
                // Summary
                Card(
                  color: C.container,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                      side: const BorderSide(color: Color(0xFFF2C6D2))),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                              '${a.severityLabel} · Anemia risk score ${a.riskPercent}%',
                              style: TextStyle(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.w800,
                                  color: C.severityColor(a.severityClass))),
                        ),
                        Text('${a.confidence} confidence',
                            style: const TextStyle(fontSize: 11, color: C.muted)),
                      ],
                    ),
                  ),
                ),
                if (a.confidenceDetail != null &&
                    (a.confidenceDetail!.basis.isNotEmpty ||
                        a.confidenceDetail!.testingSentence != null)) ...[
                  const SizedBox(height: 8),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(11),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SectionLabel('How sure is this result?'),
                          const SizedBox(height: 6),
                          if (a.confidenceDetail!.basis.isNotEmpty)
                            Text(a.confidenceDetail!.basis,
                                style: const TextStyle(
                                    fontSize: 10.5, height: 1.45)),
                          if (a.confidenceDetail!.testingSentence != null) ...[
                            const SizedBox(height: 4),
                            Text(a.confidenceDetail!.testingSentence!,
                                style: const TextStyle(
                                    fontSize: 10.5,
                                    color: C.muted,
                                    height: 1.45)),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
                if (result.model != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8, left: 4),
                    child: Text('Model: ${result.model}',
                        style: const TextStyle(fontSize: 9.5, color: C.muted)),
                  ),
              ],
            ),
          ),
          DisclaimerFooter(),
        ],
      ),
    );
  }

  Widget _featureBlock(String f, Map<String, double> mem, double? value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(featureNames[f] ?? f,
                    style: const TextStyle(
                        fontSize: 11.5, fontWeight: FontWeight.w700)),
              ),
              if (value != null)
                Text('value ${value.toStringAsFixed(3)}',
                    style: const TextStyle(fontSize: 9.5, color: C.muted)),
            ],
          ),
          const SizedBox(height: 4),
          for (final term in const ['Low', 'Medium', 'High'])
            _barRow(term, '${((mem[term] ?? 0) * 100).round()}%',
                (mem[term] ?? 0).clamp(0.0, 1.0).toDouble(),
                _termColors[term]!),
        ],
      ),
    );
  }

  Widget _barRow(String label, String value, double share, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Row(
        children: [
          SizedBox(
              width: 52,
              child: Text(label, style: const TextStyle(fontSize: 10.5))),
          const SizedBox(width: 6),
          Expanded(child: HBar(share, color: color)),
          const SizedBox(width: 6),
          SizedBox(
              width: 40,
              child: Text(value,
                  textAlign: TextAlign.right,
                  style: const TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w700))),
        ],
      ),
    );
  }
}
