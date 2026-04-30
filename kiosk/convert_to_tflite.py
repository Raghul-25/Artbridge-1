#!/usr/bin/env python3
"""
convert_to_tflite.py — Convert model.h5 → model.tflite

Run this ONCE on a machine with full TensorFlow installed (PC/laptop/cloud).
Copy the resulting model.tflite to your Raspberry Pi.

The Pi only needs  tflite-runtime  to run inference:
    pip install tflite-runtime --break-system-packages

Usage:
    python3 convert_to_tflite.py

Options (edit constants below):
    QUANTIZE = False  → float32 TFLite (same accuracy as .h5, larger file)
    QUANTIZE = True   → int8 quantised  (2-4× smaller, ~2× faster on Pi,
                        tiny accuracy drop — recommended for Pi deployment)

Output:
    model.tflite            → always produced
    model_quantised.tflite  → produced when QUANTIZE=True
"""

import os
import sys
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────
H5_PATH         = "model.h5"
TFLITE_PATH     = "model.tflite"
TFLITE_Q_PATH   = "model_quantised.tflite"

# Set True to also produce an int8-quantised model (faster on Pi, same quality)
QUANTIZE        = True

# Representative dataset directory — used for quantisation calibration.
# Point to your dataset/ folder or artbridge_photos/.
# Only needed when QUANTIZE=True.
DATASET_DIR     = "artbridge_photos"
IMG_SIZE        = 224
CALIBRATION_N   = 50    # how many images to use for calibration (50–200 is fine)


# ─────────────────────────────────────────────────────────────────────────────
#  LOAD MODEL
# ─────────────────────────────────────────────────────────────────────────────
try:
    import tensorflow as tf
except ImportError:
    print("❌  TensorFlow not installed.")
    print("    Install on your PC:  pip install tensorflow")
    sys.exit(1)

if not os.path.exists(H5_PATH):
    print(f"❌  {H5_PATH} not found in current directory.")
    print("    Run this script from the folder that contains model.h5")
    sys.exit(1)

print(f"📂  Loading {H5_PATH} …")
model = tf.keras.models.load_model(H5_PATH, compile=False)
print(f"    Input shape : {model.input_shape}")
print(f"    Output shape: {model.output_shape}")
print(f"    Parameters  : {model.count_params():,}")


# ─────────────────────────────────────────────────────────────────────────────
#  CONVERT — Float32 (no quantisation)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n🔄  Converting to float32 TFLite …")
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()
with open(TFLITE_PATH, "wb") as f:
    f.write(tflite_model)
