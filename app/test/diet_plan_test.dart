import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app/data/api_client.dart';
import 'package:app/models/diet_profile.dart';
import 'package:app/models/profile.dart';
import 'package:app/models/screening.dart';
import 'package:app/providers.dart' as p;
import 'package:app/screens/diet_questionnaire_screen.dart';
import 'package:app/screens/diet_screen.dart';
import 'package:app/theme.dart';

/// Shape of a `POST /diet/plan` response with all the new fields.
Map<String, dynamic> aiPlanJson() => jsonDecode('''
{
  "goal": "Raise iron intake to about 27 mg/day",
  "diet_type": "vegetarian",
  "meals": [
    {
      "meal": "Breakfast", "time": "8:00 am", "dish": "Ragi dosa with tomato chutney",
      "est_cost_inr": 45,
      "items": [
        {"food": "Finger millet flour", "grams": 80, "servings": 1, "iron_mg": 3.1,
         "absorbable_iron_mg": 0.31, "vitamin_c_mg": 0, "heme": false, "fdc_id": 1},
        {"food": "Tomato", "grams": 100, "servings": 1.5, "iron_mg": 0.3,
         "absorbable_iron_mg": 0.03, "vitamin_c_mg": 14, "heme": false}
      ],
      "iron_mg": 3.4, "absorbable_iron_mg": 0.34,
      "note": "Tomato chutney adds vitamin C."
    },
    {
      "meal": "Lunch", "time": "1:00 pm", "dish": "Rajma with brown rice",
      "est_cost_inr": null,
      "items": [{"food": "Kidney beans", "grams": 120, "iron_mg": 6.2, "absorbable_iron_mg": 0.62}],
      "iron_mg": 6.2, "absorbable_iron_mg": 0.62, "note": ""
    }
  ],
  "daily": {"iron_mg": 9.6, "absorbable_iron_mg": 0.96, "target_iron_mg": 27,
            "target_basis": "ICMR-NIN RDA", "absorbed_target_mg": 1.8,
            "est_cost_inr": 180, "budget_inr": 250},
  "cost_basis": "AI estimate for Tamil Nadu (urban), Nov 2026 — not official prices",
  "replacements": [
    {"disliked": "Spinach", "replacement": "Amaranth leaves", "reason": "Similar iron, milder taste"},
    {"disliked": "", "replacement": "x", "reason": "dropped"},
    "not a map"
  ],
  "generated_by": "ai",
  "ai_model": "test-model",
  "warnings": ["Budget is tight; portions kept small.", 3],
  "iron_rich_foods": [], "pair_with_vitamin_c": [], "avoid_or_limit": [],
  "sample_day": {}, "extra_tips": [], "when_to_see_clinician": "", "recovery_outlook": "",
  "data_source": "USDA FoodData Central (SR Legacy)"
}
''') as Map<String, dynamic>;

const _dp = DietProfile(
  budgetInrPerDay: 250,
  state: 'Tamil Nadu',
  city: 'Chennai',
  areaType: 'urban',
  kitchen: 'home',
  fridge: true,
  dislikes: ['Spinach', 'bitter gourd'],
  skipsBreakfast: true,
  nightShift: false,
);

class _FakeProfile extends p.ProfileNotifier {
  final UserProfile initial;
  _FakeProfile(this.initial);
  @override
  UserProfile build() => initial;
}

class _FakeApi extends ApiClient {
  final DietPlan? plan;
  final ApiException? error;
  Map<String, dynamic>? lastBody;
  _FakeApi({this.plan, this.error});

  @override
  Future<DietPlan> dietPlan({
    required UserProfile profile,
    required String severity,
    required bool anemic,
  }) async {
    lastBody = ApiClient.buildDietPlanBody(
      profile: profile,
      severity: severity,
      anemic: anemic,
    );
    if (error != null) throw error!;
    return plan!;
  }
}

BatchScreening _resultWithPlan(Map<String, dynamic>? plan) =>
    BatchScreening.fromJson({
      'aggregate': {
        'p_anemic': 0.6,
        'severity_class': 'Mild',
        'anemic': true,
        'n_used': 1,
        'agreement': 1.0,
        'confidence': 'Medium',
        'verdict': {'status': 'anemic', 'headline': 'Possible anemia (Mild)'},
      },
      'per_image': [],
      'diet_plan': plan ?? {'goal': 'Raise iron', 'diet_type': 'vegetarian'},
      'disclaimer': 'Screening only, not a diagnosis.',
    });

