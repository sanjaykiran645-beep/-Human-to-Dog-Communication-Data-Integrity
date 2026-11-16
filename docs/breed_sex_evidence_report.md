# Breed and Sex Calibration Evidence & Allometry Report

**Document ID:** CSAI-AUDIT-PHASE5-BREED-001  
**Version:** 2.0.0  
**Auditor:** Bioacoustics Researcher & Veterinary Ethology Auditor  
**Date:** 2026-11-15  

---

## 1. Executive Summary

Bioacoustic systems frequently claim to "calibrate" sound analysis and synthesis to specific dog breeds and biological sexes. This audit inspected all 25+ breed profiles, acoustic formant calculations, fundamental pitch ranges ($F_0$), sex multipliers, and behavioral priors in `backend/app/services/breed_intelligence.py`.

### Critical Scientific Findings:
1. **Coren Trainability Separation:** The platform references Stanley Coren's *The Intelligence of Dogs* (1994). This ranking reflects working and obedience trial trainability under human instruction. **It has zero physiological or acoustic relationship to vocal tract geometry or vocal fold mass.** In the codebase, Coren rankings are strictly sequestered under `cognitive_obedience_tier` and are never used to derive acoustic parameters.
2. **Allometric Approximations vs Empirical Dataset:** The breed-specific formant frequencies ($F_1, F_2, F_3$) and pitch ranges ($F_0$) are **allometric body-mass scaling approximations** derived from bioacoustic theory (Taylor & Reby 2010; Fitch 2000), **not directly measured empirical corpora of live dogs of each breed**.
3. **Sex Multipliers:** The male multiplier ($\times 0.91$) and female multiplier ($\times 1.08$) are **heuristic allometric dimorphism priors**, reflecting average canine sexual dimorphism in body mass, rather than individual clinical acoustic measurements.

---

## 2. Scientific Source & Mathematical Formulation

### 2.1 Acoustic Allometry Formulation
In vertebrate bioacoustics (source-filter theory):
- **Vocal Fold Mass and Fundamental Frequency ($F_0$):**
  $$F_0 \propto M_{\text{body}}^{-0.25}$$
  Larger canines possess thicker, longer vocal folds that vibrate at lower fundamental frequencies.
- **Vocal Tract Length ($VTL$) and Formant Dispersion ($\Delta F$):**
  $$VTL \propto M_{\text{body}}^{0.333}$$
  $$\Delta F = \frac{c}{2 \cdot VTL}$$
  where $c = 344\text{ m/s}$ (speed of sound in warm moist air). Longer vocal tracts project lower, more closely spaced formant resonance poles ($F_1, F_2, F_3$).

### 2.2 Table of Breed Categories and Parameters

| Body Size Category | Reference Weight ($M_{\text{kg}}$) | Allometric $F_0$ Range (Hz) | Synthesizer Formants $[F_1, F_2, F_3]$ (Hz) | Evidence Classification |
| :--- | :--- | :--- | :--- | :--- |
| **Toy** (e.g. Chihuahua, Maltese) | 2.5–4.0 kg | 350 – 950 Hz | $[880, 2150, 3500]$ Hz | Allometric Scaled Prior |
| **Small** (e.g. Jack Russell, Beagle) | 6.0–12.0 kg | 260 – 780 Hz | $[750, 1850, 3100]$ Hz | Allometric Scaled Prior |
| **Medium** (e.g. Border Collie) | 16.0–22.0 kg | 170 – 500 Hz | $[610, 1520, 2720]$ Hz | Allometric Scaled Prior |
| **Large** (e.g. Golden Retriever, GSD) | 28.0–36.0 kg | 140 – 410 Hz | $[520, 1380, 2500]$ Hz | Allometric Scaled Prior |
| **Giant** (e.g. Great Dane, Bernese) | 44.0–60.0 kg | 95 – 310 Hz | $[440, 1200, 2260]$ Hz | Allometric Scaled Prior |

---

## 3. Sex Dimorphism Adjustments

In `resolve_breed_intelligence`:
```python
if norm_sex == "male":
    # Male: -9% pitch shift and formant downscaling
    f0_range = [int(f0[0] * 0.91), int(f0[1] * 0.91)]
    formants = [round(f * 0.91, 1) for f in formants]
elif norm_sex == "female":
    # Female: +8% pitch shift and formant upscaling
    f0_range = [int(f0[0] * 1.08), int(f0[1] * 1.08)]
    formants = [round(f * 1.08, 1) for f in formants]
```

### Empirical Limitations:
1. **Intra-Breed Overlap:** In domestic dogs, sexual dimorphism in body mass is modest (~8–12% difference in weight). Individual variations within the same sex frequently exceed the difference between sexes.
2. **Skull Shape Diversity (Cranial Conformation):** Brachycephalic breeds (Pugs, Bulldogs, French Bulldogs) possess compressed, foreshortened vocal tracts with elongated soft palates, completely decoupling $VTL$ from body weight. Dolichocephalic breeds (Greyhounds, Collies) exhibit lengthened vocal tracts producing deeper formants than predicted by weight alone.
3. **Mandatory Software Labeling:** The API response explicitly tags these parameters:
   ```json
   "parameter_provenance": "Acoustic F0 and formant priors are allometric body-mass approximations (Taylor & Reby source-filter allometry), not breed-certified empirical measurements. Sex multipliers (male x0.91, female x1.08) are heuristic dimorphism priors."
   ```

---

## 4. Personal Dog Baseline vs Breed Prior

The system enforces an explicit hierarchy:
1. **Tier 1 (Highest Authority):** Individual Dog Personal Empirical Baseline (`personal_f0_mean_hz`, `personal_f0_std_hz`), calculated dynamically from that specific dog's historical clean vocalizations in SQLite ($N \ge 3$).
2. **Tier 2 (Fallback Prior):** Breed/Weight/Sex Allometric Prior (`allometric_acoustic_prior`).
3. **Tier 3 (Default):** Medium Canine 20 kg Baseline.

Whenever an individual dog baseline is available, the software sets `"personal_baseline_used": true`, ensuring that generic breed heuristics do not override real measurements of that specific animal.
