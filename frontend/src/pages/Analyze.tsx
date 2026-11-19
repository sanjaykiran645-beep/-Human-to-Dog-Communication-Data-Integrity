import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Dog } from "../api";

function extensionForMime(mimeType: string): string {
  const m = (mimeType || "").toLowerCase();
  if (m.includes("mp4") || m.includes("m4a")) return "m4a";
  if (m.includes("ogg")) return "ogg";
  if (m.includes("wav")) return "wav";
  if (m.includes("mpeg") || m.includes("mp3")) return "mp3";
  return "webm";
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
      .catch((e: any) => {
        setErr(String(e?.message || "Failed to load companion profiles."));
      });

    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function runAnalysis(file: File | Blob, mode: "mic" | "upload") {
    setErr(null);
    if (mode === "mic") setProcessingMic(true);
    else setUploadingFile(true);

    try {
      if (localAudioUrl) URL.revokeObjectURL(localAudioUrl);
      setLocalAudioUrl(URL.createObjectURL(file));

      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 30000);
      try {
        const fd = new FormData();
        const fallbackName =
          mode === "mic" ? `mic-recording.${extensionForMime(file.type)}` : "recording.wav";
        fd.append("file", file, (file as File).name || fallbackName);
        if (dogId) fd.append("dog_id", dogId);
        fd.append("source", mode === "mic" ? "microphone" : "upload");

        const serverData = await api<any>("/api/recordings/analyze", {
          method: "POST",
          body: fd,
          signal: controller.signal,
        });
        window.clearTimeout(timeoutId);
        setRecResult(serverData);
      } catch (e: any) {
        window.clearTimeout(timeoutId);
        if (e?.name === "AbortError") {
          throw new Error("Audio analysis timed out. Please retry with a shorter clip.");
        }
        throw e;
      }
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

    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setErr(
        "Live microphone recording is not supported in this browser/WebView. Please use Upload Dog Audio File (WAV, MP3, M4A, OGG, or WEBM)."
      );
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
        const mime = mr.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mime });
        await runAnalysis(blob, "mic");
      };

      mr.start();
      setSecs(0);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        setSecs((s) => s + 1);
      }, 1000);
    } catch {
      setErr(
        "Microphone access was blocked by the browser. Click the lock icon in the address bar to allow Microphone, or use Upload Dog Audio File."
      );
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
              <div className="muted" style={{ fontSize: 12 }}>Directly Measured Pitch &amp; Intensity</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>
                {Math.round(Number(analysis.features?.f0_mean || 340))} Hz ({Number(analysis.features?.f0_mean || 340) > 350 ? "High Pitch Alert" : "Grounded Pitch"})
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Measured from audio PCM</div>
            </div>
            <div style={{ padding: 14, borderRadius: 12, background: "rgba(0,0,0,0.025)" }}>
              <div className="muted" style={{ fontSize: 12 }}>Estimated Arousal / Urgency</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, textTransform: "capitalize" }}>
                {analysis.behavior?.arousal_label || "High"} Attention
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Heuristic context (unvalidated)</div>
            </div>
            <div style={{ padding: 14, borderRadius: 12, background: "rgba(0,0,0,0.025)" }}>
              <div className="muted" style={{ fontSize: 12 }}>Breed / Sex Context Prior</div>
              <div style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>
                {dogProfile?.intelligence_tier || "Allometric / Heuristic Prior"}
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Not a measured vocal diagnosis</div>
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
