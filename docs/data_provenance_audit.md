# CanineSense AI — Forensic Dataset Provenance Audit Report
**Phase 1 Deliverable — Priority 6 Master Plan**  
**Auditor Roles:** Senior Canine Bioacoustics Researcher & Scientific Data and Evaluation Auditor  
**Date:** November 15, 2026  
**Audited Sources:** `manifest.json`, `manifest.csv`, `data/reference_library/processed/` (169 audio assets)

---

## 1. Executive Forensic Summary

A forensic provenance audit was performed across all 169 reported reference assets in the CanineSense AI reference library. The audit inspected raw manifests, filesystem integrity, cryptographic SHA-256 hashes, source download origins, nominal dog identities, breed/sex metadata completeness, and acoustic segment relationships.

### Key Audit Findings
1. **Zero Verified Biological Subjects ($N_{\text{verified}} = 0$):** Not a single recording in the repository is linked to a verified individual canine subject with veterinary records, microchip, or controlled ethological observation logs. All 69 nominal `dog_id` tags are heuristic labels derived from soundbank filenames (e.g. `dog-0112` from `ANMLDog_Barking dog inside (ID 0112)_BigSoundBank.com.mp3`), unassigned pools, or pack recordings (`dog-pack-2953`).
2. **100% Missing Breed and Sex Metadata:** 169 out of 169 assets (100.0%) possess no verified breed or sex metadata.
3. **Sound-Effect Dominance:** 112 assets (66.3%) originate from the public sound-effects library `BigSoundBank.com`, 48 assets (28.4%) from unverified compressed archives, and 9 assets (5.3%) from Pixabay/downloads.
4. **Severe Class Imbalance:** Barks ($N=75$) and non-canonical/rejected calls ($N=61$) represent 80.5% of the data. Vital communicative vocalizations have near-zero representation: Growl ($N=3$), Whine ($N=7$), Yip ($N=8$).
5. **Exact Duplicates and Segment Acoustic Leakage:** Two pairs of exact SHA-256 duplicate files were discovered. Additionally, 15 assets are subsegments cut from 11 parent sound-effects recordings, posing severe acoustic leakage hazards if split across train and test sets.

---

## 2. Seven-Tier Provenance Classification

Each of the 169 assets was categorized under the required 7-tier provenance taxonomy:

| Tier | Category | Count | Percentage | Description / Sources |
| :---: | :--- | :---: | :---: | :--- |
| **1** | Verified real canine recording | **0** | 0.0% | Controlled ethological or clinical recordings with verified canine subject ID. |
| **2** | Real canine recording with incomplete provenance | **9** | 5.3% | Pixabay user uploads and standalone downloads; field audio of likely dogs without identity records. |
| **3** | Commercial or public sound-effect recording | **79** | 46.7% | Direct tracks from `BigSoundBank.com` curated sound effects repository. |
| **4** | Unverified archive recording | **48** | 28.4% | Audio from web scrape archives (`archive_DvC_Dogs`, `dog recode.zip`, `dog reg 2.zip`). |
| **5** | Synthetic or test-generated recording | **0** | 0.0% | No synthetic generated tones are stored in the reference library (stored in `evaluation_samples/`). |
| **6** | Non-canine or rejected recording | **33** | 19.5% | Assets rejected during technical validation as non-canine noise, human sounds, or low-quality. |
| **7** | Unknown provenance | **0** | 0.0% | All assets had trace origin paths. |
| **Total** | | **169** | **100.0%** | |

---

## 3. Canonical 6-Class Usable Distribution

The platform maps canine vocalizations into six canonical classes: `bark`, `growl`, `whine`, `howl`, `yip`, and `unknown` (which encompasses abstentions, non-canine sounds, and non-canonical calls like whimper, grunt, cry, and groan).

```
Class Distribution Across 169 Audited Assets:
============================================================
Bark:       [========================================] 75 (44.4%)
Unknown:    [=================================] 61 (36.1%)
Howl:       [========] 15 (8.9%)
Yip:        [====] 8 (4.7%)
Whine:      [===] 7 (4.1%)
Growl:      [=] 3 (1.8%)
============================================================
```

### Bioacoustic Risk Analysis of Class Imbalance:
- **Growl ($N=3$):** Represents defensive warning or play growling. A dataset with only 3 growls cannot support statistical machine learning or biological variance modeling.
- **Whine ($N=7$):** Narrow-band stress and attention signals. 7 samples cannot capture the acoustic diversity across dog sizes and affective states.
- **Yip ($N=8$):** Short high-frequency burst calls.
- **Bark ($N=75$):** Highly over-represented, biasing any unweighted classifier toward predicting barks.

