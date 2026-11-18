import 'diet_profile.dart';

/// User profile captured during setup. Sent to the backend as `user_context`
/// and used to personalise the diet plan. Never leaves the device except as
/// request metadata with a screening or a diet-plan request.
class UserProfile {
  final int? age;
  final String sex; // male | female | other
  final bool pregnant;
  final String diet; // omnivore | vegetarian | vegan
  final String allergies; // comma-separated free text

  /// Diet questionnaire answers; null until the user fills it in.
  final DietProfile? dietProfile;

  const UserProfile({
    this.age,
    this.sex = 'female',
    this.pregnant = false,
    this.diet = 'omnivore',
    this.allergies = '',
    this.dietProfile,
  });

  /// Tolerant: profiles saved by older versions (no diet questionnaire) and
  /// oddly-typed values still load.
  factory UserProfile.fromMap(Map<String, dynamic> m) {
    final age = m['age'];
    final sex = m['sex'];
    final pregnant = m['pregnant'];
    final diet = m['diet'];
    final allergies = m['allergies'];
    return UserProfile(
      age: age is num ? age.toInt() : null,
      sex: sex is String ? sex : 'female',
      pregnant: pregnant is bool ? pregnant : false,
      diet: diet is String ? diet : 'omnivore',
      allergies: allergies is String ? allergies : '',
      dietProfile: DietProfile.tryParse(m['diet_profile']),
    );
  }

  Map<String, dynamic> toMap() => {
    if (age != null) 'age': age,
    'sex': sex,
    'pregnant': pregnant,
    'diet': diet,
    'allergies': allergies,
    if (dietProfile != null) 'diet_profile': dietProfile!.toJson(),
  };

  UserProfile copyWith({
    int? age,
    String? sex,
    bool? pregnant,
    String? diet,
    String? allergies,
    DietProfile? dietProfile,
  }) => UserProfile(
    age: age ?? this.age,
    sex: sex ?? this.sex,
    pregnant: pregnant ?? this.pregnant,
    diet: diet ?? this.diet,
    allergies: allergies ?? this.allergies,
    dietProfile: dietProfile ?? this.dietProfile,
  );

  /// Context payload expected by the API (`POST /screen/batch` `data` field,
  /// `POST /diet/plan`, `POST /diet/recommendations`).
  Map<String, dynamic> toUserContext() => {
    if (age != null) 'age': age,
    if (sex == 'male' || sex == 'female') 'sex': sex,
    if (sex == 'female' && pregnant) 'pregnant': true,
    'diet': diet,
    if (allergies.trim().isNotEmpty)
      'allergies': allergies
          .split(',')
          .map((a) => a.trim())
          .where((a) => a.isNotEmpty)
          .toList(),
    if (dietProfile != null) 'diet_profile': dietProfile!.toJson(),
  };

  bool get isComplete => age != null && age! > 0;

  bool get hasDietProfile => dietProfile != null;
}
