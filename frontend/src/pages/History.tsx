import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import AudioPlayer from "../components/AudioPlayer";
import ResultView from "../components/ResultView";
import SpectrogramViewer from "../components/SpectrogramViewer";

export default function History() {
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<any[]>([]);
  const [open, setOpen] = useState<any>(null);
  const [filterClass, setFilterClass] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    const targetId = searchParams.get("id");
    const qParam = searchParams.get("q");
    if (qParam !== null) {
      setSearchQuery(qParam);
    }
    api<any[]>("/api/recordings")
      .then((list) => {
        setRows(list);
        if (targetId) {
          const found = list.find((r) => r.id === targetId);
          if (found) setOpen(found);
        } else if (list[0]) {
          setOpen(list[0]);
        }
      })
      .catch((e) => setErr(e.message));
  }, [searchParams]);

  async function remove(id: string) {
    if (!confirm("Delete this recording and its analysis?")) return;
    await api(`/api/recordings/${id}`, { method: "DELETE" });
    setRows((r) => {
      const next = r.filter((x) => x.id !== id);
      if (open?.id === id) {
        setOpen(next[0] || null);
      }
      return next;
    });
  }

  const filteredRows = rows.filter((r) => {
    if (filterClass && (r.analysis?.vocalization || "unknown") !== filterClass) return false;
    if (
      searchQuery &&
      !String(r.original_filename || "")
        .toLowerCase()
        .includes(searchQuery.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="kicker">Archive</div>
          <h1>Recording history</h1>
          <p>Only your recordings. Select any row to inspect its audio playback, waveform, interactive STFT spectrogram, and full analysis.</p>
        </div>
      </div>
      {err && <div className="error">{err}</div>}

      <div className="card">
        {rows.length > 0 && (
          <div className="grid-2" style={{ marginBottom: 14 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Search filename</label>
              <input
                type="text"
                placeholder="Filter by filename…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Filter by acoustic class</label>
              <select value={filterClass} onChange={(e) => setFilterClass(e.target.value)}>
                <option value="">All classes ({rows.length})</option>
                {["bark", "growl", "whine", "howl", "yip", "grunt", "other", "unknown"].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {!filteredRows.length && <div className="empty">No matching recordings found.</div>}
        {!!filteredRows.length && (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>File</th>
                <th>Source</th>
                <th>Duration</th>
                <th>Class</th>
                <th>Score / Status</th>
                <th>Quality</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => setOpen(r)}
                  style={open?.id === r.id ? { background: "#fbf4ea" } : undefined}
                >
                  <td>{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                  <td>{r.original_filename}</td>
                  <td>
                    <span className="tiny">{r.source || "upload"}</span>
                  </td>
                  <td>{r.duration_sec ? `${Number(r.duration_sec).toFixed(2)}s` : "—"}</td>
                  <td>
                    <span className="badge">{r.analysis?.vocalization ?? "—"}</span>
                  </td>
                  <td>
                    {r.analysis?.abstained
                      ? "abstained"
                      : r.analysis?.confidence != null
                        ? `${Math.round(r.analysis.confidence * 100)}%`
                        : "—"}
                  </td>
                  <td>{r.quality_status}</td>
                  <td>
                    <button
                      className="btn ghost"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        remove(r.id);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {open && (
        <div className="card media" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Signal &amp; STFT Spectrogram — {open.original_filename}</h2>
            <div className="row">
              <span className="badge">{open.sample_rate || 22050} Hz · {open.channels || 1} ch</span>
              {open.sha256 && (
                <span className="badge" title={open.sha256}>
                  SHA-256 {String(open.sha256).slice(0, 12)}…
                </span>
              )}
            </div>
          </div>

          <AudioPlayer
            mediaPath={`/api/recordings/${open.id}/media/processed`}
            title={`Playback — ${open.original_filename}`}
            downloadFilename={`recording-${open.id.slice(0, 8)}.wav`}
          />

          <SpectrogramViewer
            spectrogramDataPath={`/api/recordings/${open.id}/spectrogram-data`}
            spectrogramImagePath={`/api/recordings/${open.id}/media/spectrogram`}
            waveformPath={`/api/recordings/${open.id}/media/waveform`}
            title={`Time–Frequency STFT Spectrogram — ${open.original_filename}`}
          />
        </div>
      )}

      {open?.analysis && <ResultView analysis={open.analysis} quality={open.quality} />}
    </div>
  );
}