---

## 4. Dog Identity Hierarchy and Group Validity Audit

### Nominal Dog ID Categories
| Dog ID Classification | Number of IDs | Number of Assets | Examples | Validity Assessment |
| :--- | :---: | :---: | :--- | :--- |
| **Ethologically Verified Individual** | **0** | **0** | None | **None exist.** |
| **Filename / Soundbank ID** | 56 | 97 | `dog-0112`, `dog-0612`, `dog-1547`, `dog-2450` | Derived from sound-effect item numbers; not verified dogs. |
| **Nominal Field / Archive ID** | 12 | 34 | `field-03ba6d96`, `dvc-dog-01` | Arbitrary cluster labels; single dogs may have multiple IDs. |
| **Multi-Dog Pack ID** | 1 | 3 | `dog-pack-2953` | Audio of multiple overlapping dogs; cannot serve as individual baseline. |
| **Unassigned / Generic Reference** | 2 | 35 | `curated_reference`, `None` | Mixed unassigned assets. |

### Source-Group & Individual-Dog Identity Hierarchy:
To prevent acoustic leakage in bioacoustic research, splitting must occur at the highest verifiable group level:
1. **Tier 1 (Strongest): Source Recording Master File:** All segments sliced from the same master file must remain together in either Train or Test.
2. **Tier 2: Recording Session / Environment:** Sounds recorded in the same acoustic space (same reverb, microphone, and background noise) must not be split.
3. **Tier 3: Nominal Soundbank ID:** Filename-derived IDs.
4. **Tier 4 (Unverified): Individual Dog:** Currently cannot be established due to lack of animal records.

---

## 5. Duplicate Recordings and Subsegment Leakage

### A. Exact SHA-256 Duplicates ($N = 2$ Pairs)
1. `SHA-256: f6017f455f08811e5e09f27c5ec8ad7427d2c3ae945a8ec6d81ea19921b7cbf2`
   - `dragon-studio-dog-barking-406629.mp3` (`asset_id: 1a1652b3-8367-5c74-a44c-de91244e8ec6`)
   - `dragon-studio-dog-barking-406629 (1).mp3` (`asset_id: 64b8c9d1-817e-52eb-8f72-9a67a86976ce`)
2. `SHA-256: 66e54164faf2dfb142ad1055740447eafe771dc52a5598d9ba8d7a1ee6cfb5e2`
   - `WhatsApp Audio 2026-10-27 at 7.46.50 PM.mpeg` (`asset_id: 97899e31-8e05-4f7f-8ec1-c30084ba3989`)
   - `WhatsApp Audio 2026-10-27 at 7.52.11 PM (2).mpeg` (`asset_id: 9c3d44f7-8720-4e3a-9694-be7ba1cf0dbd`)

### B. Extracted Subsegments ($15$ Segments from $11$ Parent Files)
Multiple assets in the reference library are subsegments extracted from identical parent sound-effects tracks:
- `ANMLDog_Dogs barking and crying 1 (ID 1544)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment
- `ANMLDog_Dogs barking and crying 2 (ID 1545)_BigSoundBank.com.mp3` $\rightarrow$ 2 segments
- `ANMLDog_Dogs barking and crying 3 (ID 1546)_BigSoundBank.com.mp3` $\rightarrow$ 2 segments
- `ANMLDog_Dog singing 2 (ID 2451)_BigSoundBank.com.mp3` $\rightarrow$ 2 segments
- `ANMLDog_Small dogs bark growl (ID 1060)_BigSoundBank.com.mp3` $\rightarrow$ 2 segments
- `ANMLDog_Old dog barking 1 (ID 2352)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment
- `ANMLDog_Old dog barking 3 (ID 2354)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment
- `ANMLDog_Dogs breathing (ID 1547)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment
- `ANMLDog_Dog singing 1 (ID 2450)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment
- `ANMLDog_Small dog barking (ID 0612)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment
- `ANMLDog_Barking of a spitz (ID 0682)_BigSoundBank.com.mp3` $\rightarrow$ 1 segment

**Defensive Rule:** In any training or cross-validation protocol, these segments MUST be grouped together with their parent track ID to prevent acoustic background leakage between train and test splits.

---

## 6. Audit Conclusion & Compliance Action
- **Zero Fabrication:** Missing metadata is reported as completely absent (100% missing breed/sex; 0 verified dogs).
- **Status:** The existing reference library is an acoustic reference and playback bank, NOT a verified biological corpus.
- **Remediation:** Phase 3 evaluation must enforce Tier 1 Master File / Session group splitting and explicitly declare that generalization across *empirically verified individual dogs* cannot be established with the current dataset.
