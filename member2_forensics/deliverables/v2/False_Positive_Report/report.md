# BeautyProof — TruFor Hard Negative & False Positive Analysis

## 1. Objective

This experiment evaluates the behavior of the TruFor forensic model on face images under JPEG compression and examines potential false positives on visually pristine images.

The experiment focuses on:

- TruFor integrity score
- Score direction conversion
- JPEG compression as a hard-negative condition
- False-positive behavior at different thresholds

---

## 2. Score Direction

TruFor outputs an integrity score.

For BeautyProof, the score direction is converted as:

**BeautyProof Suspicion Score = 1 - TruFor Integrity Score**

A higher BeautyProof Suspicion Score therefore indicates a stronger forensic suspicion.

Important: this is a direction conversion only. It is **not a calibrated manipulation probability**.

---

## 3. Hard Negative Experiment

Eight FFHQ face images were evaluated in three conditions:

1. Original image
2. JPEG Q50 compression
3. JPEG Q20 compression

### Results

| Face | Original | Q50 | ΔQ50 | Q20 | ΔQ20 |
|---|---:|---:|---:|---:|---:|
| Face03 | 0.240410 | 0.331227 | +0.090817 | 0.266086 | +0.025676 |
| Face04 | 0.375314 | 0.425798 | +0.050484 | 0.632302 | +0.256988 |
| Face05 | 0.162176 | 0.256146 | +0.093970 | 0.453816 | +0.291640 |
| Face06 | 0.123244 | 0.551291 | +0.428047 | 0.383078 | +0.259834 |
| Face07 | 0.113137 | 0.219553 | +0.106416 | 0.395290 | +0.282153 |
| Face08 | 0.338507 | 0.366607 | +0.028100 | 0.365039 | +0.026532 |
| Face09 | 0.555832 | 0.670843 | +0.115011 | 0.535144 | -0.020688 |
| Face10 | 0.170617 | 0.235324 | +0.064707 | 0.335783 | +0.165166 |

### Summary

- Mean Original score: **0.259905**
- Mean Q50 score: **0.382099**
- Mean Q20 score: **0.420817**
- Q50 increased in **8/8** images.
- Q20 increased in **7/8** images.

The results show that JPEG compression can substantially change TruFor's integrity score even when the underlying visual content is unchanged.

The effect is image-dependent and is not strictly monotonic with compression strength.

Therefore, JPEG compression should be treated as an important hard-negative condition during system evaluation.

---

## 4. False Positive Analysis

False-positive rates were calculated using 10 pristine/original images and the corresponding JPEG-compressed hard-negative sets.

### False Positive Rate by Threshold

| Threshold | Pristine | Q50 | Q20 |
|---:|---:|---:|---:|
| 0.20 | 4/10 (40%) | 9/10 (90%) | 10/10 (100%) |
| 0.30 | 3/10 (30%) | 6/10 (60%) | 8/10 (80%) |
| 0.40 | 1/10 (10%) | 4/10 (40%) | 4/10 (40%) |
| 0.50 | 1/10 (10%) | 2/10 (20%) | 3/10 (30%) |
| 0.60 | 0/10 (0%) | 1/10 (10%) | 1/10 (10%) |
| 0.70 | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) |
| 0.80 | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) |
| 0.90 | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) |

A separate tampered sample produced a TruFor score of **0.997613**.

These results are preliminary because the dataset is small and contains only one tampered example. They should not be interpreted as a formal benchmark or as evidence for a universally optimal threshold.

---

## 5. Key Findings

### Finding 1 — JPEG compression is a meaningful hard negative

JPEG compression can increase forensic suspicion scores even without intentional image manipulation.

This means that a practical BeautyProof system should consider image-quality and compression artifacts when interpreting forensic signals.

### Finding 2 — The response is image-dependent

The magnitude of the score change varies substantially between images.

For example, Q50 produced only a small increase for Face08 (+0.028100), while Face06 increased by +0.428047.

Therefore, the model response should not be treated as a simple linear function of JPEG quality.

### Finding 3 — Score threshold alone may generate false positives

At lower thresholds, both pristine images and JPEG-compressed images can produce relatively high scores.

This suggests that BeautyProof should avoid relying exclusively on a single TruFor score when making a final user-facing judgment.

---

## 6. Limitations

This experiment has several limitations:

1. The sample size is small.
2. Only eight paired FFHQ faces were used for the main hard-negative comparison.
3. The false-positive analysis contains only ten pristine/original examples.
4. Only one tampered sample was included in the preliminary comparison.
5. The experiment does not constitute a formal evaluation of TruFor's overall forensic accuracy.
6. The converted BeautyProof Suspicion Score is not a calibrated probability.
7. JPEG compression is only one type of hard negative; additional real-world distortions should be tested.

---

## 7. Recommended Next Experimental Directions

Future experiments should expand the hard-negative set to include:

- Different JPEG quality levels
- Image resizing
- Screenshots
- Social-media recompression
- Cropping
- Blur
- Sharpening
- Color and exposure changes
- Different skin tones and facial structures
- Images containing makeup but no digital manipulation

These cases can help evaluate whether forensic signals are caused by actual manipulation or by benign image-processing operations.

---

## 8. Deliverables

Generated experimental materials:

- `hard_negative_results.csv`
- `score_conversion.csv`
- `threshold_analysis.csv`
- TruFor `.npz` inference outputs
- TruFor visualization results