void _tallView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1080, 5000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
}

void main() {
  group('/diet/plan parsing', () {
    test('parses the new fields', () {
      final d = DietPlan.fromJson(aiPlanJson());
      expect(d.isAiPlanned, isTrue);
      expect(d.aiModel, 'test-model');
      expect(d.meals, hasLength(2));
      final b = d.meals.first;
      expect(b.dish, 'Ragi dosa with tomato chutney');
      expect(b.time, '8:00 am');
      expect(b.estCostInr, 45);
      expect(b.items[1].servings, 1.5);
      expect(d.meals[1].estCostInr, isNull);
      expect(d.meals[1].items.first.servings, isNull);
      expect(d.daily!.estCostInr, 180);
      expect(d.daily!.budgetInr, 250);
      expect(d.costBasis, contains('not official prices'));
      expect(d.replacements, hasLength(1));
      expect(d.replacements.first.replacement, 'Amaranth leaves');
      expect(d.warnings, ['Budget is tight; portions kept small.']);

      // Diet-tab cache keeps the new fields after a JSON round-trip.
      final again = DietPlan.fromJson(
        jsonDecode(jsonEncode(d.toJson())) as Map<String, dynamic>,
      );
      expect(again.meals.first.dish, b.dish);
      expect(again.meals.first.time, '8:00 am');
      expect(again.meals.first.estCostInr, 45);
      expect(again.meals.first.items[1].servings, 1.5);
      expect(again.daily!.budgetInr, 250);
      expect(again.costBasis, d.costBasis);
      expect(again.replacements.first.reason, 'Similar iron, milder taste');
      expect(again.generatedBy, 'ai');
      expect(again.warnings, d.warnings);
    });

    test('plans without the new fields still parse', () {
      final j = aiPlanJson()
        ..remove('cost_basis')
        ..remove('replacements')
        ..remove('generated_by')
        ..remove('ai_model')
        ..remove('warnings');
      for (final m in (j['meals'] as List).cast<Map<String, dynamic>>()) {
        m
          ..remove('dish')
          ..remove('time')
          ..remove('est_cost_inr');
      }
      (j['daily'] as Map)
        ..remove('est_cost_inr')
        ..remove('budget_inr');
      final d = DietPlan.fromJson(j);
      expect(d.meals.first.dish, '');
      expect(d.meals.first.time, '');
      expect(d.meals.first.estCostInr, isNull);
      expect(d.daily!.estCostInr, isNull);
      expect(d.costBasis, isNull);
      expect(d.replacements, isEmpty);
      expect(d.generatedBy, isNull);
      expect(d.warnings, isEmpty);

      // Wrongly typed values never crash.
      final odd = DietPlan.fromJson({
        'replacements': 'x',
        'warnings': {'a': 1},
        'generated_by': 5,
        'cost_basis': '  ',
        'meals': [
          {
            'meal': 'X',
            'dish': 3,
            'est_cost_inr': 'cheap',
            'items': [
              {'food': 'Y', 'servings': 'two'},
            ],
          },
        ],
      });
      expect(odd.replacements, isEmpty);
      expect(odd.warnings, isEmpty);
      expect(odd.generatedBy, isNull);
      expect(odd.costBasis, isNull);
      expect(odd.meals.first.estCostInr, isNull);
      expect(odd.meals.first.items.first.servings, isNull);
    });
  });

  group('diet_profile in user_context', () {
    test('questionnaire values are serialised', () {
      const profile = UserProfile(
        age: 24,
        sex: 'female',
        diet: 'vegetarian',
        dietProfile: _dp,
      );
      final ctx = profile.toUserContext();
      expect(ctx['diet_profile'], {
        'budget_inr_per_day': 250.0,
        'state': 'Tamil Nadu',
        'city': 'Chennai',
        'area_type': 'urban',
        'kitchen': 'home',
        'fridge': true,
        'dislikes': ['Spinach', 'bitter gourd'],
        'skips_breakfast': true,
        'night_shift': false,
      });

      // Screen batch and diet plan both carry it.
      final screen = jsonDecode(
        ApiClient.buildScreenData(
          userContext: ctx,
          roiBoxes: const [
            [0.1, 0.1, 0.5, 0.5],
          ],
        ),
      ) as Map;
      expect(
        (screen['user_context'] as Map)['diet_profile']['state'],
        'Tamil Nadu',
      );
      final body = ApiClient.buildDietPlanBody(
        profile: profile,
        severity: 'Mild',
        anemic: true,
      );
      expect(body['severity_class'], 'Mild');
      expect(body['anemic'], isTrue);
      expect(
        (body['user_context'] as Map)['diet_profile']['budget_inr_per_day'],
        250.0,
      );
      expect(jsonEncode(body).contains('hb'), isFalse);

      // Stored round-trip.
      final again = UserProfile.fromMap(
        jsonDecode(jsonEncode(profile.toMap())) as Map<String, dynamic>,
      );
      expect(again.dietProfile!.dislikes, ['Spinach', 'bitter gourd']);
      expect(again.dietProfile!.skipsBreakfast, isTrue);
    });

    test('city is optional and old profiles still load', () {
      const noCity = DietProfile(
        budgetInrPerDay: 100,
        state: 'Delhi',
        areaType: 'hostel',
        kitchen: 'none',
      );
      expect(noCity.toJson().containsKey('city'), isFalse);

      final old = UserProfile.fromMap({
        'age': 30,
        'sex': 'male',
        'pregnant': false,
        'diet': 'omnivore',
        'allergies': '',
      });
      expect(old.age, 30);
      expect(old.dietProfile, isNull);
      expect(old.toUserContext().containsKey('diet_profile'), isFalse);

      final broken = UserProfile.fromMap({
        'age': 30,
        'diet_profile': {'budget_inr_per_day': 'lots', 'state': 'Goa'},
      });
      expect(broken.dietProfile, isNull);
    });
  });

  group('Diet screen with an AI plan', () {
    testWidgets('shows AI badge, cost estimates, replacements and warnings', (
      tester,
    ) async {
      _tallView(tester);
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: buildHemoSenseTheme(),
            home: DietScreen(result: _resultWithPlan(aiPlanJson())),
          ),
        ),
      );
      expect(
        find.text('AI-planned · nutrients from USDA data'),
        findsOneWidget,
      );
      expect(find.text('8:00 am'), findsOneWidget);
      expect(find.text('Ragi dosa with tomato chutney'), findsOneWidget);
      expect(find.text('≈ ₹45 (AI estimate)'), findsOneWidget);
      // No estimate for Lunch: nothing invented.
      expect(find.textContaining('(AI estimate)'), findsNWidgets(2));
      expect(find.text('≈ ₹180 of ₹250 budget'), findsOneWidget);
      expect(find.text('Est. cost (AI estimate)'), findsOneWidget);
      expect(find.textContaining('not official prices'), findsOneWidget);
      expect(
        find.textContaining('1.5 servings · 100 g · iron 0.30 mg'),
        findsOneWidget,
      );
      expect(find.text('YOUR DISLIKES → REPLACEMENTS'), findsOneWidget);
      expect(find.text('Spinach → Amaranth leaves'), findsOneWidget);
      expect(find.text('Similar iron, milder taste'), findsOneWidget);
      expect(
        find.text('Budget is tight; portions kept small.'),
        findsOneWidget,
      );
      expect(find.textContaining('USDA FoodData Central'), findsOneWidget);
      // No questionnaire yet: prompt to fill it, button disabled.
      expect(find.text('Fill in your diet preferences first.'), findsOneWidget);
      final gen = tester.widget<ButtonStyleButton>(
        find.ancestor(
          of: find.text('Generate my AI diet plan'),
          matching: find.bySubtype<ButtonStyleButton>(),
        ),
      );
      expect(gen.onPressed, isNull);
    });

    testWidgets('rules plan badge; cost hidden without budget', (tester) async {
      _tallView(tester);
      final j = aiPlanJson()..['generated_by'] = 'rules';
      (j['daily'] as Map).remove('budget_inr');
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: buildHemoSenseTheme(),
            home: DietScreen(result: _resultWithPlan(j)),
          ),
        ),
      );
      expect(find.text('Data-driven plan (AI unavailable)'), findsOneWidget);
      expect(find.text('AI-planned · nutrients from USDA data'), findsNothing);
      expect(find.textContaining('of ₹'), findsNothing);
      expect(find.text('≈ ₹45 (AI estimate)'), findsOneWidget);
      expect(find.textContaining('not official prices'), findsNothing);
    });

    testWidgets('generates a plan from the questionnaire', (tester) async {
      _tallView(tester);
      final api = _FakeApi(plan: DietPlan.fromJson(aiPlanJson()));
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            p.profileProvider.overrideWith(
              () => _FakeProfile(const UserProfile(age: 24, dietProfile: _dp)),
            ),
            p.apiClientProvider.overrideWithValue(api),
          ],
          child: MaterialApp(
            theme: buildHemoSenseTheme(),
            home: DietScreen(result: _resultWithPlan(null)),
          ),
        ),
      );
      expect(find.text('Edit diet preferences'), findsOneWidget);
      expect(find.text('AI-planned · nutrients from USDA data'), findsNothing);
      await tester.tap(find.text('Generate my AI diet plan'));
      await tester.pump();
      await tester.pump();
      expect(api.lastBody!['severity_class'], 'Mild');
      expect(api.lastBody!['anemic'], isTrue);
      expect(
        (api.lastBody!['user_context'] as Map)['diet_profile']['state'],
        'Tamil Nadu',
      );
      expect(
        find.text('AI-planned · nutrients from USDA data'),
        findsOneWidget,
      );
      expect(find.text('Rajma with brown rice'), findsOneWidget);
    });

    testWidgets('shows the server error with Retry', (tester) async {
      _tallView(tester);
      final api = _FakeApi(
        error: const ApiException('server', 'Diet planner is overloaded.'),
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            p.profileProvider.overrideWith(
              () => _FakeProfile(const UserProfile(age: 24, dietProfile: _dp)),
            ),
            p.apiClientProvider.overrideWithValue(api),
          ],
          child: MaterialApp(
            theme: buildHemoSenseTheme(),
            home: DietScreen(result: _resultWithPlan(null)),
          ),
        ),
      );
      await tester.tap(find.text('Generate my AI diet plan'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Diet planner is overloaded.'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });

  testWidgets('questionnaire loads foods, adds dislikes and saves', (
    tester,
  ) async {
    _tallView(tester);
    late ProviderContainer container;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          p.profileProvider.overrideWith(
            () => _FakeProfile(const UserProfile(age: 24, dietProfile: _dp)),
          ),
          p.dietFoodsProvider.overrideWith(
            (ref) async => const [
              DietFood(fdcId: 1, name: 'Spinach', group: 'Vegetables'),
              DietFood(fdcId: 2, name: 'Chicken liver', group: 'Meat'),
            ],
          ),
        ],
        child: Consumer(
          builder: (context, ref, _) {
            container = ProviderScope.containerOf(context);
            return MaterialApp(
              theme: buildHemoSenseTheme(),
              home: Builder(
                builder: (ctx) => Scaffold(
                  body: TextButton(
                    onPressed: () => Navigator.of(ctx).push(
                      MaterialPageRoute(
                        builder: (_) => const DietQuestionnaireScreen(),
                      ),
                    ),
                    child: const Text('open'),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.text("We'll suggest a replacement for each."), findsOneWidget);
    expect(find.text('Chicken liver'), findsOneWidget);
    await tester.tap(find.text('Chicken liver'));
    await tester.pump();
    await tester.enterText(find.byKey(const Key('dq_custom_dislike')), 'Okra');
    await tester.tap(find.text('Add'));
    await tester.pump();
    await tester.enterText(find.byKey(const Key('dq_budget')), '300');
    await tester.pump();
    await tester.tap(find.byKey(const Key('dq_save')));
    await tester.pumpAndSettle();
    final saved = container.read(p.profileProvider).dietProfile!;
    expect(saved.budgetInrPerDay, 300);
    expect(saved.state, 'Tamil Nadu');
    expect(
      saved.dislikes,
      containsAll(<String>['Spinach', 'bitter gourd', 'Chicken liver', 'Okra']),
    );
    expect(find.text('open'), findsOneWidget); // popped back
  });
}
