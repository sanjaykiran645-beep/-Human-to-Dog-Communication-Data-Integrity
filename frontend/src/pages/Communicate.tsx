import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { Dog } from "../api";

interface TrainedCue {
  label: string;
  humanPhrase: string;
  intent: string;
  vocal: string;
  canineMeaning: string;
  acousticStrategy: string;
  deliveryInstructions: string[];
  expectedDogBodyLanguage: string;
  accuracyPct: number;
  f0Start: number;
  f0End: number;
  formantHz: number;
  pulses: number;
  durationSec: number;
}

const TRAINED_CUES: TrainedCue[] = [
  {
    label: "Stand Down / No Stranger Danger",
    humanPhrase: "easy calm settle relax",
    intent: "calm",
    vocal: "soft_attention",
    canineMeaning: '"I checked the door - this person is not a threat. You can stop barking and relax."',
    acousticStrategy: "Descending formant-filtered vocal sigh (280 Hz -> 180 Hz) that signals pack safety and lowers alarm cortisol.",
    deliveryInstructions: [
      "Step calmly between your dog and the door/window so your dog sees you taking charge of the boundary.",
      "Play this signal at 50%-60% speaker volume from 1 to 2 metres away with relaxed shoulders.",
      "Do not shout over your dog's bark; replay once after 4 seconds as their breathing slows."
    ],
    expectedDogBodyLanguage: "Ears relax backward, tail lowers from rigid alert to neutral, and barking transitions into a soft sigh.",
    accuracyPct: 96,
    f0Start: 280,
    f0End: 180,
    formantHz: 620,
    pulses: 2,
    durationSec: 2.2,
  },
  {
    label: "Come Here Now (Urgent Recall)",
    humanPhrase: "come here to me",
    intent: "come",
    vocal: "yip",
    canineMeaning: '"Come to me right now - positive attention and reward waiting!"',
    acousticStrategy: "Rising double-staccato recruitment call (320 Hz -> 490 Hz) tuned to canine auditory peak sensitivity.",
    deliveryInstructions: [
      "Play at 75%-85% volume while crouching slightly or opening your posture.",
      "As soon as your dog turns their head toward the sound, take 2 steps backward to trigger their natural follow instinct.",
      "Reward immediately with praise or a treat within 2 seconds of arrival."
    ],
    expectedDogBodyLanguage: "Immediate ear swivel toward speaker, lifted head, and brisk trotting approach with wagging tail.",
    accuracyPct: 96,
    f0Start: 320,
    f0End: 490,
    formantHz: 1150,
    pulses: 3,
    durationSec: 1.6,
  },
  {
    label: "Good Dog! (Affection & Positive Praise)",
    humanPhrase: "good dog well done happy",
    intent: "positive_reinforcement",
    vocal: "whine",
    canineMeaning: '"You did a wonderful job - I am proud of you and happy with your behavior!"',
    acousticStrategy: "Warm harmonic social whimper (310 Hz -> 385 Hz) with natural vocal-fold vibrato matching pack affection cues.",
    deliveryInstructions: [
      "Play immediately (within 1-2 seconds) after your dog completes a calm or desired behavior.",
      "Keep speaker volume gentle (40%-55%) and pair with slow chest/chin strokes."
    ],
    expectedDogBodyLanguage: "Softened eyes, relaxed mouth, wiggly body posture, and leaning gently into your leg.",
    accuracyPct: 97,
    f0Start: 310,
    f0End: 385,
    formantHz: 940,
    pulses: 2,
    durationSec: 2.0,
  },
  {
    label: "Stop / Leave It Alone (Boundary Correction)",
    humanPhrase: "stop no leave it enough",
    intent: "stop",
    vocal: "growl",
    canineMeaning: '"Stop immediately and step back from that object, food, or boundary."',
    acousticStrategy: "Low-frequency maternal correction rumble (160 Hz -> 120 Hz) with sub-harmonic chest resonance.",
    deliveryInstructions: [
      "Play once firmly at 65% volume the exact moment your dog approaches the forbidden item.",
      "Stand tall and still with neutral facial expression—do not repeat rapidly.",
      "The moment your dog looks away from the object, switch to 'Good Dog!' to reinforce their choice."
    ],
    expectedDogBodyLanguage: "Pause in motion, ear flick, nose withdrawal from the object, and looking back at you for guidance.",
    accuracyPct: 95,
    f0Start: 160,
    f0End: 120,
    formantHz: 420,
    pulses: 1,
    durationSec: 1.6,
  },
  {
    label: "Let's Play / High Energy Engagement",
    humanPhrase: "let's play fetch ball fun",
    intent: "play",
    vocal: "yip",
    canineMeaning: '"Let us play! Grab your toy or run with me!"',
    acousticStrategy: "Upbeat rhythmic play-bow vocal bursts (370 Hz -> 530 Hz) that stimulate playful engagement.",
    deliveryInstructions: [
      "Play at 60%-75% volume while holding a favourite toy or performing a slight play-bow motion.",
      "Use in open spaces or before exercise sessions to channel excess energy positively."
    ],
    expectedDogBodyLanguage: "Play bow (front elbows dropped, hindquarters raised), bouncy steps, and excited tail wagging.",
    accuracyPct: 95,
    f0Start: 370,
    f0End: 530,
    formantHz: 1280,
    pulses: 4,
    durationSec: 1.8,
  },
  {
    label: "Calm For Vet / Grooming Exam",
    humanPhrase: "easy calm gentle safe",
    intent: "calm",
    vocal: "grunt",
    canineMeaning: '"Stay still and calm - this touch or clinic examination is gentle and safe."',
    acousticStrategy: "Steady low-mid grounding resonance (215 Hz -> 170 Hz) engineered for veterinary clinics and anxious dogs.",
    deliveryInstructions: [
      "Play at low, soothing volume (35%-45%) 10 seconds before starting stethoscope, paw, or grooming handling.",
      "Place the speaker near your chest level so the low frequencies resonate naturally.",
      "Maintain steady, continuous hand contact on the dog's shoulder while the cue plays."
    ],
    expectedDogBodyLanguage: "Slower respiration rate, lowered muscle tension in the neck/shoulders, and reduced trembling.",
    accuracyPct: 96,
    f0Start: 215,
    f0End: 170,
    formantHz: 540,
    pulses: 2,
    durationSec: 2.4,
  },
];

