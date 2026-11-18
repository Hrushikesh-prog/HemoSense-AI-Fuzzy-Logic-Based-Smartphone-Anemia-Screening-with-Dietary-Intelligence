/// Response models for the HemoSense API (`POST /screen/batch` and friends).
///
/// NOTE: the app deliberately never displays an exact hemoglobin value.
/// The ANFIS fuzzy model returns a calibrated anemia risk score and a grade
/// (Normal / Mild / Moderate-to-Severe); the app shows those, the confidence
/// and a screening disclaimer only. `predicted_hb_gdl` is never parsed.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../theme.dart';

// ---------------------------------------------------------------------------
// Tolerant JSON helpers: a missing or oddly-typed field never crashes parsing.
// ---------------------------------------------------------------------------
String? _str(Object? v) => v is String ? v : null;
double? _dbl(Object? v) => v is num ? v.toDouble() : null;
int? _int(Object? v) => v is num ? v.toInt() : null;
bool? _bool(Object? v) => v is bool ? v : null;
Map<String, dynamic> _map(Object? v) =>
    v is Map ? v.map((k, val) => MapEntry(k.toString(), val)) : const {};
List<dynamic> _list(Object? v) => v is List ? v : const [];

/// Display text for a severity class. The model grades Normal / Mild /
/// Moderate, where "Moderate" means moderate-to-severe. Older history entries
/// may still say "Severe"; they are shown the same way.
String severityDisplayLabel(String severityClass) {
  switch (severityClass) {
    case 'Moderate':
    case 'Severe':
    case 'Moderate-to-Severe':
      return 'Moderate-to-Severe';
    default:
      return severityClass;
  }
}

/// 0 = Normal, 1 = Mild, 2 = Moderate-to-Severe.
int severityLevelOf(String severityClass) {
  switch (severityClass) {
    case 'Mild':
      return 1;
    case 'Moderate':
    case 'Severe':
    case 'Moderate-to-Severe':
      return 2;
    default:
      return 0;
  }
}

/// Plain-English names of the ANFIS colour features.
const featureNames = <String, String>{
  'ei': 'Redness (erythema index)',
  'a': 'Red-green balance (CIELAB a*)',
  'hhr': 'Share of strongly red pixels',
  'sat': 'Colour saturation',
};

/// Short names used inside rule sentences.
const featureShortNames = <String, String>{
  'ei': 'Redness',
  'a': 'Red-green balance',
  'hhr': 'Share of red pixels',
  'sat': 'Saturation',
};

/// Decodes a `data:image/png;base64,...` URL; null when malformed.
Uint8List? decodeDataUrl(String? dataUrl) {
  if (dataUrl == null || dataUrl.isEmpty) return null;
  try {
    if (dataUrl.startsWith('data:')) {
      return UriData.parse(dataUrl).contentAsBytes();
    }
    return base64Decode(dataUrl);
  } catch (_) {
    return null;
  }
}

class SymptomItem {
  final String id;
  final String label;
  final bool redFlag;

  const SymptomItem({required this.id, required this.label, required this.redFlag});

  factory SymptomItem.fromJson(Map<String, dynamic> j) => SymptomItem(
        id: _str(j['id']) ?? '',
        label: _str(j['label']) ?? '',
        redFlag: _bool(j['red_flag']) ?? false,
      );
}

class RoiInfo {
  final List<double> box; // [x, y, w, h] fractions
  final int? conjunctivaPixels;
  const RoiInfo({this.box = const [], this.conjunctivaPixels});

  factory RoiInfo.fromJson(Map<String, dynamic> j) => RoiInfo(
        box: _list(j['box']).whereType<num>().map((e) => e.toDouble()).toList(),
        conjunctivaPixels: _int(j['conjunctiva_pixels']),
      );
}

class FuzzyRule {
  final Map<String, String> antecedents; // feature -> Low | Medium | High
  final double weight;
  final double risk;
  const FuzzyRule({required this.antecedents, required this.weight, required this.risk});

