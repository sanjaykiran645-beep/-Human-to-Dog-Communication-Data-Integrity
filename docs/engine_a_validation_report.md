# Engine A (Dog-to-Human) Scientific Validation & Evaluation Report

**Document ID:** CSAI-AUDIT-PHASE3-ENGA-001  
**Version:** 2.0.0  
**Auditor:** Machine Learning Research Engineer & Bioacoustics Auditor  
**Date:** 2026-11-15  
**Evaluation Script:** `scripts/reproduce_engine_a_eval.py`  
**Raw Metrics Output:** `docs/engine_a_metrics.json`  

---

## 1. Executive Summary & Production Status

Engine A is designed to perform bioacoustic feature extraction and 6-class vocalization classification (`bark`, `growl`, `whine`, `howl`, `yip`, `unknown`), inferring behavioural hypotheses and safety guidance.

**CRITICAL FINDING: Engine A achieves 85.46% balanced accuracy on held-out dogs, failing the required 90.00% production gate.**

In accordance with strict scientific validation requirements:
- **Production Gate:** 90.00% balanced accuracy under dog-independent evaluation.
- **Achieved Balanced Accuracy:** 85.46% (Gap: -4.54%).
- **Overall Accuracy:** 86.81%.
- **Macro F1:** 78.77%.
- **Dog Overlap between Train and Test:** Exactly 0 (0% leakage).
- **Target Met:** **FALSE (FAIL)**.

The system significantly outperforms the simple majority baseline (Balanced Accuracy: 16.67%, Accuracy: 60.44%), demonstrating substantial bioacoustic signal detection capability. However, severe class imbalance (55 barks vs. 4 whines and 2 growls in the test set) and acoustic overlap between whines, yips, and unvoiced signals prevent meeting the 90.00% standard without extensive biological field data collection.

---

## 2. Acoustic Feature Extraction Pipeline Audit

Engine A extracts 14 core bioacoustic features across time and frequency domains:
1. **Fundamental Frequency ($F_0$):** Extracted via autocorrelation and normalized parabolic peak interpolation with search range 80–1200 Hz. Verified numerical stability with fallback when voiced frames are absent.
2. **Signal-to-Noise Ratio (SNR):** Computed using 90th vs 10th frame RMS energy percentiles ($20 \log_{10}(P_{90} / P_{10})$). Verified non-hardcoded and dynamic across varying noise floors.
3. **Harmonics-to-Noise Ratio (HNR):** Autocorrelation peak ratio $10 \log_{10}(r_{\max} / (1 - r_{\max}))$ clipped to avoid infinite limits.
4. **RMS Energy & Burst Onset Rate:** Adaptive threshold envelope crossings ($1.65 \times \text{mean}(|\text{env}|)$). Correctly identifies staccato bark repetitions vs sustained howls.
5. **Spectral Centroid & Bandwidth:** Center of spectral mass and spread; separates deep thoracic growls (< 1100 Hz) from high squeaks (> 3000 Hz).
6. **Clipping & Quality Rejection:** Detects sample saturation ($|x| \ge 0.99$). Severe clipping triggers abstention rather than false classification.

---

## 3. Six-Class Dog-Independent Evaluation

### 3.1 Test Configuration
- **Dataset Evaluated:** 169 total reference library assets.
- **Train Dogs / Test Dogs Split:** 45 train dog clusters, 26 held-out test dog clusters.
- **Held-Out Test Sample Count ($N$):** 91 audio files.
- **Dog Identity Leakage:** 0% (train dogs $\cap$ test dogs = $\emptyset$).

### 3.2 Performance Summary Matrix

| Metric | Measured Value | Production Target | Status |
| :--- | :--- | :--- | :--- |
| **Overall Accuracy** | 86.81% | - | Solid baseline |
| **Balanced Accuracy** | **85.46%** | **90.00%** | **FAILED (-4.54%)** |
| **Macro Precision** | 80.18% | - | - |
| **Macro Recall** | 85.46% | - | - |
| **Macro F1** | 78.77% | 85.00% | FAILED |
| **Expected Calibration Error (ECE)** | 0.1440 | < 0.1000 | Needs Temperature Scaling |
| **Brier Score** | 0.1481 | - | - |
| **Abstention Rate** | 0.00% | - | Low on clean library clips |

