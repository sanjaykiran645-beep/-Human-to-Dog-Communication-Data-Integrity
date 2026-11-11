import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, isDemoSession } from "../api";
import type { Dog } from "../api";
import AudioPlayer from "../components/AudioPlayer";
import ResultView from "../components/ResultView";
import SpectrogramViewer from "../components/SpectrogramViewer";
import { encodeWav, recordPcmWav } from "../wav";

const FAMILIES = [
  { id: "bark", category: "BARK", label: "BARK — Multi-burst canine bark" },
  { id: "growl", category: "GROWL", label: "GROWL — Low-frequency growl & rumble" },
  { id: "howl", category: "HOWL", label: "HOWL — Sustained harmonic howl contour" },
  { id: "whine", category: "WHINE", label: "WHINE — High-frequency rising tonal whine" },
  { id: "yip", category: "YIP", label: "YIP — Short high-pitched small-dog yip" },
  { id: "yelp", category: "YELP", label: "YELP — Sharp high-pitched yelp burst" },
  { id: "whimper", category: "WHIMPER", label: "WHIMPER — Plaintive wavering whimper" },
  { id: "cry", category: "CRY", label: "CRY — Intense high-pitched canine crying" },
  { id: "grunt", category: "GRUNT", label: "GRUNT — Short low vocal chuff / grunt" },
  { id: "groan", category: "GROAN", label: "GROAN — Low plaintive vocal groan" },
  { id: "pant", category: "PANT", label: "PANT — Rhythmic canine breathing / panting" },
  { id: "soft_attention", category: "WHIMPER", label: "SOFT ATTENTION — Gentle whimper / attention cue" },
];

const GENERATION_METHODS = [
  {
    id: "reference_direct",
    label: "Method A · Real Reference Retrieval (Recommended — Authentic Dog Audio)",
    badge: "Original Reference Audio",
    desc: "Selects and plays the highest-suitability real dog recording from the validated Reference Library with zero artificial oscillator artifacts.",
  },
  {
    id: "reference_variation",
    label: "Method B · Controlled Reference Variation (Modified Real Recording)",
    badge: "Transformed Reference Audio",
    desc: "Applies bounded, naturalness-preserving pitch shifting (±2 semitones), time stretching (0.85×–1.18×), and low-pass smoothing to a real dog recording.",
  },
  {
    id: "generative_model",
    label: "Method C · Data-Conditioned Generative Model (Status & Safe Fallback)",
    badge: "Model Assessment / Fallback",
    desc: "Evaluates neural audio model readiness and license constraints; automatically falls back to Method B (Controlled Reference Variation) when training rights or corpus size block neural inference.",
  },
  {
    id: "experimental_dsp",
    label: "Method D · Experimental DSP Synthesizer (Synthetic Fallback Only)",
    badge: "Experimental DSP Output",
    desc: "Uses repaired parallel formant resonators and glottal pulses. Clearly labeled as synthetic audio.",
  },
];

const QUICK_COMMANDS = [
  { label: "Come here (Bark)", text: "Come here" },
  { label: "Stay (Grunt)", text: "Stay there" },
  { label: "Good dog (Yip)", text: "Good dog, well done" },
  { label: "Easy (Whimper)", text: "Easy, settle down" },
  { label: "Let's play (Bark)", text: "Let's play fetch" },
  { label: "Stop (Growl)", text: "Stop, leave it" },
  { label: "Look at me (Whine)", text: "Hey, look at me" },
  { label: "Howl call", text: "Howl with me" },
  { label: "Ambiguous test", text: "Come here and stay and play" },
];

const REFERENCE_CATEGORIES = [
  "ALL",
  "BARK",
  "GROWL",
  "HOWL",
  "WHINE",
  "YIP",
  "YELP",
  "WHIMPER",
  "CRY",
  "GRUNT",
  "GROAN",
  "PANT",
  "MIXED",
  "UNKNOWN",
];

function buildTestResponseWav(): File {
  const sr = 22050;
  const dur = 1.2;
  const n = Math.floor(sr * dur);
  const samples = new Float32Array(n);
  for (let b = 0; b < 3; b++) {
    const start = Math.floor(b * 0.36 * sr);
    const len = Math.floor(0.16 * sr);
    for (let i = 0; i < len && start + i < n; i++) {
      const t = i / sr;
      const env = Math.sin((Math.PI * i) / len) * Math.exp(-t * 10);
      const sig =
        0.55 * Math.sin(2 * Math.PI * 380 * t) +
        0.3 * Math.sin(2 * Math.PI * 760 * t) +
        0.15 * Math.sin(2 * Math.PI * 1140 * t);
      samples[start + i] = sig * env * 0.75;
    }
  }
  const blob = encodeWav([samples], sr);
  return new File([blob], "response-fixture.wav", { type: "audio/wav" });
}