  factory FuzzyRule.fromJson(Map<String, dynamic> j) => FuzzyRule(
        antecedents: _map(j['if']).map((k, v) => MapEntry(k, v.toString())),
        weight: _dbl(j['weight']) ?? 0,
        risk: _dbl(j['risk']) ?? 0,
      );

  /// "IF Redness is Low AND Share of red pixels is Low THEN risk 82% (weight 0.61)"
  String get sentence {
    final parts = antecedents.entries
        .map((e) => '${featureShortNames[e.key] ?? e.key} is ${e.value}')
        .join(' AND ');
    return 'IF $parts THEN risk ${(risk * 100).round()}% '
        '(weight ${weight.toStringAsFixed(2)})';
  }
}

class AnfisExplanation {
  final List<String> inputs;
  final Map<String, Map<String, double>> memberships; // feature -> term -> degree
  final List<FuzzyRule> topRules;

  const AnfisExplanation({
    this.inputs = const [],
    this.memberships = const {},
    this.topRules = const [],
  });

  factory AnfisExplanation.fromJson(Map<String, dynamic> j) {
    final mem = <String, Map<String, double>>{};
    _map(j['memberships']).forEach((f, terms) {
      mem[f] = _map(terms).map((t, v) => MapEntry(t, _dbl(v) ?? 0));
    });
    final inputs = _list(j['inputs']).whereType<String>().toList();
    return AnfisExplanation(
      inputs: inputs.isEmpty ? mem.keys.toList() : inputs,
      memberships: mem,
      topRules: _list(j['top_rules'])
          .whereType<Map>()
          .map((r) => FuzzyRule.fromJson(_map(r)))
          .toList(),
    );
  }

  bool get isEmpty => inputs.isEmpty && topRules.isEmpty;
}

class PerImage {
  final int index;
  final String? filename;
  final double? pAnemic;
  final String? severityClass;
  final String? severityLabel;
  final bool? anemic;
  final Map<String, double> features; // ei, a, hhr, sat
  final AnfisExplanation explanation;
  final Map<String, double> quality; // brightness, clipped_fraction, sharpness
  final RoiInfo? roi;
  final String? roiThumbnail; // PNG data-URL
  final String? error;
  final String? errorCode; // too_dark | overexposed | blurry | no_conjunctiva | bad_image

  const PerImage({
    required this.index,
    this.filename,
    this.pAnemic,
    this.severityClass,
    this.severityLabel,
    this.anemic,
    this.features = const {},
    this.explanation = const AnfisExplanation(),
    this.quality = const {},
    this.roi,
    this.roiThumbnail,
    this.error,
    this.errorCode,
  });

  bool get ok => error == null;

  factory PerImage.fromJson(Map<String, dynamic> j) {
    Map<String, double> numMap(Object? v) {
      final out = <String, double>{};
      _map(v).forEach((k, val) {
        final d = _dbl(val);
        if (d != null) out[k] = d;
      });
      return out;
    }

    final err = j['error'];
    return PerImage(
      index: _int(j['index']) ?? 0,
      filename: _str(j['filename']),
      pAnemic: _dbl(j['p_anemic']),
      severityClass: _str(j['severity_class']),
      severityLabel: _str(j['severity_label']),
      anemic: _bool(j['anemic']),
      features: numMap(j['features']),
      explanation: AnfisExplanation.fromJson(_map(j['explanation'])),
      quality: numMap(j['quality']),
      roi: j['roi'] is Map ? RoiInfo.fromJson(_map(j['roi'])) : null,
      roiThumbnail: _str(j['roi_thumbnail']),
      error: err?.toString(),
      errorCode: _str(j['error_code']),
    );
  }
}

class Verdict {
  final String status; // normal | anemic | inconclusive
  final String headline;
  final String summary;
  const Verdict({required this.status, required this.headline, required this.summary});

