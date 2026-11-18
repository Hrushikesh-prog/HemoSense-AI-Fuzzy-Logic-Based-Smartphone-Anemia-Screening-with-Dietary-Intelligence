/// Answers to the diet questionnaire. Stored inside the user profile (Hive)
/// and sent to the backend as `user_context.diet_profile` so the AI diet
/// planner can fit meals to the user's budget, region, kitchen and routine.
library;

/// All 28 states and 8 union territories of India (reference list for the
/// dropdown; not user data).
const kIndianStatesAndUts = <String>[
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chhattisgarh',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
  'Andaman and Nicobar Islands',
  'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi',
  'Jammu and Kashmir',
  'Ladakh',
  'Lakshadweep',
  'Puducherry',
];

/// Budget slider range (₹ per day).
const kBudgetMin = 50.0;
const kBudgetMax = 1000.0;
const kBudgetStep = 10.0;

/// area_type values -> labels.
const kAreaTypes = <String, String>{
  'urban': 'Urban home',
  'rural': 'Rural home',
  'hostel': 'Hostel or PG',
};

/// kitchen values -> labels.
const kKitchenTypes = <String, String>{
  'home': 'Cook at home',
  'shared': 'Shared kitchen',
  'none': 'No kitchen (eat out, canteen, mess)',
};

class DietProfile {
  final double budgetInrPerDay;
  final String state;
  final String city; // optional, '' when not given
  final String areaType; // urban | rural | hostel
  final String kitchen; // home | shared | none
  final bool fridge;
  final List<String> dislikes;
  final bool skipsBreakfast;
  final bool nightShift;

  const DietProfile({
    required this.budgetInrPerDay,
    required this.state,
    this.city = '',
    required this.areaType,
    required this.kitchen,
    this.fridge = false,
    this.dislikes = const [],
    this.skipsBreakfast = false,
    this.nightShift = false,
  });

  /// Tolerant parse of a stored map; null when the essential answers
  /// (budget, state, area, kitchen) are missing or invalid.
  static DietProfile? tryParse(Object? v) {
    if (v is! Map) return null;
    final budget = v['budget_inr_per_day'];
    final state = v['state'];
    final area = v['area_type'];
    final kitchen = v['kitchen'];
    if (budget is! num || budget <= 0) return null;
    if (state is! String || state.trim().isEmpty) return null;
    if (area is! String || !kAreaTypes.containsKey(area)) return null;
    if (kitchen is! String || !kKitchenTypes.containsKey(kitchen)) return null;
    final dislikes = v['dislikes'];
    final city = v['city'];
    return DietProfile(
      budgetInrPerDay: budget.toDouble(),
      state: state.trim(),
      city: city is String ? city.trim() : '',
      areaType: area,
      kitchen: kitchen,
      fridge: v['fridge'] == true,
      dislikes: dislikes is List
          ? dislikes
                .whereType<String>()
                .map((s) => s.trim())
                .where((s) => s.isNotEmpty)
                .toList()
          : const [],
      skipsBreakfast: v['skips_breakfast'] == true,
      nightShift: v['night_shift'] == true,
    );
  }

  /// Wire format (`user_context.diet_profile`), also used for storage.
  Map<String, dynamic> toJson() => {
    'budget_inr_per_day': budgetInrPerDay,
    'state': state,
    if (city.trim().isNotEmpty) 'city': city.trim(),
    'area_type': areaType,
    'kitchen': kitchen,
    'fridge': fridge,
    'dislikes': dislikes,
    'skips_breakfast': skipsBreakfast,
    'night_shift': nightShift,
  };

  /// "₹250" (no decimals when whole).
  String get budgetLabel => '₹${formatInr(budgetInrPerDay)}';
}

/// ₹ amounts: whole numbers without decimals, otherwise one decimal.
String formatInr(double v) =>
    v == v.roundToDouble() ? v.round().toString() : v.toStringAsFixed(1);