size_mb = os.path.getsize(TFLITE_PATH) / 1024 / 1024
print(f"✅  Saved  {TFLITE_PATH}  ({size_mb:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
#  VERIFY FLOAT32 MODEL
# ─────────────────────────────────────────────────────────────────────────────
print("\n🔍  Verifying float32 model …")
interp = tf.lite.Interpreter(model_path=TFLITE_PATH)
interp.allocate_tensors()
inp_detail = interp.get_input_details()[0]
out_detail = interp.get_output_details()[0]
print(f"    Input  : shape={inp_detail['shape']}  dtype={inp_detail['dtype']}")
print(f"    Output : shape={out_detail['shape']}  dtype={out_detail['dtype']}")

# Run one dummy inference to confirm it works
dummy = np.random.rand(1, IMG_SIZE, IMG_SIZE, 3).astype(np.float32)
interp.set_tensor(inp_detail["index"], dummy)
interp.invoke()
preds = interp.get_tensor(out_detail["index"])[0]
print(f"    Dummy output sum: {preds.sum():.4f}  (should be ≈ 1.0 for softmax)")
print("    ✅  Float32 model verified.")


# ─────────────────────────────────────────────────────────────────────────────
#  CONVERT — Int8 quantised (optional, recommended for Pi)
# ─────────────────────────────────────────────────────────────────────────────
if QUANTIZE:
    print(f"\n🔄  Converting to int8 quantised TFLite …")
    print(f"    Calibration dataset: {DATASET_DIR}/")

    # Collect representative images for calibration
    import cv2

    cal_images = []
    if os.path.isdir(DATASET_DIR):
        for root, _, files in os.walk(DATASET_DIR):
            for fname in files:
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    path = os.path.join(root, fname)
                    img = cv2.imread(path)
                    if img is None:
                        continue
                    img = cv2.resize(img, (IMG_SIZE, IMG_SIZE))
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img = img.astype(np.float32) / 255.0
                    cal_images.append(img)
                    if len(cal_images) >= CALIBRATION_N:
                        break
            if len(cal_images) >= CALIBRATION_N:
                break

    if not cal_images:
        print(f"    ⚠️   No calibration images found in {DATASET_DIR}/ —")
        print("        using random data (accuracy may be slightly lower).")
        cal_images = [
            np.random.rand(IMG_SIZE, IMG_SIZE, 3).astype(np.float32)
            for _ in range(CALIBRATION_N)
        ]

    print(f"    Using {len(cal_images)} calibration images.")

    def representative_dataset():
        for img in cal_images:
            yield [np.expand_dims(img, axis=0)]

    conv_q = tf.lite.TFLiteConverter.from_keras_model(model)
    conv_q.optimizations = [tf.lite.Optimize.DEFAULT]
    conv_q.representative_dataset = representative_dataset
    conv_q.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv_q.inference_input_type  = tf.uint8
    conv_q.inference_output_type = tf.uint8

    tflite_q = conv_q.convert()
    with open(TFLITE_Q_PATH, "wb") as f:
        f.write(tflite_q)
    size_q_mb = os.path.getsize(TFLITE_Q_PATH) / 1024 / 1024
    print(f"✅  Saved  {TFLITE_Q_PATH}  ({size_q_mb:.1f} MB)")
    print(f"    Size reduction: {size_mb:.1f} MB → {size_q_mb:.1f} MB  "
          f"({(1 - size_q_mb/size_mb)*100:.0f}% smaller)")

    # Verify quantised model
    print("\n🔍  Verifying quantised model …")
    interp_q = tf.lite.Interpreter(model_path=TFLITE_Q_PATH)
    interp_q.allocate_tensors()
    inp_q = interp_q.get_input_details()[0]
    out_q = interp_q.get_output_details()[0]
    print(f"    Input  : shape={inp_q['shape']}  dtype={inp_q['dtype']}")
    print(f"    Output : shape={out_q['shape']}  dtype={out_q['dtype']}")

    dummy_uint8 = np.random.randint(0, 255, (1, IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
    interp_q.set_tensor(inp_q["index"], dummy_uint8)
    interp_q.invoke()
    out_uint8 = interp_q.get_tensor(out_q["index"])[0]
    print(f"    Output range: {out_uint8.min()}–{out_uint8.max()}  (uint8)")
    print("    ✅  Quantised model verified.")


# ─────────────────────────────────────────────────────────────────────────────
#  ACCURACY COMPARISON (optional — only when dataset/ is available)
# ─────────────────────────────────────────────────────────────────────────────
def compare_accuracy():
    """Side-by-side accuracy: Keras h5 vs float32 TFLite vs quantised TFLite."""
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    val_gen = ImageDataGenerator(rescale=1.0/255, validation_split=0.2)
    val_data = val_gen.flow_from_directory(
        "dataset", target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=32, class_mode="categorical",
        subset="validation", shuffle=False,
    )
    if val_data.samples == 0:
        return

    print("\n📊  Accuracy comparison (validation set):")

    # Keras accuracy
    results = model.evaluate(val_data, verbose=0)
    print(f"    Keras h5       : {results[1]*100:.2f}%")

    # TFLite float32 accuracy
    correct = total = 0
    val_data.reset()
    for X, Y in val_data:
        for img, label in zip(X, Y):
            inp_arr = np.expand_dims(img, 0).astype(np.float32)
            interp.set_tensor(inp_detail["index"], inp_arr)
            interp.invoke()
            pred = interp.get_tensor(out_detail["index"])[0]
            if np.argmax(pred) == np.argmax(label):
                correct += 1
            total += 1
        if total >= val_data.samples:
            break
    print(f"    TFLite float32 : {correct/total*100:.2f}%")

    if QUANTIZE:
        correct = total = 0
        val_data.reset()
        scale_in  = inp_q["quantization"][0]
        zp_in     = inp_q["quantization"][1]
        scale_out = out_q["quantization"][0]
        zp_out    = out_q["quantization"][1]
        for X, Y in val_data:
            for img, label in zip(X, Y):
                inp_arr = (np.expand_dims(img, 0) / scale_in + zp_in
                           ).clip(0, 255).astype(np.uint8)
                interp_q.set_tensor(inp_q["index"], inp_arr)
                interp_q.invoke()
                out_arr = interp_q.get_tensor(out_q["index"])[0]
                pred_f  = (out_arr.astype(np.float32) - zp_out) * scale_out
                if np.argmax(pred_f) == np.argmax(label):
                    correct += 1
                total += 1
            if total >= val_data.samples:
                break
        print(f"    TFLite int8    : {correct/total*100:.2f}%")


if os.path.isdir("dataset"):
    compare_accuracy()


# ─────────────────────────────────────────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 56)
print("  CONVERSION COMPLETE")
print("=" * 56)
print(f"  {TFLITE_PATH}")
if QUANTIZE:
    print(f"  {TFLITE_Q_PATH}  ← copy this to Pi for best performance")
print()
print("  On Raspberry Pi:")
print("    1. Copy model.tflite (or model_quantised.tflite renamed to model.tflite)")
print("       to the artbridge_kiosk/ folder.")
print("    2. Install runtime:")
print("       pip install tflite-runtime --break-system-packages")
print("    3. Run the app — ml_service.py will auto-detect tflite_runtime.")
print()
print("  If using quantised model, update ml_service.py _TFLITE_PATH to point")
print("  to model_quantised.tflite, or just rename it to model.tflite.")
