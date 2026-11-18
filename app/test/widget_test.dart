import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/data/api_client.dart';
import 'package:app/models/roi_box.dart';
import 'package:app/models/screening.dart';
import 'package:app/screens/capture_tutorial_screen.dart';
import 'package:app/screens/diet_screen.dart';
import 'package:app/screens/review_screen.dart';
import 'package:app/screens/why_result_screen.dart';
import 'package:app/theme.dart';
import 'package:app/widgets/ui.dart';

const _png1x1 =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

/// Shape of a real `/screen/batch` success (3 photos, 1 rejected).
final Map<String, dynamic> sampleSuccess = jsonDecode('''
{
  "aggregate": {
    "predicted_hb_gdl": null,
    "p_anemic": 0.7312,
    "p_moderate_or_severe": 0.6123,
    "threshold": 0.45,
    "severity_class": "Moderate",
    "severity_label": "Moderate-to-Severe",
    "anemic": true,
    "anemic_votes": 2,
    "n_used": 2,
    "agreement": 1.0,
    "confidence": "High",
    "verdict": {
      "status": "anemic",
      "headline": "Possible anemia (Moderate-to-Severe)",
      "summary": "The colour of the inner eyelid is in the range the model associates with anemia (risk score 73%). A blood test (CBC) is needed to confirm."
    }
  },
  "per_image": [
    {
      "index": 0, "filename": "a.jpg", "anemic": true, "p_anemic": 0.74,
      "p_moderate_or_severe": 0.6, "threshold": 0.45, "severity_class": "Moderate",
      "severity_label": "Moderate-to-Severe", "predicted_hb_gdl": null,
      "features": {"ei": 0.0412, "a": 12.3, "hhr": 0.21, "sat": 0.33},
      "explanation": {
        "inputs": ["ei", "hhr", "sat"],
        "memberships": {
          "ei": {"Low": 0.81, "Medium": 0.22, "High": 0.01},
          "hhr": {"Low": 0.64, "Medium": 0.40, "High": 0.02},
          "sat": {"Low": 0.10, "Medium": 0.90, "High": 0.20}
        },
        "top_rules": [
          {"if": {"ei": "Low", "hhr": "Low", "sat": "Medium"}, "weight": 0.61, "risk": 0.82},
          {"if": {"ei": "Low", "hhr": "Medium", "sat": "Medium"}, "weight": 0.2, "risk": 0.7},
          {"if": {"ei": "Medium", "hhr": "Low", "sat": "Medium"}, "weight": 0.1, "risk": 0.5}
        ]
      },
      "quality": {"brightness": 0.55, "clipped_fraction": 0.01, "sharpness": 120.5},
      "roi": {"detected": true, "note": null, "box": [0.14, 0.42, 0.72, 0.44], "conjunctiva_pixels": 5321},
      "roi_thumbnail": "$_png1x1",
      "processing_ms": 210.4,
      "model": "anfis-sugeno0 v1"
    },
    {
      "index": 1, "filename": "b.jpg", "anemic": true, "p_anemic": 0.72,
      "severity_class": "Moderate", "features": {"ei": 0.05}
    },
    {
      "index": 2, "filename": "c.jpg",
      "error": "The photo is too dark. Turn on the torch or move to brighter light.",
      "error_code": "too_dark"
    }
  ],
  "symptoms": {"expected": [], "matched": [], "red_flags": [], "concordance": "not_reported", "note": "", "urgent": false},
  "diet_plan": {"goal": "Raise iron", "diet_type": "vegetarian", "iron_rich_foods": ["Spinach"],
                "pair_with_vitamin_c": [], "avoid_or_limit": [], "sample_day": {"breakfast": "Poha"},
                "extra_tips": [], "when_to_see_clinician": "", "recovery_outlook": ""},
  "model": "anfis-sugeno0 v1",
  "disclaimer": "Screening only, not a diagnosis."
}
''') as Map<String, dynamic>;

