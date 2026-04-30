#!/usr/bin/env python3
"""
ml_service.py — ArtBridge ML inference using TFLite Runtime.

Runs on Raspberry Pi with:
    pip install tflite-runtime --break-system-packages

Model file: model.tflite  (same folder as this script)
Converted from model.h5 via convert_to_tflite.py

═══════════════════════════════════════════════════════════════
  3-LAYER UNKNOWN / OPEN-SET REJECTION
═══════════════════════════════════════════════════════════════
  Layer 1 — PRIMARY CONFIDENCE GATE
      top-product confidence ≥ CONF_THRESHOLD (default 0.45)

  Layer 2 — CONFUSION MARGIN CHECK
      (top-1 prob) − (top-2 prob) ≥ MARGIN_THRESHOLD (default 0.15)

  Layer 3 — ENTROPY CHECK
      Shannon entropy of softmax ≤ ENTROPY_THRESHOLD (default 1.8)
      (11-class max entropy ≈ 2.40)

If ANY layer fails → returns ("Artisan Product", hint_text)
screens_main.py treats "Artisan Product" as the NOT-RECOGNISED sentinel.
═══════════════════════════════════════════════════════════════
"""

import os
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURABLE THRESHOLDS  — adjust after reading Pi console logs
# ─────────────────────────────────────────────────────────────────────────────
CONF_THRESHOLD:    float = 0.45   # min confidence for top product class
MARGIN_THRESHOLD:  float = 0.15   # min gap between top-1 and top-2
ENTROPY_THRESHOLD: float = 1.8    # max allowed softmax entropy

BACKGROUND_IDX: int = 0           # class index of 'background'

# ─────────────────────────────────────────────────────────────────────────────
#  CLASS LABELS  — alphabetical order (must match training dataset folders)
# ─────────────────────────────────────────────────────────────────────────────
CLASSES = [
    'background',            # 0
    'bamboo_basket',         # 1
    'ceramic_plate',         # 2
    'clay_pot',              # 3
    'handwoven_mat',         # 4
    'jute_bag',              # 5
    'palm_leaf_items',       # 6
    'pottery_vase',          # 7
    'terracotta_statue',     # 8
    'traditional_painting',  # 9
    'wooden_carving',        # 10
]

# ─────────────────────────────────────────────────────────────────────────────
#  DISPLAY NAMES & DESCRIPTIONS
# ─────────────────────────────────────────────────────────────────────────────
DISPLAY_NAMES = {
    'bamboo_basket':        'Bamboo Basket',
    'ceramic_plate':        'Ceramic Plate',
    'clay_pot':             'Clay Pot',
    'handwoven_mat':        'Handwoven Mat',
    'jute_bag':             'Jute Bag',
    'palm_leaf_items':      'Palm Leaf Item',
    'pottery_vase':         'Pottery Vase',
    'terracotta_statue':    'Terracotta Statue',
    'traditional_painting': 'Traditional Painting',
    'wooden_carving':       'Wooden Carving',
}

DESCRIPTIONS = {
    'bamboo_basket': (
        "A traditional handcrafted bamboo basket made by rural artisans using "
        "natural bamboo strips woven through techniques passed down through "
        "generations. Eco-friendly, lightweight, and highly durable — ideal "
        "for carrying vegetables, storing goods, and household organisation."
    ),
    'ceramic_plate': (
        "A handcrafted ceramic plate shaped with precision by skilled artisans, "
        "fired in a kiln for strength and durability. Decorated with artistic "
        "designs and glazing, these plates are both functional and decorative — "
        "perfect for serving food and enhancing dining experiences."
    ),
    'clay_pot': (
        "A traditional handcrafted clay pot made from natural clay on a potter's "
        "wheel. Widely used for cooking and storing water due to its natural "
        "cooling properties. Eco-friendly and biodegradable, representing "
        "centuries of Indian cultural heritage and sustainable living."
    ),
    'handwoven_mat': (
        "A traditional handwoven mat crafted using natural fibres such as grass, "
        "reeds, or palm leaves. Durable, flexible, and eco-friendly — commonly "
        "used for sitting, sleeping, or as decorative floor coverings. Reflects "
        "the cultural identity and craftsmanship of rural communities."
    ),
    'jute_bag': (
        "An eco-friendly jute bag made from natural jute fibres — strong, "
        "biodegradable, and renewable. Handcrafted as a sustainable alternative "
        "to plastic bags. Durable enough for heavy items, ideal for shopping "
        "and daily use, supporting rural livelihoods."
    ),
    'palm_leaf_items': (
        "Handcrafted products made from dried palm leaves, skillfully woven by "
        "rural artisans into baskets, containers, and decorative pieces. "
        "Lightweight, biodegradable, and environmentally friendly — an excellent "
        "alternative to synthetic materials."
    ),
    'pottery_vase': (
        "A decorative pottery vase handcrafted from clay using traditional "
        "techniques, dried and kiln-fired for durability. Features intricate "
        "patterns or painted designs — used for holding flowers or as a "
        "decorative piece in homes and offices."
    ),
    'terracotta_statue': (
        "A traditional terracotta sculpture handcrafted from natural clay, baked "
        "at high temperatures for strength. Used for decoration, religious "
        "purposes, and cultural representation. Each piece reflects the artisan's "
        "creativity and centuries of Indian artistic heritage."
    ),
    'traditional_painting': (
        "A handcrafted traditional painting created using cultural art styles and "
        "techniques. Depicts historical stories, religious themes, or everyday "
        "life using natural or synthetic colours with intricate regional designs. "
        "Each painting is unique and carries significant cultural meaning."
    ),
    'wooden_carving': (
        "A handcrafted wooden carving shaped by skilled artisans using specialised "
        "tools to create intricate designs and sculptures. Can include furniture, "
        "decorative items, or artistic pieces. Reflects traditional motifs and "
        "cultural themes with precision and craftsmanship."
    ),
}

