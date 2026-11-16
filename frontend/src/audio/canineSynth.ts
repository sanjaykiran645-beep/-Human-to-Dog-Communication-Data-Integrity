/**
 * Repaired Client-Side Bioacoustic DSP Synthesizer for Engine B (Human -> Dog Communicator).
 *
 * Replaces the previous unstable cascade filter / sample-rate FM white-noise / tanh overdrive
 * implementation with:
 * - Constant-peak-gain 2-pole parallel formant resonators (zero DC gain, immune to blowup)
 * - Cycle-rate (~24 Hz) smoothly interpolated organic F0 jitter (no broadband FM static)
 * - Asymmetric Rosenberg glottal pulse + register-appropriate chest & subharmonic blend
 * - Zero-DC blocker + smooth raised-cosine ADSR envelopes + soft headroom normalization
 */

export interface CanineBurstSpec {
  startSec: number;
  durSec: number;
  f0Start: number;
  f0End: number;
  f1: number;
  f2: number;
  f3?: number;
  bw1?: number;
  bw2?: number;
  bw3?: number;
  noiseLevel: number;
  growlModHz?: number;
  subharmonicLevel?: number;
  attackSec?: number;
  releaseSec?: number;
  trajectory?: "low_modulated" | "stepped_bursts" | "rising_arch" | "sustained_arch" | "rapid_arch" | "gentle_doublet" | "falling_pulse";
}

export interface SynthOutput {
  blobUrl: string;
  wavBuffer: ArrayBuffer;
  samples: Float32Array;
  sampleRate: number;
  durationSec: number;
  peak: number;
  rms: number;
  dcOffset: number;
  maxSampleStep: number;
  clippedCount: number;
  burstCount: number;
  f0Hz: number;
  formantsHz: [number, number, number];
}

export interface PcmQualityMetrics {
  sampleRate: number;
  durationSec: number;
  sampleCount: number;
  peak: number;
  rms: number;
  dcOffset: number;
  maxSampleStep: number;
  clippedCount: number;
  abruptClickCount: number;
}

export function measurePcmMetrics(samples: Float32Array, sampleRate: number): PcmQualityMetrics {
  const n = samples.length;
  if (n === 0 || sampleRate <= 0) {
    return {
      sampleRate: sampleRate || 22050,
      durationSec: 0,
      sampleCount: 0,
      peak: 0,
      rms: 0,
      dcOffset: 0,
      maxSampleStep: 0,
      clippedCount: 0,
      abruptClickCount: 0,
    };
  }
  let sum = 0;
  let sumSq = 0;
  let peak = 0;
  let clippedCount = 0;
  let maxStep = 0;
  for (let i = 0; i < n; i++) {
    const v = samples[i];
    sum += v;
    sumSq += v * v;
    const av = Math.abs(v);
    if (av > peak) peak = av;
    if (av > 0.99) clippedCount++;
    if (i > 0) {
      const diff = Math.abs(v - samples[i - 1]);
      if (diff > maxStep) maxStep = diff;
    }
  }
  const threshold = Math.max(0.72, peak * 1.25);
  let abruptClickCount = 0;
  for (let i = 1; i < n; i++) {
    if (Math.abs(samples[i] - samples[i - 1]) > threshold) {
      abruptClickCount++;
    }
  }
  return {
    sampleRate,
    durationSec: Number((n / sampleRate).toFixed(4)),
    sampleCount: n,
    peak: Number(peak.toFixed(5)),
    rms: Number(Math.sqrt(sumSq / n).toFixed(5)),
    dcOffset: Number((sum / n).toFixed(6)),
    maxSampleStep: Number(maxStep.toFixed(5)),
    clippedCount,
    abruptClickCount,
  };
}