  factory Verdict.fromJson(Map<String, dynamic> j) => Verdict(
        status: _str(j['status']) ?? 'inconclusive',
        headline: _str(j['headline']) ?? '',
        summary: _str(j['summary']) ?? '',
      );
}

/// How sure the model is, and how often it was right in cross-validation for
/// results this clear (`aggregate.confidence_detail`).
class ConfidenceDetail {
  final double? certainty; // 0..1
  final double? cvAccuracy; // 0..1, null when not available
  final int? cvN;
  final String basis;

  const ConfidenceDetail({this.certainty, this.cvAccuracy, this.cvN, this.basis = ''});

  /// Null when the field is missing or not an object.
  static ConfidenceDetail? tryParse(Object? v) {
    if (v is! Map) return null;
    final j = _map(v);
    double? frac(Object? x) {
      final d = _dbl(x);
      return (d == null || d.isNaN) ? null : d.clamp(0.0, 1.0).toDouble();
    }

    final cvN = _int(j['cv_n']);
    return ConfidenceDetail(
      certainty: frac(j['certainty']),
      cvAccuracy: frac(j['cv_accuracy']),
      cvN: (cvN != null && cvN > 0) ? cvN : null,
      basis: (_str(j['basis']) ?? '').trim(),
    );
  }

  /// "In testing, the model was right for 92% of patients with a result this
  /// clear (n = 61)". Null when there is no cross-validation accuracy.
  String? get testingSentence {
    final acc = cvAccuracy;
    if (acc == null) return null;
    final n = cvN == null ? '' : ' (n = $cvN)';
    return 'In testing, the model was right for ${(acc * 100).round()}% of '
        'patients with a result this clear$n.';
  }
}

class Aggregate {
  final String severityClass; // Normal | Mild | Moderate (= moderate-to-severe)
  final String severityLabel; // Normal | Mild | Moderate-to-Severe (shown to users)
  final double pAnemic; // calibrated anemia risk score 0..1
  final double? pModerateOrSevere;
  final double? threshold;
  final bool anemic;
  final int anemicVotes;
  final int nUsed;
  final double agreement; // 0..1
  final String confidence; // High | Medium | Low
  final ConfidenceDetail? confidenceDetail;
  final Verdict verdict;

  const Aggregate({
    required this.severityClass,
    required this.severityLabel,
    required this.pAnemic,
    this.pModerateOrSevere,
    this.threshold,
    required this.anemic,
    required this.anemicVotes,
    required this.nUsed,
    required this.agreement,
    required this.confidence,
    this.confidenceDetail,
    required this.verdict,
  });

  factory Aggregate.fromJson(Map<String, dynamic> j) {
    final cls = _str(j['severity_class']) ?? 'Normal';
    return Aggregate(
      severityClass: cls,
      severityLabel: _str(j['severity_label']) ?? severityDisplayLabel(cls),
      pAnemic: (_dbl(j['p_anemic']) ?? 0).clamp(0.0, 1.0).toDouble(),
      pModerateOrSevere: _dbl(j['p_moderate_or_severe']),
      threshold: _dbl(j['threshold']),
      anemic: _bool(j['anemic']) ?? false,
      anemicVotes: _int(j['anemic_votes']) ?? 0,
      nUsed: _int(j['n_used']) ?? 0,
      agreement: _dbl(j['agreement']) ?? 0,
      confidence: _str(j['confidence']) ?? 'Low',
      confidenceDetail: ConfidenceDetail.tryParse(j['confidence_detail']),
      verdict: Verdict.fromJson(_map(j['verdict'])),
    );
  }

  /// Share of photos that agree with the verdict (0..1).
  double get agreementScore => (nUsed == 0) ? 0 : agreement;

  /// Shown as "Anemia risk score NN%".
  int get riskPercent => (pAnemic * 100).round();

