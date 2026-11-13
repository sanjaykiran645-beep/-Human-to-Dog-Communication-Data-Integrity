import { FormEvent, useEffect, useRef, useState } from "react";
import { api, authMediaUrl, Dog } from "../api";
import AudioPlayer, { stopAllActiveAudio } from "../components/AudioPlayer";
import { recordPcmWav } from "../wav";

const QUICK_PHRASES = [
  { label: "Come here", text: "come here", vocal: "yip", desc: "Friendly recall cue" },
  { label: "Good dog!", text: "good dog", vocal: "whine", desc: "Warm praise & affection" },
  { label: "Calm down", text: "calm relax easy", vocal: "soft_attention", desc: "Soothing low-arousal cue" },
  { label: "Let?s play!", text: "let's play fetch", vocal: "yip", desc: "Playful high-energy invite" },
  { label: "Look at me", text: "hey look at me", vocal: "soft_attention", desc: "Gentle attention chime" },
  { label: "Stay / Wait", text: "stay wait hold", vocal: "grunt", desc: "Steady grounding cue" },
  { label: "Stop / Leave it", text: "stop leave it", vocal: "growl", desc: "Firm boundary signal" },
];

function mapAnyTextToVocalTarget(input: string): { intent: string; vocal: string } {
  const s = input.trim().toLowerCase();
  if (/\b(play|fetch|ball|toy|run|fun|game|jump|excited)\b/.test(s)) return { intent: "play", vocal: "yip" };
  if (/\b(calm|easy|relax|sleep|bed|quiet|shh|peace|okay|ok|rest|settle)\b/.test(s)) return { intent: "calm", vocal: "soft_attention" };
  if (/\b(good|love|happy|treat|food|eat|hungry|sweet|yes|bravo|proud|walk)\b/.test(s)) return { intent: "positive_reinforcement", vocal: "whine" };
  if (/\b(stop|no|leave|drop|bad|don't|off|enough)\b/.test(s)) return { intent: "stop", vocal: "growl" };
  if (/\b(stay|wait|sit|hold|place|down)\b/.test(s)) return { intent: "stay", vocal: "grunt" };
  if (/\b(come|here|call|return)\b/.test(s)) return { intent: "come", vocal: "yip" };
  if (/\b(howl|pack|sing|far)\b/.test(s)) return { intent: "calm", vocal: "howl" };
  if (/\b(bark|guard|alert|watch)\b/.test(s)) return { intent: "attention", vocal: "bark" };
  // Default for any conversational phrase (e.g. "hello", "app", custom sentences): gentle attention cue, NEVER random harsh barking
  return { intent: "attention", vocal: "soft_attention" };
}

export default function Communicate() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [selectedVocal, setSelectedVocal] = useState<string>("auto");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);

  // Optional dog response recording
  const [recordingResp, setRecordingResp] = useState(false);
  const [respSecs, setRespSecs] = useState(0);
  const [respAnalysis, setRespAnalysis] = useState<any | null>(null);
  const [submittingResp, setSubmittingResp] = useState(false);
  const recRef = useRef<{ stop: () => Promise<Blob> } | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    localStorage.removeItem("cs_demo_mode");
    api<Dog[]>("/api/dogs")
      .then((list) => {
        setDogs(list || []);
        if (list && list.length > 0) setDogId(list[0].id);
      })
      .catch(() => {});

    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      recRef.current?.stop().catch(() => {});
      stopAllActiveAudio();
    };
  }, []);

  async function generateSound(customText?: string, forcedVocal?: string) {
    const phrase = (customText !== undefined ? customText : text).trim();
    if (!phrase || busy) return;

    setErr(null);
    setBusy(true);
    setRespAnalysis(null);
    stopAllActiveAudio();

    try {
      const mapped = mapAnyTextToVocalTarget(phrase);
      const targetVocal = forcedVocal || (selectedVocal !== "auto" ? selectedVocal : mapped.vocal);

      const res = await api<any>("/api/communicate/generate", {
        method: "POST",
        body: JSON.stringify({
          text: phrase,
          dog_id: dogId || null,
          intent_override: mapped.intent,
          vocalization_target: targetVocal,
          generation_method: "reference_variation",
        }),
      });

      const gen = res?.generated;
      if (!gen) {
        throw new Error("Could not synthesize audio for this phrase.");
      }
      setResult(gen);
      const url = await authMediaUrl(gen.audio_url || `/api/communicate/${gen.id}/audio`);
      setAudioSrc(url);
    } catch (e: any) {
      setErr(e.message || "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  function handleFormSubmit(e: FormEvent) {
    e.preventDefault();
    generateSound();
  }

  async function toggleResponseRecording() {
    if (recordingResp) {
      if (timerRef.current) window.clearInterval(timerRef.current);
      setRecordingResp(false);
      if (!recRef.current || !result?.id) return;
      setSubmittingResp(true);
      try {
        const wavBlob = await recRef.current.stop();
        recRef.current = null;
        const fd = new FormData();
        fd.append("file", wavBlob, "dog_response.wav");
        const resp = await api<any>(`/api/communicate/${result.id}/response`, {
          method: "POST",
          body: fd,
        });
        setRespAnalysis(resp);
      } catch (e: any) {
        setErr(e.message || "Failed to analyze dog response");
      } finally {
        setSubmittingResp(false);
      }
    } else {
      try {
        setErr(null);
        stopAllActiveAudio();
        const r = await recordPcmWav(16000);
        recRef.current = r;
        setRespSecs(0);
        setRecordingResp(true);
        timerRef.current = window.setInterval(() => {
          setRespSecs((s) => s + 1);
        }, 1000);
      } catch (e: any) {
        setErr("Microphone permission is required to record your dog's response.");
      }
    }
  }

  const activeDog = dogs.find((d) => d.id === dogId);

  return (
    <div className="stack-lg" style={{ maxWidth: 920, margin: "0 auto" }}>
      <div className="card stack" style={{ padding: 30, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: "0 0 4px 0", fontSize: 24 }}>Human ? Dog Translator</h2>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Type any message or pick a quick cue. Audio is automatically tuned to your dog?s breed profile.
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
                    ?? {d.name} ({d.breed || "Mixed"})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {err && <div className="alert alert-error">{err}</div>}

        {/* Quick 1-Click Cues */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }} className="muted">
            Instant Cues
          </div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            {QUICK_PHRASES.map((q) => (
              <button
                key={q.label}
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ borderRadius: 999, padding: "7px 14px" }}
                disabled={busy}
                onClick={() => {
                  setText(q.label);
                  generateSound(q.text, q.vocal);
                }}
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>

        {/* Custom Input Form */}
        <form onSubmit={handleFormSubmit} className="stack" style={{ gap: 14 }}>
          <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type anything you want to say to your dog (e.g. 'Time for dinner', 'Relax buddy', 'Come here')..."
              style={{ flex: 1, minWidth: 240, padding: "12px 16px", borderRadius: 12, fontSize: 15 }}
            />
            <select
              value={selectedVocal}
              onChange={(e) => setSelectedVocal(e.target.value)}
              style={{ width: 200, borderRadius: 12, padding: "12px" }}
              title="Sound style"
            >
              <option value="auto">? Auto-Match Tone</option>
              <option value="soft_attention">Gentle Attention</option>
              <option value="yip">Playful Yip</option>
              <option value="whine">Affectionate Whine</option>
              <option value="grunt">Calm Grounding Grunt</option>
              <option value="howl">Social Howl</option>
              <option value="bark">Alert Bark</option>
            </select>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={busy || !text.trim()}
              style={{ borderRadius: 12, padding: "12px 24px", fontWeight: 600 }}
            >
              {busy ? "Generating..." : "Generate Sound"}
            </button>
          </div>
        </form>
      </div>

      {/* Generated Audio Output Card */}
      {result && audioSrc && (
        <div className="card stack" style={{ padding: 28, borderRadius: 20, border: "2px solid rgba(124, 45, 18, 0.18)" }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            <div>
              <span className="badge" style={{ marginBottom: 6 }}>
                Tuned for {activeDog ? `${activeDog.name} (${activeDog.breed || "Canine"})` : "Standard Canine"}
              </span>
              <h3 style={{ margin: 0, fontSize: 20 }}>
                Ready to Play: ?{result.input_text}?
              </h3>
              <p className="muted" style={{ margin: "4px 0 0 0", fontSize: 13 }}>
                Acoustic Profile: <strong>{(result.parameters?.vocalization_target || result.intent || "Social Cue").replace(/_/g, " ")}</strong>
              </p>
            </div>
          </div>

          <AudioPlayer src={audioSrc} title={`Canine Cue: ${result.input_text}`} disabled={recordingResp || submittingResp} />

          {/* Simple 1-Click Dog Reaction Check */}
          <div
            style={{
              marginTop: 8,
              padding: 18,
              borderRadius: 14,
              background: "rgba(0,0,0,0.025)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Did your dog respond?</div>
              <div className="muted" style={{ fontSize: 12 }}>
                Record your dog?s reaction after playing the sound to analyze their response.
              </div>
            </div>
            <button
              type="button"
              className={recordingResp ? "btn btn-danger btn-sm" : "btn btn-secondary btn-sm"}
              onClick={toggleResponseRecording}
              disabled={submittingResp}
              style={{ borderRadius: 999, padding: "8px 18px" }}
            >
              {submittingResp
                ? "Analyzing reaction..."
                : recordingResp
                ? `Stop Recording (${respSecs}s)`
                : "??? Record Dog?s Reaction"}
            </button>
          </div>

          {respAnalysis && (
            <div className="card" style={{ background: "#f8fafc", padding: 16, borderRadius: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                Reaction Detected: {(respAnalysis.vocalization || "Vocalization").toUpperCase()} ({Math.round((respAnalysis.confidence || 0) * 100)}%)
              </div>
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                Behavioral Context: {(respAnalysis.behavior?.context || "Social response").replace(/_/g, " ")}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
