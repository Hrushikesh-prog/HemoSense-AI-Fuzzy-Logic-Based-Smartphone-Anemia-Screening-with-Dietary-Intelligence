"""
quantize.py
Step 3.5 — Model quantization/optimization for on-device (React Native / mobile) deployment.
Produces three TFLite variants so you can trade off size vs accuracy in the paper:
  1. float32 (no quantization, sanity baseline)
  2. float16 (halves size, minimal accuracy loss, good default for this app)
  3. int8 full integer (smallest/fastest, needs a representative dataset, small accuracy hit)

Usage:
    python quantize.py --model_path saved_models/baseline_B_regression_..._final.keras --variant B
"""

import argparse
import os

import numpy as np
import tensorflow as tf

import config
from data_loader import get_datasets


def convert_float32(model_path, out_path):
    model = tf.keras.models.load_model(model_path)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    with open(out_path, "wb") as f:
        f.write(tflite_model)
    return out_path


def convert_float16(model_path, out_path):
    model = tf.keras.models.load_model(model_path)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    with open(out_path, "wb") as f:
        f.write(tflite_model)
    return out_path


def convert_int8(model_path, out_path, variant="B", n_calib_samples=200):
    model = tf.keras.models.load_model(model_path)

    # representative dataset generator required for full-integer quantization
    train_ds, _, _, _ = get_datasets(variant=variant, batch_size=1)

    def representative_dataset():
        count = 0
        for x, _ in train_ds:
            yield [tf.cast(x, tf.float32)]
            count += 1
            if count >= n_calib_samples:
                break

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.uint8
    converter.inference_output_type = tf.float32  # keep regression output as float
    tflite_model = converter.convert()
    with open(out_path, "wb") as f:
        f.write(tflite_model)
    return out_path


def compare_sizes(paths):
    print("\n[quantize] Model size comparison:")
    for p in paths:
        if os.path.exists(p):
            kb = os.path.getsize(p) / 1024
            print(f"  {os.path.basename(p):40s} {kb:8.1f} KB")


def sanity_check_tflite(tflite_path, variant="B", n_samples=20):
    """Run a handful of test-set samples through the .tflite model and report MAE
    vs the same samples' Keras predictions, to catch quantization-induced drift early."""
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    _, _, test_ds, _ = get_datasets(variant=variant, batch_size=1)

    errs = []
    for i, (x, y) in enumerate(test_ds.take(n_samples)):
        inp = x.numpy()
        if input_details[0]["dtype"] == np.uint8:
            inp = (inp * 255).astype(np.uint8)
        else:
            inp = inp.astype(np.float32)
        interpreter.set_tensor(input_details[0]["index"], inp)
        interpreter.invoke()
        pred = interpreter.get_tensor(output_details[0]["index"]).flatten()[0]
        errs.append(abs(pred - y.numpy()[0]))

    print(f"[quantize] {tflite_path}: mean abs diff on {n_samples} samples = {np.mean(errs):.3f} g/dL")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True, help="Path to trained .keras model")
    parser.add_argument("--variant", choices=["A", "B"], default="B")
    args = parser.parse_args()

    stem = os.path.splitext(os.path.basename(args.model_path))[0]
    out_dir = config.MODELS_DIR

    p32 = convert_float32(args.model_path, os.path.join(out_dir, f"{stem}_fp32.tflite"))
    p16 = convert_float16(args.model_path, os.path.join(out_dir, f"{stem}_fp16.tflite"))
    p8 = convert_int8(args.model_path, os.path.join(out_dir, f"{stem}_int8.tflite"), variant=args.variant)

    compare_sizes([args.model_path, p32, p16, p8])

    for p in (p32, p16, p8):
        sanity_check_tflite(p, variant=args.variant)