/// Shape of a `/screen/batch` 422 (no photo passed).
final Map<String, dynamic> sample422 = {
  'detail': {
    'code': 'no_conjunctiva',
    'message':
        'Could not find the pink inner eyelid inside the box. Pull the lower eyelid down gently and place the box over the pink area.',
    'per_image': [
      {
        'index': 0,
        'filename': 'a.jpg',
        'error':
            'Could not find the pink inner eyelid inside the box. Pull the lower eyelid down gently and place the box over the pink area.',
        'error_code': 'no_conjunctiva'
      },
      {
        'index': 1,
        'filename': 'b.jpg',
        'error': 'The photo is blurry. Hold the phone steady and tap to focus on the eyelid.',
        'error_code': 'blurry'
      },
    ],
  },
};

DioException _dioError(int status, Object? data) {
  final req = RequestOptions(path: '/screen/batch');
  return DioException(
    requestOptions: req,
    type: DioExceptionType.badResponse,
    response: Response(requestOptions: req, statusCode: status, data: data),
  );
}

void main() {
  group('BatchScreening parsing (ANFIS contract)', () {
    test('parses aggregate, per-image features, explanation and errors', () {
      final r = BatchScreening.fromJson(sampleSuccess);
      final a = r.aggregate;
      expect(a.pAnemic, closeTo(0.7312, 1e-9));
      expect(a.riskPercent, 73);
      expect(a.pModerateOrSevere, closeTo(0.6123, 1e-9));
      expect(a.severityClass, 'Moderate');
      expect(a.severityLabel, 'Moderate-to-Severe');
      expect(a.needsDoctor, isTrue);
      expect(a.confidence, 'High');
      expect(a.verdict.headline, contains('Possible anemia'));

      expect(r.perImage, hasLength(3));
      expect(r.validImages, hasLength(2));
      final p0 = r.perImage[0];
      expect(p0.features['ei'], closeTo(0.0412, 1e-9));
      expect(p0.explanation.inputs, ['ei', 'hhr', 'sat']);
      expect(p0.explanation.memberships['ei']!['Low'], closeTo(0.81, 1e-9));
      expect(p0.explanation.topRules, hasLength(3));
      expect(p0.explanation.topRules.first.sentence,
          'IF Redness is Low AND Share of red pixels is Low AND Saturation is Medium THEN risk 82% (weight 0.61)');
      expect(p0.quality['sharpness'], closeTo(120.5, 1e-9));
      expect(p0.roi!.conjunctivaPixels, 5321);
      expect(decodeDataUrl(p0.roiThumbnail), isNotNull);

      // Sparse per-image row must not crash.
      expect(r.perImage[1].explanation.isEmpty, isTrue);

      final skipped = r.perImage[2];
      expect(skipped.ok, isFalse);
      expect(skipped.errorCode, 'too_dark');
      expect(r.skippedNote, startsWith('1 of 3 photos skipped: The photo is too dark'));
    });

    test('tolerates missing / wrongly typed fields', () {
      final r = BatchScreening.fromJson({
        'aggregate': {'p_anemic': 'oops', 'severity_class': 'Mild', 'n_used': 1},
        'per_image': [
          {'index': 0, 'explanation': {'memberships': 'bad', 'top_rules': [1, 2]}},
          'not a map',
        ],
        'symptoms': null,
      });
      expect(r.aggregate.pAnemic, 0);
      expect(r.aggregate.severityLabel, 'Mild');
      expect(r.perImage, hasLength(1));
      expect(r.skippedNote, isNull);
      expect(BatchScreening.fromJson(const {}).aggregate.severityClass, 'Normal');
    });

    test('old history entries still load; new ones keep label + risk', () {
      final old = HistoryEntry.fromMap({
        'time': '2026-11-01T10:00:00.000',
        'severity_class': 'Severe',
        'anemic': true,
        'confidence': 'High',
        'agreement': 1.0,
        'headline': 'Anemia likely',
      });
      expect(old.label, 'Moderate-to-Severe');
      expect(old.severityLevel, 2);
      expect(old.riskPercent, isNull);

      final fresh = HistoryEntry(
        time: DateTime(2026, 11, 16),
        severityClass: 'Mild',
        anemic: true,
        confidence: 'Medium',
        agreement: 1,
        headline: 'Possible anemia (Mild)',
        severityLabel: 'Mild',
        pAnemic: 0.58,
      );
      final round = HistoryEntry.fromMap(fresh.toMap());
      expect(round.label, 'Mild');
      expect(round.riskPercent, 58);
      expect(fresh.toMap().keys.any((k) => k.contains('hb')), isFalse);
    });
  });

  group('ApiClient error mapping', () {
    test('422 surfaces the server message and code', () {
      final e = ApiClient.fromDio(_dioError(422, sample422));
      expect(e.code, 'image_quality');
      expect(e.reason, 'no_conjunctiva');
      expect(e.message, startsWith('Could not find the pink inner eyelid'));
      expect(e.photoErrors, hasLength(2));
    });

    test('422 with a plain string detail still shows it', () {
      final e = ApiClient.fromDio(_dioError(422, {'detail': 'data must be valid JSON'}));
      expect(e.code, 'image_quality');
      expect(e.message, 'data must be valid JSON');
    });

    test('503 model_unavailable and connection errors', () {
      expect(ApiClient.fromDio(_dioError(503, {'detail': 'model_unavailable'})).code,
          'model_unavailable');
      final conn = ApiClient.fromDio(DioException(
          requestOptions: RequestOptions(path: '/'),
          type: DioExceptionType.connectionError));
      expect(conn.code, 'network');
    });

    test('screen data carries roi_boxes and no Hb', () {
      final data = ApiClient.buildScreenData(
        userContext: {'age': 30},
        roiBoxes: [RoiBox.standard.toList()],
      );
      final m = jsonDecode(data) as Map<String, dynamic>;
      expect(m['roi_boxes'], [
        [0.14, 0.42, 0.72, 0.44]
      ]);
      expect(data.contains('hb'), isFalse);
    });
  });

  group('RoiBox', () {
    test('move stays inside the photo', () {
      final b = RoiBox.standard.moveBy(1, 1);
      expect(b.x + b.w, closeTo(1, 1e-9));
      expect(b.y + b.h, closeTo(1, 1e-9));
      final c = RoiBox.standard.moveBy(-5, -5);
      expect(c.x, 0);
      expect(c.y, 0);
    });

    test('resize keeps a minimum size and the opposite corner fixed', () {
      final b = RoiBox.standard.resizeCorner(3, -1, -1); // bottom-right inwards
      expect(b.w, closeTo(RoiBox.minSize, 1e-9));
      expect(b.h, closeTo(RoiBox.minSize, 1e-9));
      expect(b.x, RoiBox.standard.x);
      final t = RoiBox.standard.resizeCorner(0, -1, -1); // top-left outwards
      expect(t.x, 0);
      expect(t.y, 0);
      expect(t.x + t.w, closeTo(0.86, 1e-9));
    });
  });

  testWidgets('Pill and gauge show the label + risk score, never Hb',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildHemoSenseTheme(),
        home: const Scaffold(
          body: Column(
            children: [
              SeverityPill('Moderate'),
              RiskGauge(severity: 'Mild', riskScore: 0.83),
              DisclaimerFooter(),
            ],
          ),
        ),
      ),
    );
    expect(find.text('Moderate-to-Severe'), findsWidgets);
    expect(find.text('Anemia risk score 83%'), findsOneWidget);
    expect(find.textContaining('not a diagnosis'), findsOneWidget);
    expect(find.textContaining('g/dL'), findsNothing);
  });

  testWidgets('Why screen shows features, memberships and rule sentences',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: buildHemoSenseTheme(),
      home: WhyResultScreen(result: BatchScreening.fromJson(sampleSuccess)),
    ));
    expect(find.textContaining('ANFIS fuzzy system'),
        findsOneWidget);
    expect(find.text('Redness (erythema index)'), findsOneWidget);
    expect(find.text('Share of strongly red pixels'), findsOneWidget);
    expect(find.textContaining('IF Redness is Low AND Share of red pixels is Low'),
        findsOneWidget);
    expect(find.textContaining('g/dL'), findsNothing);
    expect(find.textContaining('hemoglobin'), findsNothing);
  });

  testWidgets('ROI editor: drag inside moves, corner drag resizes',
      (WidgetTester tester) async {
    var box = RoiBox.standard;
    final bytes = decodeDataUrl(_png1x1)!;
    Widget build() => MaterialApp(
          home: Scaffold(
            body: Align(
              alignment: Alignment.topLeft,
              child: StatefulBuilder(
                builder: (context, setState) => RoiEditor(
                  bytes: bytes,
                  displaySize: const Size(300, 200),
                  box: box,
                  onChanged: (b) => setState(() => box = b),
                ),
              ),
            ),
          ),
        );
    await tester.pumpWidget(build());
    final origin = tester.getTopLeft(find.byType(RoiEditor));
    // Centre of the default box: x = (0.14 + 0.36) * 300, y = (0.42 + 0.22) * 200
    await tester.dragFrom(origin + const Offset(150, 128), const Offset(30, 0));
    await tester.pump();
    expect(box.x, greaterThan(RoiBox.standard.x + 0.05));
    expect(box.w, closeTo(RoiBox.standard.w, 1e-9));

    // Drag the bottom-right corner inwards: width shrinks.
    final before = box;
    final br = origin + Offset((box.x + box.w) * 300, (box.y + box.h) * 200);
    await tester.dragFrom(br, const Offset(-60, -20));
    await tester.pump();
    expect(box.w, lessThan(before.w - 0.1));
    expect(box.x, closeTo(before.x, 1e-9));
  });

  group('New API fields (confidence_detail, meals, daily)', () {
    Map<String, dynamic> withNewFields() {
      final j = jsonDecode(jsonEncode(sampleSuccess)) as Map<String, dynamic>;
      (j['aggregate'] as Map<String, dynamic>)['confidence_detail'] = {
        'certainty': 0.88,
        'cv_accuracy': 0.92,
        'cv_n': 61,
        'basis': 'Risk score far from the decision threshold and all photos agree.',
      };
      (j['diet_plan'] as Map<String, dynamic>).addAll({
        'meals': [
          {
            'meal': 'Breakfast',
            'items': [
              {'food': 'Lentils, cooked', 'grams': 150, 'iron_mg': 4.8,
               'absorbable_iron_mg': 0.5, 'vitamin_c_mg': 2.25,
               'calcium_mg': 28, 'heme': false, 'fdc_id': 172421},
              {'food': 'Chicken liver', 'grams': 80, 'iron_mg': 7.2,
               'absorbable_iron_mg': 1.8, 'vitamin_c_mg': 0, 'calcium_mg': 9,
               'heme': true, 'fdc_id': 171061},
            ],
            'iron_mg': 12.0,
            'absorbable_iron_mg': 2.3,
            'note': 'Add lemon to the lentils.',
          },
          {'meal': 'Lunch', 'items': 'bad'},
        ],
        'daily': {'iron_mg': 12.0, 'absorbable_iron_mg': 2.3,
                  'target_iron_mg': 18, 'target_basis': 'RDA for adult women (ICMR-NIN 2020)',
                  'absorbed_target_mg': 1.8},
        'data_source': 'USDA FoodData Central, SR Legacy (public domain)',
      });
      return j;
    }

    test('parses confidence_detail and meal plan; missing fields are safe', () {
      final r = BatchScreening.fromJson(withNewFields());
      final cd = r.aggregate.confidenceDetail!;
      expect(cd.cvAccuracy, closeTo(0.92, 1e-9));
      expect(cd.cvN, 61);
      expect(cd.testingSentence,
          'In testing, the model was right for 92% of patients with a result this clear (n = 61).');
      final d = r.dietPlan;
      expect(d.meals, hasLength(1)); // the malformed Lunch is dropped
      expect(d.meals.first.items.last.heme, isTrue);
      expect(d.daily!.targetIronMg, 18);
      expect(d.dataSource, startsWith('USDA'));

      // The cached plan (Diet tab) keeps the meals after a JSON round-trip.
      final again = DietPlan.fromJson(
          jsonDecode(jsonEncode(d.toJson())) as Map<String, dynamic>);
      expect(again.meals.first.items.first.fdcId, 172421);
      expect(again.daily!.absorbedTargetMg, closeTo(1.8, 1e-9));

      // Older responses / cached plans without the new fields.
      final old = BatchScreening.fromJson(sampleSuccess);
      expect(old.aggregate.confidenceDetail, isNull);
      expect(old.dietPlan.meals, isEmpty);
      expect(old.dietPlan.daily, isNull);
      // Null cv_accuracy: no sentence.
      final noCv = ConfidenceDetail.tryParse(
          {'certainty': 0.5, 'cv_accuracy': null, 'cv_n': 0, 'basis': 'x'});
      expect(noCv!.testingSentence, isNull);
      expect(ConfidenceDetail.tryParse('nope'), isNull);
      expect(DailyIron.tryParse(null), isNull);
    });

    testWidgets('diet screen renders meals and daily totals from data',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 4000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final r = BatchScreening.fromJson(withNewFields());
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
            theme: buildHemoSenseTheme(), home: DietScreen(result: r)),
      ));
      expect(find.text('Breakfast'), findsOneWidget);
      expect(find.text('Chicken liver'), findsOneWidget);
      expect(find.text('heme'), findsOneWidget);
      expect(find.textContaining('150 g · iron 4.8 mg · absorbable 0.50 mg'),
          findsOneWidget);
      expect(find.text('12.0 of 18.0 mg'), findsOneWidget);
      expect(find.text('2.3 of 1.8 mg'), findsOneWidget);
      expect(find.textContaining('ICMR-NIN'), findsOneWidget);
      expect(find.textContaining('USDA FoodData Central'), findsOneWidget);
      expect(find.text('Add lemon to the lentils.'), findsOneWidget);
      expect(find.textContaining('Sample day'), findsNothing);
      expect(find.textContaining('not a diagnosis'), findsOneWidget);
    });

    testWidgets('diet screen falls back to the sample day without meals',
        (tester) async {
      tester.view.physicalSize = const Size(1080, 4000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(ProviderScope(
        child: MaterialApp(
            theme: buildHemoSenseTheme(),
            home: DietScreen(result: BatchScreening.fromJson(sampleSuccess))),
      ));
      expect(find.textContaining('SAMPLE DAY'), findsOneWidget);
      expect(find.text('Poha'), findsOneWidget);
      expect(find.textContaining('DAILY TOTAL'), findsNothing);
    });

    testWidgets('why screen shows the confidence basis', (tester) async {
      tester.view.physicalSize = const Size(1080, 5000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(MaterialApp(
        theme: buildHemoSenseTheme(),
        home: WhyResultScreen(result: BatchScreening.fromJson(withNewFields())),
      ));
      expect(find.textContaining('far from the decision threshold'),
          findsOneWidget);
      expect(find.textContaining('right for 92% of patients'), findsOneWidget);
    });
  });

  group('Review screen box sharing', () {
    Future<void> pumpReview(WidgetTester tester,
        {required bool fromGallery}) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final bytes = decodeDataUrl(_png1x1)!;
      final shots = [
        for (var i = 0; i < 3; i++)
          XFile.fromData(bytes, name: 'f$i.png', mimeType: 'image/png'),
      ];
      await tester.runAsync(() async {
        await tester.pumpWidget(MaterialApp(
          theme: buildHemoSenseTheme(),
          home: ReviewScreen(shots: shots, fromGallery: fromGallery),
        ));
        // Let readAsBytes + image decoding finish for all 3 photos.
        for (var i = 0; i < 30; i++) {
          await Future<void>.delayed(const Duration(milliseconds: 20));
          await tester.pump();
        }
      });
      await tester.pump();
    }

    RoiBox editorBox(WidgetTester tester) =>
        tester.widget<RoiEditor>(find.byType(RoiEditor)).box;

    FilledButton analyse(WidgetTester tester) =>
        tester.widget<FilledButton>(find.byType(FilledButton));

    Future<void> dragBox(WidgetTester tester) async {
      final ed = find.byType(RoiEditor);
      final tl = tester.getTopLeft(ed);
      final sz = tester.getSize(ed);
      final b = editorBox(tester);
      final centre =
          tl + Offset((b.x + b.w / 2) * sz.width, (b.y + b.h / 2) * sz.height);
      await tester.dragFrom(centre, const Offset(20, 20));
      await tester.pump();
    }

    Future<void> selectThumb(WidgetTester tester, int i) async {
      // Image widgets: [0] is the editor, [1..3] the thumbnails.
      await tester.tap(find.byType(Image).at(1 + i));
      await tester.pump();
    }

    testWidgets('burst photos share one box', (tester) async {
      await pumpReview(tester, fromGallery: false);
      expect(find.byType(RoiEditor), findsOneWidget);
      expect(find.textContaining('One box is used for all 3'), findsOneWidget);
      expect(analyse(tester).onPressed, isNull);
      await dragBox(tester);
      final moved = editorBox(tester);
      expect(moved, isNot(RoiBox.start));
      expect(analyse(tester).onPressed, isNotNull);
      // Frame 3 shows the same box and Analyse stays enabled.
      await selectThumb(tester, 2);
      expect(editorBox(tester), moved);
      expect(analyse(tester).onPressed, isNotNull);
    });

    testWidgets('gallery photos keep independent boxes', (tester) async {
      await pumpReview(tester, fromGallery: true);
      expect(find.text('Place the box on each photo'), findsOneWidget);
      await dragBox(tester);
      expect(editorBox(tester), isNot(RoiBox.start));
      expect(analyse(tester).onPressed, isNull); // photos 2 and 3 not placed
      await selectThumb(tester, 1);
      expect(editorBox(tester), RoiBox.start);
    });
  });

  testWidgets('capture tutorial steps through and auto-advances',
      (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: buildHemoSenseTheme(),
      home: const CaptureTutorialScreen(),
    ));
    expect(find.text('Find bright, even light'), findsOneWidget);
    await tester.tap(find.text('Next'));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Look up'), findsOneWidget);
    // Auto-advance after one animation cycle + short pause.
    for (var i = 0; i < 9; i++) {
      await tester.pump(const Duration(milliseconds: 500));
    }
    expect(find.text('Gently pull the lower eyelid down'), findsOneWidget);
    await tester.tap(find.text('Back'));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Look up'), findsOneWidget);
    expect(find.text('Got it, start camera'), findsOneWidget);
    expect(find.textContaining('not a diagnosis'), findsOneWidget);
    // Paint every step once (smoke test for the painters).
    for (var s = 0; s < kTutorialSteps.length; s++) {
      for (final t in const [0.0, 0.3, 0.65, 1.0]) {
        await tester.pumpWidget(SizedBox(
          width: 300,
          height: 200,
          child: CustomPaint(painter: TutorialPainter(step: s, t: t)),
        ));
      }
    }
  });
}