export default function Communicate() {
  const [text, setText] = useState("");
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [dogId, setDogId] = useState("");
  const [family, setFamily] = useState("");
  const [generationMethod, setGenerationMethod] = useState<string>("reference_direct");
  const [selectedRefAssetId, setSelectedRefAssetId] = useState<string>("");
  const [intensity, setIntensity] = useState<string>("");
  const [durationSec, setDurationSec] = useState<string>("");
  const [pitchHz, setPitchHz] = useState<string>("");
  const [pitchShiftSt, setPitchShiftSt] = useState<string>("");
  const [timeStretchRate, setTimeStretchRate] = useState<string>("");
  const [variationIndex, setVariationIndex] = useState<number>(0);

  const [intent, setIntent] = useState<any>(null);
  const [generated, setGenerated] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [listening, setListening] = useState(false);

  // Reference Library state
  const [refLibrary, setRefLibrary] = useState<any>(null);
  const [refCategoryFilter, setRefCategoryFilter] = useState<string>("ALL");
  const [showRefBrowser, setShowRefBrowser] = useState<boolean>(false);
  const [inspectedRef, setInspectedRef] = useState<any>(null);
  const [editConfirmedCat, setEditConfirmedCat] = useState<string>("");
  const [editRefNotes, setEditRefNotes] = useState<string>("");
  const [savingAnnotation, setSavingAnnotation] = useState<boolean>(false);
  const [uploadingRef, setUploadingRef] = useState<boolean>(false);
  const [uploadRefCat, setUploadRefCat] = useState<string>("");
  const refUploadInputRef = useRef<HTMLInputElement | null>(null);

  // User listening feedback state
  const [fbRating, setFbRating] = useState<number>(5);
  const [fbNatural, setFbNatural] = useState<boolean>(true);
  const [fbNotes, setFbNotes] = useState<string>("");
  const [fbSaving, setFbSaving] = useState<boolean>(false);
  const [fbSavedMsg, setFbSavedMsg] = useState<string>("");

  // Dog response recording & review state
  const [recordingResp, setRecordingResp] = useState(false);
  const [respSeconds, setRespSeconds] = useState(0);
  const [pendingRespFile, setPendingRespFile] = useState<File | null>(null);
  const [pendingRespBlobUrl, setPendingRespBlobUrl] = useState<string | null>(null);
  const [submittingResp, setSubmittingResp] = useState(false);
  const [responses, setResponses] = useState<any[]>([]);
  const [activeResponse, setActiveResponse] = useState<any>(null);

  // Blind Listening Evaluation Protocol state
  const [showBlindTest, setShowBlindTest] = useState(false);
  const [blindProtocol, setBlindProtocol] = useState<any>(null);
  const [selectedBlindSample, setSelectedBlindSample] = useState<any>(null);
  const [blindReviewerId, setBlindReviewerId] = useState("reviewer_1");
  const [blindIsDog, setBlindIsDog] = useState(true);
  const [blindPerceivedCat, setBlindPerceivedCat] = useState("BARK");
  const [blindNaturalness, setBlindNaturalness] = useState(5);
  const [blindArtifactScore, setBlindArtifactScore] = useState(5);
  const [blindNotes, setBlindNotes] = useState("");
  const [blindSubmitting, setBlindSubmitting] = useState(false);
  const [blindRevealed, setBlindRevealed] = useState<any>(null);

  const recRef = useRef<{ stop: () => void } | null>(null);
  const timerRef = useRef<number | null>(null);
  const respFileInputRef = useRef<HTMLInputElement | null>(null);

  function loadHistory() {
    api<any[]>("/api/communicate")
      .then(setHistory)
      .catch(() => {});
  }

  function loadReferenceLibrary(cat = refCategoryFilter) {
    const q = cat && cat !== "ALL" ? `?category=${encodeURIComponent(cat)}` : "";
    api<any>(`/api/communicate/references${q}`)
      .then((data) => {
        setRefLibrary(data);
        if (inspectedRef) {
          const updated = (data.assets || []).find((a: any) => a.asset_id === inspectedRef.asset_id);
          if (updated) setInspectedRef(updated);
        }
      })
      .catch(() => {});
  }

  function loadBlindProtocol() {
    api<any>("/api/communicate/blind-test")
      .then((data) => {
        setBlindProtocol(data);
        if (!selectedBlindSample && data.samples?.length) {
          setSelectedBlindSample(data.samples[0]);
        }
      })
      .catch(() => {});
  }

  async function submitBlindEvaluation() {
    if (!selectedBlindSample) return;
    setBlindSubmitting(true);
    setBlindRevealed(null);
    try {
      const res = await api<any>("/api/communicate/blind-test/submit", {
        method: "POST",
        body: JSON.stringify({
          sample_id: selectedBlindSample.sample_id,
          reviewer_id: blindReviewerId || "reviewer_1",
          sounds_like_genuine_dog: blindIsDog,
          perceived_category: blindPerceivedCat,
          naturalness_score: Number(blindNaturalness),
          artifact_severity_score: Number(blindArtifactScore),
          notes: blindNotes || null,
        }),
      });
      setBlindRevealed(res);
      loadBlindProtocol();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not submit blind rating");
    } finally {
      setBlindSubmitting(false);
    }
  }

  useEffect(() => {
    api<Dog[]>("/api/dogs")
      .then((d) => {
        setDogs(d);
        if (d[0]) setDogId(d[0].id);
      })
      .catch(() => {});
    loadHistory();
    loadReferenceLibrary("ALL");
  }, []);

  useEffect(() => {
    loadReferenceLibrary(refCategoryFilter);
  }, [refCategoryFilter]);

  useEffect(() => {
    return () => {
      if (pendingRespBlobUrl) URL.revokeObjectURL(pendingRespBlobUrl);
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [pendingRespBlobUrl]);

  function setReviewFile(file: File | null) {
    if (pendingRespBlobUrl) {
      URL.revokeObjectURL(pendingRespBlobUrl);
    }
    if (!file) {
      setPendingRespFile(null);
      setPendingRespBlobUrl(null);
      return;
    }
    setPendingRespFile(file);
    setPendingRespBlobUrl(URL.createObjectURL(file));
  }

  async function onPreviewIntent() {
    setErr("");
    if (!text.trim() && !family) {
      setErr("Please enter a command phrase or select a vocalization profile first.");
      return;
    }
    setPreviewBusy(true);
    try {
      const parsed = await api<any>("/api/communicate/intent", {
        method: "POST",
        body: JSON.stringify({
          text,
          dog_id: dogId || null,
          vocalization_target: family || null,
          generation_method: generationMethod,
          reference_asset_id: selectedRefAssetId || null,
          intensity: intensity ? Number(intensity) : null,
          duration_sec: durationSec ? Number(durationSec) : null,
          pitch_hz: pitchHz ? Number(pitchHz) : null,
          pitch_shift_semitones: pitchShiftSt ? Number(pitchShiftSt) : null,
          time_stretch_rate: timeStretchRate ? Number(timeStretchRate) : null,
          variation_index: variationIndex,
        }),
      });
      setIntent(parsed);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not analyze intent.");
    } finally {
      setPreviewBusy(false);
    }
  }

  async function onGenerate(e?: FormEvent, override?: string, nextVarIdx?: number) {
    e?.preventDefault();
    setErr("");
    setFbSavedMsg("");

    const activeVarIdx = nextVarIdx !== undefined ? nextVarIdx : variationIndex;
    if (nextVarIdx !== undefined) {
      setVariationIndex(nextVarIdx);
    }

    if (!text.trim() && !family && !override) {
      setErr("Please enter a command (such as 'come here', 'stay', 'good dog', or 'easy') or select a vocalization profile.");
      return;
    }
    if (intensity && (Number(intensity) < 0.15 || Number(intensity) > 1.0)) {
      setErr("Intensity must be between 0.15 and 1.0.");
      return;
    }
    if (durationSec && (Number(durationSec) < 0.08 || Number(durationSec) > 6.0)) {
      setErr("Duration must be between 0.08 and 6.0 seconds.");
      return;
    }
    if (pitchHz && (Number(pitchHz) < 60 || Number(pitchHz) > 2000)) {
      setErr("Fundamental pitch must be between 60 and 2000 Hz.");
      return;
    }
    if (pitchShiftSt && (Number(pitchShiftSt) < -2.0 || Number(pitchShiftSt) > 2.0)) {
      setErr("Pitch shift must stay within natural bounds (-2.0 to +2.0 semitones).");
      return;
    }
    if (timeStretchRate && (Number(timeStretchRate) < 0.85 || Number(timeStretchRate) > 1.18)) {
      setErr("Time stretch rate must stay within natural bounds (0.85 to 1.18).");
      return;
    }

    setBusy(true);
    setActiveResponse(null);
    setResponses([]);
    setReviewFile(null);

    try {
      const data = await api<any>("/api/communicate/generate", {
        method: "POST",
        body: JSON.stringify({
          text: text.trim() || family || "come here",
          dog_id: dogId || null,
          intent_override: override || null,
          vocalization_target: family || null,
          generation_method: generationMethod,
          reference_asset_id: selectedRefAssetId || null,
          intensity: intensity ? Number(intensity) : null,
          duration_sec: durationSec ? Number(durationSec) : null,
          pitch_hz: pitchHz ? Number(pitchHz) : null,
          pitch_shift_semitones: pitchShiftSt ? Number(pitchShiftSt) : null,
          time_stretch_rate: timeStretchRate ? Number(timeStretchRate) : null,
          variation_index: activeVarIdx,
        }),
      });
      setIntent(data.intent);
      if (data.status === "needs_clarification") {
        setGenerated(null);
        return;
      }
      if (!data.generated?.id || !data.generated?.validation?.valid) {
        setErr("Audio generation did not pass file validation.");
        setGenerated(null);
        return;
      }
      setGenerated(data.generated);
      loadHistory();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Audio generation failed");
      setGenerated(null);
    } finally {
      setBusy(false);
    }
  }

  async function selectGenerated(row: any) {
    setGenerated(row);
    setFbSavedMsg("");
    setIntent({
      original_input: row.source_text,
      normalized_input: row.notes?.normalized_input || row.source_text?.toLowerCase(),
      intent: row.intent,
      detected_intent: row.intent,
      confidence: row.intent_confidence,
      selected_synthesis_profile: row.vocalization_target,
      reference_category: row.requested_category,
      synthesis_parameters: row.params,
      validation: { valid: true, status: "historical_record", errors: [], warnings: [] },
      needs_clarification: false,
      mapping: { status: row.mapping_status, vocalization_target: row.vocalization_target },
    });
    setReviewFile(null);
    setErr("");
    try {
      const resps = await api<any[]>(`/api/communicate/${row.id}/responses`);
      setResponses(resps);
      setActiveResponse(resps[0] || null);
    } catch {
      setResponses([]);
      setActiveResponse(null);
    }
  }

  async function saveReferenceAnnotation() {
    if (!inspectedRef) return;
    setSavingAnnotation(true);
    setErr("");
    try {
      const updated = await api<any>(`/api/communicate/references/${inspectedRef.asset_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          confirmed_category: editConfirmedCat || "CLEAR",
          notes: editRefNotes,
        }),
      });
      setInspectedRef(updated);
      loadReferenceLibrary(refCategoryFilter);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to update reference category label");
    } finally {
      setSavingAnnotation(false);
    }
  }

  async function handleUploadReferenceFile(file: File) {
    setUploadingRef(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (uploadRefCat) fd.append("confirmed_category", uploadRefCat);
      const added = await api<any>("/api/communicate/references/upload", {
        method: "POST",
        body: fd,
      });
      setInspectedRef(added);
      setEditConfirmedCat(added.confirmed_category || "");
      setEditRefNotes(added.notes || "");
      setSelectedRefAssetId(added.asset_id);
      loadReferenceLibrary(refCategoryFilter);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not upload reference recording");
    } finally {
      setUploadingRef(false);
    }
  }

  async function submitListeningFeedback() {
    if (!generated?.id) return;
    setFbSaving(true);
    setFbSavedMsg("");
    try {
      const updated = await api<any>(`/api/communicate/${generated.id}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          rating: fbRating,
          sounds_natural: fbNatural,
          notes: fbNotes || null,
        }),
      });
      setGenerated(updated);
      setFbSavedMsg("Listening evaluation saved to audit log.");
      loadHistory();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not save feedback");
    } finally {
      setFbSaving(false);
    }
  }

  function listen() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      setErr("On-device speech recognition is not supported by this browser. Please type your phrase.");
      return;
    }
    try {
      const rec = new SR();
      rec.lang = "en-US";
      rec.onresult = (ev: any) => setText(ev.results[0][0].transcript);
      rec.onerror = () => {
        setListening(false);
        setErr("Voice input could not be captured. Check microphone permission or type instead.");
      };
      rec.onend = () => setListening(false);
      rec.start();
      setListening(true);
    } catch {
      setListening(false);
      setErr("Could not start voice recognition.");
    }
  }

  function stopResponseRec() {
    recRef.current?.stop();
    recRef.current = null;
    setRecordingResp(false);
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  async function startResponseRec() {
    if (!generated) return;
    setErr("");
    try {
      const rec = await recordPcmWav(10);
      recRef.current = rec;
      setRecordingResp(true);
      setRespSeconds(0);
      timerRef.current = window.setInterval(() => {
        setRespSeconds((s) => {
          if (s >= 9) {
            stopResponseRec();
            return 10;
          }
          return s + 1;
        });
      }, 1000);
      const f = await rec.done;
      stopResponseRec();
      setReviewFile(f);
    } catch (ex) {
      stopResponseRec();
      setErr(
        ex instanceof Error
          ? `Microphone error: ${ex.message}. You can also upload a response audio file below.`
          : "Microphone permission denied or unavailable."
      );
    }
  }

  async function submitReviewedResponse() {
    if (!generated || !pendingRespFile) return;
    setErr("");
    setSubmittingResp(true);
    try {
      const fd = new FormData();
      fd.append("file", pendingRespFile);
      const data = await api<any>(`/api/communicate/${generated.id}/response`, {
        method: "POST",
        body: fd,
      });
      setActiveResponse(data);
      setResponses((prev) => {
        const exists = prev.some((r) => r.id === data.id);
        return exists ? prev : [data, ...prev];
      });
      setReviewFile(null);
      loadHistory();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Response submission and analysis failed");
    } finally {
      setSubmittingResp(false);
    }
  }

  const synthParams = generated?.params || intent?.synthesis_parameters;
  const valInfo = generated?.validation || generated?.params?.validation;
  const primaryRef = generated?.primary_reference_asset || generated?.params?.primary_reference_asset;
  const acousticComp = generated?.acoustic_comparison || generated?.params?.acoustic_comparison;
  const genWarnings: string[] = generated?.generation_warnings || generated?.params?.generation_warnings || [];
  const activeMethodInfo = GENERATION_METHODS.find((m) => m.id === generationMethod) || GENERATION_METHODS[0];

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="kicker">Engine B · Reference-Driven Canine Vocalization Laboratory</div>
          <h1>Human → dog communication &amp; reference audio</h1>
          <p>
            Generates high-fidelity canine vocalizations grounded in genuine dog audio recordings (Retrieval &amp;
            Controlled Variation), with side-by-side reference comparison, STFT spectrograms, and quality verification.
          </p>
          {isDemoSession() && (
            <div
              className="badge warn"
              role="status"
              style={{
                padding: "8px 14px",
                marginTop: 10,
                display: "inline-block",
                background: "#FFF4E5",
                color: "#663C00",
                border: "1px solid #FFE2B3",
              }}
            >
              ⚠️ Demo Mode: Synthetic WebAudio synthesizer active. Authentic 134-clip reference library streaming and neural synthesis require a connected FastAPI backend.
            </div>
          )}
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button
            type="button"
            className={`btn ${showRefBrowser ? "accent" : "ghost"}`}
            onClick={() => setShowRefBrowser((v) => !v)}
          >
            {showRefBrowser ? "Hide Reference Library" : `Reference Audio Library (${refLibrary?.total_accepted_canine_references ?? 128} clips)`}
          </button>
          <button
            type="button"
            className={`btn ${showBlindTest ? "accent" : "ghost"}`}
            onClick={() => {
              const next = !showBlindTest;
              setShowBlindTest(next);
              if (next) loadBlindProtocol();
            }}
          >
            {showBlindTest ? "Hide Blind Listening Protocol" : "Blind Listening Evaluation"}
          </button>
          <span className="badge ok">Reference-Driven v2.1</span>
        </div>
      </div>

      {/* Blind Listening Evaluation Protocol Panel */}
      {showBlindTest && (
        <div className="card" style={{ marginBottom: 16, borderColor: "var(--accent)" }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <div>
              <h2>Independent Blind Listening Comparison Protocol</h2>
              <p className="tiny">
                Randomized, method-blinded playback across all 11 vocalization categories (Genuine Dog Control,
                Method A, Method B, and Method D). Generation methods are hidden until after you submit your rating.
              </p>
            </div>
            <span className={`badge ${blindProtocol?.human_listening_evaluation_status === "PASS" ? "ok" : "warn"}`}>
              Human Listening Status: {blindProtocol?.human_listening_evaluation_status || "PENDING"} (
              {blindProtocol?.unique_reviewers_count ?? 0} / 3 reviewers)
            </span>
          </div>

          {blindProtocol?.samples?.length > 0 && (
            <div className="grid-2" style={{ gap: 14, marginTop: 10 }}>
              <div>
                <div className="field">
                  <label>Select Blind Sample ({blindProtocol.samples.length} randomized clips)</label>
                  <select
                    value={selectedBlindSample?.sample_id || ""}
                    onChange={(e) => {
                      const found = blindProtocol.samples.find((s: any) => s.sample_id === e.target.value);
                      setSelectedBlindSample(found || null);
                      setBlindRevealed(null);
                    }}
                  >
                    {blindProtocol.samples.map((s: any) => (
                      <option key={s.sample_id} value={s.sample_id}>
                        {s.blind_code} — Blinded Sample ({Number(s.duration_sec).toFixed(2)}s)
                      </option>
                    ))}
                  </select>
                </div>

                {selectedBlindSample && (
                  <AudioPlayer
                    mediaPath={selectedBlindSample.audio_url}
                    title={`Blind Sample ${selectedBlindSample.blind_code} (Method Hidden)`}
                    downloadFilename={`${selectedBlindSample.blind_code}.wav`}
                  />
                )}
              </div>

              <div>
                <div className="grid-2" style={{ gap: 8 }}>
                  <div className="field">
                    <label>Reviewer identifier</label>
                    <input
                      type="text"
                      value={blindReviewerId}
                      onChange={(e) => setBlindReviewerId(e.target.value)}
                      placeholder="reviewer_1"
                    />
                  </div>
                  <div className="field">
                    <label>Sounds like a genuine dog?</label>
                    <select value={blindIsDog ? "yes" : "no"} onChange={(e) => setBlindIsDog(e.target.value === "yes")}>
                      <option value="yes">Yes — Sounds like a genuine dog</option>
                      <option value="no">No — Sounds synthetic or unnatural</option>
                    </select>
                  </div>
                </div>

                <div className="grid-3" style={{ gap: 8 }}>
                  <div className="field">
                    <label>Perceived category</label>
                    <select value={blindPerceivedCat} onChange={(e) => setBlindPerceivedCat(e.target.value)}>
                      {(blindProtocol.supported_categories || []).map((c: string) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>Naturalness (1–5)</label>
                    <select value={blindNaturalness} onChange={(e) => setBlindNaturalness(Number(e.target.value))}>
                      <option value={5}>5 — Indistinguishable from real dog</option>
                      <option value={4}>4 — Natural canine vocalization</option>
                      <option value={3}>3 — Acceptable</option>
                      <option value={2}>2 — Noticeably processed</option>
                      <option value={1}>1 — Artificial / poor</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Artifact freedom (1–5)</label>
                    <select value={blindArtifactScore} onChange={(e) => setBlindArtifactScore(Number(e.target.value))}>
                      <option value={5}>5 — Clean (no clicks/metallic artifacts)</option>
                      <option value={4}>4 — Minor room noise only</option>
                      <option value={3}>3 — Mild phase/stretch coloration</option>
                      <option value={2}>2 — Audible metallic/buzz artifacts</option>
                      <option value={1}>1 — Severe crackle / distortion</option>
                    </select>
                  </div>
                </div>

                <div className="row" style={{ gap: 8, marginTop: 8 }}>
                  <input
                    type="text"
                    placeholder="Optional blind evaluation notes…"
                    value={blindNotes}
                    onChange={(e) => setBlindNotes(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="btn accent"
                    disabled={blindSubmitting || !selectedBlindSample}
                    onClick={submitBlindEvaluation}
                  >
                    {blindSubmitting ? "Recording…" : "Submit Blind Rating & Reveal"}
                  </button>
                </div>

                {blindRevealed?.revealed_ground_truth && (
                  <div className="callout" style={{ marginTop: 10 }}>
                    <strong>Ground Truth Revealed for {blindRevealed.blind_code}:</strong>{" "}
                    <span className="badge ok">{blindRevealed.revealed_ground_truth.output_classification}</span> ·
                    Intended Category: <code>{blindRevealed.revealed_ground_truth.intended_category}</code> (
                    {blindRevealed.revealed_ground_truth.category_matched ? "Matched your label" : "Different from your label"})
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Reference Audio Library Inspector, Label Editor & Uploader */}
      {showRefBrowser && (
        <div className="card" style={{ marginBottom: 16, borderColor: "var(--accent)" }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <h2>Genuine Dog Audio Reference Library</h2>
              <p className="tiny">
                {refLibrary?.total_inspected ?? 0} source files inspected ·{" "}
                <strong>{refLibrary?.total_accepted_canine_references ?? 0} validated canine reference clips</strong> ·{" "}
                {refLibrary?.total_rejected ?? 0} non-canine/duplicate clips excluded. Original files are preserved unchanged.
              </p>
            </div>
            <div className="row" style={{ gap: 6 }}>
              <select
                value={uploadRefCat}
                onChange={(e) => setUploadRefCat(e.target.value)}
                style={{ width: "auto", padding: "5px 10px", fontSize: "0.78rem" }}
                aria-label="Category for uploaded reference"
              >
                <option value="">Auto-detect category on upload</option>
                {REFERENCE_CATEGORIES.filter((c) => c !== "ALL").map((c) => (
                  <option key={c} value={c}>
                    Confirm as {c}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn ghost"
                disabled={uploadingRef}
                onClick={() => refUploadInputRef.current?.click()}
                style={{ padding: "6px 12px", fontSize: "0.8rem" }}
              >
                {uploadingRef ? "Ingesting reference…" : "+ Upload Dog Reference Audio"}
              </button>
              <input
                ref={refUploadInputRef}
                type="file"
                hidden
                accept="audio/*,.wav,.mp3,.mpeg,.m4a,.ogg,.webm,.flac"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUploadReferenceFile(f);
                  e.target.value = "";
                }}
              />
            </div>
          </div>

          {/* Category Filter Pills */}
          <div className="row" style={{ gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
            {REFERENCE_CATEGORIES.map((cat) => {
              const count =
                cat === "ALL"
                  ? refLibrary?.total_accepted_canine_references
                  : refLibrary?.category_counts?.[cat] ?? 0;
              return (
                <button
                  key={cat}
                  type="button"
                  className={`btn ${refCategoryFilter === cat ? "accent" : "ghost"}`}
                  style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                  onClick={() => setRefCategoryFilter(cat)}
                >
                  {cat} {count !== undefined ? `(${count})` : ""}
                </button>
              );
            })}
          </div>

          <div className="grid-2" style={{ gap: 14 }}>
            <div style={{ maxHeight: 340, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 12 }}>
              <table className="table" style={{ margin: 0 }}>
                <thead>
                  <tr>
                    <th>Reference Clip</th>
                    <th>Suggested</th>
                    <th>Confirmed</th>
                    <th>Dur / F0</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(refLibrary?.assets || []).slice(0, 60).map((a: any) => (
                    <tr
                      key={a.asset_id}
                      onClick={() => {
                        setInspectedRef(a);
                        setEditConfirmedCat(a.confirmed_category || "");
                        setEditRefNotes(a.notes || "");
                      }}
                      style={
                        inspectedRef?.asset_id === a.asset_id
                          ? { background: "#fbf4ea" }
                          : selectedRefAssetId === a.asset_id
                            ? { background: "#eef7f1" }
                            : undefined
                      }
                    >
                      <td style={{ fontSize: "0.78rem" }}>
                        <strong>{String(a.original_filename).slice(0, 34)}</strong>
                        <div className="tiny">{a.provenance}</div>
                      </td>
                      <td>
                        <span className="badge">{a.suggested_category}</span>
                      </td>
                      <td>
                        {a.confirmed_category ? (
                          <span className="badge ok">{a.confirmed_category}</span>
                        ) : (
                          <span className="tiny">Unconfirmed</span>
                        )}
                      </td>
                      <td className="tiny">
                        {a.duration_sec}s · {a.f0_mean_hz ? `${Math.round(a.f0_mean_hz)} Hz` : `${Math.round(a.dominant_freq_hz || 0)} Hz`}
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`btn ${selectedRefAssetId === a.asset_id ? "accent" : "ghost"}`}
                          style={{ padding: "3px 8px", fontSize: "0.72rem" }}
                          onClick={(ev) => {
                            ev.stopPropagation();
                            setSelectedRefAssetId(selectedRefAssetId === a.asset_id ? "" : a.asset_id);
                          }}
                        >
                          {selectedRefAssetId === a.asset_id ? "Pinned" : "Pin Ref"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              {!inspectedRef && (
                <div className="empty">
                  Click any reference recording on the left to preview its genuine dog audio, inspect its bioacoustic
                  profile, or review/correct its vocalization category label.
                </div>
              )}
              {inspectedRef && (
                <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 12, background: "#fbf8f3" }}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <strong>{inspectedRef.original_filename}</strong>
                    <span className="badge ok">{inspectedRef.effective_category}</span>
                  </div>
                  <div className="tiny" style={{ marginTop: 4 }}>
                    Asset ID: <code>{inspectedRef.asset_id.slice(0, 12)}…</code> · SHA-256:{" "}
                    <code>{String(inspectedRef.sha256 || "").slice(0, 14)}…</code> · {inspectedRef.sample_rate} Hz ·{" "}
                    {inspectedRef.duration_sec}s · RMS {inspectedRef.rms_energy} · HNR {inspectedRef.hnr_db ?? "—"} dB
                  </div>

                  <AudioPlayer
                    mediaPath={inspectedRef.audio_url}
                    title={`Reference Preview — ${inspectedRef.original_filename}`}
                    downloadFilename={`ref-${inspectedRef.effective_category}-${inspectedRef.asset_id.slice(0, 8)}.wav`}
                  />

                  <SpectrogramViewer
                    spectrogramDataPath={inspectedRef.spectrogram_data_url}
                    spectrogramImagePath={inspectedRef.spectrogram_url}
                    waveformPath={inspectedRef.waveform_url}
                    title={`Reference STFT Spectrogram — ${inspectedRef.effective_category}`}
                    compact
                  />

                  {/* User Label Review & Correction (private uploads only; shared library labels are read-only) */}
                  {!inspectedRef.owner_user_id ? (
                    <div className="tiny" style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
                      Shared library label: <code>{inspectedRef.effective_category}</code> (
                      {inspectedRef.label_verification === "verified_by_named_reviewer"
                        ? "verified by a named reviewer"
                        : "not independently verified"}
                      ). Shared references are read-only; upload your own recording to review its label.
                    </div>
                  ) : (
                  <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
                    <div className="tiny" style={{ marginBottom: 6 }}>
                      <strong>Review / Correct Vocalization Category</strong> (Suggested:{" "}
                      <code>{inspectedRef.suggested_category}</code> — {inspectedRef.category_rationale || "acoustic match"})
                    </div>
                    <div className="row" style={{ gap: 8 }}>
                      <select
                        value={editConfirmedCat}
                        onChange={(e) => setEditConfirmedCat(e.target.value)}
                        style={{ width: "auto", padding: "5px 10px", fontSize: "0.78rem" }}
                        aria-label="Confirmed vocalization category"
                      >
                        <option value="">Use auto-suggested ({inspectedRef.suggested_category})</option>
                        {REFERENCE_CATEGORIES.filter((c) => c !== "ALL").map((c) => (
                          <option key={c} value={c}>
                            Confirm: {c}
                          </option>
                        ))}
                      </select>
                      <input
                        type="text"
                        placeholder="Reviewer notes…"
                        value={editRefNotes}
                        onChange={(e) => setEditRefNotes(e.target.value)}
                        style={{ flex: 1, padding: "5px 10px", fontSize: "0.78rem" }}
                      />
                      <button
                        type="button"
                        className="btn accent"
                        disabled={savingAnnotation}
                        onClick={saveReferenceAnnotation}
                        style={{ padding: "5px 12px", fontSize: "0.78rem" }}
                      >
                        {savingAnnotation ? "Saving…" : "Save Label"}
                      </button>
                    </div>
                  </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 1: Human Input, Generation Method & Parameter Controls */}
      <div className="card">
        <h2>1. Human input, vocalization category &amp; generation engine</h2>
        <form onSubmit={(e) => onGenerate(e)} noValidate>
          <div className="field">
            <label>Quick command presets</label>
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              {QUICK_COMMANDS.map((q) => (
                <button
                  key={q.label}
                  type="button"
                  className="btn ghost"
                  style={{ padding: "5px 11px", fontSize: "0.78rem" }}
                  onClick={() => {
                    setText(q.text);
                    setErr("");
                  }}
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label>What do you want to communicate?</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Enter a command such as 'come here', 'stay', 'good dog', 'easy', 'let's play', 'howl', or 'growl'…"
              maxLength={500}
            />
            <div className="tiny" style={{ textAlign: "right", marginTop: 4 }}>
              {text.length} / 500 characters
            </div>
          </div>

          <div className="grid-2">
            <div className="field">
              <label>Audio generation method (Engine B architecture)</label>
              <select
                value={generationMethod}
                onChange={(e) => setGenerationMethod(e.target.value)}
                data-testid="generation-method-select"
              >
                {GENERATION_METHODS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
              <div className="tiny" style={{ marginTop: 4 }}>
                <span className="badge ok" style={{ marginRight: 6 }}>
                  {activeMethodInfo.badge}
                </span>
                {activeMethodInfo.desc}
              </div>
            </div>

            <div className="field">
              <label>Vocalization category / profile (optional override)</label>
              <select value={family} onChange={(e) => setFamily(e.target.value)}>
                <option value="">Auto-select from detected command intent</option>
                {FAMILIES.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
              {selectedRefAssetId && (
                <div className="tiny" style={{ marginTop: 4, color: "var(--accent)" }}>
                  Pinned Reference Asset ID: <code>{selectedRefAssetId.slice(0, 12)}…</code>{" "}
                  <button
                    type="button"
                    className="btn ghost"
                    style={{ padding: "2px 6px", fontSize: "0.7rem", marginLeft: 6 }}
                    onClick={() => setSelectedRefAssetId("")}
                  >
                    Clear pin
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="grid-3">
            <div className="field">
              <label>Dog profile (optional context)</label>
              <select value={dogId} onChange={(e) => setDogId(e.target.value)}>
                <option value="">None</option>
                {dogs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Intensity / Peak scaling (0.15–1.0, optional)</label>
              <input
                type="number"
                min={0.15}
                max={1.0}
                step={0.05}
                placeholder="Auto (natural reference level)"
                value={intensity}
                onChange={(e) => setIntensity(e.target.value)}
              />
            </div>
            <div className="field">
              <label>Target duration sec (0.08–6.0, optional)</label>
              <input
                type="number"
                min={0.08}
                max={6.0}
                step={0.1}
                placeholder="Auto from reference clip"
                value={durationSec}
                onChange={(e) => setDurationSec(e.target.value)}
              />
            </div>
          </div>

          {(generationMethod === "reference_variation" || generationMethod === "generative_model") && (
            <div className="grid-3" style={{ marginTop: 4 }}>
              <div className="field">
                <label>Pitch shift semitones (-2.0 to +2.0)</label>
                <input
                  type="number"
                  min={-2.0}
                  max={2.0}
                  step={0.1}
                  placeholder="Auto bounded variation"
                  value={pitchShiftSt}
                  onChange={(e) => setPitchShiftSt(e.target.value)}
                />
              </div>
              <div className="field">
                <label>Time stretch rate (0.85 to 1.18)</label>
                <input
                  type="number"
                  min={0.85}
                  max={1.18}
                  step={0.02}
                  placeholder="Auto bounded rate"
                  value={timeStretchRate}
                  onChange={(e) => setTimeStretchRate(e.target.value)}
                />
              </div>
              <div className="field">
                <label>Target F0 pitch Hz (60–2000, optional)</label>
                <input
                  type="number"
                  min={60}
                  max={2000}
                  step={10}
                  placeholder="Auto from reference"
                  value={pitchHz}
                  onChange={(e) => setPitchHz(e.target.value)}
                />
              </div>
            </div>
          )}

          {generationMethod === "experimental_dsp" && (
            <div className="field">
              <label>Base F0 pitch Hz (60–2000, optional)</label>
              <input
                type="number"
                min={60}
                max={2000}
                step={10}
                placeholder="Auto from profile"
                value={pitchHz}
                onChange={(e) => setPitchHz(e.target.value)}
              />
            </div>
          )}

          <div className="row">
            <button className="btn accent" type="submit" disabled={busy}>
              {busy
                ? "Selecting reference & validating WAV…"
                : generationMethod === "reference_direct"
                  ? "Generate from Real Dog Reference"
                  : generationMethod === "reference_variation"
                    ? "Generate Controlled Reference Variation"
                    : "Generate Canine Vocalization"}
            </button>
            <button
              className="btn ghost"
              type="button"
              disabled={busy}
              onClick={() => onGenerate(undefined, undefined, variationIndex + 1)}
            >
              Regenerate Variation (#{variationIndex + 1})
            </button>
            <button className="btn ghost" type="button" onClick={onPreviewIntent} disabled={previewBusy || busy}>
              {previewBusy ? "Analyzing…" : "Inspect intent & parameters"}
            </button>
            <button className="btn ghost" type="button" onClick={listen} disabled={busy}>
              {listening ? "Listening…" : "Use voice input"}
            </button>
          </div>
        </form>

        {err && (
          <div className="error" style={{ marginTop: 12 }}>
            {err}
          </div>
        )}
      </div>

      {/* Ambiguous Intent Clarification */}
      {intent?.needs_clarification && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <h2>Clarification required — ambiguous or incomplete intent</h2>
          <p>{intent.reason}</p>
          <p className="tiny">
            Engine B does not guess when multiple command cues conflict. Select the intended category below to generate:
          </p>
          <div className="row" style={{ marginTop: 10 }}>
            {(intent.candidates || []).map((c: string) => (
              <button
                key={c}
                className="btn accent"
                type="button"
                disabled={busy}
                onClick={() => onGenerate(undefined, c)}
              >
                Use intent: {c.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 2: Deterministic Intent & Reference Selection Inspection */}
      {intent && !intent.needs_clarification && (
        <div className="card">
          <h2>2. Intent analysis, reference selection &amp; acoustic parameters</h2>
          <div className="grid-2" style={{ gap: 12 }}>
            <div>
              <table className="table">
                <tbody>
                  <tr>
                    <th>Original input</th>
                    <td>{intent.original_input || intent.text || "—"}</td>
                  </tr>
                  <tr>
                    <th>Normalized input</th>
                    <td>
                      <code>{intent.normalized_input || "—"}</code>
                    </td>
                  </tr>
                  <tr>
                    <th>Detected intent</th>
                    <td>
                      <span className="badge">{intent.detected_intent || intent.intent}</span>{" "}
                      <span className="tiny">({Math.round((intent.confidence || 0) * 100)}% rule confidence)</span>
                    </td>
                  </tr>
                  <tr>
                    <th>Target vocalization category</th>
                    <td>
                      <span className="badge ok">
                        {intent.reference_category || intent.selected_synthesis_profile?.toUpperCase() || "BARK"}
                      </span>{" "}
                      <span className="tiny">
                        (profile: <code>{intent.selected_synthesis_profile || intent.mapping?.vocalization_target}</code>)
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <th>Generation method</th>
                    <td>
                      <span className="badge exp">
                        {generated?.output_classification ||
                          intent.generation_method ||
                          generationMethod}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {synthParams && (
              <div>
                <table className="table">
                  <tbody>
                    <tr>
                      <th>Sample rate / Duration</th>
                      <td>
                        {synthParams.sr} Hz · {Number(synthParams.duration || 0).toFixed(2)}s
                      </td>
                    </tr>
                    <tr>
                      <th>Primary reference clip</th>
                      <td>
                        {primaryRef ? (
                          <>
                            <strong>{primaryRef.original_filename}</strong>{" "}
                            <span className="badge ok">{primaryRef.effective_category}</span>
                          </>
                        ) : (
                          "Synthetic DSP template (no reference audio)"
                        )}
                      </td>
                    </tr>
                    <tr>
                      <th>Transformation mode</th>
                      <td>
                        <code>{synthParams.transformation_parameters?.mode || synthParams.generation_method || "—"}</code>
                        {synthParams.transformation_parameters?.pitch_shift_semitones !== undefined && (
                          <span className="tiny">
                            {" "}
                            (Δpitch {synthParams.transformation_parameters.pitch_shift_semitones} st · stretch{" "}
                            {synthParams.transformation_parameters.time_stretch_rate}×)
                          </span>
                        )}
                      </td>
                    </tr>
                    <tr>
                      <th>Measured F0 / Dominant freq</th>
                      <td>{synthParams.f0_base_hz ?? synthParams.f0} Hz</td>
                    </tr>
                    <tr>
                      <th>Vocal-tract formants</th>
                      <td>{(synthParams.formants_hz || synthParams.formants || []).join(" Hz, ")} Hz</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <p className="tiny" style={{ marginTop: 8 }}>
            {intent.disclaimer}
          </p>
        </div>
      )}

      {/* Step 3: Validated Output + Side-by-Side Reference vs Generated Comparison */}
      {generated && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <h2>3. Validated canine vocalization output &amp; reference comparison</h2>
            <div className="row" style={{ gap: 6 }}>
              <span
                className={`badge ${
                  generated.is_reference_recording
                    ? "ok"
                    : generated.is_modified_recording
                      ? "warn"
                      : "exp"
                }`}
                data-testid="output-classification-badge"
              >
                {generated.output_classification ||
                  (generated.synthetic
                    ? "Experimental DSP Output (Synthetic)"
                    : "Original Reference Audio (Retrieval)")}
              </span>
              <span className="badge">category: {generated.requested_category || generated.vocalization_target}</span>
              <span className="badge ok">WAV verified</span>
              <button
                type="button"
                className="btn ghost"
                disabled={busy}
                style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                onClick={() => onGenerate(undefined, generated.intent, variationIndex + 1)}
              >
                Regenerate Variation
              </button>
            </div>
          </div>

          <p className="callout" style={{ marginTop: 10 }}>
            <strong>Provenance &amp; Scientific Notice:</strong>{" "}
            {generated.notes?.disclaimer ||
              "Audio generated for canine acoustic communication research. No claim is made that a dog will comprehend human intent."}
          </p>

          {genWarnings.length > 0 && (
            <div
              className="error"
              style={{
                marginTop: 10,
                background: "#fff8eb",
                borderColor: "#e4c99e",
                color: "#6b2b12",
              }}
            >
              {genWarnings.map((w, idx) => (
                <div key={idx}>{w}</div>
              ))}
            </div>
          )}

          {valInfo && (
            <div className="row" style={{ marginTop: 10, gap: 8, flexWrap: "wrap" }}>
              <span className="badge">
                {valInfo.sample_rate} Hz · {valInfo.channels} ch · {valInfo.subtype || "PCM_16"}
              </span>
              <span className="badge">
                {valInfo.sample_count} samples ({valInfo.duration_sec}s)
              </span>
              <span className="badge">
                RMS {valInfo.rms} · Peak {valInfo.peak}
              </span>
              <span className="badge">Size {(valInfo.file_size_bytes / 1024).toFixed(1)} KB</span>
              {valInfo.sha256 && (
                <span className="badge" title={valInfo.sha256}>
                  SHA-256 {String(valInfo.sha256).slice(0, 12)}…
                </span>
              )}
            </div>
          )}

          {/* Side-by-Side Original Reference vs Generated/Transformed Audio & Spectrograms */}
          {primaryRef ? (
            <div style={{ marginTop: 14 }}>
              <h3>Side-by-Side Comparison: Original Reference Recording vs. Generated / Transformed Output</h3>
              <div className="grid-2" style={{ gap: 14, marginTop: 8 }}>
                <div
                  style={{
                    border: "1px solid var(--line)",
                    borderRadius: 14,
                    padding: 12,
                    background: "#f8fbf9",
                  }}
                >
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <strong>Source Reference Recording (Authentic Dog)</strong>
                    <span className="badge ok">{primaryRef.effective_category}</span>
                  </div>
                  <div className="tiny" style={{ marginTop: 4 }}>
                    File: <code>{primaryRef.original_filename}</code> · Provenance: {primaryRef.provenance} ·{" "}
                    {primaryRef.duration_sec}s
                  </div>
                  <AudioPlayer
                    mediaPath={primaryRef.audio_url}
                    title={`Original Reference — ${primaryRef.original_filename}`}
                    downloadFilename={`reference-${primaryRef.effective_category}-${primaryRef.asset_id.slice(0, 8)}.wav`}
                  />
                  <SpectrogramViewer
                    spectrogramDataPath={primaryRef.spectrogram_data_url}
                    spectrogramImagePath={primaryRef.spectrogram_url}
                    waveformPath={primaryRef.waveform_url}
                    title={`Original Reference Waveform & STFT (${primaryRef.effective_category})`}
                    compact
                  />
                </div>

                <div
                  style={{
                    border: "1px solid var(--line)",
                    borderRadius: 14,
                    padding: 12,
                    background: "#fdfaf5",
                  }}
                >
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <strong>Engine B Output ({generated.output_classification})</strong>
                    <span className="badge exp">{generated.generation_method}</span>
                  </div>
                  <div className="tiny" style={{ marginTop: 4 }}>
                    Command: &ldquo;{generated.source_text}&rdquo; · Mode:{" "}
                    <code>{generated.transformation_parameters?.mode || generated.generation_method}</code> ·{" "}
                    {valInfo?.duration_sec}s
                  </div>
                  <AudioPlayer
                    mediaPath={`/api/communicate/${generated.id}/audio`}
                    title={`Generated ${generated.requested_category || generated.vocalization_target} (${generated.output_classification})`}
                    downloadFilename={`caninesense-${generated.vocalization_target}-${generated.id.slice(0, 8)}.wav`}
                  />
                  <SpectrogramViewer
                    spectrogramDataPath={`/api/communicate/${generated.id}/spectrogram-data`}
                    spectrogramImagePath={`/api/communicate/${generated.id}/media/spectrogram`}
                    waveformPath={`/api/communicate/${generated.id}/media/waveform`}
                    title={`Output Waveform & STFT (${generated.output_classification})`}
                    compact
                  />
                </div>
              </div>
            </div>
          ) : (
            <>
              <AudioPlayer
                mediaPath={`/api/communicate/${generated.id}/audio`}
                title={`Generated ${generated.vocalization_target}-like sound (${generated.source_text})`}
                downloadFilename={`caninesense-${generated.vocalization_target}-${generated.id.slice(0, 8)}.wav`}
              />
              <SpectrogramViewer
                spectrogramDataPath={`/api/communicate/${generated.id}/spectrogram-data`}
                spectrogramImagePath={`/api/communicate/${generated.id}/media/spectrogram`}
                waveformPath={`/api/communicate/${generated.id}/media/waveform`}
                title={`Synthesized ${generated.vocalization_target}-like signal — Waveform & STFT Spectrogram`}
              />
            </>
          )}

          {/* Objective Acoustic Comparison Metrics */}
          {acousticComp && (
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                <strong>Objective Bioacoustic Comparison (Output vs. Source Reference)</strong>
                <div className="row" style={{ gap: 6 }}>
                  <span className="badge ok">
                    Spectral Envelope Similarity: {(Number(acousticComp.spectral_envelope_similarity || 0) * 100).toFixed(1)}%
                  </span>
                  <span className="badge ok">
                    MFCC Timbre Similarity: {(Number(acousticComp.mfcc_timbre_similarity || 0) * 100).toFixed(1)}%
                  </span>
                  <span
                    className={`badge ${
                      acousticComp.unnatural_crackle_or_transient_detected ? "warn" : "ok"
                    }`}
                  >
                    {acousticComp.unnatural_crackle_or_transient_detected
                      ? "Elevated transients detected"
                      : "No breaking-stick / crackle artifacts"}
                  </span>
                </div>
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>Acoustic Metric</th>
                    <th>Original Reference</th>
                    <th>Engine B Output</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Duration (s)</td>
                    <td>{acousticComp.reference_metrics?.duration_sec}s</td>
                    <td>{acousticComp.generated_metrics?.duration_sec}s</td>
                    <td>{acousticComp.duration_delta_sec}s</td>
                  </tr>
                  <tr>
                    <td>RMS Energy / Peak</td>
                    <td>
                      {acousticComp.reference_metrics?.rms_energy} / {acousticComp.reference_metrics?.peak_amplitude}
                    </td>
                    <td>
                      {acousticComp.generated_metrics?.rms_energy} / {acousticComp.generated_metrics?.peak_amplitude}
                    </td>
                    <td>{acousticComp.rms_delta}</td>
                  </tr>
                  <tr>
                    <td>Mean F0 / Dominant Frequency (Hz)</td>
                    <td>
                      {acousticComp.reference_metrics?.f0_mean_hz ?? "Unvoiced"} (dom{" "}
                      {acousticComp.reference_metrics?.dominant_freq_hz} Hz)
                    </td>
                    <td>
                      {acousticComp.generated_metrics?.f0_mean_hz ?? "Unvoiced"} (dom{" "}
                      {acousticComp.generated_metrics?.dominant_freq_hz} Hz)
                    </td>
                    <td>—</td>
                  </tr>
                  <tr>
                    <td>Spectral Centroid (Hz)</td>
                    <td>{acousticComp.reference_metrics?.spectral_centroid_hz} Hz</td>
                    <td>{acousticComp.generated_metrics?.spectral_centroid_hz} Hz</td>
                    <td>{acousticComp.centroid_delta_hz} Hz</td>
                  </tr>
                  <tr>
                    <td>Harmonic-to-Noise Ratio (HNR dB)</td>
                    <td>{acousticComp.reference_metrics?.hnr_db} dB</td>
                    <td>{acousticComp.generated_metrics?.hnr_db} dB</td>
                    <td>{acousticComp.hnr_delta_db} dB</td>
                  </tr>
                </tbody>
              </table>
              <p className="tiny">{acousticComp.disclaimer}</p>
            </div>
          )}

          {/* User Listening Evaluation Feedback */}
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div className="row" style={{ gap: 8 }}>
                <strong style={{ fontSize: "0.86rem" }}>Listening Quality Check:</strong>
                <label className="tiny" style={{ display: "inline-flex", alignItems: "center", gap: 4, margin: 0 }}>
                  <input
                    type="checkbox"
                    checked={fbNatural}
                    onChange={(e) => setFbNatural(e.target.checked)}
                    style={{ width: "auto" }}
                  />
                  Sounds like a genuine dog vocalization
                </label>
                <select
                  value={fbRating}
                  onChange={(e) => setFbRating(Number(e.target.value))}
                  style={{ width: "auto", padding: "4px 8px", fontSize: "0.78rem" }}
                  aria-label="Listening quality rating"
                >
                  <option value={5}>5 / 5 — Authentic canine sound</option>
                  <option value={4}>4 / 5 — Natural with minor variation</option>
                  <option value={3}>3 / 5 — Acceptable</option>
                  <option value={2}>2 / 5 — Audible artifacts</option>
                  <option value={1}>1 / 5 — Artificial / poor</option>
                </select>
                <input
                  type="text"
                  placeholder="Optional listening notes…"
                  value={fbNotes}
                  onChange={(e) => setFbNotes(e.target.value)}
                  style={{ width: 200, padding: "4px 8px", fontSize: "0.78rem" }}
                />
                <button
                  type="button"
                  className="btn ghost"
                  disabled={fbSaving}
                  onClick={submitListeningFeedback}
                  style={{ padding: "4px 10px", fontSize: "0.78rem" }}
                >
                  {fbSaving ? "Saving…" : "Record Feedback"}
                </button>
              </div>
              {fbSavedMsg && <span className="badge ok">{fbSavedMsg}</span>}
            </div>
          </div>

          {/* Step 4: Optional Dog-Response Recording & Review */}
          <div
            style={{
              marginTop: 20,
              paddingTop: 16,
              borderTop: "1px solid var(--line)",
            }}
          >
            <h2>4. Optional dog-response recording &amp; independent Engine A analysis</h2>
            <p className="tiny">
              Record or upload your dog&apos;s acoustic response after playing the generated sound. You can review the
              recorded audio before submitting it to Engine A. A response is not proof that the dog understood the
              sound.
            </p>

            <div className="row" style={{ marginTop: 10 }}>
              <button
                className={`btn ${recordingResp ? "danger" : "accent"}`}
                type="button"
                onClick={recordingResp ? stopResponseRec : startResponseRec}
                disabled={submittingResp}
              >
                {recordingResp
                  ? `Stop recording (${respSeconds}s / 10s)`
                  : "Record dog response (microphone)"}
              </button>

              <button
                className="btn ghost"
                type="button"
                onClick={() => respFileInputRef.current?.click()}
                disabled={recordingResp || submittingResp}
              >
                Upload response audio file
              </button>
              <input
                ref={respFileInputRef}
                type="file"
                hidden
                accept="audio/*,.wav,.mp3,.mpeg,.m4a,.ogg,.webm,.flac"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setReviewFile(f);
                  e.target.value = "";
                }}
              />

              <button
                className="btn ghost"
                type="button"
                onClick={() => setReviewFile(buildTestResponseWav())}
                disabled={recordingResp || submittingResp}
              >
                Load synthetic response test fixture
              </button>
            </div>

            {pendingRespFile && pendingRespBlobUrl && (
              <div
                style={{
                  marginTop: 14,
                  padding: 14,
                  borderRadius: 14,
                  border: "1px solid var(--accent)",
                  background: "#fffaf1",
                }}
              >
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong>Review captured response before submitting to Engine A</strong>
                  <span className="badge">
                    {pendingRespFile.name} ({(pendingRespFile.size / 1024).toFixed(1)} KB)
                  </span>
                </div>

                <AudioPlayer
                  blobUrl={pendingRespBlobUrl}
                  title="Captured response preview"
                  downloadFilename={pendingRespFile.name}
                />

                <div className="row" style={{ marginTop: 12 }}>
                  <button
                    className="btn accent"
                    type="button"
                    onClick={submitReviewedResponse}
                    disabled={submittingResp}
                  >
                    {submittingResp ? "Submitting & analyzing with Engine A…" : "Submit response to Engine A"}
                  </button>
                  <button
                    className="btn ghost"
                    type="button"
                    onClick={() => setReviewFile(null)}
                    disabled={submittingResp}
                  >
                    Discard / Re-record
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 5: Response Analysis & Side-by-Side Spectrogram Comparison */}
      {activeResponse?.recording && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>5. Recorded dog response — independent Engine A analysis</h2>
            <div className="row">
              {responses.length > 1 && (
                <select
                  value={activeResponse.id}
                  onChange={(e) => {
                    const found = responses.find((r) => r.id === e.target.value);
                    if (found) setActiveResponse(found);
                  }}
                  style={{ width: "auto", padding: "4px 10px", fontSize: "0.78rem" }}
                >
                  {responses.map((r, i) => (
                    <option key={r.id} value={r.id}>
                      Response #{responses.length - i} ({r.recording?.analysis?.vocalization || "unknown"})
                    </option>
                  ))}
                </select>
              )}
              <span className="badge">Response ID {activeResponse.id?.slice(0, 8)}</span>
            </div>
          </div>

          <p className="callout" style={{ marginTop: 10 }}>
            {activeResponse.interpretation_warning}
          </p>

          <AudioPlayer
            mediaPath={`/api/recordings/${activeResponse.recording.id}/media/processed`}
            title={`Recorded dog response (${activeResponse.recording.original_filename})`}
            downloadFilename={`dog-response-${activeResponse.recording.id.slice(0, 8)}.wav`}
          />

          {generated && (
            <div style={{ marginTop: 16 }}>
              <h2>Side-by-side spectrogram comparison (Engine B Output vs. Recorded Dog Response)</h2>
              <div className="grid-2">
                <div>
                  <SpectrogramViewer
                    spectrogramDataPath={`/api/communicate/${generated.id}/spectrogram-data`}
                    spectrogramImagePath={`/api/communicate/${generated.id}/media/spectrogram`}
                    title={`Engine B Output (${generated.vocalization_target})`}
                    compact
                  />
                </div>
                <div>
                  <SpectrogramViewer
                    spectrogramDataPath={`/api/recordings/${activeResponse.recording.id}/spectrogram-data`}
                    spectrogramImagePath={`/api/recordings/${activeResponse.recording.id}/media/spectrogram`}
                    waveformPath={`/api/recordings/${activeResponse.recording.id}/media/waveform`}
                    title={`Engine A Recorded Response (${activeResponse.recording.analysis?.vocalization || "unknown"})`}
                    compact
                  />
                </div>
              </div>
            </div>
          )}

          {activeResponse.recording.analysis && (
            <ResultView
              analysis={activeResponse.recording.analysis}
              quality={activeResponse.recording.quality}
            />
          )}
        </div>
      )}

      {/* Recent Generated Sounds History */}
      <div className="card" style={{ marginTop: 16 }}>
        <h2>Recent generated sounds</h2>
        {!history.length && (
          <div className="empty">No generated sounds yet. Submit a command above to generate audio.</div>
        )}
        {history.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Prompt</th>
                <th>Intent</th>
                <th>Category</th>
                <th>Method / Classification</th>
                <th>Duration</th>
                <th>Responses</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 12).map((g) => (
                <tr
                  key={g.id}
                  onClick={() => selectGenerated(g)}
                  style={generated?.id === g.id ? { background: "#fbf4ea" } : undefined}
                >
                  <td>{g.created_at ? new Date(g.created_at).toLocaleString() : "—"}</td>
                  <td>{g.source_text}</td>
                  <td>{g.intent}</td>
                  <td>
                    <span className="badge">{g.requested_category || g.vocalization_target}</span>
                  </td>
                  <td>
                    <span className={`badge ${g.synthetic ? "exp" : "ok"}`}>
                      {g.output_classification || g.generation_method}
                    </span>
                  </td>
                  <td>{g.params?.duration ? `${Number(g.params.duration).toFixed(2)}s` : "—"}</td>
                  <td>
                    <span className="badge">{g.response_count ?? 0}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
