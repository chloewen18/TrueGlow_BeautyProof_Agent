#!/usr/bin/env python3
"""
Hard-Negative Generation Pipeline for TrueGlow 映真
====================================================
Generates realistic social-media-style image degradations from a set of
clean, unretouched portraits.  EVERY output image is labeled
`digital_retouch=0` because the pipeline deliberately avoids any
skin-smoothing / beautification operators.

Supported perturbations (per clean image):
    1. jpeg            - JPEG re-compression at quality factors 30/50/70
    2. denoise         - bilateral filter emulating in-camera noise reduction
    3. softlight       - gaussian-blur overlay simulating ambient soft light
    4. resize          - downsample then upsample (platform thumbnail re-open)
    5. exposure_hdr    - brighten / darken / local tone-curve adjustments
    6. depth_of_field  - background blur while keeping the face in focus

Run:
    python hard_negative_pipeline.py \
        --input_dir  ./raw_portraits \
        --output_dir ./hard_negatives \
        --metadata   ./hard_negatives.csv

Requirements:
    opencv-python, numpy, Pillow
"""

import argparse
import csv
import os
from pathlib import Path
from typing import Callable, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageFilter


# ---------------------------------------------------------------------------
# Safety guard: refuse to load images that already look retouched
# ---------------------------------------------------------------------------

SKIN_SMOOTHING_KEYWORDS = (
    "smooth", "beauty", "retouch", "磨皮", "美颜", "beautify",
    "facetune", "meitu", "airbrush", "perfect365",
)


def looks_like_retouched_path(path: Path) -> bool:
    """Heuristic rejection of filenames that hint at prior retouching."""
    lowered = path.name.lower()
    return any(k in lowered for k in SKIN_SMOOTHING_KEYWORDS)


# ---------------------------------------------------------------------------
# Perturbation helpers (NO skin-smoothing / bilateral-on-skin-only tricks)
# ---------------------------------------------------------------------------

def apply_jpeg_compression(img: np.ndarray, quality: int) -> np.ndarray:
    """Re-encode the image as JPEG at the given quality factor."""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, enc = cv2.imencode(".jpg", img, encode_param)
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)


def apply_bilateral_denoise(img: np.ndarray, d: int = 9,
                            sigma_color: float = 75,
                            sigma_space: float = 75) -> np.ndarray:
    """
    Bilateral filter approximating phone-camera noise reduction.
    Applied to the WHOLE image, NOT only skin regions.
    """
    return cv2.bilateralFilter(img, d, sigma_color, sigma_space)


def apply_softlight(img: np.ndarray, blur_radius: int = 31,
                    opacity: float = 0.25) -> np.ndarray:
    """
    Overlay a heavily blurred copy onto the original to mimic soft ambient
    lighting / a beauty dish.  This changes global/local contrast but does
    NOT remove skin texture the way skin-smoothing does.
    """
    # Convert to PIL, blur, convert back
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    blurred = pil.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    blurred_np = cv2.cvtColor(np.array(blurred), cv2.COLOR_RGB2BGR)

    # Soft-light blend: result = 2*base*blend  when blend<0.5 else 1-2*(1-base)*(1-blend)
    base = img.astype(np.float32) / 255.0
    blend = blurred_np.astype(np.float32) / 255.0
    mask = blend < 0.5
    result = np.zeros_like(base)
    result[mask] = 2 * base[mask] * blend[mask]
    result[~mask] = 1 - 2 * (1 - base[~mask]) * (1 - blend[~mask])
    result = cv2.addWeighted(base, 1.0 - opacity, result, opacity, 0)
    return (np.clip(result, 0, 1) * 255).astype(np.uint8)