### 3.3 Per-Class Performance Breakdown

| Vocalization Class | Precision | Recall | F1 Score | Test Support ($N$) | Primary Failure Mode |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bark** | 96.43% | 98.18% | 97.30% | 55 | Excellent detection; 1 howl misclassified as bark |
| **Growl** | 100.00% | 100.00% | 100.00% | 2 | Very high precision; extremely low support |
| **Whine** | **40.00%** | 100.00% | **57.14%** | 4 | 6 false positives from unvoiced and yip calls |
| **Howl** | 87.50% | 87.50% | 87.50% | 8 | 1 misclassified as bark |
| **Yip** | 57.14% | 80.00% | 66.66% | 5 | Confusion with short high barks and whines |
| **Unknown** | 100.00% | 47.06% | 64.00% | 17 | 9 non-canine/ambient tracks classified as vocal |

### 3.4 Six-Class Confusion Matrix

Rows represent Ground Truth, Columns represent Model Predictions:

```
                Bark   Growl   Whine   Howl    Yip   Unknown
True Bark        54       0       0      1      0        0
True Growl        0       2       0      0      0        0
True Whine        0       0       4      0      0        0
True Howl         1       0       0      7      0        0
True Yip          1       0       0      0      4        0
True Unknown      0       0       6      0      3        8
```

*Key Confusion Matrix Observations:*
1. **High Bark Purity:** 54 out of 55 true barks were correctly classified (98.18% recall).
2. **False Positive Whines & Yips on Unknowns:** 6 unknown/non-canine files were misclassified as whines, and 3 as yips. High-frequency ambient sounds (whistles, mechanical whine) trigger narrow-band pitch detectors.

---

## 4. Comparison Against Simple Baselines

To confirm that the machine learning and acoustic models learn genuine signal rather than artifactual heuristics, performance was benchmarked against simple baselines:

| Model / Baseline | Accuracy | Balanced Accuracy | Macro F1 |
| :--- | :--- | :--- | :--- |
| **Majority Class Predictor (Always 'bark')** | 60.44% | 16.67% | 12.55% |
| **Random Uniform 6-Class Guessing** | 16.67% | 16.67% | 16.67% |
| **Engine A (Bioacoustic Prior Inference)** | **86.81%** | **85.46%** | **78.77%** |
| **Net Scientific Advantage** | **+26.37%** | **+68.79%** | **+66.22%** |

Engine A demonstrates a massive +68.79% balanced accuracy advantage over naive baselines, confirming strong bioacoustic discrimination despite falling short of the 90.00% threshold.

---

## 5. Calibration & Abstention Analysis

### 5.1 5-Bin Reliability Diagram
- **Bin [0.4 - 0.6]:** 18 samples, Mean Confidence: 52.20%, Empirical Accuracy: 83.33%, Calibration Gap: 0.3114 (Under-confident).
- **Bin [0.6 - 0.8]:** 17 samples, Mean Confidence: 73.08%, Empirical Accuracy: 94.12%, Calibration Gap: 0.2103 (Under-confident).
- **Bin [0.8 - 1.0]:** 56 samples, Mean Confidence: 92.72%, Empirical Accuracy: 85.71%, Calibration Gap: 0.0701 (Slightly over-confident).

### 5.2 Expected Calibration Error (ECE)
- **Measured ECE:** 0.1440 (14.40%).
- **Recommendation:** Implement Platt scaling / temperature scaling on the softmax outputs prior to public production release.

---

## 6. Audit of Scenario Intelligence & Quick-Analyze

1. **Elimination of Artificial Scores:**
   - Previous hardcoded confidence (0.95) and artificial accuracy claims (90–96%) in `scenario_intelligence.py` and `quick_analyze_recording` have been explicitly reclassified as `"heuristic_rule_match_pct"` and tagged with `"hypothesis_label": "Rule-Based Bioacoustic Hypothesis (Unvalidated Without Visual Context)"`.
2. **Abstention on Ambiguity:**
   - Ambiguous acoustic cues or unclassified segments no longer silently default to a bark. They yield an explicit `uncertain` scenario with clinical safety notices.
3. **Clinical Non-Diagnostic Disclaimer:**
   - The platform explicitly states that acoustic measurements alone cannot diagnose medical conditions or exclude pain, and advises veterinary consultation whenever distress is suspected.
