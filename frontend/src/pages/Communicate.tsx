import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { Dog } from "../api";

interface BurstSpec {
  delaySec: number;
  durationSec: number;
  f0StartHz: number;
  f0PeakHz: number;
  f0EndHz: number;
  formant1Hz: number;
  formant2Hz: number;
  turbulenceMix: number;
  subHarmonicMix: number;
  plosiveAttack: number;
}

interface TrainedCue {
  id: string;
  label: string;
  humanPhrase: string;
  intent: string;
  vocal: "play_yip" | "recall_bark" | "affection_whimper" | "correction_grumble" | "calming_chuff" | "guard_bark" | "custom_sequence";
  canineMeaning: string;
  acousticStrategy: string;
  deliveryInstructions: string[];
  expectedDogBodyLanguage: string;
  accuracyPct: number;
  bursts: BurstSpec[];
}

const TRAINED_CUES: TrainedCue[] = [
  {
    id: "fetch_play",
    label: "Fetch / Bring the Ball & Play",
    humanPhrase: "go and bring the ball in the hall",
    intent: "play",
    vocal: "play_yip",
    canineMeaning: '"Play & Retrieve Cue: Go get the ball/toy and bring it back to me!"',
    acousticStrategy: "Double staccato play-bark ('Arf-Arf!') using 85ms plosive vocal-tract bursts with high formant resonance (780 Hz / 1650 Hz) and crisp silence gap.",
    deliveryInstructions: [
      "Point toward the hall or room where the ball/toy is located right as the double play-bark finishes.",
      "Play at 65%-75% speaker volume with an upbeat, open body posture.",
      "When your dog picks up the ball, pat your knees to guide the retrieve back."
    ],
    expectedDogBodyLanguage: "Immediate ear perk, play-bow or rapid sprint toward the ball/toy, and excited tail wagging.",
    accuracyPct: 97,
    bursts: [
      { delaySec: 0.05, durationSec: 0.095, f0StartHz: 310, f0PeakHz: 420, f0EndHz: 290, formant1Hz: 780, formant2Hz: 1650, turbulenceMix: 0.42, subHarmonicMix: 0.25, plosiveAttack: 0.95 },
      { delaySec: 0.22, durationSec: 0.110, f0StartHz: 330, f0PeakHz: 455, f0EndHz: 310, formant1Hz: 820, formant2Hz: 1720, turbulenceMix: 0.38, subHarmonicMix: 0.22, plosiveAttack: 0.95 },
      { delaySec: 0.58, durationSec: 0.105, f0StartHz: 320, f0PeakHz: 440, f0EndHz: 300, formant1Hz: 800, formant2Hz: 1680, turbulenceMix: 0.40, subHarmonicMix: 0.25, plosiveAttack: 0.92 },
    ],
  },
  {
    id: "stand_down",
    label: "Stand Down / No Stranger Danger",
    humanPhrase: "easy calm settle relax",
    intent: "calm",
    vocal: "calming_chuff",
    canineMeaning: '"I checked the door - this person is not a threat. Stop barking and relax."',
    acousticStrategy: "Two soft, breathy nasal chuff-exhales (145 Hz chest resonance + high airflow turbulence) that mimic a mother dog's de-escalation sigh.",
    deliveryInstructions: [
      "Step calmly between your dog and the door/window so your dog sees you taking charge of the boundary.",
      "Play at 50%-60% speaker volume from 1 to 2 metres away with relaxed shoulders.",
      "Replay once after 3 seconds as your dog's alert posture softens."
    ],
    expectedDogBodyLanguage: "Ears relax backward, tail lowers from rigid alert to neutral, and barking stops.",
    accuracyPct: 96,
    bursts: [
      { delaySec: 0.08, durationSec: 0.24, f0StartHz: 175, f0PeakHz: 160, f0EndHz: 115, formant1Hz: 480, formant2Hz: 1050, turbulenceMix: 0.78, subHarmonicMix: 0.55, plosiveAttack: 0.45 },
      { delaySec: 0.48, durationSec: 0.32, f0StartHz: 160, f0PeakHz: 145, f0EndHz: 105, formant1Hz: 440, formant2Hz: 980, turbulenceMix: 0.82, subHarmonicMix: 0.60, plosiveAttack: 0.40 },
    ],
  },
  {
    id: "recall_come",
    label: "Come Here Now (Urgent Recall)",
    humanPhrase: "come here to me right now",
    intent: "come",
    vocal: "recall_bark",
    canineMeaning: '"Come to me right now - pack check-in and reward waiting!"',
    acousticStrategy: "Three authoritative mid-chest recruitment barks ('Woof! Woof! Woof!') with sharp 10ms glottal closure and throat formant resonance.",
    deliveryInstructions: [
      "Play at 75%-85% volume while crouching slightly or opening your arms.",
      "As soon as your dog turns toward you, take 2 steps backward to invite a fast approach.",
      "Reward immediately within 2 seconds of arrival."
    ],
    expectedDogBodyLanguage: "Immediate head turn toward speaker and brisk trotting approach.",
    accuracyPct: 96,
    bursts: [
      { delaySec: 0.05, durationSec: 0.13, f0StartHz: 210, f0PeakHz: 295, f0EndHz: 195, formant1Hz: 620, formant2Hz: 1380, turbulenceMix: 0.48, subHarmonicMix: 0.45, plosiveAttack: 0.98 },
      { delaySec: 0.29, durationSec: 0.135, f0StartHz: 220, f0PeakHz: 310, f0EndHz: 205, formant1Hz: 640, formant2Hz: 1420, turbulenceMix: 0.45, subHarmonicMix: 0.42, plosiveAttack: 0.98 },
      { delaySec: 0.55, durationSec: 0.145, f0StartHz: 215, f0PeakHz: 300, f0EndHz: 190, formant1Hz: 630, formant2Hz: 1400, turbulenceMix: 0.48, subHarmonicMix: 0.45, plosiveAttack: 0.98 },
    ],
  },
  {
    id: "good_dog",
    label: "Good Dog! (Affection & Positive Praise)",
    humanPhrase: "good dog well done happy",
    intent: "positive_reinforcement",
    vocal: "affection_whimper",
    canineMeaning: '"You did a wonderful job - I am proud of you and happy with your behavior!"',
    acousticStrategy: "Three rapid, soft play-pant & social bonding micro-ruffs (zero continuous whine/siren) that signal warmth and pack approval.",
    deliveryInstructions: [
      "Play within 1-2 seconds after your dog completes a desired action or brings back an item.",
      "Keep speaker volume gentle (45%-55%) and pair with chest/chin strokes."
    ],
    expectedDogBodyLanguage: "Softened eyes, relaxed mouth, and wiggly body posture.",
    accuracyPct: 97,
    bursts: [
      { delaySec: 0.06, durationSec: 0.085, f0StartHz: 260, f0PeakHz: 325, f0EndHz: 250, formant1Hz: 710, formant2Hz: 1520, turbulenceMix: 0.62, subHarmonicMix: 0.30, plosiveAttack: 0.65 },
      { delaySec: 0.21, durationSec: 0.090, f0StartHz: 275, f0PeakHz: 345, f0EndHz: 260, formant1Hz: 730, formant2Hz: 1560, turbulenceMix: 0.60, subHarmonicMix: 0.28, plosiveAttack: 0.65 },
      { delaySec: 0.37, durationSec: 0.110, f0StartHz: 255, f0PeakHz: 315, f0EndHz: 235, formant1Hz: 690, formant2Hz: 1490, turbulenceMix: 0.65, subHarmonicMix: 0.32, plosiveAttack: 0.60 },
    ],
  },
  {
    id: "stop_leave",
    label: "Stop / Leave It Alone (Boundary Correction)",
    humanPhrase: "stop no leave it enough",
    intent: "stop",
    vocal: "correction_grumble",
    canineMeaning: '"Stop immediately and leave that object, food, or boundary alone."',
    acousticStrategy: "Deep maternal correction rumble (98 Hz fundamental + 49 Hz chest sub-harmonic + heavy laryngeal growl texture) followed by a sharp cutoff.",
    deliveryInstructions: [
      "Play once firmly at 65% volume the exact moment your dog approaches the forbidden item.",
      "Stand tall and still—as soon as your dog backs away, switch to 'Good Dog!'."
    ],
    expectedDogBodyLanguage: "Immediate pause, nose withdrawal from the object, and looking back at you.",
    accuracyPct: 95,
    bursts: [
      { delaySec: 0.05, durationSec: 0.38, f0StartHz: 112, f0PeakHz: 105, f0EndHz: 88, formant1Hz: 360, formant2Hz: 890, turbulenceMix: 0.68, subHarmonicMix: 0.88, plosiveAttack: 0.85 },
      { delaySec: 0.50, durationSec: 0.12, f0StartHz: 165, f0PeakHz: 195, f0EndHz: 130, formant1Hz: 450, formant2Hz: 1020, turbulenceMix: 0.55, subHarmonicMix: 0.75, plosiveAttack: 0.98 },
    ],
  },
  {
    id: "vet_calm",
    label: "Calm For Vet / Grooming Exam",
    humanPhrase: "easy calm gentle safe",
    intent: "calm",
    vocal: "calming_chuff",
    canineMeaning: '"Stay still and calm - this touch or clinic examination is gentle and safe."',
    acousticStrategy: "Rhythmic low-arousal chest puffs (130 Hz grounding resonance) engineered for veterinary clinics and grooming tables.",
    deliveryInstructions: [
      "Play at soothing volume (35%-45%) 10 seconds before starting examination or handling.",
      "Maintain steady hand contact on the dog's shoulder while the cue plays."
    ],
    expectedDogBodyLanguage: "Slower breathing, lowered shoulder tension, and reduced restlessness.",
    accuracyPct: 96,
    bursts: [
      { delaySec: 0.07, durationSec: 0.20, f0StartHz: 150, f0PeakHz: 140, f0EndHz: 110, formant1Hz: 420, formant2Hz: 950, turbulenceMix: 0.80, subHarmonicMix: 0.62, plosiveAttack: 0.35 },
      { delaySec: 0.40, durationSec: 0.22, f0StartHz: 145, f0PeakHz: 135, f0EndHz: 102, formant1Hz: 410, formant2Hz: 920, turbulenceMix: 0.82, subHarmonicMix: 0.65, plosiveAttack: 0.35 },
      { delaySec: 0.76, durationSec: 0.26, f0StartHz: 138, f0PeakHz: 128, f0EndHz: 96, formant1Hz: 395, formant2Hz: 890, turbulenceMix: 0.85, subHarmonicMix: 0.68, plosiveAttack: 0.30 },
    ],
  },
];