  /// Moderate (= moderate-to-severe) needs a doctor.
  bool get needsDoctor => severityLevel >= 2;

  int get severityLevel => severityLevelOf(severityClass);

  Color get color => C.severityColor(severityClass);
}

class SymptomReport {
  final List<SymptomItem> expected;
  final List<SymptomItem> matched;
  final List<SymptomItem> redFlags;
  final String concordance; // concordant | discordant | not_reported
  final String note;
  final bool urgent;

  const SymptomReport({
    required this.expected,
    required this.matched,
    required this.redFlags,
    required this.concordance,
    required this.note,
    required this.urgent,
  });

  factory SymptomReport.fromJson(Map<String, dynamic> j) {
    List<SymptomItem> list(String key) => _list(j[key])
        .whereType<Map>()
        .map((m) => SymptomItem.fromJson(_map(m)))
        .where((s) => s.label.isNotEmpty)
        .toList();
    return SymptomReport(
      expected: list('expected'),
      matched: list('matched'),
      redFlags: list('red_flags'),
      concordance: _str(j['concordance']) ?? 'not_reported',
      note: _str(j['note']) ?? '',
      urgent: _bool(j['urgent']) ?? false,
    );
  }
}

/// One food in a meal, with USDA-derived nutrients for the given portion.
class MealItem {
  final String food;
  final double? grams;
  final double? ironMg;
  final double? absorbableIronMg;
  final double? vitaminCMg;
  final double? calciumMg;
  final bool heme;
  final int? fdcId;
  final double? servings;

  const MealItem({
    required this.food,
    this.grams,
    this.ironMg,
    this.absorbableIronMg,
    this.vitaminCMg,
    this.calciumMg,
    this.heme = false,
    this.fdcId,
    this.servings,
  });

  factory MealItem.fromJson(Map<String, dynamic> j) => MealItem(
        food: (_str(j['food']) ?? '').trim(),
        grams: _dbl(j['grams']),
        ironMg: _dbl(j['iron_mg']),
        absorbableIronMg: _dbl(j['absorbable_iron_mg']),
        vitaminCMg: _dbl(j['vitamin_c_mg']),
        calciumMg: _dbl(j['calcium_mg']),
        heme: _bool(j['heme']) ?? false,
        fdcId: _int(j['fdc_id']),
        servings: _dbl(j['servings']),
      );

  Map<String, dynamic> toJson() => {
        'food': food,
        'servings': ?servings,
        'grams': ?grams,
        'iron_mg': ?ironMg,
        'absorbable_iron_mg': ?absorbableIronMg,
        'vitamin_c_mg': ?vitaminCMg,
        'calcium_mg': ?calciumMg,
        'heme': heme,
        'fdc_id': ?fdcId,
      };
}

/// One meal of the day (Breakfast / Lunch / Snack / Dinner).
class Meal {
  final String meal;
  final List<MealItem> items;
  final double? ironMg;
  final double? absorbableIronMg;
  final String note;

  /// Local dish suggestion, e.g. "Rajma with brown rice" ('' when absent).
  final String dish;

  /// Suggested time, e.g. "8:00 am" ('' when absent).
  final String time;

  /// AI-estimated cost of the meal in rupees (null when not provided).
  final double? estCostInr;

  const Meal({
    required this.meal,
    required this.items,
    this.ironMg,
    this.absorbableIronMg,
    this.note = '',
    this.dish = '',
    this.time = '',
    this.estCostInr,
  });

  factory Meal.fromJson(Map<String, dynamic> j) => Meal(
        meal: (_str(j['meal']) ?? '').trim(),
        items: _list(j['items'])
            .whereType<Map>()
            .map((m) => MealItem.fromJson(_map(m)))
            .where((i) => i.food.isNotEmpty)
            .toList(),
        ironMg: _dbl(j['iron_mg']),
        absorbableIronMg: _dbl(j['absorbable_iron_mg']),
        note: (_str(j['note']) ?? '').trim(),
        dish: (_str(j['dish']) ?? '').trim(),
        time: (_str(j['time']) ?? '').trim(),
        estCostInr: _dbl(j['est_cost_inr']),
      );

