import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Dog } from "../api";
import AudioPlayer from "../components/AudioPlayer";
import ResultView from "../components/ResultView";
import SpectrogramViewer from "../components/SpectrogramViewer";
import { encodeWav, recordPcmWav } from "../wav";

function buildQuickTestSignal(kind: "bark" | "whine" | "growl" | "howl" | "squeak"): File {
  const sr = 22050;
  let dur = 1.2;
  if (kind === "howl") dur = 2.2;
  if (kind === "growl") dur = 1.5;
  const n = Math.floor(sr * dur);
  const out = new Float32Array(n);

  if (kind === "bark") {
    for (let b = 0; b < 3; b++) {
      const start = Math.floor(b * 0.34 * sr);
      const len = Math.floor(0.15 * sr);
      for (let i = 0; i < len && start + i < n; i++) {
        const t = i / sr;
        const env = Math.sin((Math.PI * i) / len) * Math.exp(-t * 11);
        out[start + i] =
          env *
          (0.5 * Math.sin(2 * Math.PI * 360 * t) +
            0.3 * Math.sin(2 * Math.PI * 720 * t) +
            0.2 * Math.sin(2 * Math.PI * 1440 * t));
      }
    }
  } else if (kind === "whine") {
    for (let i = 0; i < n; i++) {
      const t = i / sr;
      const u = i / n;
      const f0 = 760 + 280 * u;
      const env = Math.sin(Math.PI * u) ** 0.5;
      out[i] = env * (0.65 * Math.sin(2 * Math.PI * f0 * t) + 0.2 * Math.sin(2 * Math.PI * 2 * f0 * t));
    }
  } else if (kind === "growl") {
    for (let i = 0; i < n; i++) {
      const t = i / sr;
      const u = i / n;
      const am = 0.55 + 0.45 * Math.sin(2 * Math.PI * 42 * t);
      const env = Math.sin(Math.PI * u) ** 0.5;
      out[i] =
        env *
        am *
        (0.55 * Math.sin(2 * Math.PI * 115 * t) +
          0.3 * Math.sin(2 * Math.PI * 230 * t) +
          0.15 * Math.sin(2 * Math.PI * 345 * t));
    }
  } else if (kind === "howl") {
    for (let i = 0; i < n; i++) {
      const t = i / sr;
      const u = i / n;
      const f0 = 420 + 90 * Math.sin(Math.PI * u);
      const env = Math.sin(Math.PI * u) ** 0.6;
      out[i] =
        env *
        (0.65 * Math.sin(2 * Math.PI * f0 * t) +
          0.22 * Math.sin(2 * Math.PI * 2 * f0 * t) +
          0.1 * Math.sin(2 * Math.PI * 3 * f0 * t));
    }
  } else {
    // High-frequency mechanical squeak fixture (> 4 kHz)
    for (let i = 0; i < n; i++) {
      const t = i / sr;
      const u = i / n;
      const env = Math.sin(Math.PI * u) ** 0.5;
      out[i] = env * (0.55 * Math.sin(2 * Math.PI * 4300 * t) + 0.35 * Math.sin(2 * Math.PI * 6450 * t));
    }
  }
  const blob = encodeWav([out], sr);
  return new File([blob], `synthetic-${kind}-fixture.wav`, { type: "audio/wav" });
}