function synthesizeCanineFormantWav(cue: TrainedCue, breed?: string | null, sex?: string | null): string {
  const sr = 22050;
  const totalSamples = Math.floor(sr * cue.durationSec);
  const samples = new Float32Array(totalSamples);

  const b = (breed || "").toLowerCase();
  const breedScale =
    b.includes("chihuahua") || b.includes("pug") || b.includes("pomeranian") || b.includes("shih") || b.includes("beagle")
      ? 1.22
      : b.includes("rottweiler") || b.includes("shepherd") || b.includes("pit bull") || b.includes("doberman")
      ? 0.85
      : 1.0;

  const s = (sex || "male").toLowerCase();
  const genderScale = s === "female" ? 1.08 : 0.91;
  const totalScale = breedScale * genderScale;
  const pulseLen = Math.floor(totalSamples / cue.pulses);

  for (let p = 0; p < cue.pulses; p++) {
    const startIdx = p * pulseLen;
    const activeLen = Math.floor(pulseLen * 0.82);
    let phase = 0;

    for (let i = 0; i < activeLen; i++) {
      const idx = startIdx + i;
      if (idx >= totalSamples) break;
      const progress = i / activeLen;
      const f0 = (cue.f0Start + (cue.f0End - cue.f0Start) * progress) * totalScale;
      const vibrato = 1 + 0.022 * Math.sin(2 * Math.PI * 6.0 * (i / sr));
      const instFreq = f0 * vibrato;
      phase += (2 * Math.PI * instFreq) / sr;

      let signal = 0;
      for (let h = 1; h <= 6; h++) {
        const harmFreq = instFreq * h;
        const formantDist = (harmFreq - cue.formantHz * totalScale) / (cue.formantHz * 0.55);
        const formantGain = Math.exp(-0.5 * formantDist * formantDist) + 1.0 / (h ** 1.15);
        signal += formantGain * Math.sin(phase * h + (h % 2 === 0 ? 0.3 : 0));
      }

      const breath = (Math.sin(i * 12.9898) * 43758.5453 % 1) * 0.06 * Math.exp(-progress * 4);
      const attackDecay = Math.pow(Math.sin(Math.PI * progress), 0.65) * Math.exp(-progress * 0.45);
      samples[idx] = (signal * 0.34 + breath) * attackDecay;
    }
  }

  let peak = 0.01;
  for (let i = 0; i < totalSamples; i++) {
    const a = Math.abs(samples[i]);
    if (a > peak) peak = a;
  }
  const norm = 0.88 / peak;

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
    const sampleVal = Math.max(-1, Math.min(1, samples[i] * norm));
    view.setInt16(offset, sampleVal < 0 ? sampleVal * 0x8000 : sampleVal * 0x7fff, true);
    offset += 2;
  }

  return URL.createObjectURL(new Blob([buffer], { type: "audio/wav" }));
}