  Map<String, dynamic> toJson() => {
        'meal': meal,
        if (dish.isNotEmpty) 'dish': dish,
        if (time.isNotEmpty) 'time': time,
        'est_cost_inr': ?estCostInr,
        'items': [for (final i in items) i.toJson()],
        'iron_mg': ?ironMg,
        'absorbable_iron_mg': ?absorbableIronMg,
        'note': note,
      };
}

/// Daily iron totals of the meal plan against the target.
class DailyIron {
  final double? ironMg;
  final double? absorbableIronMg;
  final double? targetIronMg;
  final String targetBasis;
  final double? absorbedTargetMg;

  /// AI-estimated cost of the whole day in rupees and the user's budget.
  final double? estCostInr;
  final double? budgetInr;

  const DailyIron({
    this.ironMg,
    this.absorbableIronMg,
    this.targetIronMg,
    this.targetBasis = '',
    this.absorbedTargetMg,
    this.estCostInr,
    this.budgetInr,
  });

  static DailyIron? tryParse(Object? v) {
    if (v is! Map) return null;
    final j = _map(v);
    return DailyIron(
      ironMg: _dbl(j['iron_mg']),
      absorbableIronMg: _dbl(j['absorbable_iron_mg']),
      targetIronMg: _dbl(j['target_iron_mg']),
      targetBasis: (_str(j['target_basis']) ?? '').trim(),
      absorbedTargetMg: _dbl(j['absorbed_target_mg']),
      estCostInr: _dbl(j['est_cost_inr']),
      budgetInr: _dbl(j['budget_inr']),
    );
  }

  Map<String, dynamic> toJson() => {
        'iron_mg': ?ironMg,
        'absorbable_iron_mg': ?absorbableIronMg,
        'target_iron_mg': ?targetIronMg,
        'target_basis': targetBasis,
        'absorbed_target_mg': ?absorbedTargetMg,
        'est_cost_inr': ?estCostInr,
        'budget_inr': ?budgetInr,
      };
}

/// A food the user dislikes and what the planner used instead.
class DietReplacement {
  final String disliked;
  final String replacement;
  final String reason;

  const DietReplacement({
    required this.disliked,
    required this.replacement,
    this.reason = '',
  });

  static DietReplacement? tryParse(Object? v) {
    if (v is! Map) return null;
    final j = _map(v);
    final disliked = (_str(j['disliked']) ?? '').trim();
    final replacement = (_str(j['replacement']) ?? '').trim();
    if (disliked.isEmpty || replacement.isEmpty) return null;
    return DietReplacement(
      disliked: disliked,
      replacement: replacement,
      reason: (_str(j['reason']) ?? '').trim(),
    );
  }

  Map<String, dynamic> toJson() =>
      {'disliked': disliked, 'replacement': replacement, 'reason': reason};
}

/// One entry of `GET /diet/foods` (USDA foods the planner knows).
class DietFood {
  final int? fdcId;
  final String name;
  final String group;

  const DietFood({this.fdcId, required this.name, this.group = ''});

  factory DietFood.fromJson(Map<String, dynamic> j) => DietFood(
        fdcId: _int(j['fdc_id']),
        name: (_str(j['name']) ?? '').trim(),
        group: (_str(j['group']) ?? '').trim(),
      );
}

class DietPlan {
  final String goal;
  final String dietType;
  final List<String> ironRichFoods;
  final List<String> pairWithVitaminC;
  final List<String> avoidOrLimit;
  final Map<String, String> sampleDay;
  final List<String> extraTips;
  final String whenToSeeClinician;
  final String recoveryOutlook;

