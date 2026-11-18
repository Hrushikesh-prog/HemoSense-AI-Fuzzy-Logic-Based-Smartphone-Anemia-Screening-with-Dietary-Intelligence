import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../theme.dart';
import 'review_screen.dart';

/// ⑦ Camera — full-screen preview with the oval "inner eyelid" overlay,
/// left/right eye toggle, flash toggle and the shutter row. Fires an
/// automatic 3-frame burst with the torch on when supported.
class CameraScreen extends StatefulWidget {
  final List<String> symptoms;
  const CameraScreen({super.key, this.symptoms = const []});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  int _cameraIndex = 0;
  bool _torchOn = false;
  int _burstCount = 0;
  bool _bursting = false;
  bool _settling = false; // waiting for exposure/focus after the torch turns on
  String _eyeSide = 'Left eye';

  @override
  void initState() {
    super.initState();
    _setup();
  }

  Future<void> _setup() async {
    try {
      _cameras = await availableCameras();
    } catch (e) {
      _toast('Camera unavailable ($e). Use the gallery button instead.');
      return;
    }
    if (_cameras.isEmpty) {
      _toast('No camera found on this device. Use the gallery button instead.');
      return;
    }
    if (_cameraIndex >= _cameras.length) _cameraIndex = 0;
    final controller = CameraController(
      _cameras[_cameraIndex],
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );
    try {
      await controller.initialize();
    } catch (e) {
      _toast('Could not start camera ($e). Use the gallery button instead.');
      return;
    }
    if (!mounted) {
      await controller.dispose();
      return;
    }
    setState(() => _controller = controller);
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg), backgroundColor: C.severe));
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _switchCamera() async {
    if (_cameras.length < 2) return;
    setState(() {
      _cameraIndex = (_cameraIndex + 1) % _cameras.length;
      _controller = null;
    });
    await _setup();
  }

  Future<void> _toggleTorch() async {
    final c = _controller;
    if (c == null || !c.value.isInitialized) return;
    try {
      final next = !_torchOn;
      await c.setFlashMode(next ? FlashMode.torch : FlashMode.off);
      if (mounted) setState(() => _torchOn = next);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Torch not available on this camera')));
      }
    }
  }

  Future<void> _startBurst() async {
    final c = _controller;
    if (c == null || !c.value.isInitialized || _bursting) return;
    setState(() {
      _bursting = true;
      _burstCount = 0;
    });
    var torchSwitched = false;
    try {
      final torchWasOn = _torchOn;
      if (!torchWasOn &&
          _cameras[_cameraIndex].lensDirection == CameraLensDirection.back) {
        try {
          await c.setFlashMode(FlashMode.torch);
          torchSwitched = true;
        } catch (_) {}
      }
      // Keep continuous auto focus / auto exposure so the camera re-meters
      // for the new (torch) light.
      try {
        await c.setFocusMode(FocusMode.auto);
      } catch (_) {}
      try {
        await c.setExposureMode(ExposureMode.auto);
      } catch (_) {}
      // Give auto-exposure and focus time to settle after the torch comes on;
      // otherwise frame 1 is often under-exposed and rejected as too dark.
      if (torchSwitched) {
        if (mounted) setState(() => _settling = true);
        await Future<void>.delayed(const Duration(milliseconds: 800));
        if (mounted) setState(() => _settling = false);
      }
      final shots = <XFile>[];
      for (var i = 0; i < 3; i++) {
        final x = await c.takePicture();
        shots.add(XFile(x.path, mimeType: 'image/jpeg'));
        if (mounted) setState(() => _burstCount = i + 1);
        if (i < 2) await Future<void>.delayed(const Duration(milliseconds: 350));
      }
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => ReviewScreen(shots: shots, symptoms: widget.symptoms, eyeSide: _eyeSide)));
    } catch (e) {
      _toast('Capture failed: $e');
    } finally {
      if (torchSwitched) {
        try {
          await c.setFlashMode(FlashMode.off);
        } catch (_) {}
      }
      if (mounted) {
        setState(() {
          _bursting = false;
          _settling = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = _controller;
    final ready = c != null && c.value.isInitialized;

    return Scaffold(
      backgroundColor: const Color(0xFF0C0C0C),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0C0C0C),
        foregroundColor: Colors.white,
        titleSpacing: 0,
        automaticallyImplyLeading: false,
        title: Row(
          children: [
            IconButton(
              icon: const Icon(Icons.close_rounded, size: 20),
              onPressed: () => Navigator.of(context).pop(),
            ),
            const Spacer(),
            _eyeToggle(),
            const Spacer(),
            IconButton(
              icon: Icon(_torchOn ? Icons.bolt_rounded : Icons.bolt_outlined,
                  size: 20),
              onPressed: _toggleTorch,
            ),
          ],
        ),
      ),
      body: Stack(
        fit: StackFit.expand,
        children: [
          if (ready) CameraPreview(c) else const Center(child: CircularProgressIndicator(color: Colors.white)),
          if (ready) ..._overlay(),
          Positioned(
            left: 0,
            right: 0,
            bottom: 14,
            child: Column(
              children: [
                Text(
                  _settling
                      ? 'Hold still, adjusting light…'
                      : _bursting
                      ? 'Capturing $_burstCount/3…'
                      : 'Tap to capture 3 quick frames',
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    GestureDetector(
                      onTap: _bursting
                          ? null
                          : () => pickFromGalleryAndReview(context,
                              symptoms: widget.symptoms, replace: true),
                      child: Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.15),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.photo_library_outlined,
                            color: Colors.white, size: 22),
                      ),
                    ),
                    GestureDetector(
                      onTap: _startBurst,
                      child: Container(
                        width: 62,
                        height: 62,
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 3.5),
                        ),
                        child: Container(
                          decoration: const BoxDecoration(
                              color: Colors.white, shape: BoxShape.circle),
                        ),
                      ),
                    ),
                    GestureDetector(
                      onTap: _switchCamera,
                      child: Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.15),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.cameraswitch_rounded,
                            color: Colors.white, size: 22),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _eyeToggle() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final side in const ['Left eye', 'Right eye'])
            GestureDetector(
              onTap: () => setState(() => _eyeSide = side),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _eyeSide == side ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(side,
                    style: TextStyle(
                        fontSize: 10,
                        fontWeight:
                            _eyeSide == side ? FontWeight.w700 : FontWeight.w400,
                        color: _eyeSide == side ? Colors.black : Colors.white)),
              ),
            ),
        ],
      ),
    );
  }

  List<Widget> _overlay() {
    return [
      // Vignette dim around the oval target
      IgnorePointer(
        child: Container(
          decoration: BoxDecoration(
            gradient: RadialGradient(
              radius: 0.75,
              colors: [Colors.transparent, Colors.transparent, Colors.black.withValues(alpha: 0.55)],
              stops: const [0, 0.55, 0.85],
            ),
          ),
        ),
      ),
      // Oval guide
      Center(
        child: Container(
          width: double.infinity,
          height: 220,
          margin: const EdgeInsets.symmetric(horizontal: 18),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.white, width: 2.5),
            borderRadius: BorderRadius.circular(110),
          ),
        ),
      ),
      // Top hint
      Positioned(
        top: 10,
        left: 0,
        right: 0,
        child: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: Colors.black54,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Text(
              'Fit the pink inner eyelid inside the oval',
              style: TextStyle(color: Colors.white, fontSize: 10),
            ),
          ),
        ),
      ),
    ];
  }
}
