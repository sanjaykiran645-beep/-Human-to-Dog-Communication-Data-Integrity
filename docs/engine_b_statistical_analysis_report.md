# CanineSense AI — Engine B Statistical Analysis & Evaluation Report
**Document ID:** `CS-DOC-P7-006`  
**Version:** 2.0.0 (Priority 7 Real-World Validation)  
**Status:** Mathematical & Methodological Standard  
**Date:** November 2026  
**Implementation Reference:** `CanineSense_AI/backend/app/services/trial_service.py` (`compute_experimental_metrics`)  

---

## 1. Statistical Framework Overview

To scientifically demonstrate that dogs understand and act upon synthesized Engine B vocal cues, the evaluation framework must prove that motor execution is non-random, stimulus-specific, and sustained across repeated trials.

This report documents the exact mathematical formulations used in CanineSense AI.

---

## 2. Core Behavioural Metrics & Formulas

### 2.1 Target Intention Congruence Rate ($R_{\text{target}}$)
The proportion of valid Target Cue presentations that elicit the intended ethogram action:
$$R_{\text{target}} = \frac{N(\text{Target Cues with Correct Action})}{N(\text{Total Valid Target Cues})}$$
* **Threshold for Demonstrated Communication:** $R_{\text{target}} \ge 0.75$ ($75\%$).

### 2.2 Attention-Only Rate ($R_{\text{attention}}$)
The proportion of Target Cues that elicit orienting (head turn, ear swivel) without subsequent motor execution:
$$R_{\text{attention}} = \frac{N(\text{Target Cues with Attention Only})}{N(\text{Total Valid Target Cues})}$$
* **Critical Distinction:** $R_{\text{attention}}$ reflects sensory detection and acoustic salience, **not semantic comprehension**.

### 2.3 Acoustic Discrimination Ratio ($D_{\text{ratio}}$)
The primary index establishing that the dog discriminates the communicative cue from control sounds. It computes the normalized difference between the target action rate on the Target Cue versus acoustic control conditions (Silence C1, Pure Tone C2, Matched Noise C3):
$$D_{\text{ratio}} = \frac{R_{\text{target}} - R_{\text{controls}}}{\max(R_{\text{target}} + R_{\text{controls}},\, \epsilon)}$$
where:
$$R_{\text{controls}} = \frac{\sum_{c \in \{\text{C1, C2, C3}\}} N(\text{Action on Condition } c)}{\sum_{c \in \{\text{C1, C2, C3}\}} N(\text{Total Presentations of Condition } c)}$$
and $\epsilon = 10^{-6}$ prevents division by zero.
* **Interpretation of $D_{\text{ratio}}$:**
  * $D_{\text{ratio}} \in [-1.0, 1.0]$.
  * $D_{\text{ratio}} \approx 0.0$: Dog responds equally to target cue and control noise (zero acoustic specificity).
  * $D_{\text{ratio}} < 0.0$: Paradoxical response (higher response to controls).
  * $D_{\text{ratio}} \ge 0.50$: **Statistically meaningful acoustic discrimination**.
  * $D_{\text{ratio}} \ge 0.75$: **High-fidelity communicative stimulus specificity**.

### 2.4 Control False-Positive Rate ($FPR_{\text{ctrl}}$)
The proportion of control presentations where the dog spontaneously executes the target action:
$$FPR_{\text{ctrl}} = R_{\text{controls}}$$
* **Threshold:** Must be $\le 0.15$ ($15\%$) to exclude spontaneous hyperactivity or guessing.

---

## 3. Temporal Response Latencies

CanineSense AI tracks two distinct high-resolution temporal milestones (in milliseconds):
1. **$T_{\text{orient}}$ (Latency to Orient):** Time from audio onset to head/ear turn toward the speaker.
2. **$T_{\text{action}}$ (Latency to Action):** Time from audio onset to initiation of the target physical action.

For a cohort of $N$ valid trials, the service calculates:
* Mean Latency: $\mu_T = \frac{1}{N} \sum_{i=1}^N T_i$
* Standard Deviation: $\sigma_T = \sqrt{\frac{1}{N-1} \sum_{i=1}^N (T_i - \mu_T)^2}$
* Median ($P_{50}$), $P_{25}$, and $P_{75}$ percentiles.

*A true conditioned response characteristically demonstrates a tight, low-variance distribution ($\sigma_T \ll \mu_T$) and a steady reduction in latency across learning sessions.*

---

## 4. Longitudinal Dynamics: Habituation & Learning Trajectories

### 4.1 Habituation Index ($HI$)
Acoustic cues can lose salience through repetitive exposure without biologically relevant outcomes. The Habituation Index compares performance across early versus late blocks within a session:
$$HI = \frac{R_{\text{late}} - R_{\text{early}}}{\max(R_{\text{early}},\, \epsilon)}$$
* $HI \approx 0$: Stable response; no habituation.
* $HI < -0.30$: Significant habituation or motivational fatigue.

### 4.2 Learning Trajectory Across Sessions
For multi-session protocols ($S_1, S_2, \dots, S_K$), the service tracks session-by-session correct action rates. A linear regression slope is fitted:
$$R_{\text{target}}(S) = \beta_1 \cdot S + \beta_0$$
A positive slope ($\beta_1 > 0$, $p < 0.05$) indicates acquisition and associative conditioning.

---

## 5. Statistical Significance Testing & Within-Dog Modeling

Because individual dogs vary in auditory acuity, temperament, and training history:
* **Repeated-Measures Modeling:** Trials must be analyzed using Generalized Linear Mixed-Effects Models (GLMM) with a binomial logit link function:
  $$\text{logit}\big(P(Y_{ijt} = 1)\big) = \beta_0 + \beta_1 \cdot \text{Condition}_{ijt} + u_i + v_j + \epsilon_{ijt}$$
  where $Y_{ijt}$ is the binary action outcome for dog $i$, session $j$, trial $t$; $u_i \sim \mathcal{N}(0, \sigma_u^2)$ is the random intercept for individual dog identity; and $v_j \sim \mathcal{N}(0, \sigma_v^2)$ is the random intercept for session.
* **Hypothesis Test:** The condition effect $\beta_1$ for Target vs Controls must satisfy $p < 0.01$ (Wald $z$-test or likelihood ratio test).
