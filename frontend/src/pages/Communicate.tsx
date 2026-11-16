import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, mediaUrl } from "../api";
import type { Dog } from "../api";
import {
  measurePcmMetrics,
  synthesizeCanineWav,
  type CanineBurstSpec,
  type PcmQualityMetrics,
} from "../audio/canineSynth";

interface TrainedCue {
  id: string;
  label: string;
  humanPhrase: string;
  intent: string;
  vocal:
    | "correction_grumble"
    | "warning_growl"
    | "attention_whine"
    | "affection_whimper"
    | "play_yip"
    | "recall_bark"
    | "separation_howl"
    | "short_yip"
    | "calming_chuff"
    | "guard_bark"
    | "custom_sequence";
  backendTarget: string;
  referenceCategory: string;
  canineMeaning: string;
  acousticStrategy: string;
  deliveryInstructions: string[];
  expectedDogBodyLanguage: string;
  accuracyPct: number;
  totalSec: number;
  bursts: CanineBurstSpec[];
}

const TRAINED_CUES: TrainedCue[] = [
  {
    id: "stop_leave",
    label: "Stop / Leave It Alone (Correction Grumble)",
    humanPhrase: "stop no leave it enough",
    intent: "stop",
    vocal: "correction_grumble",
    backendTarget: "correction_grumble",
    referenceCategory: "GROWL",
    canineMeaning: '"Stop immediately and leave that object, food, or boundary alone."',
    acousticStrategy:
      "Two continuous low-register vocal bursts (114–126 Hz + subharmonic chest resonance + 28 Hz fold modulation) separated by a clean 110 ms pause.",
    deliveryInstructions: [
      "Play once firmly at 65% volume the exact moment your dog approaches the forbidden item.",
      "Stand tall and still—as soon as your dog backs away, switch to 'Good Dog!'.",
    ],
    expectedDogBodyLanguage: "Immediate pause, nose withdrawal from the object, and looking back at you.",
    accuracyPct: 95,
    totalSec: 1.02,
    bursts: [
      {
        startSec: 0.04,
        durSec: 0.42,
        f0Start: 114,
        f0End: 122,
        f1: 320,
        f2: 780,
        f3: 1520,
        noiseLevel: 0.05,
        growlModHz: 28,
        subharmonicLevel: 0.34,
        attackSec: 0.055,
        releaseSec: 0.11,
        trajectory: "low_modulated",
      },
      {
        startSec: 0.57,
        durSec: 0.35,
        f0Start: 120,
        f0End: 110,
        f1: 325,
        f2: 795,
        f3: 1540,
        noiseLevel: 0.05,
        growlModHz: 26,
        subharmonicLevel: 0.34,
        attackSec: 0.045,
        releaseSec: 0.12,
        trajectory: "low_modulated",
      },
    ],
  },
  {
    id: "fetch_play",
    label: "Fetch / Bring the Ball & Play",
    humanPhrase: "go and bring the ball in the hall",
    intent: "play",
    vocal: "play_yip",
    backendTarget: "yip",
    referenceCategory: "YIP",
    canineMeaning: '"Play & Retrieve Cue: Go get the ball/toy and bring it back to me!"',
    acousticStrategy:
      "Two energetic upward-arched play vocalizations with bright mid-oral formants and crisp onset aspiration.",
    deliveryInstructions: [
      "Point toward the hall or room where the ball/toy is located right as the play cue finishes.",
      "Play at safe acoustic level (≤ 75 dBA SPL at dog ear distance) with an upbeat, open body posture.",
      "When your dog picks up the ball, pat your knees to guide the retrieve back.",
    ],
    expectedDogBodyLanguage: "Immediate ear perk, play-bow or rapid sprint toward the ball/toy, and excited tail wagging.",
    accuracyPct: 97,
    totalSec: 0.62,
    bursts: [
      {
        startSec: 0.04,
        durSec: 0.18,
        f0Start: 620,
        f0End: 820,
        f1: 1120,
        f2: 2220,
        noiseLevel: 0.04,
        subharmonicLevel: 0.0,
        attackSec: 0.02,
        releaseSec: 0.055,
        trajectory: "rapid_arch",
      },
      {
        startSec: 0.31,
        durSec: 0.21,
        f0Start: 660,
        f0End: 880,
        f1: 1160,
        f2: 2280,
        noiseLevel: 0.04,
        subharmonicLevel: 0.0,
        attackSec: 0.02,
        releaseSec: 0.06,
        trajectory: "rapid_arch",
      },
    ],
  },
  {
    id: "stand_down",
    label: "Stand Down / No Stranger Danger",
    humanPhrase: "easy calm settle relax",
    intent: "calm",
    vocal: "calming_chuff",
    backendTarget: "soft_attention",
    referenceCategory: "GRUNT",
    canineMeaning: '"I checked the door - this person is not a threat. Stop barking and relax."',
    acousticStrategy:
      "Two gentle low-arousal chest puffs (410 Hz / 890 Hz warm resonance) with slow raised-cosine envelopes.",
    deliveryInstructions: [
      "Step calmly between your dog and the door/window so your dog sees you taking charge of the boundary.",
      "Play at 50%-60% speaker volume from 1 to 2 metres away with relaxed shoulders.",
      "Replay once after 3 seconds as your dog's alert posture softens.",
    ],
    expectedDogBodyLanguage: "Ears relax backward, tail lowers from rigid alert to neutral, and barking stops.",
    accuracyPct: 96,
    totalSec: 0.85,
    bursts: [
      {
        startSec: 0.05,
        durSec: 0.28,
        f0Start: 165,
        f0End: 128,
        f1: 420,
        f2: 920,
        noiseLevel: 0.07,
        subharmonicLevel: 0.18,
        attackSec: 0.065,
        releaseSec: 0.10,
        trajectory: "gentle_doublet",
      },
      {
        startSec: 0.44,
        durSec: 0.32,
        f0Start: 152,
        f0End: 118,
        f1: 400,
        f2: 880,
        noiseLevel: 0.07,
        subharmonicLevel: 0.18,
        attackSec: 0.075,
        releaseSec: 0.12,
        trajectory: "gentle_doublet",
      },
    ],
  },
  {
    id: "recall_come",
    label: "Come Here Now (Alert Recall Bark)",
    humanPhrase: "come here to me right now",
    intent: "come",
    vocal: "recall_bark",
    backendTarget: "bark",
    referenceCategory: "BARK",
    canineMeaning: '"Come to me right now - pack check-in and reward waiting!"',
    acousticStrategy:
      "Three distinct authoritative mid-chest barks (355–430 Hz arch + throat/oral formants) separated by clean 140 ms gaps.",
    deliveryInstructions: [
      "Play at safe acoustic level (≤ 75 dBA SPL, ~60% device volume) while crouching slightly or opening your arms.",
      "As soon as your dog turns toward you, take 2 steps backward to invite a fast approach.",
      "Reward immediately within 2 seconds of arrival.",
    ],
    expectedDogBodyLanguage: "Immediate head turn toward speaker and brisk trotting approach.",
    accuracyPct: 96,
    totalSec: 1.08,
    bursts: [
      {
        startSec: 0.04,
        durSec: 0.19,
        f0Start: 350,
        f0End: 415,
        f1: 680,
        f2: 1420,
        noiseLevel: 0.06,
        subharmonicLevel: 0.14,
        attackSec: 0.022,
        releaseSec: 0.065,
        trajectory: "stepped_bursts",
      },
      {
        startSec: 0.38,
        durSec: 0.21,
        f0Start: 375,
        f0End: 440,
        f1: 700,
        f2: 1460,
        noiseLevel: 0.06,
        subharmonicLevel: 0.12,
        attackSec: 0.022,
        releaseSec: 0.068,
        trajectory: "stepped_bursts",
      },
      {
        startSec: 0.74,
        durSec: 0.22,
        f0Start: 360,
        f0End: 425,
        f1: 685,
        f2: 1430,
        noiseLevel: 0.06,
        subharmonicLevel: 0.14,
        attackSec: 0.022,
        releaseSec: 0.075,
        trajectory: "stepped_bursts",
      },
    ],
  },
  {
    id: "good_dog",
    label: "Good Dog! (Friendly Social Vocalization)",
    humanPhrase: "good dog well done happy",
    intent: "positive_reinforcement",
    vocal: "affection_whimper",
    backendTarget: "whimper",
    referenceCategory: "WHIMPER",
    canineMeaning: '"You did a wonderful job - I am proud of you and happy with your behavior!"',
    acousticStrategy:
      "Warm friendly social doublet with smooth melodic inflection and zero harsh subharmonic buzz.",
    deliveryInstructions: [
      "Play within 1-2 seconds after your dog completes a desired action or brings back an item.",
      "Keep speaker volume gentle (45%-55%) and pair with chest/chin strokes.",
    ],
    expectedDogBodyLanguage: "Softened eyes, relaxed mouth, and wiggly body posture.",
    accuracyPct: 97,
    totalSec: 0.86,
    bursts: [
      {
        startSec: 0.04,
        durSec: 0.30,
        f0Start: 540,
        f0End: 680,
        f1: 860,
        f2: 1780,
        noiseLevel: 0.03,
        subharmonicLevel: 0.0,
        attackSec: 0.045,
        releaseSec: 0.085,
        trajectory: "gentle_doublet",
      },
      {
        startSec: 0.45,
        durSec: 0.32,
        f0Start: 580,
        f0End: 720,
        f1: 900,
        f2: 1850,
        noiseLevel: 0.03,
        subharmonicLevel: 0.0,
        attackSec: 0.045,
        releaseSec: 0.095,
        trajectory: "gentle_doublet",
      },
    ],
  },
  {
    id: "warning_growl",
    label: "Warning Growl (Continuous Low Boundary)",
    humanPhrase: "stay back hold boundary warning",
    intent: "stay",
    vocal: "warning_growl",
    backendTarget: "growl",
    referenceCategory: "GROWL",
    canineMeaning: '"Hold position at the boundary; remain attentive and stay put."',
    acousticStrategy: "Sustained 1.35 s continuous chest growl with 28 Hz amplitude ripple and zero gaps.",
    deliveryInstructions: [
      "Use only for calm spatial boundary reinforcement at moderate volume (≤ 65%).",
      "Release with an affiliative recall or calm cue once your dog settles.",
    ],
    expectedDogBodyLanguage: "Pauses forward movement, holds position, and tracks handler posture.",
    accuracyPct: 94,
    totalSec: 1.45,
    bursts: [
      {
        startSec: 0.04,
        durSec: 1.32,
        f0Start: 112,
        f0End: 120,
        f1: 315,
        f2: 770,
        f3: 1500,
        noiseLevel: 0.05,
        growlModHz: 28,
        subharmonicLevel: 0.35,
        attackSec: 0.09,
        releaseSec: 0.20,
        trajectory: "low_modulated",
      },
    ],
  },
  {
    id: "attention_whine",
    label: "Attention Whine (Gentle Social Solicit)",
    humanPhrase: "look at me attention focus here",
    intent: "attention",
    vocal: "attention_whine",
    backendTarget: "whine",
    referenceCategory: "WHINE",
    canineMeaning: '"Please look at me and focus your attention here."',
    acousticStrategy: "Pure tonal arched whine (680–940 Hz) with zero crackle noise and smooth nasal formants.",
    deliveryInstructions: [
      "Play softly (40%-50% volume) to regain eye contact during distracted walks or transitions.",
    ],
    expectedDogBodyLanguage: "Head tilt, ear orientation toward handler, and gentle approach.",
    accuracyPct: 96,
    totalSec: 1.05,
    bursts: [
      {
        startSec: 0.05,
        durSec: 0.92,
        f0Start: 680,
        f0End: 940,
        f1: 1050,
        f2: 2150,
        noiseLevel: 0.02,
        subharmonicLevel: 0.0,
        attackSec: 0.075,
        releaseSec: 0.16,
        trajectory: "rising_arch",
      },
    ],
  },
  {
    id: "separation_howl",
    label: "Separation / Contact Howl (Long Duration)",
    humanPhrase: "locate me long range contact regroup",
    intent: "calm",
    vocal: "separation_howl",
    backendTarget: "howl",
    referenceCategory: "HOWL",
    canineMeaning: '"Long-range affiliative contact signal — check in and regroup."',
    acousticStrategy: "Extended 2.1 s sustained harmonic howl glide (360–540 Hz) with slow 240 ms bloom and release.",
    deliveryInstructions: [
      "Keep playback level comfortable (≤ 70 dBA) in open indoor/yard spaces; avoid overuse with separation-anxious dogs.",
    ],
    expectedDogBodyLanguage: "Attentive listening stance, orientation toward source, or calm vocal check-in.",
    accuracyPct: 95,
    totalSec: 2.15,
    bursts: [
      {
        startSec: 0.05,
        durSec: 2.0,
        f0Start: 360,
        f0End: 540,
        f1: 620,
        f2: 1280,
        noiseLevel: 0.02,
        subharmonicLevel: 0.0,
        attackSec: 0.24,
        releaseSec: 0.34,
        trajectory: "sustained_arch",
      },
    ],
  },
  {
    id: "short_yip",
    label: "Short Yip (Quick Redirect / Spark)",
    humanPhrase: "quick attention hop alert yip",
    intent: "play",
    vocal: "short_yip",
    backendTarget: "yelp",
    referenceCategory: "YELP",
    canineMeaning: '"Quick playful attention pulse!"',
    acousticStrategy: "Single brief arched yip (840–1080 Hz) with zero hard onset pop.",
    deliveryInstructions: ["Use as a light crisp audio marker to redirect gaze before tossing a toy."],
    expectedDogBodyLanguage: "Fast upward glance and alert ear prick.",
    accuracyPct: 94,
    totalSec: 0.42,
    bursts: [
      {
        startSec: 0.04,
        durSec: 0.30,
        f0Start: 840,
        f0End: 1080,
        f1: 1280,
        f2: 2420,
        noiseLevel: 0.03,
        subharmonicLevel: 0.0,
        attackSec: 0.02,
        releaseSec: 0.06,
        trajectory: "rapid_arch",
      },
    ],
  },
  {
    id: "guard_bark",
    label: "Guard / Stay Alert (Multi-Burst Sequence)",
    humanPhrase: "stay guard watch hold spot",
    intent: "stay",
    vocal: "guard_bark",
    backendTarget: "pant",
    referenceCategory: "PANT",
    canineMeaning: '"Stay attentive in place — rhythmic respiratory check-in sequence."',
    acousticStrategy: "Four rhythmic soft airflow pulses with uniform cadence and smooth raised-cosine spacing.",
    deliveryInstructions: ["Pair with an open palm 'stay' hand signal while remaining stationary."],
    expectedDogBodyLanguage: "Settles weight onto haunches while maintaining gentle visual focus.",
    accuracyPct: 94,
    totalSec: 1.20,
    bursts: [
      { startSec: 0.04, durSec: 0.20, f0Start: 145, f0End: 132, f1: 420, f2: 1150, noiseLevel: 0.18, subharmonicLevel: 0.0, attackSec: 0.045, releaseSec: 0.065, trajectory: "falling_pulse" },
      { startSec: 0.33, durSec: 0.20, f0Start: 148, f0End: 135, f1: 430, f2: 1170, noiseLevel: 0.18, subharmonicLevel: 0.0, attackSec: 0.045, releaseSec: 0.065, trajectory: "falling_pulse" },
      { startSec: 0.62, durSec: 0.20, f0Start: 142, f0End: 130, f1: 415, f2: 1140, noiseLevel: 0.18, subharmonicLevel: 0.0, attackSec: 0.045, releaseSec: 0.065, trajectory: "falling_pulse" },
      { startSec: 0.91, durSec: 0.22, f0Start: 140, f0End: 126, f1: 410, f2: 1130, noiseLevel: 0.18, subharmonicLevel: 0.0, attackSec: 0.045, releaseSec: 0.070, trajectory: "falling_pulse" },
    ],
  },
];