  /// Real meal plan with per-food nutrients (empty for older servers / cache).
  final List<Meal> meals;
  final DailyIron? daily;
  final String dataSource;

  /// e.g. "AI estimate for Tamil Nadu (urban), Nov 2026 - not official prices".
  final String? costBasis;
  final List<DietReplacement> replacements;

  /// "ai" | "rules" | null (screening-time plans from older servers).
  final String? generatedBy;
  final String? aiModel;
  final List<String> warnings;

  const DietPlan({
    required this.goal,
    required this.dietType,
    required this.ironRichFoods,
    required this.pairWithVitaminC,
    required this.avoidOrLimit,
    required this.sampleDay,
    required this.extraTips,
    required this.whenToSeeClinician,
    required this.recoveryOutlook,
    this.meals = const [],
    this.daily,
    this.dataSource = '',
    this.costBasis,
    this.replacements = const [],
    this.generatedBy,
    this.aiModel,
    this.warnings = const [],
  });

  bool get isAiPlanned => generatedBy == 'ai';
  bool get isRulesPlanned => generatedBy == 'rules';

  factory DietPlan.fromJson(Map<String, dynamic> j) {
    List<String> strs(Object? v) => _list(v).map((e) => e.toString()).toList();
    String? nonEmpty(Object? v) {
      final t = _str(v)?.trim();
      return (t == null || t.isEmpty) ? null : t;
    }

    return DietPlan(
      goal: _str(j['goal']) ?? '',
      dietType: _str(j['diet_type']) ?? 'omnivore',
      ironRichFoods: strs(j['iron_rich_foods']),
      pairWithVitaminC: strs(j['pair_with_vitamin_c']),
      avoidOrLimit: strs(j['avoid_or_limit']),
      sampleDay: _map(j['sample_day']).map((k, v) => MapEntry(k, v.toString())),
      extraTips: strs(j['extra_tips']),
      whenToSeeClinician: _str(j['when_to_see_clinician']) ?? '',
      recoveryOutlook: _str(j['recovery_outlook']) ?? '',
      meals: _list(j['meals'])
          .whereType<Map>()
          .map((m) => Meal.fromJson(_map(m)))
          .where((m) => m.items.isNotEmpty)
          .toList(),
      daily: DailyIron.tryParse(j['daily']),
      dataSource: (_str(j['data_source']) ?? '').trim(),
      costBasis: nonEmpty(j['cost_basis']),
      replacements: _list(j['replacements'])
          .map(DietReplacement.tryParse)
          .whereType<DietReplacement>()
          .toList(),
      generatedBy: nonEmpty(j['generated_by']),
      aiModel: nonEmpty(j['ai_model']),
      warnings: _list(j['warnings'])
          .whereType<String>()
          .map((w) => w.trim())
          .where((w) => w.isNotEmpty)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'goal': goal,
        'diet_type': dietType,
        'iron_rich_foods': ironRichFoods,
        'pair_with_vitamin_c': pairWithVitaminC,
        'avoid_or_limit': avoidOrLimit,
        'sample_day': sampleDay,
        'extra_tips': extraTips,
        'when_to_see_clinician': whenToSeeClinician,
        'recovery_outlook': recoveryOutlook,
        if (meals.isNotEmpty) 'meals': [for (final m in meals) m.toJson()],
        if (daily != null) 'daily': daily!.toJson(),
        if (dataSource.isNotEmpty) 'data_source': dataSource,
        'cost_basis': ?costBasis,
        if (replacements.isNotEmpty)
          'replacements': [for (final r in replacements) r.toJson()],
        'generated_by': ?generatedBy,
        'ai_model': ?aiModel,
        if (warnings.isNotEmpty) 'warnings': warnings,
      };
}

class BatchScreening {
  final Aggregate aggregate;
  final List<PerImage> perImage;
  final SymptomReport symptoms;
  final DietPlan dietPlan;
  final String? model;
  final String disclaimer;