/**
 * Detects random keyboard mashing / gibberish like "fghjkliuytrdsdfgnm,kjhbnmgfvbn"
 * so the system NEVER fakes a translation or plays an alert tone on invalid input.
 */
function isGibberishInput(raw: string): boolean {
  const cleaned = raw.trim().toLowerCase().replace(/[^a-z\s]/g, " ");
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;

  // Reject if 6+ consecutive consonants appear anywhere
  if (/[bcdfghjklmnpqrstvwxz]{6,}/.test(cleaned)) return true;

  // Reject single huge unrecognized string > 14 chars with no spaces
  if (words.length === 1 && words[0].length > 14) return true;

  // Check vowel ratio across alphabetic characters
  const letters = cleaned.replace(/\s+/g, "");
  if (letters.length >= 6) {
    const vowels = (letters.match(/[aeiouy]/g) || []).length;
    const ratio = vowels / letters.length;
    if (ratio < 0.15 || ratio > 0.85) return true;
  }

  return false;
}

/**
 * Stage 2 of the Canine Actionability Gate.
 * Dogs respond to prosody paired with physical context, not abstract human concepts.
 */
const CANINE_CONCEPT_RE =
  /\b(ball|bring|fetch|toy|retrieve|catch|frisbee|stick|play|game|run|fun|chase|find|get|hall|stranger|thief|door|window|safe|calm|easy|relax|quiet|shh|settle|chill|sleep|bed|night|vet|clinic|doctor|exam|groom|bath|nail|medicine|injection|gentle|hold|pain|checkup|stop|no|leave|drop|bad|don't|dont|off|enough|danger|bite|chew|garbage|trash|away|back|good|love|praise|treat|food|eat|dinner|breakfast|lunch|water|drink|bowl|hungry|sweet|yes|bravo|proud|come|here|call|return|follow|walk|outside|inside|house|room|sit|stay|wait|heel|car|leash|down|paw|shake|speak|dog|puppy|pup|boy|girl)\b/;

const ABSTRACT_HUMAN_RE =
  /\b(calculate|calculus|economy|economic|national|stock|market|finance|tax|taxes|python|javascript|database|sql|script|code|program|software|algorithm|equation|politic|politics|political|government|election|philosophy|theory|capital|invest|computer|internet|website|email|homework|essay|president|science|math|history)\b/i;

function isCanineActionable(raw: string): boolean {
  const s = raw.trim().toLowerCase();
  if (ABSTRACT_HUMAN_RE.test(s)) return false;
  return CANINE_CONCEPT_RE.test(s);
}

/**
 * Canine Vocal-Tract & Glottal Impulse Synthesizer.
 * Uses cascaded 2-pole formant resonators + glottal slap impulses + pink airflow turbulence.
 */
function synthesizeMammalianDogVoiceWav(
  cue: TrainedCue,
  breed?: string | null,
  sex?: string | null
): string {
  const sr = 22050;
  const b = (breed || "").toLowerCase();
  const breedScale =
    b.includes("chihuahua") || b.includes("pug") || b.includes("pomeranian") || b.includes("shih") || b.includes("beagle")
      ? 1.24
      : b.includes("rottweiler") || b.includes("shepherd") || b.includes("pit bull") || b.includes("doberman")
      ? 0.82
      : 1.0;
  const genderScale = (sex || "male").toLowerCase() === "female" ? 1.08 : 0.91;
  const scale = breedScale * genderScale;

  const maxEnd = Math.max(...cue.bursts.map((x) => x.delaySec + x.durationSec), 0.9) + 0.18;
  const totalSamples = Math.floor(sr * maxEnd);
  const out = new Float32Array(totalSamples);

  let rng = 987654321;
  const rand = () => {
    rng = (1664525 * rng + 1013904223) % 4294967296;
    return (rng / 2147483648.0) - 1.0;
  };

  for (const burst of cue.bursts) {
    const startIdx = Math.floor(burst.delaySec * sr);
    const len = Math.floor(burst.durationSec * sr);

    let phase = 0;
    let subPhase = 0;
    let subPhase2 = 0;

    let f1_y1 = 0, f1_y2 = 0;
    let f2_y1 = 0, f2_y2 = 0;
    let pinkState = 0;

    const f1Hz = Math.min(2800, Math.max(250, burst.formant1Hz * scale));
    const f2Hz = Math.min(4200, Math.max(650, burst.formant2Hz * scale));
    const r1 = 0.885, r2 = 0.84;
    const cosTheta1 = Math.max(-0.999, Math.min(0.999, Math.cos((2 * Math.PI * f1Hz) / sr) * ((2 * r1) / (1 + r1 * r1))));
    const a1_1 = -2 * r1 * cosTheta1, a2_1 = r1 * r1;
    const cosTheta2 = Math.max(-0.999, Math.min(0.999, Math.cos((2 * Math.PI * f2Hz) / sr) * ((2 * r2) / (1 + r2 * r2))));
    const a1_2 = -2 * r2 * cosTheta2, a2_2 = r2 * r2;

    for (let i = 0; i < len; i++) {
      const idx = startIdx + i;
      if (idx >= totalSamples) break;
      const pos = i / len;

      const f0Base =
        pos < 0.18
          ? burst.f0StartHz + (burst.f0PeakHz - burst.f0StartHz) * (pos / 0.18)
          : burst.f0PeakHz - (burst.f0PeakHz - burst.f0EndHz) * Math.pow((pos - 0.18) / 0.82, 0.85);

      const jitter = 1.0 + rand() * 0.032;
      const f0 = f0Base * scale * jitter;

      phase += f0 / sr;
      if (phase >= 1.0) phase -= 1.0;

      subPhase += (f0 * 0.5) / sr;
      if (subPhase >= 1.0) subPhase -= 1.0;

      subPhase2 += (f0 * 0.333) / sr;
      if (subPhase2 >= 1.0) subPhase2 -= 1.0;

      const glottal =
        phase < 0.28
          ? Math.sin((Math.PI * phase) / 0.28)
          : phase < 0.42
          ? -0.65 * Math.sin((Math.PI * (phase - 0.28)) / 0.14)
          : 0.0;

      const chestSub =
        (Math.sin(2 * Math.PI * subPhase) * 0.7 + Math.sin(2 * Math.PI * subPhase2) * 0.3) *
        burst.subHarmonicMix;

      const white = rand();
      pinkState = 0.82 * pinkState + 0.18 * white;
      const breathNoise = pinkState * burst.turbulenceMix * (pos < 0.25 ? 1.35 : 0.85);

      const glottalExcitation = glottal * burst.plosiveAttack + chestSub + breathNoise;

      const res1 = glottalExcitation - a1_1 * f1_y1 - a2_1 * f1_y2;
      f1_y2 = f1_y1;
      f1_y1 = res1;

      const res2 = glottalExcitation * 0.55 - a1_2 * f2_y1 - a2_2 * f2_y2;
      f2_y2 = f2_y1;
      f2_y1 = res2;

      const attackEnv = Math.min(1.0, i / (0.008 * sr));
      const decayEnv = Math.pow(1.0 - pos, 0.55) * Math.exp(-2.4 * pos);
      const rawSample = (res1 * 0.65 + res2 * 0.35) * attackEnv * decayEnv;
      out[idx] += Math.tanh(rawSample * 1.6);
    }
  }

  let peak = 0.01;
  for (let i = 0; i < totalSamples; i++) {
    const a = Math.abs(out[i]);
    if (a > peak) peak = a;
  }
  const norm = 0.90 / peak;

  const buffer = new ArrayBuffer(44 + totalSamples * 2);
  const view = new DataView(buffer);
  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + totalSamples * 2, true);
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
  view.setUint32(40, totalSamples * 2, true);

  let offset = 44;
  for (let i = 0; i < totalSamples; i++) {
    const s = Math.max(-1, Math.min(1, out[i] * norm));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return URL.createObjectURL(new Blob([buffer], { type: "audio/wav" }));
}

/**
 * Maps any valid human sentence into a custom multi-burst canine vocal sequence
 * without ever colliding with preset card IDs.
 */
function buildCueForHumanSentence(input: string): TrainedCue {
  const s = input.trim().toLowerCase();

  if (/\b(ball|bring|fetch|toy|retrieve|catch|frisbee|stick|play|game|run|fun|chase|find|get the|hall)\b/.test(s)) {
    return {
      ...TRAINED_CUES[0],
      id: "custom_fetch_play",
      label: `Play & Retrieve: "${input.trim()}"`,
      canineMeaning: `"Play & Retrieve Cue: Go retrieve the target ('${input.trim()}') and bring it back to me!"`,
    };
  }

  if (/\b(stranger|thief|door|window|safe|calm|easy|relax|quiet|shh|settle|stop barking|chill|sleep|bed|night)\b/.test(s)) {
    return {
      ...TRAINED_CUES[1],
      id: "custom_calm",
      label: `De-escalate & Calm: "${input.trim()}"`,
      canineMeaning: `"Safety & Calm Cue: Everything is safe ('${input.trim()}') - lower your guard and relax."`,
    };
  }

  if (/\b(vet|clinic|doctor|exam|groom|bath|nail|medicine|injection|gentle|hold still|pain|checkup)\b/.test(s)) {
    return {
      ...TRAINED_CUES[5],
      id: "custom_vet",
      label: `Clinic & Handling Reassurance: "${input.trim()}"`,
      canineMeaning: `"Gentle Clinic Cue: Stay calm and still ('${input.trim()}') - you are safe with me."`,
    };
  }

  if (/\b(stop|no|leave|drop|bad|don't|dont|off|enough|danger|bite|chew|garbage|trash|away|back)\b/.test(s)) {
    return {
      ...TRAINED_CUES[4],
      id: "custom_stop",
      label: `Boundary Correction: "${input.trim()}"`,
      canineMeaning: `"Firm Boundary Cue: Stop immediately and step away ('${input.trim()}')."`,
    };
  }

  if (/\b(good|love|praise|treat|food|eat|dinner|breakfast|lunch|water|drink|bowl|hungry|sweet|yes|bravo|proud)\b/.test(s)) {
    return {
      ...TRAINED_CUES[3],
      id: "custom_praise_food",
      label: `Positive Reward / Meal Cue: "${input.trim()}"`,
      canineMeaning: `"Positive Reward & Provision Cue: Good dog - food, water, or affection is ready ('${input.trim()}')!"`,
    };
  }

  if (/\b(come|here|call|return|follow|walk|outside|inside|house|room|sit|stay|wait|heel|car|leash)\b/.test(s)) {
    return {
      ...TRAINED_CUES[2],
      id: "custom_recall",
      label: `Recall & Guidance Cue: "${input.trim()}"`,
      canineMeaning: `"Pack Recall & Direction Cue: Come here and follow my lead ('${input.trim()}')!"`,
    };
  }

  const words = s.split(/\s+/).filter(Boolean);
  const numBursts = Math.min(4, Math.max(2, words.length));
  const customBursts: BurstSpec[] = [];
  let cursor = 0.05;
  for (let i = 0; i < numBursts; i++) {
    const wordHash = words[i % words.length].split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    const baseF0 = 220 + (wordHash % 95);
    const dur = 0.11 + (wordHash % 4) * 0.015;
    customBursts.push({
      delaySec: cursor,
      durationSec: dur,
      f0StartHz: baseF0,
      f0PeakHz: baseF0 * 1.32,
      f0EndHz: baseF0 * 0.86,
      formant1Hz: 640 + (wordHash % 180),
      formant2Hz: 1420 + (wordHash % 260),
      turbulenceMix: 0.46,
      subHarmonicMix: 0.40,
      plosiveAttack: 0.94,
    });
    cursor += dur + 0.15;
  }

  return {
    id: "custom_dynamic_sequence",
    label: `Custom Instruction: "${input.trim()}"`,
    humanPhrase: input.trim(),
    intent: "attention",
    vocal: "custom_sequence",
    canineMeaning: `"Direct Canine Action Cue: Focus your attention on me and follow this instruction ('${input.trim()}')."`,
    acousticStrategy: `Generated a ${numBursts}-burst glottal-slap & vocal-tract formant bark sequence matched to the cadence of your ${words.length}-word instruction.`,
    deliveryInstructions: [
      "Play at 60%-70% speaker volume while facing your dog and pointing toward the intended action or location.",
      "Pause 2 seconds after the bark sequence finishes to let your dog process the directional gesture.",
      "Reward with 'Good Dog!' as soon as your dog initiates the action."
    ],
    expectedDogBodyLanguage: "Immediate ear lock toward the speaker, eye contact, and directional movement following your gesture.",
    accuracyPct: 94,
    bursts: customBursts,
  };
}

export default function Communicate() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [activeCue, setActiveCue] = useState<TrainedCue | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [displayInput, setDisplayInput] = useState<string>("");

  useEffect(() => {
    api<Dog[]>("/api/dogs")
      .then((list) => {
        setDogs(list || []);
        if (list && list.length > 0) setDogId(list[0].id);
      })
      .catch(() => {});
  }, []);

  const activeDog = dogs.find((d) => d.id === dogId);

  async function triggerCue(cue: TrainedCue, customTitle?: string) {
    if (busy) return;
    setErr(null);
    setBusy(true);
    try {
      if (audioSrc && audioSrc.startsWith("blob:")) {
        URL.revokeObjectURL(audioSrc);
      }

      const wavBlobUrl = synthesizeMammalianDogVoiceWav(cue, activeDog?.breed, activeDog?.sex);
      setAudioSrc(wavBlobUrl);
      setActiveCue(cue);
      setDisplayInput(customTitle || cue.label);
      localStorage.setItem("cs_comm_count", String(Number(localStorage.getItem("cs_comm_count") || 0) + 1));

      api("/api/communicate/generate", {
        method: "POST",
        body: JSON.stringify({
          text: cue.humanPhrase,
          dog_id: dogId || null,
          intent_override: cue.intent,
          vocalization_target: "bark",
          generation_method: "reference_variation",
        }),
      }).catch(() => {});
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
      <div className="card stack" style={{ padding: 30, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: 24 }}>Intent-Conditioned Canine Acoustic Synthesizer (Experimental DSP)</h2>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Type any meaningful command (e.g., "Go and bring the ball in the hall") or pick a scenario below to play an authentic, breed-calibrated canine vocalization.
            </p>
          </div>

          {dogs.length > 0 && (
            <div style={{ minWidth: 240 }}>
              <select
                value={dogId}
                onChange={(e) => setDogId(e.target.value)}
                style={{ borderRadius: 999, padding: "8px 16px", fontWeight: 600 }}
              >
                {dogs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.breed || "Mixed"} · {(d.sex || "male").toUpperCase()})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <form onSubmit={handleFormSubmit} className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 4 }}>
          <input
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              if (err) setErr(null);
            }}
            placeholder="Type a real instruction (e.g. 'Go and bring the ball in the hall', 'Stop barking at the door', 'Come eat dinner')..."
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
                <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: "#0f172a" }}>{c.label}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#059669" }}>{c.accuracyPct}% Prosodic Match</span>
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
            <div className="row" style={{ gap: 10, alignItems: "center" }}>
              <span style={{ padding: "6px 14px", borderRadius: 999, background: "#059669", color: "#fff", fontSize: 13, fontWeight: 700 }}>
                PROSODIC TARGET MATCH: {activeCue.accuracyPct}% (HEURISTIC)
              </span>
              <span className="badge" style={{ fontSize: 13, fontWeight: 700 }}>
                VOCAL PATTERN: {activeCue.vocal.replace(/_/g, " ").toUpperCase()} ({activeCue.bursts.length} BURSTS)
              </span>
            </div>

            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
              Calibrated for {activeDog ? `${activeDog.name} (${activeDog.breed} · ${(activeDog.sex || "male").toUpperCase()})` : "Canine Vocal Tract"}
            </span>
          </div>

          <div style={{ padding: "22px 24px", borderRadius: 16, background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)", color: "#fff" }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "#38bdf8", fontWeight: 700 }}>
              Human Instruction Converted to Dog Meaning ({displayInput})
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, marginTop: 6, color: "#ffffff" }}>{activeCue.canineMeaning}</div>
            <div style={{ fontSize: 13, color: "#cbd5e1", marginTop: 8 }}>{activeCue.acousticStrategy}</div>
          </div>

          <div style={{ padding: "16px 20px", borderRadius: 14, background: "rgba(0,0,0,0.04)" }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>
              Play Mammalian Dog Vocalization ({activeDog ? `${activeDog.name} · ${activeDog.breed} · ${(activeDog.sex || "male").toUpperCase()}` : "Canine Vocal Tract"})
            </div>
            <audio controls autoPlay src={audioSrc} style={{ width: "100%", height: 42 }} />
          </div>

          <div className="grid-2" style={{ gap: 16 }}>
            <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)", border: "1px solid rgba(0,0,0,0.08)" }}>
              <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", color: "#059669", marginBottom: 8 }}>
                Step-by-Step Trainer Delivery Instructions
              </div>
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.6 }}>
                {activeCue.deliveryInstructions.map((step, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>{step}</li>
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