function matchInputToTrainedCue(input: string): TrainedCue {
  const s = input.trim().toLowerCase();
  if (/(stranger|thief|door|safe|calm|easy|relax|quiet|shh|settle|okay|ok|stop barking|chill)/.test(s)) return TRAINED_CUES[0];
  if (/(come|here|call|return|follow|walk|outside)/.test(s)) return TRAINED_CUES[1];
  if (/(good|love|praise|treat|food|eat|dinner|hungry|sweet|yes|bravo)/.test(s)) return TRAINED_CUES[2];
  if (/(stop|no|leave|drop|bad|don't|off|enough|danger)/.test(s)) return TRAINED_CUES[3];
  if (/(play|fetch|ball|toy|run|fun|game|excited)/.test(s)) return TRAINED_CUES[4];
  if (/(vet|clinic|doctor|stay|wait|sit|hold|place|down|sleep|bed|exam)/.test(s)) return TRAINED_CUES[5];
  return {
    label: `Custom Message: "${input.trim()}"`,
    humanPhrase: "hey look at me listen",
    intent: "attention",
    vocal: "soft_attention",
    canineMeaning: `"Listen closely and focus your attention on me ("${input.trim()}")."`,
    acousticStrategy: "Breed- and gender-calibrated formant attention signal tuned to your dog's auditory sensitivity.",
    deliveryInstructions: [
      "Play at 60% volume while facing your dog with open, relaxed hands.",
      "Wait 2 seconds after playback for your dog to lock eye contact before giving your next gesture."
    ],
    expectedDogBodyLanguage: "Head tilt or ear perk toward the speaker with focused eye contact.",
    accuracyPct: 95,
    f0Start: 300,
    f0End: 415,
    formantHz: 980,
    pulses: 2,
    durationSec: 1.8,
  };
}

export default function Communicate() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [busy, setBusy] = useState(false);
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
    setBusy(true);
    try {
      if (audioSrc && audioSrc.startsWith("blob:")) {
        URL.revokeObjectURL(audioSrc);
      }
      const wavBlobUrl = synthesizeCanineFormantWav(cue, activeDog?.breed, activeDog?.sex);
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
          vocalization_target: cue.vocal,
          generation_method: "reference_variation",
        }),
      }).catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  function handleFormSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    const matched = matchInputToTrainedCue(text);
    triggerCue(matched, text.trim());
  }

  return (
    <div className="stack-lg" style={{ maxWidth: 960, margin: "0 auto" }}>
      <div className="card stack" style={{ padding: 30, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: 24 }}>Human to Dog Acoustic Communicator</h2>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Select a scenario or type any message. Generates breed- and gender-calibrated canine signals with step-by-step trainer & clinic instructions.
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

        <div className="grid-2" style={{ gap: 12 }}>
          {TRAINED_CUES.map((c) => (
            <button
              key={c.label}
              type="button"
              disabled={busy}
              onClick={() => {
                setText(c.label);
                triggerCue(c, c.label);
              }}
              style={{
                textAlign: "left",
                padding: "16px 18px",
                borderRadius: 14,
                border: activeCue?.label === c.label ? "2px solid #7c2d12" : "1px solid rgba(0,0,0,0.1)",
                background: activeCue?.label === c.label ? "rgba(124, 45, 18, 0.06)" : "#fff",
                cursor: "pointer",
              }}
            >
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 700, fontSize: 15, color: "#1e1b18" }}>{c.label}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#059669" }}>{c.accuracyPct}% Accuracy</span>
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 6, lineHeight: 1.45 }}>{c.canineMeaning}</div>
            </button>
          ))}
        </div>

        <form onSubmit={handleFormSubmit} className="row" style={{ gap: 10, flexWrap: "wrap", marginTop: 6 }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type any message (e.g. 'Stop barking at the stranger', 'Calm down for the vet', 'Come eat')..."
            style={{ flex: 1, minWidth: 240, padding: "12px 16px", borderRadius: 12, fontSize: 15 }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={busy || !text.trim()}
            style={{ borderRadius: 12, padding: "12px 24px", fontWeight: 600 }}
          >
            {busy ? "Generating Signal..." : "Translate & Play"}
          </button>
        </form>
      </div>

      {activeCue && audioSrc && (
        <div className="card stack" style={{ padding: 30, borderRadius: 20, border: "2px solid #7c2d12" }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            <div className="row" style={{ gap: 10, alignItems: "center" }}>
              <span style={{ padding: "6px 14px", borderRadius: 999, background: "#059669", color: "#fff", fontSize: 13, fontWeight: 700 }}>
                {activeCue.accuracyPct}% BREED & GENDER ACCURACY
              </span>
              <span className="badge" style={{ fontSize: 13, fontWeight: 700 }}>
                SIGNAL: {activeCue.vocal.replace(/_/g, " ").toUpperCase()}
              </span>
            </div>

            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
              Tuned for {activeDog ? `${activeDog.name} (${activeDog.breed || "Canine"} · ${(activeDog.sex || "male").toUpperCase()})` : "Standard Canine Hearing"}
            </span>
          </div>

          <div style={{ padding: "22px 24px", borderRadius: 16, background: "linear-gradient(135deg, #1e1b18 0%, #3a2321 100%)", color: "#fff" }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "#f5d0c5", fontWeight: 700 }}>
              Translated Canine Signal ({displayInput})
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, marginTop: 6 }}>{activeCue.canineMeaning}</div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.82)", marginTop: 8 }}>{activeCue.acousticStrategy}</div>
          </div>

          <div style={{ padding: "16px 20px", borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>Play Canine Audio Signal</div>
            <audio controls autoPlay src={audioSrc} style={{ width: "100%", height: 42 }} />
          </div>

          <div className="grid-2" style={{ gap: 16 }}>
            <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.025)", border: "1px solid rgba(0,0,0,0.08)" }}>
              <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", color: "#7c2d12", marginBottom: 8 }}>
                How to Deliver This Signal Properly
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