# Sentinel — "Artisan Product" is the NOT-RECOGNISED signal to screens_main.py
_UNKNOWN = (
    "Artisan Product",
    "A unique handcrafted product made by a skilled rural artisan using "
    "traditional techniques and natural materials. Place the product clearly "
    "in front of the camera with good lighting for a better result.",
)

_DIR        = os.path.dirname(os.path.abspath(__file__))
_TFLITE_PATH = os.path.join(_DIR, "model.tflite")
_H5_PATH     = os.path.join(_DIR, "model.h5")      # fallback for dev machines


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER — Shannon entropy
# ─────────────────────────────────────────────────────────────────────────────
def _entropy(probs: np.ndarray) -> float:
    """H = -Σ p·ln(p).  Range 0 (perfect) → ln(11)≈2.40 (uniform/confused)."""
    safe = np.clip(probs, 1e-9, 1.0)
    return float(-np.sum(safe * np.log(safe)))


# ─────────────────────────────────────────────────────────────────────────────
#  DETECTOR CLASS
# ─────────────────────────────────────────────────────────────────────────────
class ArtisanDetector:
    """
    TFLite-based inference with 3-layer open-set rejection.

    Load order:
      1. model.tflite via tflite_runtime  (Raspberry Pi — fast, lightweight)
      2. model.tflite via tensorflow.lite (full TF install on dev machine)
      3. model.h5     via tensorflow.keras (dev machine fallback)
    """

    def __init__(
        self,
        tflite_path:       str   = _TFLITE_PATH,
        h5_path:           str   = _H5_PATH,
        conf_threshold:    float = CONF_THRESHOLD,
        margin_threshold:  float = MARGIN_THRESHOLD,
        entropy_threshold: float = ENTROPY_THRESHOLD,
    ):
        self._tflite_path      = tflite_path
        self._h5_path          = h5_path
        self._conf_threshold   = conf_threshold
        self._margin_threshold = margin_threshold
        self._entropy_threshold = entropy_threshold

        # Runtime state — only one of these will be set
        self._interpreter = None   # TFLite interpreter
        self._keras_model = None   # Keras model (dev fallback only)
        self._backend     = None   # "tflite_runtime" | "tf_lite" | "keras" | None

        # TFLite tensor details (set after loading)
        self._input_details  = None
        self._output_details = None

        self._load_model()

    # ── Model loading — tries 3 backends ─────────────────────────────────────

    def _load_model(self):
        if self._try_tflite_runtime():
            return
        if self._try_tensorflow_lite():
            return
        if self._try_keras_h5():
            return
        print("[ML] ❌  No inference backend could be loaded.")

    def _try_tflite_runtime(self) -> bool:
        """tflite-runtime — the lightweight Pi package."""
        if not os.path.exists(self._tflite_path):
            print(f"[ML] model.tflite not found at {self._tflite_path}")
            return False
        try:
            from tflite_runtime.interpreter import Interpreter
            interp = Interpreter(model_path=self._tflite_path)
            interp.allocate_tensors()
            self._interpreter    = interp
            self._input_details  = interp.get_input_details()
            self._output_details = interp.get_output_details()
            self._backend        = "tflite_runtime"
            print(f"[ML] ✅  Backend : tflite_runtime  ({self._tflite_path})")
            self._log_thresholds()
            return True
        except Exception as exc:
            print(f"[ML]    tflite_runtime unavailable: {exc}")
            return False

    def _try_tensorflow_lite(self) -> bool:
        """tensorflow.lite.Interpreter — full TF install."""
        if not os.path.exists(self._tflite_path):
            return False
        try:
            import tensorflow as tf
            interp = tf.lite.Interpreter(model_path=self._tflite_path)
            interp.allocate_tensors()
            self._interpreter    = interp
            self._input_details  = interp.get_input_details()
            self._output_details = interp.get_output_details()
            self._backend        = "tf_lite"
            print(f"[ML] ✅  Backend : tensorflow.lite  ({self._tflite_path})")
            self._log_thresholds()
            return True
        except Exception as exc:
            print(f"[ML]    tensorflow.lite unavailable: {exc}")
            return False

    def _try_keras_h5(self) -> bool:
        """Full Keras model — dev machine fallback only."""
        if not os.path.exists(self._h5_path):
            return False
        try:
            import tensorflow as tf
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
            self._keras_model = tf.keras.models.load_model(
                self._h5_path, compile=False
            )
            self._backend = "keras"
            print(f"[ML] ✅  Backend : keras h5  ({self._h5_path})")
            print("[ML]    ⚠️  For Raspberry Pi, run convert_to_tflite.py first!")
            self._log_thresholds()
            return True
        except Exception as exc:
            print(f"[ML]    keras h5 unavailable: {exc}")
            return False

    def _log_thresholds(self):
        print(f"[ML]    conf≥{self._conf_threshold}  "
              f"margin≥{self._margin_threshold}  "
              f"entropy≤{self._entropy_threshold}")

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, image_path: str) -> tuple:
        """
        Returns (display_name, description).
        Returns _UNKNOWN sentinel when image is unrecognised.
        """
        if self._backend is None:
            return _UNKNOWN
        if not image_path or image_path == "placeholder":
            return _UNKNOWN
        if not os.path.exists(image_path):
            print(f"[ML] Image not found: {image_path}")
            return _UNKNOWN
        try:
            return self._run_inference(image_path)
        except Exception as exc:
            print(f"[ML] Inference error: {exc}")
            return _UNKNOWN

    # ── Inference ─────────────────────────────────────────────────────────────

    def _preprocess(self, image_path: str) -> np.ndarray:
        """Load image, resize to 224×224, normalise 0-1, add batch dim."""
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"cv2.imread failed: {image_path}")
        img = cv2.resize(img, (224, 224))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        return np.expand_dims(img, axis=0)          # (1, 224, 224, 3)

    def _forward(self, img_batch: np.ndarray) -> np.ndarray:
        """Run forward pass via whichever backend loaded."""
        if self._backend in ("tflite_runtime", "tf_lite"):
            # TFLite interpreter path
            inp = self._input_details[0]

            # Handle quantised models (uint8 input tensor)
            if inp["dtype"] == np.uint8:
                scale, zero_point = inp["quantization"]
                img_batch = (img_batch / scale + zero_point).astype(np.uint8)
            else:
                img_batch = img_batch.astype(inp["dtype"])

            self._interpreter.set_tensor(inp["index"], img_batch)
            self._interpreter.invoke()

            out = self._output_details[0]
            preds = self._interpreter.get_tensor(out["index"])[0]

            # De-quantise uint8 output if needed
            if out["dtype"] == np.uint8:
                scale, zero_point = out["quantization"]
                preds = (preds.astype(np.float32) - zero_point) * scale

            return preds.astype(np.float32)

        elif self._backend == "keras":
            return self._keras_model.predict(img_batch, verbose=0)[0]

        raise RuntimeError("No backend loaded")

    def _run_inference(self, image_path: str) -> tuple:
        img   = self._preprocess(image_path)
        preds = self._forward(img)                   # shape: (num_classes,)

        # Suppress background class
        product = preds.copy()
        product[BACKGROUND_IDX] = 0.0

        ranked    = np.argsort(product)[::-1]
        top1_idx  = int(ranked[0])
        top2_idx  = int(ranked[1])
        top1_conf = float(product[top1_idx])
        margin    = top1_conf - float(product[top2_idx])
        ent       = _entropy(preds)
        label     = CLASSES[top1_idx]

        # Diagnostic log
        print("[ML] ─────────────────────────────────────")
        for rank, idx in enumerate(ranked[:4], 1):
            bar = "█" * int(product[idx] * 25)
            print(f"[ML]   #{rank} {CLASSES[idx]:25s} {product[idx]:.3f}  {bar}")
        ok_conf   = top1_conf >= self._conf_threshold
        ok_margin = margin    >= self._margin_threshold
        ok_ent    = ent       <= self._entropy_threshold
        print(f"[ML] Confidence {top1_conf:.3f} ({'✅' if ok_conf else '❌'}≥{self._conf_threshold})  "
              f"Margin {margin:.3f} ({'✅' if ok_margin else '❌'}≥{self._margin_threshold})  "
              f"Entropy {ent:.3f} ({'✅' if ok_ent else '❌'}≤{self._entropy_threshold})")

        # Layer 1 — confidence
        if not ok_conf:
            print(f"[ML] ❌ UNKNOWN  (low confidence)")
            return _UNKNOWN

        # Layer 2 — margin
        if not ok_margin:
            print(f"[ML] ❌ UNKNOWN  (confused: {CLASSES[top1_idx]} vs {CLASSES[top2_idx]})")
            return _UNKNOWN

        # Layer 3 — entropy
        if not ok_ent:
            print(f"[ML] ❌ UNKNOWN  (high entropy)")
            return _UNKNOWN

        print(f"[ML] ✅ ACCEPTED  {label}  [{self._backend}]")
        return DISPLAY_NAMES.get(label, "Artisan Product"), DESCRIPTIONS.get(label, _UNKNOWN[1])


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────
detector = ArtisanDetector()