def apply_resize_upscale(img: np.ndarray, downscale_factor: float = 0.25,
                         interpolation_down=cv2.INTER_AREA,
                         interpolation_up=cv2.INTER_CUBIC) -> np.ndarray:
    """Downsample then upscale to mimic a platform thumbnail being reopened."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (int(w * downscale_factor), int(h * downscale_factor)),
                       interpolation=interpolation_down)
    return cv2.resize(small, (w, h), interpolation=interpolation_up)


def apply_exposure_hdr(img: np.ndarray, mode: str = "brighten") -> np.ndarray:
    """
    Tone-curve adjustments.  Modes: brighten, darken, highlight.
    These are global/region-agnostic, NOT local skin brightening.
    """
    img_f = img.astype(np.float32) / 255.0
    if mode == "brighten":
        gamma = 0.75
        out = np.power(img_f, gamma)
    elif mode == "darken":
        gamma = 1.3
        out = np.power(img_f, gamma)
    elif mode == "highlight":
        # S-curve: lift shadows, compress highlights (HDR-ish)
        out = (img_f ** 2) * (3 - 2 * img_f)
    else:
        raise ValueError(f"Unknown exposure mode: {mode}")
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def apply_shallow_dof(img: np.ndarray, face_bbox: Tuple[int, int, int, int] = None,
                      blur_strength: int = 21) -> np.ndarray:
    """
    Gaussian blur the whole image then blend back the face region in focus.
    If no face_bbox is provided, the center 40% of the image is kept sharp
    (fallback for batch generation).
    """
    h, w = img.shape[:2]
    blurred = cv2.GaussianBlur(img, (blur_strength, blur_strength), 0)

    if face_bbox is None:
        cx, cy = w // 2, h // 2
        ww, hh = int(w * 0.4), int(h * 0.5)
        x1, y1 = max(0, cx - ww // 2), max(0, cy - hh // 2)
        x2, y2 = min(w, x1 + ww), min(h, y1 + hh)
        face_bbox = (x1, y1, x2, y2)
    else:
        x1, y1, x2, y2 = face_bbox

    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 255
    # Feather the mask so the transition is smooth
    mask = cv2.GaussianBlur(mask, (blur_strength * 2 + 1, blur_strength * 2 + 1), 0)
    mask_f = mask.astype(np.float32) / 255.0
    mask_f = np.expand_dims(mask_f, axis=-1)

    out = (img.astype(np.float32) * mask_f +
           blurred.astype(np.float32) * (1 - mask_f))
    return out.astype(np.uint8)


# ---------------------------------------------------------------------------
# Perturbation registry
# ---------------------------------------------------------------------------

def perturbation_registry() -> List[Tuple[str, Callable]]:
    """Return (suffix, function) pairs."""
    registry = []
    for q in (30, 50, 70):
        registry.append((f"jpeg_q{q}", lambda img, q=q: apply_jpeg_compression(img, q)))

    registry.append(("denoise", apply_bilateral_denoise))
    registry.append(("softlight", apply_softlight))
    registry.append(("resize_up", apply_resize_upscale))

    for mode in ("brighten", "darken", "highlight"):
        registry.append((f"exposure_{mode}", lambda img, m=mode: apply_exposure_hdr(img, m)))

    registry.append(("shallow_dof", apply_shallow_dof))
    return registry


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def detect_face_bbox(img: np.ndarray) -> Tuple[int, int, int, int]:
    """Try to detect a face; return bbox or None."""
    cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, 1.1, 4)
    if len(faces) == 0:
        return None
    # Use the largest face
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    x, y, w, h = faces[0]
    return (x, y, x + w, y + h)


def generate_for_image(input_path: Path, output_dir: Path,
                       face_bbox: Tuple[int, int, int, int] = None) -> List[dict]:
    """Generate all hard-negative variants for one clean image."""
    img = cv2.imread(str(input_path))
    if img is None:
        raise RuntimeError(f"Could not read {input_path}")

    records = []
    stem = input_path.stem
    registry = perturbation_registry()

    # Always keep a no-perturbation reference copy (still digital_retouch=0)
    ref_path = output_dir / f"{stem}_no_retouch.jpg"
    cv2.imwrite(str(ref_path), img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    records.append({
        "filename": ref_path.name,
        "source": input_path.name,
        "perturbation": "no_retouch",
        "digital_retouch": 0,
        "params": "quality=95",
    })

    for suffix, fn in registry:
        if suffix == "shallow_dof":
            out = fn(img, face_bbox=face_bbox)
        else:
            out = fn(img)
        out_path = output_dir / f"{stem}_{suffix}.jpg"
        cv2.imwrite(str(out_path), out, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        records.append({
            "filename": out_path.name,
            "source": input_path.name,
            "perturbation": suffix,
            "digital_retouch": 0,
            "params": "",
        })
    return records


def main():
    parser = argparse.ArgumentParser(description="Generate hard-negative portrait samples")
    parser.add_argument("--input_dir", required=True, help="Folder of clean portraits")
    parser.add_argument("--output_dir", required=True, help="Where to write variants")
    parser.add_argument("--metadata", default="hard_negatives.csv", help="CSV metadata path")
    parser.add_argument("--detect_faces", action="store_true",
                        help="Use Haar cascade to improve shallow-DoF face region")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(p for p in input_dir.iterdir()
                         if p.suffix.lower() in (".jpg", ".jpeg", ".png"))

    all_records = []
    for p in image_paths:
        if looks_like_retouched_path(p):
            print(f"SKIP (suspected retouched filename): {p.name}")
            continue

        face_bbox = detect_face_bbox(cv2.imread(str(p))) if args.detect_faces else None
        try:
            records = generate_for_image(p, output_dir, face_bbox=face_bbox)
            all_records.extend(records)
            print(f"Generated {len(records)} variants for {p.name}")
        except Exception as e:
            print(f"ERROR processing {p.name}: {e}")

    # Write metadata
    with open(args.metadata, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "source", "perturbation",
                                               "digital_retouch", "params"])
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\nDone. {len(all_records)} hard-negative images written to {output_dir}")
    print(f"Metadata saved to {args.metadata}")


if __name__ == "__main__":
    main()