function deterministicSeededRng(seedNum: number): () => number {
  let state = (seedNum >>> 0) || 1337;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function rosenbergPulse(phase01: number, openFrac = 0.58, closeFrac = 0.14): number {
  const p = phase01 - Math.floor(phase01);
  if (p < openFrac) {
    return 0.5 * (1 - Math.cos((Math.PI * p) / openFrac));
  }
  if (p < openFrac + closeFrac) {
    return Math.cos((0.5 * Math.PI * (p - openFrac)) / closeFrac);
  }
  return 0;
}

class ConstantPeakFormantBiquad {
  private readonly b0: number;
  private readonly a1: number;
  private readonly a2: number;
  private x1 = 0;
  private x2 = 0;
  private y1 = 0;
  private y2 = 0;

  constructor(freqHz: number, bwHz: number, sr: number) {
    const r = Math.exp((-Math.PI * Math.max(40, bwHz)) / sr);
    const theta = (2 * Math.PI * Math.max(40, Math.min(freqHz, sr * 0.45))) / sr;
    this.b0 = 0.5 * (1 - r * r);
    this.a1 = -2 * r * Math.cos(theta);
    this.a2 = r * r;
  }

  process(x: number): number {
    const y = this.b0 * (x - this.x2) - this.a1 * this.y1 - this.a2 * this.y2;
    this.x2 = this.x1;
    this.x1 = x;
    this.y2 = this.y1;
    this.y1 = y;
    return y;
  }
}

function buildPinkNoiseBuffer(n: number, rng: () => number): Float64Array {
  const out = new Float64Array(n);
  let b0 = 0;
  let b1 = 0;
  let b2 = 0;
  let b3 = 0;
  for (let i = 0; i < n; i++) {
    const white = (rng() - 0.5) * 2;
    b0 = 0.99765 * b0 + white * 0.099046;
    b1 = 0.963 * b1 + white * 0.2965164;
    b2 = 0.57 * b2 + white * 1.0526913;
    b3 = 0.1848 * white;
    out[i] = b0 + b1 + b2 + b3;
  }
  let sum = 0;
  for (let i = 0; i < n; i++) sum += out[i];
  const mean = sum / Math.max(1, n);
  let varSum = 0;
  for (let i = 0; i < n; i++) {
    out[i] -= mean;
    varSum += out[i] * out[i];
  }
  const std = Math.sqrt(varSum / Math.max(1, n)) + 1e-9;
  for (let i = 0; i < n; i++) out[i] /= std;
  return out;
}

function buildAdsrEnvelope(n: number, sr: number, attackSec: number, releaseSec: number): Float64Array {
  const env = new Float64Array(n);
  if (n <= 4) {
    env.fill(1);
    return env;
  }
  const att = Math.min(Math.floor(n * 0.42), Math.max(6, Math.round(attackSec * sr)));
  const rel = Math.min(Math.floor(n * 0.45), Math.max(8, Math.round(releaseSec * sr)));
  const dec = Math.min(Math.floor(n * 0.22), Math.max(4, Math.round(Math.min(0.14, n / sr * 0.2) * sr)));
  const sustainStart = att + dec;
  const releaseStart = Math.max(sustainStart, n - rel);
  const sustainLevel = 0.78;

  for (let i = 0; i < n; i++) {
    if (i < att) {
      env[i] = 0.5 * (1 - Math.cos((Math.PI * i) / Math.max(1, att - 1)));
    } else if (i < sustainStart) {
      const dPos = (i - att) / Math.max(1, dec);
      env[i] = sustainLevel + (1 - sustainLevel) * (0.5 * (1 + Math.cos(Math.PI * dPos)));
    } else if (i < releaseStart) {
      env[i] = sustainLevel;
    } else {
      const rPos = (i - releaseStart) / Math.max(1, n - 1 - releaseStart);
      env[i] = sustainLevel * (0.5 * (1 + Math.cos(Math.PI * Math.min(1, rPos))));
    }
  }
  return env;
}

export function encodeMonoPcm16Wav(samples: Float32Array, sr: number): ArrayBuffer {
  const n = samples.length;
  const buffer = new ArrayBuffer(44 + n * 2);
  const view = new DataView(buffer);
  const writeStr = (off: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + n * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sr, true);
  view.setUint32(28, sr * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

export function synthesizeCanineWav(
  bursts: CanineBurstSpec[],
  totalSec: number,
  seed = 42,
  sampleRate = 22050
): SynthOutput {
  const safeTotal = Math.max(0.25, Math.min(6.0, totalSec));
  const numSamples = Math.max(16, Math.round(sampleRate * safeTotal));
  const out = new Float64Array(numSamples);
  const rng = deterministicSeededRng(seed);

  let avgF0 = 240;
  let lastFormants: [number, number, number] = [620, 1420, 2450];

  if (bursts.length > 0) {
    avgF0 = bursts.reduce((acc, b) => acc + (b.f0Start + b.f0End) * 0.5, 0) / bursts.length;
    const refB = bursts[0];
    lastFormants = [refB.f1, refB.f2, refB.f3 ?? Math.min(sampleRate * 0.42, refB.f2 * 1.65)];
  }

  for (let bIdx = 0; bIdx < bursts.length; bIdx++) {
    const b = bursts[bIdx];
    const startIdx = Math.max(0, Math.round(b.startSec * sampleRate));
    const bLen = Math.min(numSamples - startIdx, Math.max(32, Math.round(b.durSec * sampleRate)));
    if (bLen <= 16) continue;

    const f3 = b.f3 ?? Math.min(sampleRate * 0.42, Math.round(b.f2 * 1.68));
    const res1 = new ConstantPeakFormantBiquad(b.f1, b.bw1 ?? (b.f0Start < 200 ? 140 : 185), sampleRate);
    const res2 = new ConstantPeakFormantBiquad(b.f2, b.bw2 ?? (b.f0Start < 200 ? 220 : 270), sampleRate);
    const res3 = new ConstantPeakFormantBiquad(f3, b.bw3 ?? 360, sampleRate);
    const breathBand = new ConstantPeakFormantBiquad((b.f1 + b.f2) * 0.5, 650, sampleRate);

    const pink = buildPinkNoiseBuffer(bLen, rng);
    const env = buildAdsrEnvelope(
      bLen,
      sampleRate,
      b.attackSec ?? (b.f0Start < 200 ? 0.055 : 0.024),
      b.releaseSec ?? (b.f0Start < 200 ? 0.11 : 0.065)
    );

    // Cycle-rate jitter knots (~24 Hz)
    const durS = bLen / sampleRate;
    const nKnots = Math.max(4, Math.round(durS * 24) + 2);
    const knots = new Float64Array(nKnots);
    for (let k = 0; k < nKnots; k++) knots[k] = (rng() - 0.5) * 2 * 0.0085;

    const rawExcit = new Float64Array(bLen);
    let phase = 0;
    const subRatio = b.subharmonicLevel ?? (b.f0Start < 210 ? 0.34 : 0.05);
    const traj = b.trajectory ?? (b.f0Start < 210 ? "low_modulated" : "rapid_arch");

    for (let i = 0; i < bLen; i++) {
      const u = i / Math.max(1, bLen - 1);

      // Interpolate cycle-rate micro-jitter
      const kf = u * (nKnots - 1);
      const k0 = Math.min(nKnots - 2, Math.floor(kf));
      const frac = kf - k0;
      const jitter = knots[k0] * (1 - frac) + knots[k0 + 1] * frac;

      let f0 = b.f0Start;
      if (traj === "low_modulated") {
        const rise = 0.5 * (1 - Math.cos(Math.PI * Math.min(1, u / 0.45)));
        const tail = 1 - 0.12 * Math.max(0, (u - 0.65) / 0.35);
        f0 = (b.f0Start + (b.f0End - b.f0Start) * rise) * tail;
      } else if (traj === "rising_arch" || traj === "sustained_arch") {
        f0 = b.f0Start + (b.f0End - b.f0Start) * Math.sin(Math.PI * Math.min(1, u * 0.86));
      } else if (traj === "gentle_doublet") {
        f0 = b.f0Start + (b.f0End - b.f0Start) * (0.5 - 0.5 * Math.cos(Math.PI * u));
      } else {
        const arch = Math.sin(Math.PI * Math.pow(u, 0.78));
        f0 = b.f0Start + (b.f0End - b.f0Start) * arch - 0.05 * b.f0Start * u * u;
      }
      f0 = Math.max(50, Math.min(sampleRate * 0.4, f0 * (1 + jitter)));
      phase += f0 / sampleRate;

      const main = rosenbergPulse(phase);
      const sub = subRatio > 0 ? rosenbergPulse(0.5 * phase, 0.62, 0.16) : 0;
      const chest = 0.28 * Math.sin(2 * Math.PI * phase) + 0.12 * Math.sin(4 * Math.PI * phase);
      const subSine = subRatio > 0.15 ? 0.12 * Math.sin(Math.PI * phase) : 0;
      rawExcit[i] = main + subRatio * sub + chest + subSine;
    }

    // Zero-mean and std normalize periodic excitation
    let exMean = 0;
    for (let i = 0; i < bLen; i++) exMean += rawExcit[i];
    exMean /= bLen;
    let exVar = 0;
    for (let i = 0; i < bLen; i++) {
      rawExcit[i] -= exMean;
      exVar += rawExcit[i] * rawExcit[i];
    }
    const exStd = Math.sqrt(exVar / bLen) + 1e-9;
    for (let i = 0; i < bLen; i++) rawExcit[i] /= exStd;

    // Parallel formant filtering + breath blend + DC blocker
    const formed = new Float64Array(bLen);
    const nr = Math.max(0, Math.min(0.32, b.noiseLevel));
    let dcPrevX = 0;
    let dcPrevY = 0;
    let maxFormed = 1e-9;

    for (let i = 0; i < bLen; i++) {
      const t = i / sampleRate;
      const breath = breathBand.process(pink[i]);
      const onsetGate = b.f0Start < 210 ? 0.72 : 0.35 + 0.9 * Math.exp(-t / 0.025);
      const src = (1 - nr) * rawExcit[i] + nr * breath * onsetGate;

      const fOut = 0.78 * (res1.process(src) + 0.58 * res2.process(src) + 0.28 * res3.process(src)) + 0.22 * src;
      const dcClean = fOut - dcPrevX + 0.995 * dcPrevY;
      dcPrevX = fOut;
      dcPrevY = dcClean;
      formed[i] = dcClean;
      const a = Math.abs(dcClean);
      if (a > maxFormed) maxFormed = a;
    }

    // Gentle headroom compression, vocal fold AM, and smooth ADSR envelope
    const amHz = b.growlModHz ?? 0;
    const amDepth = amHz > 0 ? 0.32 : 0;
    for (let i = 0; i < bLen; i++) {
      const t = i / sampleRate;
      const y = Math.tanh(0.92 * (formed[i] / maxFormed));
      const am = amDepth > 0 ? 1 - 0.5 * amDepth * (1 - Math.cos(2 * Math.PI * amHz * t)) : 1;
      out[startIdx + i] += y * am * env[i];
    }
  }

  // Overall normalize with DC removal & headroom
  let mean = 0;
  for (let i = 0; i < numSamples; i++) mean += out[i];
  mean /= numSamples;
  let peak = 0;
  for (let i = 0; i < numSamples; i++) {
    out[i] -= mean;
    const a = Math.abs(out[i]);
    if (a > peak) peak = a;
  }
  const scale = peak > 1e-9 ? 0.85 / peak : 0;
  const f32 = new Float32Array(numSamples);
  for (let i = 0; i < numSamples; i++) {
    f32[i] = out[i] * scale;
  }

  // Smooth 6ms boundary fade so start/end are always clean zero-crossings
  const fade = Math.min(Math.floor(numSamples / 4), Math.round(0.006 * sampleRate));
  for (let i = 0; i < fade; i++) {
    const r = 0.5 * (1 - Math.cos((Math.PI * i) / fade));
    f32[i] *= r;
    f32[numSamples - 1 - i] *= r;
  }

  const metrics = measurePcmMetrics(f32, sampleRate);
  const wavBuffer = encodeMonoPcm16Wav(f32, sampleRate);
  const blobUrl = URL.createObjectURL(new Blob([wavBuffer], { type: "audio/wav" }));

  return {
    blobUrl,
    wavBuffer,
    samples: f32,
    sampleRate,
    durationSec: metrics.durationSec,
    peak: metrics.peak,
    rms: metrics.rms,
    dcOffset: metrics.dcOffset,
    maxSampleStep: metrics.maxSampleStep,
    clippedCount: metrics.clippedCount,
    burstCount: bursts.length,
    f0Hz: Math.round(avgF0),
    formantsHz: lastFormants,
  };
}

/** Built-in profile generator used by offline mockBackend fallback */
export function synthesizeProfileFallbackWav(profile: string, f0Override?: number, durOverride?: number): SynthOutput {
  const p = (profile || "bark").toLowerCase();
  if (p.includes("growl") || p.includes("grumble")) {
    return synthesizeCanineWav(
      [
        {
          startSec: 0.04,
          durSec: 0.42,
          f0Start: f0Override ?? 116,
          f0End: (f0Override ?? 116) + 12,
          f1: 320,
          f2: 780,
          f3: 1520,
          noiseLevel: 0.05,
          growlModHz: 28,
          subharmonicLevel: 0.34,
          trajectory: "low_modulated",
        },
        {
          startSec: 0.56,
          durSec: 0.34,
          f0Start: (f0Override ?? 116) + 6,
          f0End: (f0Override ?? 116) - 4,
          f1: 325,
          f2: 790,
          f3: 1540,
          noiseLevel: 0.05,
          growlModHz: 26,
          subharmonicLevel: 0.34,
          trajectory: "low_modulated",
        },
      ],
      durOverride ?? 1.0,
      101
    );
  }
  if (p.includes("whine") || p.includes("whimper") || p.includes("cry")) {
    return synthesizeCanineWav(
      [
        {
          startSec: 0.04,
          durSec: 0.9,
          f0Start: f0Override ?? 680,
          f0End: (f0Override ?? 680) + 260,
          f1: 1050,
          f2: 2150,
          f3: 3200,
          noiseLevel: 0.02,
          subharmonicLevel: 0,
          trajectory: "rising_arch",
        },
      ],
      durOverride ?? 1.05,
      202
    );
  }
  if (p.includes("howl")) {
    return synthesizeCanineWav(
      [
        {
          startSec: 0.05,
          durSec: 1.8,
          f0Start: f0Override ?? 360,
          f0End: (f0Override ?? 360) + 180,
          f1: 620,
          f2: 1280,
          f3: 2180,
          noiseLevel: 0.02,
          subharmonicLevel: 0,
          attackSec: 0.22,
          releaseSec: 0.32,
          trajectory: "sustained_arch",
        },
      ],
      durOverride ?? 2.0,
      303
    );
  }
  if (p.includes("yip") || p.includes("yelp")) {
    return synthesizeCanineWav(
      [
        { startSec: 0.03, durSec: 0.14, f0Start: 780, f0End: 980, f1: 1250, f2: 2350, noiseLevel: 0.04, subharmonicLevel: 0, trajectory: "rapid_arch" },
        { startSec: 0.25, durSec: 0.14, f0Start: 820, f0End: 1020, f1: 1250, f2: 2350, noiseLevel: 0.04, subharmonicLevel: 0, trajectory: "rapid_arch" },
      ],
      durOverride ?? 0.45,
      404
    );
  }
  // Default alert/recall bark (2–3 clean bursts)
  return synthesizeCanineWav(
    [
      { startSec: 0.04, durSec: 0.16, f0Start: f0Override ?? 360, f0End: 430, f1: 680, f2: 1420, noiseLevel: 0.06, subharmonicLevel: 0.14, trajectory: "stepped_bursts" },
      { startSec: 0.34, durSec: 0.17, f0Start: (f0Override ?? 360) + 15, f0End: 445, f1: 690, f2: 1450, noiseLevel: 0.06, subharmonicLevel: 0.14, trajectory: "stepped_bursts" },
    ],
    durOverride ?? 0.72,
    505
  );
}