  const BatchScreening({
    required this.aggregate,
    required this.perImage,
    required this.symptoms,
    required this.dietPlan,
    this.model,
    required this.disclaimer,
  });

  factory BatchScreening.fromJson(Map<String, dynamic> j) => BatchScreening(
        aggregate: Aggregate.fromJson(_map(j['aggregate'])),
        perImage: _list(j['per_image'])
            .whereType<Map>()
            .map((m) => PerImage.fromJson(_map(m)))
            .toList(),
        symptoms: SymptomReport.fromJson(_map(j['symptoms'])),
        dietPlan: DietPlan.fromJson(_map(j['diet_plan'])),
        model: _str(j['model']),
        disclaimer: _str(j['disclaimer']) ?? 'Screening only, not a diagnosis.',
      );

  /// Photos the server could analyse.
  List<PerImage> get validImages => perImage.where((i) => i.ok).toList();

  /// Photos the server rejected (bad light, blur, no eyelid found...).
  List<PerImage> get skippedImages => perImage.where((i) => !i.ok).toList();

  /// e.g. "1 of 3 photos skipped: The photo is too dark..." or null.
  String? get skippedNote {
    final skipped = skippedImages;
    if (skipped.isEmpty || perImage.isEmpty) return null;
    final n = perImage.length;
    return '${skipped.length} of $n photo${n == 1 ? '' : 's'} skipped: '
        '${skipped.first.error}';
  }
}

/// One saved screening in the on-device history. No Hb numbers are stored.
class HistoryEntry {
  final DateTime time;
  final String severityClass;
  final bool anemic;
  final String confidence;
  final double agreement;
  final String headline;
  final String severityLabel; // shown to users ('' for old entries)
  final double? pAnemic; // risk score 0..1 (null for entries from older versions)

  const HistoryEntry({
    required this.time,
    required this.severityClass,
    required this.anemic,
    required this.confidence,
    required this.agreement,
    required this.headline,
    this.severityLabel = '',
    this.pAnemic,
  });

  Map<String, dynamic> toMap() => {
        'time': time.toIso8601String(),
        'severity_class': severityClass,
        'severity_label': label,
        'anemic': anemic,
        'confidence': confidence,
        'agreement': agreement,
        'headline': headline,
        'p_anemic': ?pAnemic,
      };

  factory HistoryEntry.fromMap(Map<String, dynamic> m) => HistoryEntry(
        time: DateTime.tryParse(_str(m['time']) ?? '') ?? DateTime.now(),
        severityClass: _str(m['severity_class']) ?? 'Normal',
        anemic: _bool(m['anemic']) ?? false,
        confidence: _str(m['confidence']) ?? 'Low',
        agreement: _dbl(m['agreement']) ?? 0,
        headline: _str(m['headline']) ?? '',
        severityLabel: _str(m['severity_label']) ?? '',
        pAnemic: _dbl(m['p_anemic']),
      );

  /// User-facing label (older entries derive it from the class).
  String get label =>
      severityLabel.isEmpty ? severityDisplayLabel(severityClass) : severityLabel;

  int? get riskPercent => pAnemic == null ? null : (pAnemic! * 100).round();

  int get severityLevel => severityLevelOf(severityClass);
}

class HealthStatus {
  final String status;
  final String? modelName;
  final bool modelLoaded;
  final String? reasonNotLoaded;

  const HealthStatus({
    required this.status,
    this.modelName,
    required this.modelLoaded,
    this.reasonNotLoaded,
  });

  factory HealthStatus.fromJson(Map<String, dynamic> j) {
    final model = _map(j['model']);
    return HealthStatus(
      status: _str(j['status']) ?? 'unknown',
      modelName: _str(model['name']),
      modelLoaded: _bool(model['loaded']) ?? false,
      reasonNotLoaded: _str(model['reason_not_loaded']),
    );
  }
}
