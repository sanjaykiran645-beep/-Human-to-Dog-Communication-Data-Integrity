# Engine B Control Conditions Specification

**Document ID:** CSAI-SPEC-ENG-B-CTRL-001  
**Version:** 2.0.0  
**Author:** DSP Engineer & Experimental Ethologist  
**Date:** 2026-11-15  

---

## 1. Scientific Necessity of Rigorous Control Conditions

In animal psychoacoustics, a dog's response to an unfamiliar sound can be triggered by:
- Pure auditory startle (unconditioned acoustic startle reflex).
- Novelty-induced orienting (neophilia or curiosity).
- General acoustic energy / loudness salience.
- Owner presence or subtle unconscious handler cuing (Clever Hans effect).

To prove that a behavioral response is specific to the **canine-inspired bioacoustic structure** of Engine B rather than generic acoustic disruption, every experimental session must interleave four rigorous control conditions.

---

## 2. Specification of the Four Control Conditions

### Condition C1: Silent Baseline Control (Spontaneous Activity Baseline)
- **Signal:** Zero acoustic playback ($0.0$ amplitude) for $2.5$ seconds.
- **Scientific Purpose:** Measures baseline spontaneous orientation, motor movement, and environmental scanning in the absence of any stimulus.
- **Verification Rule:** Any orientation towards the loudspeaker during C1 establishes the false-positive baseline rate.

### Condition C2: Neutral Acoustic Pure Tone (Startle & Auditory Salience Control)
- **Signal:** Pure sinusoidal tone at $500$ Hz, $1.5$ seconds duration, 50 ms cosine-squared onset/offset ramps to prevent transient clicks.
- **RMS Energy & SPL:** Calibrated to exactly match the target Engine B cue ($\pm 0.5$ dBA SPL).
- **Scientific Purpose:** Rules out non-specific orientation caused purely by sound onset or tonal salience. A dog must demonstrate significant differential response between C2 and the target canine cue to prove cue-specific discrimination.

### Condition C3: Spectrally Matched Noise / Formant-Shaped Noise (Acoustic Energy Control)
- **Signal:** Pink noise shaped by the exact same 2-pole all-pole digital resonator filter bank ($F_1, F_2, F_3$) used by Engine B's parametric synthesizer, but lacking glottal harmonic periodicity ($F_0$), subharmonics, or pitch contour.
- **Duration & Envelope:** Identical envelope contour and duration to the target cue.
- **Scientific Purpose:** Establishes whether canine response requires the harmonic pitch contour and glottal pulse periodicity of real vocalizations, or whether static formant energy bands suffice.

### Condition C4: Familiar Human Verbal Command (Positive Benchmark Control)
- **Signal:** Recorded audio of the dog's primary owner speaking the equivalent verbal command (e.g. "Come", "Sit", "Stay") at normal conversational volume (65 dBA).
- **Scientific Purpose:** Provides the individual dog's benchmark capability for conditioned auditory comprehension. Performance on Engine B cues is assessed relative to this positive training ceiling.

---

## 3. Latin Square Interleaving & Presentation Schedule

To avoid ordering artifacts, fatigue, or sensory habituation:
- Trials are organized in pseudorandomized blocks using a balanced Latin Square design:
  - Block A: Target Cue $\rightarrow$ C1 $\rightarrow$ C3 $\rightarrow$ Target Cue $\rightarrow$ C2 $\rightarrow$ C4
  - Block B: C2 $\rightarrow$ Target Cue $\rightarrow$ C1 $\rightarrow$ C4 $\rightarrow$ Target Cue $\rightarrow$ C3
- **Inter-Trial Interval (ITI):** Minimum 45 seconds of quiescence between consecutive trials.
- Maximum 12 trials per day per individual dog.