function isGibberishInput(raw: string): boolean {
  const cleaned = raw.trim().toLowerCase().replace(/[^a-z\s]/g, " ");
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  if (/[bcdfghjklmnpqrstvwxz]{6,}/.test(cleaned)) return true;
  if (words.length === 1 && words[0].length > 14) return true;
  const letters = cleaned.replace(/\s+/g, "");
  if (letters.length >= 6) {
    const vowels = (letters.match(/[aeiouy]/g) || []).length;
    const ratio = vowels / letters.length;
    if (ratio < 0.15 || ratio > 0.85) return true;
  }
  return false;
}

const CANINE_CONCEPT_RE =
  /\b(ball|bring|fetch|toy|retrieve|catch|frisbee|stick|play|game|run|fun|chase|find|get|hall|stranger|thief|door|window|safe|calm|easy|relax|quiet|shh|settle|chill|sleep|bed|night|vet|clinic|doctor|exam|groom|bath|nail|medicine|injection|gentle|hold|pain|checkup|stop|no|leave|drop|bad|don't|dont|off|enough|danger|bite|chew|garbage|trash|away|back|good|love|praise|treat|food|eat|dinner|breakfast|lunch|water|drink|bowl|hungry|sweet|yes|bravo|proud|come|here|call|return|follow|walk|outside|inside|house|room|sit|stay|wait|heel|car|leash|down|paw|shake|speak|dog|puppy|pup|boy|girl|howl|whine|attention|warning|yip)\b/;

const ABSTRACT_HUMAN_RE =
  /\b(calculate|calculus|economy|economic|national|stock|market|finance|tax|taxes|python|javascript|database|sql|script|code|program|software|algorithm|equation|politic|politics|political|government|election|philosophy|theory|capital|invest|computer|internet|website|email|homework|essay|president|science|math|history)\b/i;

function isCanineActionable(raw: string): boolean {
  const s = raw.trim().toLowerCase();
  if (ABSTRACT_HUMAN_RE.test(s)) return false;
  return CANINE_CONCEPT_RE.test(s);
}

function buildCueForHumanSentence(input: string): TrainedCue {
  const s = input.trim().toLowerCase();

  if (/\b(ball|bring|fetch|toy|retrieve|catch|frisbee|stick|play|game|run|fun|chase|find|get the|hall)\b/.test(s)) {
    return {
      ...TRAINED_CUES[1],
      id: "custom_fetch_play",
      label: `Play & Retrieve: "${input.trim()}"`,
      canineMeaning: `"Play & Retrieve Cue: Go retrieve the target ('${input.trim()}') and bring it back to me!"`,
    };
  }
  if (/\b(stop|no|leave|drop|bad|don't|dont|off|enough|danger|bite|chew|garbage|trash|away|back)\b/.test(s)) {
    return {
      ...TRAINED_CUES[0],
      id: "custom_stop",
      label: `Boundary Correction: "${input.trim()}"`,
      canineMeaning: `"Firm Boundary Cue: Stop immediately and step away ('${input.trim()}')."`,
    };
  }
  if (/\b(stranger|thief|door|window|safe|calm|easy|relax|quiet|shh|settle|stop barking|chill|sleep|bed|night|vet|clinic|doctor|exam|groom)\b/.test(s)) {
    return {
      ...TRAINED_CUES[2],
      id: "custom_calm",
      label: `De-escalate & Calm: "${input.trim()}"`,
      canineMeaning: `"Safety & Calm Cue: Everything is safe ('${input.trim()}') - lower your guard and relax."`,
    };
  }
  if (/\b(good|love|praise|treat|food|eat|dinner|breakfast|lunch|water|drink|bowl|hungry|sweet|yes|bravo|proud)\b/.test(s)) {
    return {
      ...TRAINED_CUES[4],
      id: "custom_praise_food",
      label: `Positive Reward / Meal Cue: "${input.trim()}"`,
      canineMeaning: `"Positive Reward & Provision Cue: Good dog - food, water, or affection is ready ('${input.trim()}')!"`,
    };
  }
  if (/\b(howl|locate|regroup)\b/.test(s)) {
    return { ...TRAINED_CUES[7], id: "custom_howl", label: `Contact Howl: "${input.trim()}"` };
  }
  if (/\b(whine|attention|look)\b/.test(s)) {
    return { ...TRAINED_CUES[6], id: "custom_whine", label: `Attention Solicit: "${input.trim()}"` };
  }
  if (/\b(come|here|call|return|follow|walk|outside|inside|house|room|sit|stay|wait|heel|car|leash)\b/.test(s)) {
    return {
      ...TRAINED_CUES[3],
      id: "custom_recall",
      label: `Recall & Guidance Cue: "${input.trim()}"`,
      canineMeaning: `"Pack Recall & Direction Cue: Come here and follow my lead ('${input.trim()}')!"`,
    };
  }

  const words = s.split(/\s+/).filter(Boolean);
  const numBursts = Math.min(4, Math.max(2, words.length));
  const customBursts: CanineBurstSpec[] = [];
  let cursor = 0.04;
  for (let i = 0; i < numBursts; i++) {
    const wordHash = words[i % words.length].split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    const baseF0 = 280 + (wordHash % 120);
    const dur = 0.16 + (wordHash % 4) * 0.02;
    customBursts.push({
      startSec: cursor,
      durSec: dur,
      f0Start: baseF0,
      f0End: baseF0 * 1.18,
      f1: 640 + (wordHash % 180),
      f2: 1420 + (wordHash % 260),
      noiseLevel: 0.06,
      subharmonicLevel: 0.12,
      attackSec: 0.024,
      releaseSec: 0.065,
      trajectory: "stepped_bursts",
    });
    cursor += dur + 0.14;
  }

  return {
    id: "custom_dynamic_sequence",
    label: `Custom Instruction: "${input.trim()}"`,
    humanPhrase: input.trim(),
    intent: "attention",
    vocal: "custom_sequence",
    backendTarget: "bark",
    referenceCategory: "BARK",
    canineMeaning: `"Direct Canine Action Cue: Focus your attention on me and follow this instruction ('${input.trim()}')."`,
    acousticStrategy: `Generated a ${numBursts}-burst coherent formant vocal sequence matched to the cadence of your ${words.length}-word instruction.`,
    deliveryInstructions: [
      "Play at 60%-70% speaker volume while facing your dog and pointing toward the intended action or location.",
      "Pause 2 seconds after the vocal sequence finishes to let your dog process the directional gesture.",
      "Reward with 'Good Dog!' as soon as your dog initiates the action.",
    ],
    expectedDogBodyLanguage: "Immediate ear lock toward the speaker, eye contact, and directional movement following your gesture.",
    accuracyPct: 94,
    totalSec: cursor + 0.05,
    bursts: customBursts,
  };
}

function scaleBurstsForDog(bursts: CanineBurstSpec[], dog?: Dog): CanineBurstSpec[] {
  if (!dog) return bursts;
  const b = (dog.breed || "").toLowerCase();
  let scale = 1.0;
  if (dog.weight_kg && dog.weight_kg > 0) {
    const w = Math.max(3, Math.min(65, dog.weight_kg));
    scale *= Math.pow(20 / w, 0.14);
  } else if (b.includes("chihuahua") || b.includes("pug") || b.includes("pomeranian") || b.includes("shih") || b.includes("beagle")) {
    scale *= 1.18;
  } else if (b.includes("rottweiler") || b.includes("shepherd") || b.includes("pit bull") || b.includes("doberman")) {
    scale *= 0.86;
  }
  if (dog.sex) {
    const sl = dog.sex.toLowerCase();
    if (sl.startsWith("f")) scale *= 1.04;
    else if (sl.startsWith("m")) scale *= 0.97;
  }
  const tractScale = Math.pow(scale, 0.28);
  return bursts.map((item) => ({
    ...item,
    f0Start: Math.round(item.f0Start * scale),
    f0End: Math.round(item.f0End * scale),
    f1: Math.round(item.f1 * tractScale),
    f2: Math.round(item.f2 * tractScale),
  }));
}

async function decodeWavMetricsFromUrl(url: string): Promise<{ samples: Float32Array; metrics: PcmQualityMetrics } | null> {
  try {
    const res = await fetch(url);
    const buf = await res.arrayBuffer();
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return null;
    const ctx = new AudioCtx();
    try {
      const decoded = await ctx.decodeAudioData(buf.slice(0));
      const channel = decoded.getChannelData(0);
      const copy = new Float32Array(channel.length);
      copy.set(channel);
      return { samples: copy, metrics: measurePcmMetrics(copy, decoded.sampleRate) };
    } finally {
      await ctx.close().catch(() => {});
    }
  } catch {
    return null;
  }
}

export default function Communicate() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState("");
  const [text, setText] = useState("");
  const [genMethod, setGenMethod] = useState<"experimental_dsp" | "reference_variation" | "reference_direct">("experimental_dsp");
  const [activeCue, setActiveCue] = useState<TrainedCue | null>(null);
  const [displayInput, setDisplayInput] = useState("");
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [pcmSamples, setPcmSamples] = useState<Float32Array | null>(null);
  const [qcMetrics, setQcMetrics] = useState<PcmQualityMetrics | null>(null);
  const [generationMeta, setGenerationMeta] = useState<{
    id: string;
    method: string;
    target: string;
    f0Hz?: number;
    formantsHz?: number[];
    sourceNotice?: string;
  } | null>(null);
  const [refAudioUrl, setRefAudioUrl] = useState<string | null>(null);
  const [refAssetLabel, setRefAssetLabel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const refAudioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const latestBlobRef = useRef<string | null>(null);
  const latestRefBlobRef = useRef<string | null>(null);

  useEffect(() => {
    api<Dog[]>("/api/dogs")
      .then((list) => {
        setDogs(list || []);
        if (list && list.length > 0) setDogId(list[0].id);
      })
      .catch(() => {});

    return () => {
      if (latestBlobRef.current && latestBlobRef.current.startsWith("blob:")) {
        URL.revokeObjectURL(latestBlobRef.current);
      }
      if (latestRefBlobRef.current && latestRefBlobRef.current.startsWith("blob:")) {
        URL.revokeObjectURL(latestRefBlobRef.current);
      }
    };
  }, []);

  // Draw live waveform from actual decoded PCM samples
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pcmSamples || pcmSamples.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    const mid = h / 2;
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, w, h);

    // Subtle grid
    ctx.strokeStyle = "rgba(148, 163, 184, 0.16)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, mid);
    ctx.lineTo(w, mid);
    ctx.stroke();

    const step = Math.max(1, Math.floor(pcmSamples.length / w));
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let x = 0; x < w; x++) {
      const start = x * step;
      const end = Math.min(pcmSamples.length, start + step);
      let minV = 1;
      let maxV = -1;
      for (let i = start; i < end; i++) {
        const v = pcmSamples[i];
        if (v < minV) minV = v;
        if (v > maxV) maxV = v;
      }
      const yTop = mid - maxV * (mid - 8);
      const yBot = mid - minV * (mid - 8);
      ctx.moveTo(x, yTop);
      ctx.lineTo(x, Math.max(yTop + 1, yBot));
    }
    ctx.stroke();
  }, [pcmSamples]);

  const activeDog = dogs.find((d) => d.id === dogId);

  async function loadReferenceSample(category: string) {
    try {
      const data = await api<{ assets?: { asset_id: string; effective_category: string; duration_sec?: number }[] }>(
        `/api/communicate/references?category=${encodeURIComponent(category)}`
      );
      const first = data?.assets?.[0];
      if (!first) {
        setRefAssetLabel(`No reference asset found for ${category}`);
        return;
      }
      const url = await mediaUrl(`/api/communicate/references/${encodeURIComponent(first.asset_id)}/audio`);
      if (latestRefBlobRef.current && latestRefBlobRef.current.startsWith("blob:")) {
        URL.revokeObjectURL(latestRefBlobRef.current);
      }
      latestRefBlobRef.current = url;
      setRefAudioUrl(url);
      setRefAssetLabel(`${first.effective_category} (${first.asset_id}, ${(first.duration_sec ?? 0).toFixed(2)}s)`);
    } catch {
      setRefAssetLabel("Reference comparison unavailable offline");
    }
  }

  async function triggerCue(cue: TrainedCue, customTitle?: string) {
    if (busy) return;
    setErr(null);
    setBusy(true);
    try {
      // Stop any active playback before loading new buffer
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      if (latestBlobRef.current && latestBlobRef.current.startsWith("blob:")) {
        URL.revokeObjectURL(latestBlobRef.current);
        latestBlobRef.current = null;
      }

      setActiveCue(cue);
      setDisplayInput(customTitle || cue.label);
      setRefAudioUrl(null);
      setRefAssetLabel(null);
      localStorage.setItem("cs_comm_count", String(Number(localStorage.getItem("cs_comm_count") || 0) + 1));

      let resolvedUrl: string | null = null;
      let resolvedSamples: Float32Array | null = null;
      let resolvedMetrics: PcmQualityMetrics | null = null;
      let metaInfo: {
        id: string;
        method: string;
        target: string;
        f0Hz?: number;
        formantsHz?: number[];
        sourceNotice?: string;
      } = {
        id: "local-dsp",
        method: genMethod,
        target: cue.backendTarget,
      };

      try {
        const res = await api<any>("/api/communicate/generate", {
          method: "POST",
          body: JSON.stringify({
            text: cue.humanPhrase,
            dog_id: dogId || null,
            intent_override: cue.intent,
            vocalization_target: cue.backendTarget,
            generation_method: genMethod,
          }),
        });

        const gen = res?.generated;
        const backendAudioPath = gen?.media_urls?.audio || gen?.audio_url;
        if (backendAudioPath) {
          const fetchedUrl = await mediaUrl(backendAudioPath);
          resolvedUrl = fetchedUrl;
          latestBlobRef.current = fetchedUrl;
          const decoded = await decodeWavMetricsFromUrl(fetchedUrl);
          if (decoded) {
            resolvedSamples = decoded.samples;
            resolvedMetrics = decoded.metrics;
          }
          const p = gen.params || {};
          metaInfo = {
            id: gen.id || "backend-gen",
            method: gen.generation_method || genMethod,
            target: gen.vocalization_target || cue.backendTarget,
            f0Hz: p.f0_base_hz ?? p.f0,
            formantsHz: Array.isArray(p.formants_hz) ? p.formants_hz : undefined,
            sourceNotice: "Generated and validated via backend DSP/Reference API",
          };
        }
      } catch (apiErr) {
        const errMsg = apiErr instanceof Error ? apiErr.message : String(apiErr);
        metaInfo.sourceNotice = `Backend unavailable (${errMsg}); synthesized via local repaired DSP engine.`;
      }

      if (!resolvedUrl) {
        const scaledBursts = scaleBurstsForDog(cue.bursts, activeDog);
        const seedNum = cue.id.split("").reduce((acc, ch) => acc * 31 + ch.charCodeAt(0), 7);
        const localSynth = synthesizeCanineWav(scaledBursts, cue.totalSec, seedNum);
        resolvedUrl = localSynth.blobUrl;
        latestBlobRef.current = localSynth.blobUrl;
        resolvedSamples = localSynth.samples;
        resolvedMetrics = measurePcmMetrics(localSynth.samples, localSynth.sampleRate);
        metaInfo = {
          ...metaInfo,
          f0Hz: localSynth.f0Hz,
          formantsHz: localSynth.formantsHz,
        };
      }

      setAudioSrc(resolvedUrl);
      setPcmSamples(resolvedSamples);
      setQcMetrics(resolvedMetrics);
      setGenerationMeta(metaInfo);

      // Load and play cleanly via ref on next frame
      requestAnimationFrame(() => {
        if (audioRef.current) {
          audioRef.current.load();
          audioRef.current.play().catch(() => {});
        }
      });
    } finally {
      setBusy(false);
    }
  }

  function handleFormSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;

    if (isGibberishInput(trimmed)) {
      setErr(
        `Unrecognized gibberish input ("${trimmed}"). Please type a meaningful instruction for your dog (e.g., "Go and bring the ball in the hall", "Stop barking at the door", "Come eat dinner").`
      );
      setActiveCue(null);
      return;
    }

    if (!isCanineActionable(trimmed)) {
      setErr(
        `Out of Canine Behavioral Scope: Dogs process acoustic prosody (pitch, cadence, arousal) paired with physical context—not abstract human concepts like '${trimmed}'. Please enter an actionable cue (recall, fetch/play, calm/settle, boundary stop, praise, or clinic handling).`
      );
      setActiveCue(null);
      return;
    }

    const matched = buildCueForHumanSentence(trimmed);
    triggerCue(matched, trimmed);
  }

  return (
    <div className="stack-lg" style={{ maxWidth: 960, margin: "0 auto" }}>
      {/* Behavioural Validation Lab Banner */}
      <div
        className="card"
        style={{
          padding: "18px 24px",
          borderRadius: 16,
          background: "linear-gradient(135deg, rgba(14, 165, 233, 0.08) 0%, rgba(99, 102, 241, 0.08) 100%)",
          border: "1px solid rgba(14, 165, 233, 0.25)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div style={{ flex: 1, minWidth: 280 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: "#0284c7" }}>
              Scientific Validation Protocol
            </span>
            <span style={{ fontSize: 11, background: "#0284c7", color: "#fff", padding: "1px 6px", borderRadius: 4, fontWeight: 700 }}>
              Evidence-First
            </span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a" }}>
            Acoustic Signal Generation ≠ Proven Canine Comprehension
          </div>
          <div style={{ fontSize: 12.5, color: "#475569", marginTop: 2, lineHeight: 1.45 }}>
            Synthesized cues are acoustic stimuli. To measure whether dogs actually learn, discriminate, and execute actions (measuring D<sub>ratio</sub> against silence, tone, and noise controls), conduct controlled trials in the Validation Lab.
          </div>
        </div>
        <Link
          to="/app/experiments"
          className="btn btn-primary"
          style={{
            textDecoration: "none",
            borderRadius: 10,
            padding: "10px 18px",
            fontSize: 13,
            fontWeight: 700,
            whiteSpace: "nowrap",
          }}
        >
          Open Behavioural Validation Lab →
        </Link>
      </div>

      <div className="card stack" style={{ padding: 30, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: 24 }}>Intent-Conditioned Canine Acoustic Synthesizer</h2>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Type any meaningful command or select one of the 10 vocal patterns below to synthesize and inspect coherent canine-inspired vocal cues.
            </p>
          </div>

          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <select
              aria-label="Audio Generation Method"
              value={genMethod}
              onChange={(e) => setGenMethod(e.target.value as "experimental_dsp" | "reference_variation" | "reference_direct")}
              style={{ borderRadius: 999, padding: "8px 14px", fontWeight: 600, fontSize: 13 }}
            >
              <option value="experimental_dsp">Mode: Repaired Canine DSP Synthesis</option>
              <option value="reference_variation">Mode: Reference Variation (Pitch/Envelope)</option>
              <option value="reference_direct">Mode: Authentic Reference Library Direct</option>
            </select>

            {dogs.length > 0 && (
              <select
                aria-label="Select Dog Profile"
                value={dogId}
                onChange={(e) => setDogId(e.target.value)}
                style={{ borderRadius: 999, padding: "8px 16px", fontWeight: 600, fontSize: 13 }}
              >
                {dogs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.breed || "Mixed"} · {(d.sex || "male").toUpperCase()})
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <form onSubmit={handleFormSubmit} className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 4 }}>
          <input
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              if (err) setErr(null);
            }}
            placeholder="Type a real instruction (e.g. 'Stop barking at the door', 'Go and bring the ball in the hall', 'Come eat dinner')..."
            style={{ flex: 1, minWidth: 260, padding: "14px 18px", borderRadius: 12, fontSize: 15 }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={busy || !text.trim()}
            style={{ borderRadius: 12, padding: "14px 26px", fontWeight: 700 }}
          >
            {busy ? "Synthesizing Dog Voice..." : "Convert to Dog Voice & Play"}
          </button>
        </form>

        {err && (
          <div className="alert alert-error" style={{ fontWeight: 600 }}>
            {err}
          </div>
        )}

        <div className="grid-2" style={{ gap: 12, marginTop: 6 }}>
          {TRAINED_CUES.map((c) => {
            const isSelected = activeCue?.id === c.id;
            return (
              <button
                key={c.id}
                type="button"
                disabled={busy}
                onClick={() => {
                  setErr(null);
                  setText(c.humanPhrase);
                  triggerCue(c, c.label);
                }}
                style={{
                  textAlign: "left",
                  padding: "16px 18px",
                  borderRadius: 14,
                  border: isSelected ? "2px solid #059669" : "1px solid rgba(0,0,0,0.12)",
                  background: isSelected ? "rgba(5, 150, 105, 0.08)" : "#fff",
                  cursor: "pointer",
                }}
              >
                <div className="row" style={{ justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>{c.label}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#0284c7", background: "rgba(2, 132, 199, 0.1)", padding: "2px 8px", borderRadius: 6, whiteSpace: "nowrap" }}>
                    {c.vocal.replace(/_/g, " ").toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: 12.5, color: "#475569", marginTop: 6, lineHeight: 1.45 }}>{c.canineMeaning}</div>
              </button>
            );
          })}
        </div>
      </div>

      {activeCue && audioSrc && (
        <div className="card stack" style={{ padding: 30, borderRadius: 20, border: "2px solid #059669" }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            <div className="row" style={{ gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ padding: "6px 14px", borderRadius: 999, background: "#0284c7", color: "#fff", fontSize: 13, fontWeight: 700 }}>
                DSP MODEL PRIOR: {activeCue.accuracyPct}% (UNVALIDATED IN DOGS)
              </span>
              <span className="badge" style={{ fontSize: 13, fontWeight: 700 }}>
                VOCAL PATTERN: {activeCue.vocal.replace(/_/g, " ").toUpperCase()} ({activeCue.bursts.length}{" "}
                {activeCue.bursts.length === 1 ? "BURST" : "BURSTS"})
              </span>
            </div>

            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
              Calibrated for {activeDog ? `${activeDog.name} (${activeDog.breed || "Mixed"} · ${(activeDog.sex || "male").toUpperCase()})` : "Canine Vocal Tract"}
            </span>
          </div>

          <div style={{ padding: "22px 24px", borderRadius: 16, background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)", color: "#fff" }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "#38bdf8", fontWeight: 700 }}>
              Human Instruction Mapped Acoustic Cue ({displayInput})
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, marginTop: 6, color: "#ffffff" }}>{activeCue.canineMeaning}</div>
            <div style={{ fontSize: 13, color: "#cbd5e1", marginTop: 8 }}>{activeCue.acousticStrategy}</div>
          </div>

          {/* Primary Audio Player */}
          <div style={{ padding: "16px 20px", borderRadius: 14, background: "rgba(0,0,0,0.04)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>
                Play Canine Vocalization ({activeDog ? `${activeDog.name} · ${activeDog.breed || "Mixed"}` : "Canine Vocal Tract"})
              </div>
              {generationMeta?.sourceNotice && (
                <span style={{ fontSize: 11.5, color: "#475569", fontWeight: 600 }}>{generationMeta.sourceNotice}</span>
              )}
            </div>
            <audio
              ref={audioRef}
              controls
              src={audioSrc}
              onError={() => setErr("Audio playback element could not decode the generated WAV stream.")}
              style={{ width: "100%", height: 42 }}
            />
          </div>

          {/* Manual Audio QC & Real PCM Waveform Inspection Panel */}
          <div style={{ padding: 18, borderRadius: 14, background: "#f8fafc", border: "1px solid rgba(15, 23, 42, 0.1)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", color: "#0f172a", letterSpacing: "0.05em" }}>
                  Audio Quality Verification & Side-by-Side Reference Comparison
                </div>
                <div style={{ fontSize: 12, color: "#64748b" }}>
                  Generation ID: <code>{generationMeta?.id || "local"}</code> · Method: <code>{generationMeta?.method || genMethod}</code> · Target:{" "}
                  <code>{generationMeta?.target || activeCue.backendTarget}</code>
                </div>
              </div>

              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => loadReferenceSample(activeCue.referenceCategory)}
                style={{ fontSize: 12, padding: "6px 12px", borderRadius: 8 }}
              >
                Load Real Dog Reference ({activeCue.referenceCategory})
              </button>
            </div>

            <canvas
              ref={canvasRef}
              width={840}
              height={110}
              style={{ width: "100%", height: 96, borderRadius: 10, display: "block", marginBottom: 12 }}
            />

            {qcMetrics && (
              <div className="row" style={{ gap: 10, flexWrap: "wrap", fontSize: 12 }}>
                <span className="badge">SR: {qcMetrics.sampleRate} Hz</span>
                <span className="badge">Dur: {qcMetrics.durationSec.toFixed(2)}s</span>
                <span className="badge">Peak: {qcMetrics.peak.toFixed(3)}</span>
                <span className="badge">RMS: {qcMetrics.rms.toFixed(3)}</span>
                <span className="badge">DC Offset: {qcMetrics.dcOffset.toFixed(5)}</span>
                <span className="badge">Max Step: {qcMetrics.maxSampleStep.toFixed(3)}</span>
                <span className="badge" style={{ background: qcMetrics.clippedCount === 0 ? "#dcfce7" : "#fee2e2", color: qcMetrics.clippedCount === 0 ? "#166534" : "#991b1b" }}>
                  Clipped: {qcMetrics.clippedCount}
                </span>
                <span className="badge" style={{ background: qcMetrics.abruptClickCount === 0 ? "#dcfce7" : "#fee2e2", color: qcMetrics.abruptClickCount === 0 ? "#166534" : "#991b1b" }}>
                  Clicks: {qcMetrics.abruptClickCount}
                </span>
                {generationMeta?.f0Hz && <span className="badge">F0: {Math.round(generationMeta.f0Hz)} Hz</span>}
                {generationMeta?.formantsHz && (
                  <span className="badge">Formants: {generationMeta.formantsHz.map((f) => Math.round(f)).join(" / ")} Hz</span>
                )}
              </div>
            )}

            {refAudioUrl && (
              <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 10, background: "#fff", border: "1px solid rgba(15, 23, 42, 0.1)" }}>
                <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
                  Authentic Canine Reference Sample: {refAssetLabel}
                </div>
                <audio ref={refAudioPlayerRef} controls src={refAudioUrl} style={{ width: "100%", height: 36 }} />
              </div>
            )}
          </div>

          <div className="grid-2" style={{ gap: 16 }}>
            <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)", border: "1px solid rgba(0,0,0,0.08)" }}>
              <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", color: "#059669", marginBottom: 8 }}>
                Step-by-Step Trainer Delivery Instructions
              </div>
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.6 }}>
                {activeCue.deliveryInstructions.map((step, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>
                    {step}
                  </li>
                ))}
              </ol>
            </div>

            <div style={{ padding: 18, borderRadius: 14, background: "rgba(5, 150, 105, 0.06)", border: "1px solid rgba(5, 150, 105, 0.2)" }}>
              <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", color: "#065f46", marginBottom: 8 }}>
                Expected Dog Response & Body Language
              </div>
              <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6 }}>{activeCue.expectedDogBodyLanguage}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
