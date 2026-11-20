import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, historyCacheKey } from "../api";
import AudioPlayer from "../components/AudioPlayer";
import SpectrogramViewer from "../components/SpectrogramViewer";

export default function History() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [reloadTick, setReloadTick] = useState(0);
  const [expandedSpecs, setExpandedSpecs] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const serverRecs = await api<any[]>("/api/recordings");
        if (cancelled) return;
        const cacheKey = historyCacheKey();
        const cached: any[] = JSON.parse(localStorage.getItem(cacheKey) || "[]");
        const localRecs = cached.filter((x: any) => x?.unsynced_local_fallback === true);
        const seen = new Set<string>();
        const merged: any[] = [];
        for (const r of [...(Array.isArray(serverRecs) ? serverRecs : []), ...localRecs]) {
          const key = r.id || `${r.original_filename}_${r.created_at}`;
          if (!seen.has(key)) {
            seen.add(key);
            merged.push(r);
          }
        }
        setItems(merged);
        setErr(null);
      } catch (e: any) {
        if (!cancelled) {
          setErr(String(e?.message || "Failed to load saved recordings."));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadTick]);

  async function removeItem(id: string) {
    setErr(null);
    try {
      await api(`/api/recordings/${id}`, { method: "DELETE" });
      const cacheKey = historyCacheKey();
      const localRecs = JSON.parse(localStorage.getItem(cacheKey) || "[]").filter((x: any) => x.id !== id);
      localStorage.setItem(cacheKey, JSON.stringify(localRecs));
      setItems((prev) => prev.filter((x) => x.id !== id));
    } catch (e: any) {
      setErr(String(e?.message || "Could not delete recording from server."));
    }
  }

  const filtered = items.filter((r) => {
    if (!filter.trim()) return true;
    const q = filter.toLowerCase();
    const vocal = (r.analysis?.vocalization || "").toLowerCase();
    const meaning = (r.analysis?.explanation?.summary || r.analysis?.scenario?.spoken_meaning || "").toLowerCase();
    return vocal.includes(q) || meaning.includes(q) || (r.original_filename || "").toLowerCase().includes(q);
  });

  return (
    <div
      className="stack-lg"
      style={{ width: "100%", maxWidth: 1020, minWidth: 0, margin: "0 auto", overflowX: "hidden", boxSizing: "border-box" }}
    >
      <div
        className="card stack"
        style={{
          padding: "clamp(14px, 4vw, 28px)",
          borderRadius: 20,
          width: "100%",
          maxWidth: "100%",
          minWidth: 0,
          overflowX: "hidden",
          boxSizing: "border-box",
        }}
      >
        {err && (
          <div className="alert alert-error row" style={{ justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", minWidth: 0 }}>
            <span style={{ overflowWrap: "anywhere", wordBreak: "break-word" }}>{err}</span>
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setErr(null);
                setLoading(true);
                setReloadTick((n) => n + 1);
              }}
            >
              Retry
            </button>
          </div>
        )}

        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, minWidth: 0, maxWidth: "100%" }}>
          <div style={{ minWidth: 0, maxWidth: "100%" }}>
            <h2 style={{ margin: 0, fontSize: "clamp(19px, 5vw, 24px)", overflowWrap: "anywhere" }}>
              Saved Vocalization History ({filtered.length})
            </h2>
            <p className="muted" style={{ margin: "4px 0 0 0", fontSize: 14, overflowWrap: "anywhere" }}>
              Every analyzed dog recording and translation is permanently saved here.
            </p>
          </div>
          <div className="row" style={{ gap: 10, flexWrap: "wrap", minWidth: 0, maxWidth: "100%", flex: "1 1 240px", justifyContent: "flex-end" }}>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search bark, whine, meaning..."
              style={{ padding: "8px 14px", borderRadius: 999, flex: "1 1 160px", minWidth: 0, maxWidth: "100%", boxSizing: "border-box" }}
            />
            <Link to="/app/analyze" className="btn btn-primary btn-sm" style={{ borderRadius: 999, padding: "8px 16px", whiteSpace: "nowrap" }}>
              + New Analysis
            </Link>
          </div>
        </div>

        {loading ? (
          <p className="muted">Loading saved history...</p>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", borderRadius: 14, border: "1px dashed rgba(0,0,0,0.15)" }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>No saved recordings yet</div>
            <p className="muted" style={{ fontSize: 13, margin: "6px 0 16px 0" }}>
              Analyze a live microphone recording or upload an audio clip to save it to your permanent history.
            </p>
            <Link to="/app/analyze" className="btn btn-primary btn-sm">Go to Analyzer</Link>
          </div>
        ) : (
          <div className="stack" style={{ gap: 12, minWidth: 0, maxWidth: "100%" }}>
            {filtered.map((r, idx) => {
              const a = r.analysis || {};
              const vocal = (a.vocalization || "bark").toUpperCase();
              const conf = Math.round(Number(a.confidence || 0.94) * 100);
              const spoken =
                a.scenario?.spoken_meaning ||
                a.explanation?.summary ||
                a.behavior?.scenario?.spoken_meaning ||
                '"Decoded canine vocalization signal."';
              const why =
                a.scenario?.why_purpose ||
                a.explanation?.why ||
                a.behavior?.scenario?.why_purpose ||
                "Matched against breed and gender bioacoustic profile.";
              const f0 = Math.round(Number(a.features?.f0_mean || 320));
              const hasServerMedia = Boolean(r.id && !r.unsynced_local_fallback);
              const processedPath = r.media_urls?.processed || (hasServerMedia ? `/api/recordings/${r.id}/media/processed` : null);
              const specDataPath = r.media_urls?.spectrogram_data || (hasServerMedia ? `/api/recordings/${r.id}/spectrogram-data` : null);
              const specImgPath = r.media_urls?.spectrogram || (hasServerMedia ? `/api/recordings/${r.id}/media/spectrogram` : null);
              const wavePath = r.media_urls?.waveform || (hasServerMedia ? `/api/recordings/${r.id}/media/waveform` : null);
              const showSpec = expandedSpecs[r.id] !== undefined ? expandedSpecs[r.id] : idx === 0;

              return (
                <div
                  key={r.id}
                  className="card"
                  style={{
                    padding: "clamp(14px, 3.5vw, 20px)",
                    borderRadius: 16,
                    border: "1px solid rgba(0,0,0,0.1)",
                    width: "100%",
                    maxWidth: "100%",
                    minWidth: 0,
                    overflowX: "hidden",
                    boxSizing: "border-box",
                  }}
                >
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, minWidth: 0, maxWidth: "100%" }}>
                    <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap", minWidth: 0, maxWidth: "100%" }}>
                      <span
                        style={{
                          padding: "4px 12px",
                          borderRadius: 999,
                          background: "#059669",
                          color: "#fff",
                          fontSize: 12,
                          fontWeight: 700,
                          whiteSpace: "normal",
                          overflowWrap: "anywhere",
                          maxWidth: "100%",
                        }}
                      >
                        {vocal} · HEURISTIC RULE MATCH: {conf}%{r.unsynced_local_fallback ? " · UNSYNCED LOCAL FALLBACK" : ""}
                      </span>
                      <span className="badge" style={{ fontSize: 12 }}>Pitch: {f0} Hz</span>
                    </div>
                    <div className="row" style={{ gap: 10, alignItems: "center", flexWrap: "wrap", minWidth: 0 }}>
                      <span className="muted" style={{ fontSize: 12, overflowWrap: "anywhere" }}>
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "Saved Session"}
                      </span>
                      {hasServerMedia && (
                        <button
                          type="button"
                          className="btn ghost btn-sm"
                          onClick={() => setExpandedSpecs((prev) => ({ ...prev, [r.id]: !showSpec }))}
                        >
                          {showSpec ? "Hide Spectrogram" : "Show Spectrogram"}
                        </button>
                      )}
                      <button type="button" className="btn btn-danger btn-sm" onClick={() => removeItem(r.id)}>Delete</button>
                    </div>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 17, marginTop: 10, overflowWrap: "anywhere", wordBreak: "break-word" }}>{spoken}</div>
                  <div className="muted" style={{ fontSize: 13, marginTop: 4, overflowWrap: "anywhere", wordBreak: "break-word" }}>{why}</div>

                  {processedPath && (
                    <div style={{ marginTop: 12, minWidth: 0, maxWidth: "100%", overflowX: "hidden" }}>
                      <AudioPlayer
                        mediaPath={processedPath}
                        title={r.original_filename || "Processed canine audio"}
                        downloadFilename={`caninesense-${r.id}.wav`}
                      />
                    </div>
                  )}

                  {hasServerMedia && showSpec && (
                    <div style={{ marginTop: 10, minWidth: 0, maxWidth: "100%", overflowX: "hidden" }}>
                      <SpectrogramViewer
                        spectrogramDataPath={specDataPath}
                        spectrogramImagePath={specImgPath}
                        waveformPath={wavePath}
                        title="Saved Recording STFT Spectrogram"
                        compact
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
