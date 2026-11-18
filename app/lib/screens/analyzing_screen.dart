import 'dart:async';

import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';
import '../providers.dart' as p;
import '../theme.dart';
import '../widgets/ui.dart';
import 'result_screen.dart';
import 'error_screen.dart';

/// ⑨ Analyzing — circular progress + the backend pipeline steps as a
/// checklist (simulated while the single batch API call runs).
class AnalyzingScreen extends ConsumerStatefulWidget {
  final List<XFile> shots;
  final List<List<double>>? roiBoxes; // one [x, y, w, h] per shot
  final List<String> symptoms;
  final String eyeSide;
  const AnalyzingScreen({
    super.key,
    required this.shots,
    this.roiBoxes,
    this.symptoms = const [],
    this.eyeSide = 'Left eye',
  });

  @override
  ConsumerState<AnalyzingScreen> createState() => _AnalyzingScreenState();
}

class _AnalyzingScreenState extends ConsumerState<AnalyzingScreen> {
  static const _steps = [
    'Uploading images securely',
    'Checking light & focus',
    'Finding the inner eyelid in your box',
    'Fuzzy (ANFIS) colour analysis',
    'Building your diet plan',
  ];
  int _step = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 900), (t) {
      if (_step < _steps.length - 1 && mounted) setState(() => _step++);
    });
    _run();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _run() async {
    try {
      final client = ref.read(p.apiClientProvider);
      final profile = ref.read(p.profileProvider);
      final result = await client.screenBatch(
          files: widget.shots,
          roiBoxes: widget.roiBoxes,
          profile: profile,
          symptoms: widget.symptoms);
      _timer?.cancel();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => ResultScreen(result: result)));
    } on ApiException catch (e) {
      _timer?.cancel();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => _error(e)));
    } catch (e) {
      _timer?.cancel();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => _error(ApiException(
              'server', 'Unexpected error while reading the result ($e). Please try again.'))));
    }
  }

  ErrorScreen _error(ApiException e) => ErrorScreen(
        failure: e,
        shots: widget.shots,
        roiBoxes: widget.roiBoxes,
        symptoms: widget.symptoms,
        eyeSide: widget.eyeSide,
      );

  @override
  Widget build(BuildContext context) {
    final progress = (_step + 1) / _steps.length;
    return Scaffold(
      appBar: AppBar(title: const Text('Analyzing')),
      body: Column(
        children: [
          Expanded(
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 130,
                    height: 130,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        SizedBox(
                          width: 130,
                          height: 130,
                          child: CircularProgressIndicator(
                            value: progress,
                            strokeWidth: 10,
                            color: C.primary,
                            backgroundColor: const Color(0xFFF2E4E8),
                            strokeCap: StrokeCap.round,
                          ),
                        ),
                        Text('${(progress * 100).round()}%',
                            style: const TextStyle(
                                fontSize: 19,
                                fontWeight: FontWeight.w800,
                                color: C.primaryDark)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  const Text('Analyzing your scan',
                      style: TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 3),
                  const Text('Usually takes 5–15 seconds',
                      style: TextStyle(fontSize: 10.5, color: C.muted)),
                  const SizedBox(height: 16),
                  Container(
                    width: 260,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: C.outline),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Column(
                      children: [
                        for (var i = 0; i < _steps.length; i++)
                          _stepRow(_steps[i], i <= _step, i == _step),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          DisclaimerFooter(),
        ],
      ),
    );
  }

  Widget _stepRow(String text, bool done, bool active) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          done
              ? Container(
                  width: 18,
                  height: 18,
                  decoration: const BoxDecoration(
                      color: C.ok, shape: BoxShape.circle),
                  child: const Icon(Icons.check, size: 11, color: Colors.white),
                )
              : Container(
                  width: 16,
                  height: 16,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                        color: active ? C.primary : const Color(0xFFDCCBD1),
                        width: 2),
                  ),
                ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(text,
                style: TextStyle(
                    fontSize: 11,
                    color: done || active ? C.text : C.muted,
                    fontWeight: active ? FontWeight.w700 : FontWeight.w400)),
          ),
        ],
      ),
    );
  }
}
