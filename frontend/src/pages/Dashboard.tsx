import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, getUser } from "../api";

type Summary = {
  recordings: number;
  dogs: number;
  generated: number;
  analyses: number;
  abstentions: number;
  most_frequent_vocalization: string | null;
  vocalization_counts: Record<string, number>;
  recent: Array<{
    analysis_id: string;
    recording_id: string;
    vocalization: string;
    confidence: number;
    abstained: boolean;
    filename: string | null;
    created_at: string | null;
  }>;
};

export default function Dashboard() {
  const user = getUser();
  const nav = useNavigate();
  const [data, setData] = useState<Summary | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Summary>("/api/analytics/summary")
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  const vocEntries = Object.entries(data?.vocalization_counts || {}).sort((a, b) => b[1] - a[1]);
  const totalVoc = vocEntries.reduce((acc, [, c]) => acc + c, 0) || 1;
  const resolvedCount = Math.max(0, (data?.analyses ?? 0) - (data?.abstentions ?? 0));

  return (
    <div className="dash-shell">
      {/* Premium Warm Minimalist Welcome Banner */}
      <section className="dash-welcome-banner">
        <div className="dash-welcome-copy">
          <div className="dash-status-pill">
            <span className="dash-pulse-dot" />
            CanineSense AI · Dual-Engine Bioacoustic Workspace
          </div>
          <h1 className="dash-hero-title">Hello{user?.name ? `, ${user.name}` : ""}</h1>
          <p className="dash-hero-sub">
            Welcome to your private canine bioacoustics laboratory. Analyze dog vocalizations with STFT spectrograms and
            abstention safeguards, or generate authentic reference-driven canine vocalizations.
          </p>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <Link to="/app/analyze" className="btn accent">
              Analyze audio
            </Link>
            <Link to="/app/communicate" className="btn ghost">
              Communicate Lab →
            </Link>
            <Link to="/app/history" className="btn ghost">
              Archive ({data?.recordings ?? 0})
            </Link>
            <a href="/api/download/apk" download="CanineSense_AI_v1.0.0.apk" className="btn ghost">
              Download Android APK
            </a>
          </div>
        </div>

        {/* Custom Canine Bioacoustic Visual Card */}
        <div className="dash-welcome-visual" aria-hidden="true">
          <div className="dash-visual-card">
            <div className="dash-visual-head">
              <span>ACOUSTIC SPECTRUM · 22.05 kHz</span>
              <span>REF LIBRARY v2.1</span>
            </div>
            <svg viewBox="0 0 280 72" width="100%" height="72" fill="none">
              <rect x="4" y="28" width="6" height="16" rx="3" fill="#A66B55" opacity="0.55" />
              <rect x="16" y="18" width="6" height="36" rx="3" fill="#762F3D" />
              <rect x="28" y="10" width="6" height="52" rx="3" fill="#762F3D" />
              <rect x="40" y="22" width="6" height="28" rx="3" fill="#A66B55" />
              <rect x="52" y="6" width="6" height="60" rx="3" fill="#382820" />
              <rect x="64" y="16" width="6" height="40" rx="3" fill="#762F3D" />
              <rect x="76" y="26" width="6" height="20" rx="3" fill="#A66B55" opacity="0.7" />
              <rect x="88" y="14" width="6" height="44" rx="3" fill="#762F3D" />
              <rect x="100" y="20" width="6" height="32" rx="3" fill="#A66B55" />
              <rect x="112" y="8" width="6" height="56" rx="3" fill="#382820" />
              <rect x="124" y="18" width="6" height="36" rx="3" fill="#762F3D" />
              <rect x="136" y="24" width="6" height="24" rx="3" fill="#A66B55" opacity="0.75" />
              <rect x="148" y="12" width="6" height="48" rx="3" fill="#762F3D" />
              <rect x="160" y="6" width="6" height="60" rx="3" fill="#382820" />
              <rect x="172" y="20" width="6" height="32" rx="3" fill="#A66B55" />
              <rect x="184" y="28" width="6" height="16" rx="3" fill="#A66B55" opacity="0.6" />
              <rect x="196" y="14" width="6" height="44" rx="3" fill="#762F3D" />
              <rect x="208" y="10" width="6" height="52" rx="3" fill="#762F3D" />
              <rect x="220" y="22" width="6" height="28" rx="3" fill="#A66B55" />
              <rect x="232" y="16" width="6" height="40" rx="3" fill="#382820" />
              <rect x="244" y="24" width="6" height="24" rx="3" fill="#762F3D" />
              <rect x="256" y="18" width="6" height="36" rx="3" fill="#A66B55" />
              <rect x="268" y="28" width="6" height="16" rx="3" fill="#A66B55" opacity="0.55" />
            </svg>
            <div className="dash-visual-head" style={{ marginTop: 6, marginBottom: 0 }}>
              <span>ENGINE A: CLASSIFIER</span>
              <span>ENGINE B: 128 CLIPS</span>
            </div>
          </div>
        </div>
      </section>

      {err && <div className="error">{err}</div>}
      {loading && <p className="tiny">Loading workspace summary…</p>}

      {/* 4 Key Metric Cards */}
      <section className="dash-bento-4" aria-label="Key corpus statistics">
        <div className="dash-metric-card stat">
          <div className="dash-metric-top">
            <span>SIGNAL CORPUS</span>
            <span className="dash-metric-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 12h3l2-6 4 12 3-8 2 2h4" />
              </svg>
            </span>
          </div>
          <div className="dash-metric-val num">{data?.recordings ?? "—"}</div>
          <div className="dash-metric-foot lbl">
            <span>Recordings</span>
            <span>{data?.dogs ?? 0} dog profiles</span>
          </div>
        </div>

        <div className="dash-metric-card stat">
          <div className="dash-metric-top">
            <span>DOMINANT CLASS</span>
            <span className="dash-metric-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 19V9M12 19V5M19 19v-7" />
              </svg>
            </span>
          </div>
          <div className="dash-metric-val num" style={{ textTransform: "capitalize" }}>
            {data?.most_frequent_vocalization ?? "—"}
          </div>
          <div className="dash-metric-foot lbl">
            <span>Most frequent class</span>
            <span>{resolvedCount} classified</span>
          </div>
        </div>

        <div className="dash-metric-card stat">
          <div className="dash-metric-top">
            <span>SAFETY GATE</span>
            <span className="dash-metric-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 3l8 4v5c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V7l8-4z" />
              </svg>
            </span>
          </div>
          <div className="dash-metric-val num">{data?.abstentions ?? "—"}</div>
          <div className="dash-metric-foot lbl">
            <span>Unknown / abstain</span>
            <span>Conservative guard</span>
          </div>
        </div>

        <div className="dash-metric-card stat">
          <div className="dash-metric-top">
            <span>ENGINE B OUTPUTS</span>
            <span className="dash-metric-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 8h8v8H4l-2 3V8h2zM14 9c1.5 1 1.5 5 0 6M17 7c2.5 2 2.5 8 0 10" />
              </svg>
            </span>
          </div>
          <div className="dash-metric-val num">{data?.generated ?? "—"}</div>
          <div className="dash-metric-foot lbl">
            <span>Generated vocalizations</span>
            <span>Ref Library v2.1</span>
          </div>
        </div>
      </section>

      {/* Quick Actions Row */}
      <section className="dash-quick-grid" aria-label="Quick actions">
        <Link to="/app/analyze" className="dash-quick-card">
          <span className="dash-quick-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <path d="M3 12h3l2-6 4 12 3-8 2 2h4" />
            </svg>
          </span>
          <div>
            <strong>Analyze Dog Audio</strong>
            <span>Upload or record WAV, MP3, M4A, OGG, WEBM, or FLAC</span>
          </div>
        </Link>

        <Link to="/app/communicate" className="dash-quick-card">
          <span className="dash-quick-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <path d="M4 8h8v8H4l-2 3V8h2zM14 9c1.5 1 1.5 5 0 6M17 7c2.5 2 2.5 8 0 10" />
            </svg>
          </span>
          <div>
            <strong>Reference Vocalizer</strong>
            <span>Generate from 128 real dog clips &amp; compare spectrograms</span>
          </div>
        </Link>

        <Link to="/app/dogs" className="dash-quick-card">
          <span className="dash-quick-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <path d="M4 11c2-5 6-6 8-6 2 0 3 1 5 1 2 0 3-2 3-2v6c0 5-3 9-8 9s-8-4-8-8z" />
            </svg>
          </span>
          <div>
            <strong>Dog Profiles ({data?.dogs ?? 0})</strong>
            <span>Configure breed &amp; weight for F0-size consistency notes</span>
          </div>
        </Link>

        <Link to="/app/analytics" className="dash-quick-card">
          <span className="dash-quick-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <path d="M5 19V9M12 19V5M19 19v-7" />
            </svg>
          </span>
          <div>
            <strong>Corpus &amp; Model Card</strong>
            <span>Inspect class distribution and model transparency notes</span>
          </div>
        </Link>
      </section>

      {/* Main Content Workspace: Recent Analyses & Vocalization Topology */}
      <div className="dash-workspace-grid">
        <div className="card" style={{ margin: 0 }}>
          <div className="dash-panel-head">
            <div>
              <div className="dash-tag">ENGINE A · RECENT ACTIVITY</div>
              <h2>Recent analyses</h2>
            </div>
            <Link to="/app/history" className="btn ghost" style={{ padding: "6px 14px", fontSize: "0.8rem" }}>
              Full history →
            </Link>
          </div>

          {!data?.recent?.length && (
            <div className="empty">No analyses yet. Start with a recording to populate your workspace.</div>
          )}

          {!!data?.recent?.length && (
            <div className="dash-stream-list">
              {data.recent.map((r) => {
                const pct = r.abstained ? 0 : Math.round(r.confidence * 100);
                return (
                  <div
                    key={r.analysis_id}
                    className="dash-stream-row"
                    onClick={() => nav(`/app/history?id=${r.recording_id}`)}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "0.92rem", color: "var(--ink)" }}>
                        {r.filename || "Acoustic capture"}
                      </div>
                      <div className="tiny">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                      </div>
                    </div>

                    <span className={`badge ${r.abstained ? "warn" : "ok"}`}>{r.vocalization}</span>

                    <div className="dash-conf-wrap">
                      <div className="dash-conf-bar">
                        <span
                          style={{
                            width: `${pct}%`,
                            background: r.abstained ? "var(--muted)" : "var(--accent)",
                          }}
                        />
                      </div>
                      <span className="tiny" style={{ minWidth: 58, textAlign: "right", fontWeight: 500 }}>
                        {r.abstained ? "abstained" : `${pct}%`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <p className="tiny" style={{ marginTop: 14, marginBottom: 0 }}>
            Click any recording above to open its audio player, waveform, interactive STFT spectrogram, and acoustic
            evidence in History.
          </p>
        </div>

        {/* Right Column: Vocalization Distribution & Active Engines */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ margin: 0 }}>
            <div className="dash-panel-head">
              <div>
                <div className="dash-tag">CORPUS BREAKDOWN</div>
                <h2>Vocalization distribution</h2>
              </div>
              <Link to="/app/analytics" className="tiny">
                Details →
              </Link>
            </div>

            {!vocEntries.length && (
              <div className="empty" style={{ padding: "18px 10px" }}>
                Class distribution will appear after your first acoustic analysis.
              </div>
            )}

            {vocEntries.map(([cls, count]) => {
              const pct = Math.round((count / totalVoc) * 100);
              return (
                <div key={cls} className="prob" style={{ margin: "10px 0" }}>
                  <span style={{ textTransform: "capitalize", fontWeight: 500, color: "var(--ink)" }}>{cls}</span>
                  <div className="bar">
                    <span style={{ width: `${pct}%` }} />
                  </div>
                  <span className="tiny" style={{ textAlign: "right" }}>
                    {count} ({pct}%)
                  </span>
                </div>
              );
            })}
          </div>

          <div className="card" style={{ margin: 0 }}>
            <div className="dash-panel-head">
              <div>
                <div className="dash-tag">ACTIVE SYSTEM MODULES</div>
                <h2>Bioacoustic engines</h2>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="dash-node-card">
                <div>
                  <strong style={{ fontSize: "0.9rem", color: "var(--ink)" }}>
                    Engine A · Bioacoustic Classifier
                  </strong>
                  <div className="tiny">YIN F0 · Spectral Centroid · HNR · Abstention Gate</div>
                </div>
                <Link to="/app/analyze" className="badge ok">
                  Open →
                </Link>
              </div>

              <div className="dash-node-card">
                <div>
                  <strong style={{ fontSize: "0.9rem", color: "var(--ink)" }}>
                    Engine B · Reference Vocalizer v2.1
                  </strong>
                  <div className="tiny">128 Validated Dog Clips · Retrieval &amp; Variation</div>
                </div>
                <Link to="/app/communicate" className="badge">
                  Open →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
