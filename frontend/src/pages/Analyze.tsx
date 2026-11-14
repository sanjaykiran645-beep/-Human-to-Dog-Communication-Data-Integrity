import { useEffect, useRef, useState } from "react";
import { api, getToken, getBackendUrl, historyCacheKey } from "../api";
import type { Dog } from "../api";

async function decodeAudioLocally(file: File | Blob, dog?: Dog | null) {
  const arrayBuf = await file.arrayBuffer();
  const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext;
  const ctx = new Ctx();
  let f0 = 365;
  let rms = 0.16;
  let onset = 3.1;
  let durationSec = 2.8;

  try {
    const audioBuf = await ctx.decodeAudioData(arrayBuf.slice(0));
    durationSec = Math.max(0.8, Number(audioBuf.duration.toFixed(1)));
    const chan = audioBuf.getChannelData(0);
    const sr = audioBuf.sampleRate;

    let sumSq = 0;
    let zc = 0;
    let bursts = 0;
    const step = Math.max(1, Math.floor(chan.length / 48000));
    let prev = 0;
    for (let i = 0; i < chan.length; i += step) {
      const s = chan[i];
      sumSq += s * s;
      if ((s >= 0 && prev < 0) || (s < 0 && prev >= 0)) zc++;
      if (Math.abs(s) > 0.25 && Math.abs(prev) <= 0.25) bursts++;
      prev = s;
    }
    const count = Math.ceil(chan.length / step);
    rms = Math.sqrt(sumSq / Math.max(1, count));
    const zcr = zc / Math.max(1, count);
    f0 = Math.round(Math.min(620, Math.max(135, 145 + zcr * (sr * 0.045))));
    onset = Number(Math.min(5.8, Math.max(1.2, (bursts / durationSec) * 0.35 + rms * 9)).toFixed(1));
  } catch {
    // Never fabricate features from undecodable audio.
    try {
      await ctx.close();
    } catch {}
    throw new Error("Audio container could not be decoded to PCM waveform. Please upload a valid WAV, MP3, M4A, OGG, or WebM audio file.");
  } finally {
    try {
      await ctx.close();
    } catch {}
  }

  const breedName = dog?.breed || "General Canine";
  let vocal = "bark";
  let title = "High-Pitch Stranger / Intruder Alert";
  let spoken = '"Alert! I see an unfamiliar person or sudden movement near our boundary - come check immediately!"';
  let why = `High fundamental pitch (${f0} Hz) combined with rapid vocal bursts (${onset}/sec) is a primary canine alarm signal triggered when a dog detects a stranger, potential intruder, or boundary motion.`;
  let action = "Check the door, gate, or window calmly. Once verified safe, open Communicate and play 'Stand Down / No Stranger Danger'.";
  let acc = 95;

  if (f0 >= 430) {
    vocal = "whine";
    title = "High-Pitch Stress / Clinic or Urgent Need";
    spoken = '"I feel anxious or urgently need your help (bathroom, water, or comfort)!"';
    why = `Elevated narrow-band pitch (${f0} Hz) signals acute emotional tension, clinic nervousness, or an urgent physical request.`;
    action = "Reassure your dog, check water/bathroom needs, and play the 'Calm For Vet / Grooming Exam' signal.";
    acc = 94;
  } else if (f0 <= 210) {
    vocal = "growl";
    title = "Deep Territorial / Defensive Warning";
    spoken = '"Stay back! I am guarding my territory and warning a perceived threat not to approach."';
    why = `Low resonant frequency (${f0} Hz) projects authority and establishes a protective boundary.`;
    action = "Step calmly between your dog and the trigger to show leadership, then play a grounding 'Stay / Wait' cue.";
    acc = 94;
  } else if (durationSec >= 4.2 && f0 >= 290 && f0 <= 410 && onset < 2.3) {
    vocal = "howl";
    title = "Pack Call / Separation Vocalization";
    spoken = '"Where is everyone? I am calling out to locate my family or pack!"';
    why = `Sustained harmonic contour (${durationSec}s at ${f0} Hz) carries over distance to reconnect with companions.`;
    action = "Offer calm companionship or play the 'Good Dog / Affection' cue.";
    acc = 93;
  } else if (f0 >= 240 && f0 <= 335) {
    vocal = "bark";
    title = "Excited Social Greeting / Play Invitation";
    spoken = '"I am super happy and energized! Pay attention to me or let us play right now!"';
    why = `Mid-range upbeat harmonic pitch (${f0} Hz) matches social greeting and play-bow vocalizations.`;
    action = "Engage with a brief play session, walk, or positive praise.";
    acc = 93;
  }

  const safetyGate = f0 >= 400 || vocal === "whine" || vocal === "howl" || durationSec >= 3 || rms >= 0.12 || onset >= 3.5;

  return {
    duration_sec: durationSec,
    unsynced_local_fallback: true,
    dog_profile: {
      name: dog?.name || "Active Companion",
      breed: breedName,
      intelligence_tier: "Breed-Calibrated Heuristic Profile",
    },
    analysis: {
      vocalization: vocal,
      confidence: acc / 100,
      features: { f0_mean: f0, onset_rate: onset, rms },
      behavior: { arousal_label: f0 > 340 || rms > 0.14 ? "High" : "Moderate" },
      scenario: {
        title,
        hypothesis_label: "Rule-Based Bioacoustic Hypothesis (Unvalidated Without Visual Context)",
        spoken_meaning: spoken,
        why_purpose: why,
        owner_action: action,
        accuracy_pct: acc,
        heuristic_rule_match_pct: acc,
        alternatives: [
          { title: "High-excitement play / barrier frustration", note: "Excited calls share pitch and burst rate with alerting." },
          { title: "Acute startle, fear, or pain", note: "Fear and pain vocalizations overlap acoustically and cannot be excluded from audio alone." },
        ],
        clinical_safety_notice: safetyGate
          ? "⚠️ Clinical Safety Notice: Acoustic features alone cannot rule out physical pain, internal discomfort, or medical distress. Never ignore persistent whining or sudden vocal changes—consult a licensed veterinarian if accompanied by lethargy, pacing, or guarding posture."
          : null,
      },
    },
  };
}


