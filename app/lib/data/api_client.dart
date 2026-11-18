import 'dart:convert';

import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';

import '../models/profile.dart';
import '../models/screening.dart';
import 'local_store.dart';

/// Error surfaced to the UI.
///
/// [code]: network | timeout | server | bad_image | image_quality | model_unavailable
/// [reason]: for `image_quality`, the server's machine code
///   (too_dark | overexposed | blurry | no_conjunctiva | bad_image).
/// [photoErrors]: per-photo messages from the server, when it sent them.
class ApiException implements Exception {
  final String code;
  final String message;
  final String? reason;
  final List<String> photoErrors;

  const ApiException(this.code, this.message,
      {this.reason, this.photoErrors = const []});

  @override
  String toString() => message;
}

/// Default ROI box (x, y, w, h fractions) — same as the server default.
const kDefaultRoiBox = <double>[0.14, 0.42, 0.72, 0.44];

class ApiClient {
  Dio _dio() {
    final dio = Dio(BaseOptions(
      baseUrl: LocalStore.backendUrl,
      connectTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 60),
      receiveTimeout: const Duration(seconds: 120),
    ));
    return dio;
  }

  /// Maps a Dio failure onto a user-facing [ApiException]. Public so it can
  /// be unit-tested with a synthetic response.
  static ApiException fromDio(DioException e) {
    final status = e.response?.statusCode;
    final body = e.response?.data;
    Object? detail;
    if (body is Map) {
      detail = body['detail'];
    } else if (body is String) {
      // A JSON body that Dio did not decode (e.g. wrong content-type).
      try {
        final decoded = jsonDecode(body);
        detail = decoded is Map ? decoded['detail'] : body;
      } catch (_) {
        detail = body;
      }
    }
    final detailStr = detail is Map || detail is List
        ? jsonEncode(detail)
        : (detail ?? e.message ?? '').toString();

    if (e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout) {
      return const ApiException('network',
          'Could not reach the HemoSense server. Check the backend URL in Settings and that the phone is on the same network.');
    }
    if (e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return const ApiException('timeout',
          'The server took too long to answer. Check the connection and try again.');
    }
    if (status == 503) {
      if (detailStr.contains('model_unavailable')) {
        return const ApiException('model_unavailable',
            'The server is running but the screening model is not loaded. Ask the operator to create models/anfis.json and restart the backend.');
      }
      return const ApiException(
          'model_unavailable', 'The screening service is temporarily unavailable.');
    }
    if (status == 422) {
      // New contract: detail = {code, message, per_image: [...]}
      if (detail is Map) {
        final msg = detail['message'];
        final code = detail['code'];
        final perImage = detail['per_image'];
        final photoErrors = <String>[
          if (perImage is List)
            for (final row in perImage)
              if (row is Map && row['error'] != null) row['error'].toString(),
        ];
        if (msg is String && msg.trim().isNotEmpty) {
          return ApiException('image_quality', msg,
              reason: code is String ? code : null, photoErrors: photoErrors);
        }
      }
      if (detail is String && detail.trim().isNotEmpty) {
        return ApiException('image_quality', detail);
      }
      return const ApiException('image_quality',
          'The photo could not be analysed. Retake it in bright, even light with the lower eyelid gently pulled down, and place the box over the pink inner eyelid.');
    }
    if (status == 413) {
      return const ApiException('bad_image',
          'The photo is too large for the server. Choose a smaller photo or use the in-app camera.');
    }
    if (status == 415) {
      return const ApiException('bad_image',
          'This photo format is not supported. Use a JPEG or PNG photo.');
    }
    if (status == 400) {
      final msg = detailStr.trim().isEmpty
          ? 'The photos could not be processed. Retake them holding the phone steady.'
          : detailStr;
      return ApiException('bad_image', msg);
    }
    if (status != null) {
      return ApiException('server', 'Server error ($status). Please try again in a moment.');
    }
    return const ApiException('network', 'Something went wrong while contacting the server.');
  }

  Future<HealthStatus> health() async {
    try {
      final r = await _dio().get<dynamic>('/health');
      final data = r.data;
      return HealthStatus.fromJson(data is Map<String, dynamic> ? data : const {});
    } on DioException catch (e) {
      throw fromDio(e);
    }
  }

  Future<List<SymptomItem>> symptoms() async {
    try {
      final r = await _dio().get<dynamic>('/symptoms');
      final data = r.data;
      return (data is List ? data : const [])
          .whereType<Map<String, dynamic>>()
          .map(SymptomItem.fromJson)
          .where((s) => s.id.isNotEmpty)
          .toList();
    } on DioException catch (e) {
      throw fromDio(e);
    }
  }

  static DioMediaType _mediaType(XFile f) {
    final mime = (f.mimeType ?? '').toLowerCase();
    final name = f.name.toLowerCase();
    if (mime == 'image/png' || name.endsWith('.png')) return DioMediaType('image', 'png');
    if (mime == 'image/webp' || name.endsWith('.webp')) return DioMediaType('image', 'webp');
    if (mime == 'image/bmp' || name.endsWith('.bmp')) return DioMediaType('image', 'bmp');
    return DioMediaType('image', 'jpeg');
  }

  /// Builds the `data` JSON string for `/screen/batch`.
  static String buildScreenData({
    required Map<String, dynamic> userContext,
    required List<List<double>> roiBoxes,
  }) =>
      jsonEncode({'user_context': userContext, 'roi_boxes': roiBoxes});

  /// Uploads 1-10 photos with one ROI box each ([x, y, w, h] fractions of the
  /// photo as displayed) and the profile context.
  Future<BatchScreening> screenBatch({
    required List<XFile> files,
    required UserProfile profile,
    List<List<double>>? roiBoxes,
    List<String> symptoms = const [],
  }) async {
    if (files.isEmpty) {
      throw const ApiException('bad_image', 'Take or choose at least one photo.');
    }
    final userContext = profile.toUserContext();
    if (symptoms.isNotEmpty) userContext['symptoms'] = symptoms;
    final boxes = <List<double>>[
      for (var i = 0; i < files.length; i++)
        (roiBoxes != null && i < roiBoxes.length && roiBoxes[i].length == 4)
            ? roiBoxes[i].map((v) => v.clamp(0.0, 1.0).toDouble()).toList()
            : kDefaultRoiBox,
    ];
    final data = buildScreenData(userContext: userContext, roiBoxes: boxes);

    final parts = <MapEntry<String, MultipartFile>>[];
    try {
      for (var i = 0; i < files.length; i++) {
        final f = files[i];
        final name = f.name.isEmpty ? 'photo_${i + 1}.jpg' : f.name;
        parts.add(MapEntry(
            'images',
            MultipartFile.fromBytes(await f.readAsBytes(),
                filename: name, contentType: _mediaType(f))));
      }
    } catch (_) {
      throw const ApiException(
          'bad_image', 'One of the photos could not be read from the phone. Please retake it.');
    }
    final form = FormData()
      ..files.addAll(parts)
      ..fields.add(MapEntry('data', data));
    try {
      final r = await _dio().post<dynamic>('/screen/batch', data: form);
      final body = r.data;
      if (body is! Map<String, dynamic>) {
        throw const ApiException('server', 'The server sent an unexpected answer. Check the backend URL in Settings.');
      }
      return BatchScreening.fromJson(body);
    } on DioException catch (e) {
      throw fromDio(e);
    }
  }

  /// Foods the planner knows (`GET /diet/foods`), used for the dislikes
  /// chips in the diet questionnaire.
  Future<List<DietFood>> dietFoods() async {
    try {
      final r = await _dio().get<dynamic>('/diet/foods');
      var data = r.data;
      if (data is Map && data['foods'] is List) data = data['foods'];
      final seen = <String>{};
      return (data is List ? data : const [])
          .whereType<Map>()
          .map((m) => DietFood.fromJson(
              m.map((k, v) => MapEntry(k.toString(), v))))
          .where((f) => f.name.isNotEmpty && seen.add(f.name.toLowerCase()))
          .toList();
    } on DioException catch (e) {
      throw fromDiet(e);
    }
  }

  /// JSON body for `POST /diet/plan`. The profile's `user_context` carries
  /// the diet questionnaire answers as `diet_profile`. Only the grade is
  /// sent, never an Hb value.
  static Map<String, dynamic> buildDietPlanBody({
    required UserProfile profile,
    required String severity,
    required bool anemic,
  }) =>
      {
        'user_context': profile.toUserContext(),
        'severity_class': severity,
        'anemic': anemic,
      };

  /// AI-personalised diet plan (`POST /diet/plan`). The AI can be slow, so
  /// the receive timeout is 90 s.
  Future<DietPlan> dietPlan({
    required UserProfile profile,
    required String severity,
    required bool anemic,
  }) async {
    final dio = _dio()..options.receiveTimeout = const Duration(seconds: 90);
    try {
      final r = await dio.post<dynamic>(
        '/diet/plan',
        data: jsonEncode(
            buildDietPlanBody(profile: profile, severity: severity, anemic: anemic)),
        options: Options(contentType: Headers.jsonContentType),
      );
      var body = r.data;
      if (body is String) {
        try {
          body = jsonDecode(body);
        } catch (_) {}
      }
      if (body is! Map) {
        throw const ApiException('server',
            'The server sent an unexpected answer. Check the backend URL in Settings.');
      }
      final map = body.map((k, v) => MapEntry(k.toString(), v));
      // Accept either the plan itself or {"diet_plan": {...}}.
      final inner = map['diet_plan'];
      return DietPlan.fromJson(inner is Map
          ? inner.map((k, v) => MapEntry(k.toString(), v))
          : map);
    } on DioException catch (e) {
      throw fromDiet(e);
    }
  }

  /// Error mapping for the diet endpoints: prefer the server's own message
  /// (`detail` string or `detail.message`) over the generic screening texts.
  static ApiException fromDiet(DioException e) {
    if (e.response == null) return fromDio(e);
    final status = e.response!.statusCode;
    Object? body = e.response!.data;
    if (body is String) {
      try {
        body = jsonDecode(body);
      } catch (_) {}
    }
    Object? detail = body is Map ? (body['detail'] ?? body['message']) : null;
    if (detail is Map) detail = detail['message'];
    if (detail is String && detail.trim().isNotEmpty) {
      return ApiException('server', detail.trim());
    }
    if (status == 404) {
      return const ApiException('server',
          'This server does not offer AI diet plans yet. Update the backend and try again.');
    }
    if (status == 503) {
      return const ApiException('server',
          'The diet planning service is temporarily unavailable. Try again in a moment.');
    }
    return fromDio(e);
  }

  /// Optional LLM dietary intelligence (`POST /diet/recommendations`).
  /// Only the grade is sent — never an Hb value.
  Future<({String text, String model, List<TipSource> sources})> dietRecommendations({
    required String severity,
    required bool anemic,
    required UserProfile profile,
  }) async {
    final data = jsonEncode({
      'screening': {
        'severity_class': severity,
        'anemic': anemic,
      },
      'user_context': profile.toUserContext(),
    });
    final form = FormData.fromMap(<String, Object?>{'data': data});
    try {
      final r = await _dio().post<dynamic>('/diet/recommendations', data: form);
      final body = r.data is Map ? r.data as Map : const {};
      return (
        text: body['recommendations'] is String ? body['recommendations'] as String : '',
        model: body['model_used'] is String ? body['model_used'] as String : '',
        sources: body['sources'] is List
            ? (body['sources'] as List)
                .whereType<Map>()
                .map(TipSource.fromJson)
                .where((s) => s.source.isNotEmpty)
                .toList()
            : const <TipSource>[],
      );
    } on DioException catch (e) {
      throw fromDio(e);
    }
  }
}

/// A guideline excerpt the AI tips were grounded on (RAG), cited in the text as [S1], [S2]...
class TipSource {
  final String ref;
  final String source;
  final int? page;
  const TipSource({required this.ref, required this.source, this.page});

  factory TipSource.fromJson(Map m) => TipSource(
        ref: m['ref'] is String ? m['ref'] as String : '',
        source: m['source'] is String ? m['source'] as String : '',
        page: m['page'] is num ? (m['page'] as num).toInt() : null,
      );
}
