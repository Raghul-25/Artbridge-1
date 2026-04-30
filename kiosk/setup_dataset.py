#!/usr/bin/env python3
"""
setup_dataset.py — One-time dataset setup helper.

What this does:
  1. Creates the correct dataset/ folder structure including unknown/
  2. Auto-generates synthetic unknown images from your artbridge_photos/
     by applying extreme distortions (blurring, noise, colour shifts)
  3. Lets you test augmentation by saving 10 preview images

Run BEFORE train.py:
    python3 setup_dataset.py

Then manually add real photos to each folder (see checklist at the end).
"""

import os
import random
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
#  1. CREATE FOLDER STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────
PRODUCT_CLASSES = [
    "bamboo_basket", "ceramic_plate", "clay_pot", "handwoven_mat",
    "jute_bag", "palm_leaf_items", "pottery_vase", "terracotta_statue",
    "traditional_painting", "wooden_carving",
    "unknown",   # ← teaches model what does NOT belong
]


def create_structure(base: str = "dataset") -> None:
    for cls in PRODUCT_CLASSES:
        os.makedirs(os.path.join(base, cls), exist_ok=True)
    print(f"✅  Dataset folders created under ./{base}/")
    print("    Each product folder needs 100–300 real images.")
    print("    unknown/ needs 200–400 diverse non-product images.\n")


# ─────────────────────────────────────────────────────────────────────────────
#  2. GENERATE SYNTHETIC UNKNOWN IMAGES
#     Extreme transforms on existing captured photos so the model learns
#     these highly-distorted inputs do NOT belong to any product class.
# ─────────────────────────────────────────────────────────────────────────────
TRANSFORMS = [
    "extreme_blur",
    "very_dark",
    "very_bright",
    "heavy_noise",
    "corner_crop",
    "solid_colour",
    "flip_blur",
    "posterise",
]


def _apply(img: np.ndarray, transform: str) -> np.ndarray:
    """Apply one extreme transform and return the result (uint8, BGR)."""
    import cv2

    out = img.copy()

    if transform == "extreme_blur":
        k = random.choice([21, 31, 41])
        out = cv2.GaussianBlur(out, (k, k), 0)

    elif transform == "very_dark":
        factor = random.uniform(0.04, 0.18)
        out = (out.astype(np.float32) * factor).clip(0, 255).astype(np.uint8)

    elif transform == "very_bright":
        factor = random.uniform(2.8, 4.5)
        out = (out.astype(np.float32) * factor).clip(0, 255).astype(np.uint8)

    elif transform == "heavy_noise":
        noise = np.random.randint(-90, 90, out.shape, dtype=np.int16)
        out = (out.astype(np.int16) + noise).clip(0, 255).astype(np.uint8)

    elif transform == "corner_crop":
        x = random.randint(0, 150)
        y = random.randint(0, 150)
        patch = out[y:y+70, x:x+70]
        out = cv2.resize(patch, (224, 224))
        out = cv2.GaussianBlur(out, (17, 17), 0)

    elif transform == "solid_colour":
        r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
        out = np.full((224, 224, 3), [b, g, r], dtype=np.uint8)
        noise = np.random.randint(-25, 25, out.shape, dtype=np.int16)
        out = (out.astype(np.int16) + noise).clip(0, 255).astype(np.uint8)

    elif transform == "flip_blur":
        out = cv2.flip(out, 1)
        out = cv2.GaussianBlur(out, (19, 19), 0)

    elif transform == "posterise":
        # Reduce to very few colour levels — looks very unnatural
        levels = random.choice([4, 6, 8])
        step = 256 // levels
        out = (out.astype(np.int32) // step * step).clip(0, 255).astype(np.uint8)

    return out


def generate_synthetic_unknowns(
    source_dir:   str = "artbridge_photos",
    out_dir:      str = "dataset/unknown",
    n_per_image:  int = 4,
) -> None:
    try:
        import cv2
    except ImportError:
        print("⚠️   OpenCV not installed — skipping synthetic unknown generation.")
        return

    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isdir(source_dir):
        print(f"⚠️   {source_dir}/ not found — skipping.")
        return

    photos = [
        f for f in os.listdir(source_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    if not photos:
        print(f"⚠️   No photos in {source_dir}/ — skipping.")
        return

    count = 0
    for fname in photos:
        img = cv2.imread(os.path.join(source_dir, fname))
        if img is None:
            continue
        img = cv2.resize(img, (224, 224))

        chosen = random.sample(TRANSFORMS, min(n_per_image, len(TRANSFORMS)))
        for tf in chosen:
            out   = _apply(img, tf)
            stem  = os.path.splitext(fname)[0]
            oname = f"syn_{stem}_{tf}.jpg"
            cv2.imwrite(os.path.join(out_dir, oname), out)
            count += 1

    print(f"✅  Generated {count} synthetic unknown images → {out_dir}/")


# ─────────────────────────────────────────────────────────────────────────────
#  3. AUGMENTATION PREVIEW  (visual sanity-check)
# ─────────────────────────────────────────────────────────────────────────────
def test_augmentation(
    image_path: str,
    out_dir:    str = "aug_preview",
    n:          int = 10,
) -> None:
    try:
        import cv2
        from tensorflow.keras.preprocessing.image import ImageDataGenerator
    except ImportError:
        print("⚠️   OpenCV / TensorFlow not found — skipping augmentation preview.")
        return

    os.makedirs(out_dir, exist_ok=True)

    img = cv2.imread(image_path)
    if img is None:
        print(f"⚠️   Cannot read {image_path}")
        return

    img = cv2.resize(img, (224, 224))
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    arr = img_rgb.astype(np.float32) / 255.0
    arr = np.expand_dims(arr, 0)

    gen = ImageDataGenerator(
        rotation_range=25,
        width_shift_range=0.12,
        height_shift_range=0.12,
        shear_range=0.10,
        zoom_range=0.20,
        horizontal_flip=True,
        brightness_range=[0.65, 1.35],
        channel_shift_range=20.0,
        fill_mode="nearest",
    ).flow(arr, batch_size=1)

    for i in range(n):
        aug = next(gen)[0]
        aug_bgr = cv2.cvtColor((aug * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        cv2.imwrite(os.path.join(out_dir, f"aug_{i:02d}.jpg"), aug_bgr)

    print(f"✅  {n} augmented preview images saved → {out_dir}/  (review visually)")


# ─────────────────────────────────────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== ArtBridge Dataset Setup ===\n")

    create_structure("dataset")

    generate_synthetic_unknowns(
        source_dir="artbridge_photos",
        out_dir="dataset/unknown",
        n_per_image=4,
    )

    print("\n=== Next steps ===")
    print("[ ] Add 100–300 real photos to each product folder in dataset/")
    print("[ ] Add 200–400 real unknown images to dataset/unknown/")
    print("    Examples: faces, phones, food, plain walls, blurred shots")
    print("[ ] Run:  python3 train.py")
    print("[ ] Copy model.h5 to artbridge_kiosk/")
    print("[ ] Check class order printed by train.py, update CLASSES in ml_service.py")
    print("[ ] Tune thresholds in ml_service.py based on Pi logs")