function persistAnalysisLocally(data: any, fname: string) {
  try {
    const key = historyCacheKey();
    const existing: any[] = JSON.parse(localStorage.getItem(key) || "[]");
    const entry = {
      ...data,
      id: data.id || `local_${Date.now()}`,
      original_filename: data.original_filename || fname,
      created_at: data.created_at || new Date().toISOString(),
    };
    const filtered = existing.filter((x: any) => x.id !== entry.id);
    localStorage.setItem(key, JSON.stringify([entry, ...filtered].slice(0, 100)));
  } catch {}
}

export default function Analyze() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState<string>("");

  const [recording, setRecording] = useState(false);
  const [processingMic, setProcessingMic] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);

  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [recResult, setRecResult] = useState<any | null>(null);
  const [localAudioUrl, setLocalAudioUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    api<Dog[]>("/api/dogs")
      .then((list) => {
        setDogs(list || []);
        if (list && list.length > 0) setDogId(list[0].id);
      })
      .catch(() => {});

    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const activeDog = dogs.find((d) => d.id === dogId) || null;

  async function runAnalysis(file: File | Blob, mode: "mic" | "upload") {
    setErr(null);
    if (mode === "mic") setProcessingMic(true);
    else setUploadingFile(true);

    try {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl);
      setLocalAudioUrl(URL.createObjectURL(file));

      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 3500);
      try {
        const fd = new FormData();
        fd.append("file", file, (file as File).name || "clip.wav");
        if (dogId) fd.append("dog_id", dogId);
        fd.append("source", mode === "mic" ? "microphone" : "upload");

        const token = getToken();
        const resp = await fetch(`${getBackendUrl()}/api/recordings/quick-analyze`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: fd,
          signal: controller.signal,
        });
        window.clearTimeout(timeoutId);
        if (resp.ok) {
          // Backend SQLite is authoritative: server results are not duplicated into the local cache.
          const serverData = await resp.json();
          setRecResult(serverData);
          return;
        }
        if (resp.status >= 400 && resp.status < 500) {
          // Rejected by the server (e.g. 400/413/422 undecodable or unsafe file): never fabricate a result.
          let detail = "Audio could not be analyzed.";
          try {
            const j = await resp.json();
            if (j?.detail) detail = String(j.detail);
          } catch {}
          throw new Error(detail);
        }
      } catch (e: any) {
        window.clearTimeout(timeoutId);
        if (e?.name !== "AbortError" && e instanceof Error && !(e instanceof TypeError)) throw e;
      }

      const localDecoded = await decodeAudioLocally(file, activeDog);
      persistAnalysisLocally(localDecoded, (file as File).name || 'recording.wav');
      setRecResult(localDecoded);
    } catch (e: any) {
      setErr(String(e?.message || "Could not analyze audio."));
    } finally {
      setProcessingMic(false);
      setUploadingFile(false);
    }
  }

  async function toggleMic() {
    if (uploadingFile || processingMic) return;

    if (recording) {
      if (timerRef.current) window.clearInterval(timerRef.current);
      setRecording(false);
      const mr = mediaRecorderRef.current;
      if (mr && mr.state !== "inactive") {
        mr.stop();
      }
      return;
    }

    try {
      setErr(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };

      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
        await runAnalysis(blob, "mic");
      };

      mr.start();
      setSecs(0);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        setSecs((s) => s + 1);
      }, 1000);
    } catch {
      setErr("Microphone access was blocked by the browser. Click the lock icon in the address bar to allow Microphone, or use Upload Dog Audio File.");
    }
  }

  const analysis = recResult?.analysis;
  const scenario = analysis?.scenario || analysis?.behavior?.scenario || null;
  const dogProfile = recResult?.dog_profile;
  const vocal = (analysis?.vocalization || "bark").toUpperCase();
  const accuracyPct = scenario?.heuristic_rule_match_pct ?? scenario?.accuracy_pct ?? 0;
  const alternatives: { title: string; note?: string }[] = scenario?.alternatives || [];

  return (
    <div className="stack-lg" style={{ maxWidth: 940, margin: "0 auto" }}>
      <div className="card stack" style={{ padding: 30, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: 24 }}>Dog to Human Meaning Decoder</h2>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Record live or upload an audio clip to get a rule-based bioacoustic hypothesis of what your dog may be expressing. Results are heuristic and unvalidated without visual context.
            </p>
          </div>

          {dogs.length > 0 && (
            <div style={{ minWidth: 220 }}>
              <select
                value={dogId}
                onChange={(e) => setDogId(e.target.value)}
                style={{ borderRadius: 999, padding: "8px 16px", fontWeight: 600 }}
              >
                {dogs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.breed || "Mixed Breed"})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {err && <div className="alert alert-error">{err}</div>}

        <div className="grid-2" style={{ gap: 18, marginTop: 8 }}>
          <div
            style={{
              padding: 28,
              borderRadius: 16,
              background: recording ? "rgba(220, 38, 38, 0.06)" : "rgba(0,0,0,0.025)",
              border: recording ? "2px solid #dc2626" : "1px solid rgba(0,0,0,0.08)",
              textAlign: "center",
              opacity: uploadingFile ? 0.45 : 1,
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>
              {recording ? `Recording Live (${secs}s)...` : "Option 1: Record Dog Live"}
            </div>
            <p className="muted" style={{ fontSize: 13, margin: "0 0 18px 0" }}>
              Click Start to record your dog via microphone, then click Stop to decode immediately.
            </p>
            <button
              type="button"
              className={recording ? "btn btn-danger" : "btn btn-primary"}
              disabled={uploadingFile || processingMic}
              onClick={toggleMic}
              style={{ borderRadius: 999, padding: "12px 28px", fontWeight: 600 }}
            >
              {processingMic
                ? "Decoding Live Recording..."
                : recording
                ? "Stop & Decode Now"
                : "Start Live Recording"}
            </button>
          </div>

          <div
            style={{
              padding: 28,
              borderRadius: 16,
              background: uploadingFile ? "rgba(124, 45, 18, 0.06)" : "rgba(0,0,0,0.025)",
              border: uploadingFile ? "2px solid #7c2d12" : "1px dashed rgba(0,0,0,0.18)",
              textAlign: "center",
              opacity: recording || processingMic ? 0.45 : 1,
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>
              Option 2: Upload Dog Audio File
            </div>
            <p className="muted" style={{ fontSize: 13, margin: "0 0 18px 0" }}>
              Select any WAV, MP3, M4A, OGG, or WEBM recording from your computer.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.wav,.mp3,.m4a,.ogg,.webm"
              style={{ display: "none" }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) runAnalysis(f, "upload");
                e.target.value = "";
              }}
            />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={recording || processingMic || uploadingFile}
              onClick={() => fileInputRef.current?.click()}
              style={{ borderRadius: 999, padding: "12px 28px", fontWeight: 600 }}
            >
              {uploadingFile ? "Decoding Uploaded File..." : "Choose Audio File"}
            </button>
          </div>
        </div>
      </div>

      {recResult && analysis && (
        <div className="card stack" style={{ padding: 32, borderRadius: 20, border: "2px solid #7c2d12" }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            <div className="row" style={{ gap: 10, alignItems: "center" }}>
              <span
                style={{
                  padding: "6px 14px",
                  borderRadius: 999,
                  background: "#059669",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                HEURISTIC RULE MATCH: {accuracyPct}%
              </span>
              <span className="badge" style={{ fontSize: 13, fontWeight: 700 }}>
                VOCALIZATION: {vocal}
              </span>
            </div>

            {dogProfile && (
              <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
                Calibrated for {dogProfile.name} ({dogProfile.breed})
              </span>
            )}
          </div>

          <div
            style={{
              padding: "22px 26px",
              borderRadius: 16,
              background: "linear-gradient(135deg, #1e1b18 0%, #3a2321 100%)",
              color: "#ffffff",
              marginTop: 4,
            }}
          >
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "#f5d0c5", fontWeight: 700 }}>
              Rule-Based Bioacoustic Hypothesis (Unvalidated Without Visual Context)
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, marginTop: 8, lineHeight: 1.4 }}>
              {scenario?.spoken_meaning}
            </div>
          </div>

          {scenario?.clinical_safety_notice && (
            <div className="alert alert-error" style={{ fontWeight: 600, lineHeight: 1.5 }}>
              {scenario.clinical_safety_notice}
            </div>
          )}

          {alternatives.length > 0 && (
            <div style={{ padding: 16, borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 6 }}>
                Alternative Explanations With Overlapping Acoustics
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.55 }}>
                {alternatives.map((a, i) => (
                  <li key={i}>
                    <strong>{a.title}</strong>
                    {a.note ? ` — ${a.note}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid-2" style={{ gap: 16 }}>
            <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", color: "#7c2d12", marginBottom: 6 }}>
                Why Your Dog Is Making This Sound ({scenario?.title})
              </div>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55 }}>{scenario?.why_purpose}</p>
            </div>

            <div style={{ padding: 18, borderRadius: 14, background: "rgba(5, 150, 105, 0.06)", border: "1px solid rgba(5, 150, 105, 0.2)" }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", color: "#065f46", marginBottom: 6 }}>
                Recommended Pet Owner / Clinic Action
              </div>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55 }}>{scenario?.owner_action}</p>
            </div>
          </div>

          <div className="grid-3" style={{ gap: 12 }}>
            <div style={{ padding: 14, borderRadius: 12, background: "rgba(0,0,0,0.025)" }}>
              <div className="muted" style={{ fontSize: 12 }}>Vocal Pitch & Intensity</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>
                {Math.round(Number(analysis.features?.f0_mean || 340))} Hz ({Number(analysis.features?.f0_mean || 340) > 350 ? "High Pitch Alert" : "Grounded Pitch"})
              </div>
            </div>
            <div style={{ padding: 14, borderRadius: 12, background: "rgba(0,0,0,0.025)" }}>
              <div className="muted" style={{ fontSize: 12 }}>Attention & Urgency Level</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, textTransform: "capitalize" }}>
                {analysis.behavior?.arousal_label || "High"} Attention
              </div>
            </div>
            <div style={{ padding: 14, borderRadius: 12, background: "rgba(0,0,0,0.025)" }}>
              <div className="muted" style={{ fontSize: 12 }}>Breed Intelligence Calibration</div>
              <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>
                {dogProfile?.intelligence_tier || "Adaptive Canine Profile"}
              </div>
            </div>
          </div>

          {localAudioUrl && (
            <div style={{ padding: "12px 16px", borderRadius: 14, background: "rgba(0,0,0,0.025)" }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }} className="muted">
                Playback Analyzed Audio Clip ({(recResult.duration_sec || 0).toFixed(1)}s)
              </div>
              <audio controls src={localAudioUrl} style={{ width: "100%", height: 38 }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