export default function Analyze() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<any>(null);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [decoderOk, setDecoderOk] = useState<boolean | null>(null);
  const [decoderHint, setDecoderHint] = useState("");
  const stopRecRef = useRef<(() => void) | null>(null);
  const timer = useRef<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastSource = useRef("upload");

  useEffect(() => {
    api<Dog[]>("/api/dogs")
      .then((d) => {
        setDogs(d);
        if (d[0]) setDogId(d[0].id);
      })
      .catch(() => {});
    api<any>("/api/health")
      .then((h) => {
        setDecoderOk(Boolean(h?.decoder?.ffmpeg_available || h?.decoder?.soundfile_wav));
        setDecoderHint(h?.decoder?.install_hint || "");
      })
      .catch(() => setDecoderOk(null));
  }, []);

  useEffect(() => {
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  async function run(f: File, source: string) {
    lastSource.current = source;
    setBusy(true);
    setErr("");
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("source", source);
      if (dogId) fd.append("dog_id", dogId);
      const data = await api<any>("/api/recordings/analyze", { method: "POST", body: fd });
      setResult(data);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function startRec() {
    setErr("");
    try {
      const rec = await recordPcmWav(60);
      stopRecRef.current = rec.stop;
      setRecording(true);
      setSeconds(0);
      timer.current = window.setInterval(() => {
        setSeconds((s) => {
          if (s >= 59) {
            stopRec();
            return 59;
          }
          return s + 1;
        });
      }, 1000);
      const f = await rec.done;
      setFile(f);
      await run(f, "microphone");
    } catch (ex) {
      setRecording(false);
      setErr(ex instanceof Error ? ex.message : "Microphone permission denied or unavailable.");
    }
  }

  function stopRec() {
    stopRecRef.current?.();
    stopRecRef.current = null;
    setRecording(false);
    if (timer.current) window.clearInterval(timer.current);
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="kicker">Engine A · Acoustic Analysis &amp; STFT Spectrogram</div>
          <h1>Analyze dog audio</h1>
          <p>
            Upload or record audio. Originals are stored privately, decoded on the server, analyzed for acoustic
            features and STFT spectrogram structure, and evaluated with conservative abstention safeguards.
          </p>
        </div>
      </div>

      {decoderOk === false && decoderHint && <div className="error">{decoderHint}</div>}

      <div className="grid-2">
        <div className="card">
          <div className="field">
            <label>Dog profile (optional, improves F0-size consistency note only)</label>
            <select value={dogId} onChange={(e) => setDogId(e.target.value)}>
              <option value="">No profile</option>
              {dogs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div
            className="drop"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const f = e.dataTransfer.files[0];
              if (f) {
                setFile(f);
                run(f, "upload");
              }
            }}
          >
            <strong>Drop WAV, MP3, M4A, OGG, WEBM, or FLAC</strong>
            <p className="tiny">Max 50 MB, 300 seconds. {file ? file.name : "No file selected."}</p>
            <input
              ref={inputRef}
              type="file"
              hidden
              accept="audio/*,.wav,.mp3,.mpeg,.m4a,.ogg,.webm,.weba,.flac"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                  setFile(f);
                  run(f, "upload");
                }
                e.target.value = "";
              }}
            />
          </div>
          <div className="row" style={{ marginTop: 16, justifyContent: "center" }}>
            <button
              className={`rec-btn ${recording ? "live" : ""}`}
              type="button"
              onClick={recording ? stopRec : startRec}
              disabled={busy}
            >
              {recording ? "Stop" : "Rec"}
            </button>
          </div>
          <p className="tiny" style={{ textAlign: "center" }}>
            {recording
              ? `Recording… ${seconds}s / 60s`
              : "Microphone is captured as PCM WAV in the browser, then analyzed on the server."}
          </p>

          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
            <label>Synthetic engineering test fixtures (pipeline verification)</label>
            <div className="row" style={{ gap: 6 }}>
              {(["bark", "whine", "growl", "howl", "squeak"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  className="btn ghost"
                  disabled={busy || recording}
                  style={{ padding: "5px 10px", fontSize: "0.76rem" }}
                  onClick={() => {
                    const fx = buildQuickTestSignal(k);
                    setFile(fx);
                    run(fx, "upload");
                  }}
                >
                  Test {k}
                </button>
              ))}
            </div>
          </div>

          {busy && <p style={{ marginTop: 12 }}>Analyzing… decoding, computing STFT spectrogram, extracting features.</p>}
          {err && (
            <div className="error" style={{ marginTop: 12 }}>
              {err}
              <div className="row" style={{ marginTop: 8 }}>
                {file && (
                  <button
                    className="btn ghost"
                    type="button"
                    onClick={() => run(file, lastSource.current)}
                    disabled={busy}
                  >
                    Retry
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="card media">
          <h2>Signal, Playback &amp; STFT Spectrogram</h2>
          {busy && <div className="empty">Building waveform, STFT spectrogram, and playback stream…</div>}
          {!busy && !result && !err && (
            <div className="empty">Waveform, interactive STFT spectrogram, and audio player appear after analysis.</div>
          )}
          {result?.id && (
            <>
              <AudioPlayer
                mediaPath={`/api/recordings/${result.id}/media/processed`}
                title={`Processed 22.05 kHz mono WAV — ${result.original_filename}`}
                downloadFilename={`processed-${result.original_filename || "audio"}.wav`}
              />
              <SpectrogramViewer
                spectrogramDataPath={`/api/recordings/${result.id}/spectrogram-data`}
                spectrogramImagePath={`/api/recordings/${result.id}/media/spectrogram`}
                waveformPath={`/api/recordings/${result.id}/media/waveform`}
                title={`Signal Analysis — ${result.original_filename}`}
              />
            </>
          )}
        </div>
      </div>

      {result?.analysis && <ResultView analysis={result.analysis} quality={result.quality} />}
    </div>
  );
}
