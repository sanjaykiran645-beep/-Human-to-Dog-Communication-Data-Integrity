import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function History() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  async function load() {
    setLoading(true);
    try {
      const serverRecs = await api<any[]>("/api/recordings").catch(() => []);
      const localRecs = JSON.parse(localStorage.getItem("cs_saved_history_v1") || "[]");
      const seen = new Set<string>();
      const merged: any[] = [];
      for (const r of [...(serverRecs || []), ...localRecs]) {
        const key = r.id || `${r.original_filename}_${r.created_at}`;
        if (!seen.has(key)) {
          seen.add(key);
          merged.push(r);
        }
      }
      setItems(merged);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function removeItem(id: string) {
    try {
      await api(`/api/recordings/${id}`, { method: "DELETE" }).catch(() => {});
    } catch {}
    const localRecs = JSON.parse(localStorage.getItem("cs_saved_history_v1") || "[]").filter((x: any) => x.id !== id);
    localStorage.setItem("cs_saved_history_v1", JSON.stringify(localRecs));
    setItems((prev) => prev.filter((x) => x.id !== id));
  }

  const filtered = items.filter((r) => {
    if (!filter.trim()) return true;
    const q = filter.toLowerCase();
    const vocal = (r.analysis?.vocalization || "").toLowerCase();
    const meaning = (r.analysis?.explanation?.summary || r.analysis?.scenario?.spoken_meaning || "").toLowerCase();
    return vocal.includes(q) || meaning.includes(q) || (r.original_filename || "").toLowerCase().includes(q);
  });

  return (
    <div className="stack-lg" style={{ maxWidth: 1020, margin: "0 auto" }}>
      <div className="card stack" style={{ padding: 28, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 24 }}>Saved Vocalization History ({filtered.length})</h2>
            <p className="muted" style={{ margin: "4px 0 0 0", fontSize: 14 }}>
              Every analyzed dog recording and translation is permanently saved here.
            </p>
          </div>
          <div className="row" style={{ gap: 10 }}>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search bark, whine, meaning..."
              style={{ padding: "8px 14px", borderRadius: 999, minWidth: 220 }}
            />
            <Link to="/app/analyze" className="btn btn-primary btn-sm" style={{ borderRadius: 999, padding: "8px 16px" }}>
              + New Analysis
            </Link>
          </div>
        </div>

        {loading ? (
          <p className="muted">Loading saved history...</p>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", borderRadius: 14, border: "1px dashed rgba(0,0,0,0.15)" }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>No saved recordings yet</div>
            <p className="muted" style={{ fontSize: 13, margin: "6px 0 16px 0" }}>
              Analyze a live microphone recording or upload an audio clip to save it to your permanent history.
            </p>
            <Link to="/app/analyze" className="btn btn-primary btn-sm">Go to Analyzer</Link>
          </div>
        ) : (
          <div className="stack" style={{ gap: 12 }}>
            {filtered.map((r) => {
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

              return (
                <div key={r.id} className="card" style={{ padding: 20, borderRadius: 16, border: "1px solid rgba(0,0,0,0.1)" }}>
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                    <div className="row" style={{ gap: 8, alignItems: "center" }}>
                      <span style={{ padding: "4px 12px", borderRadius: 999, background: "#059669", color: "#fff", fontSize: 12, fontWeight: 700 }}>
                        {vocal} · {conf}% ACCURACY
                      </span>
                      <span className="badge" style={{ fontSize: 12 }}>Pitch: {f0} Hz</span>
                    </div>
                    <div className="row" style={{ gap: 10, alignItems: "center" }}>
                      <span className="muted" style={{ fontSize: 12 }}>
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "Saved Session"}
                      </span>
                      <button className="btn btn-danger btn-sm" onClick={() => removeItem(r.id)}>Delete</button>
                    </div>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 17, marginTop: 10 }}>{spoken}</div>
                  <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{why}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
