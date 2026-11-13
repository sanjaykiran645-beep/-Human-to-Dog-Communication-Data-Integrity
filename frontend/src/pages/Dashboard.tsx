import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Dog, getUser, Recording } from "../api";

export default function Dashboard() {
  const user = getUser();
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    localStorage.removeItem("cs_demo_mode");
    Promise.all([
      api<Dog[]>("/api/dogs").catch(() => []),
      api<Recording[]>("/api/recordings").catch(() => []),
    ]).then(([d, r]) => {
      setDogs(d || []);
      setRecordings(r || []);
      setLoading(false);
    });
  }, []);

  const activeDog = dogs[0] || null;
  const recentRecs = recordings.slice(0, 4);

  return (
    <div className="stack-lg" style={{ maxWidth: 1080, margin: "0 auto" }}>
      {/* Sleek Minimalist Hero Banner */}
      <div
        className="card"
        style={{
          background: "linear-gradient(135deg, #1e1b18 0%, #3a2321 100%)",
          color: "#ffffff",
          border: "none",
          padding: "32px 36px",
          borderRadius: 20,
          boxShadow: "0 16px 40px rgba(30, 27, 24, 0.14)",
        }}
      >
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 24 }}>
          <div style={{ maxWidth: 580 }}>
            <span
              style={{
                display: "inline-block",
                padding: "4px 12px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.12)",
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                marginBottom: 12,
              }}
            >
              CanineSense AI Studio
            </span>
            <h1 style={{ fontSize: 32, fontWeight: 700, margin: "0 0 10px 0", color: "#fff" }}>
              Welcome back, {user?.name || "Trainer"}
            </h1>
            <p style={{ margin: "0 0 24px 0", fontSize: 15, color: "rgba(255,255,255,0.82)", lineHeight: 1.6 }}>
              Understand what your dog is expressing and generate breed-calibrated vocal cues in one click.
            </p>
            <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
              <Link
                to="/app/analyze"
                className="btn"
                style={{
                  background: "#ffffff",
                  color: "#1e1b18",
                  fontWeight: 600,
                  padding: "10px 22px",
                  borderRadius: 999,
                }}
              >
                Analyze Dog Audio
              </Link>
              <Link
                to="/app/communicate"
                className="btn"
                style={{
                  background: "rgba(255,255,255,0.14)",
                  color: "#ffffff",
                  border: "1px solid rgba(255,255,255,0.28)",
                  fontWeight: 600,
                  padding: "10px 22px",
                  borderRadius: 999,
                }}
              >
                Speak to Dog ?
              </Link>
            </div>
          </div>

          {/* Minimalist Active Dog Pill */}
          <div
            style={{
              background: "rgba(255,255,255,0.08)",
              backdropFilter: "blur(10px)",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: 16,
              padding: "20px 24px",
              minWidth: 240,
            }}
          >
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,255,255,0.65)" }}>
              Active Companion
            </div>
            {activeDog ? (
              <>
                <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6, color: "#fff" }}>{activeDog.name}</div>
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", marginTop: 2 }}>
                  {activeDog.breed || "Mixed Breed"} ? Breed Intelligence Active
                </div>
                <Link
                  to="/app/dogs"
                  style={{ display: "inline-block", marginTop: 12, fontSize: 12, color: "#f5d0c5", textDecoration: "none", fontWeight: 600 }}
                >
                  Manage profiles ?
                </Link>
              </>
            ) : (
              <>
                <div style={{ fontSize: 16, fontWeight: 600, marginTop: 6, color: "#fff" }}>No dog profile yet</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)", marginTop: 4 }}>
                  Add your dog?s breed to auto-calibrate pitch & behavior.
                </div>
                <Link
                  to="/app/dogs"
                  style={{ display: "inline-block", marginTop: 12, fontSize: 12, color: "#f5d0c5", textDecoration: "none", fontWeight: 600 }}
                >
                  + Add your dog ?
                </Link>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 3 Clean Action Cards */}
      <div className="grid-3" style={{ gap: 18 }}>
        <Link to="/app/analyze" className="card" style={{ textDecoration: "none", color: "inherit", padding: 24, borderRadius: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7c2d12", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Dog ? Human
          </div>
          <h3 style={{ fontSize: 20, margin: "8px 0" }}>Analyze Vocalization</h3>
          <p className="muted" style={{ fontSize: 14, margin: "0 0 16px 0", lineHeight: 1.5 }}>
            Record or upload a bark, whine, or howl to detect emotional state and acoustic patterns.
          </p>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#7c2d12" }}>Open Analyzer ?</span>
        </Link>

        <Link to="/app/communicate" className="card" style={{ textDecoration: "none", color: "inherit", padding: 24, borderRadius: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7c2d12", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Human ? Dog
          </div>
          <h3 style={{ fontSize: 20, margin: "8px 0" }}>Translate & Speak</h3>
          <p className="muted" style={{ fontSize: 14, margin: "0 0 16px 0", lineHeight: 1.5 }}>
            Type or speak any phrase to generate a calm, playful, or attention cue tuned to your dog?s breed.
          </p>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#7c2d12" }}>Open Translator ?</span>
        </Link>

        <Link to="/app/dogs" className="card" style={{ textDecoration: "none", color: "inherit", padding: 24, borderRadius: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#7c2d12", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Smart Calibration
          </div>
          <h3 style={{ fontSize: 20, margin: "8px 0" }}>Dog Profiles ({dogs.length})</h3>
          <p className="muted" style={{ fontSize: 14, margin: "0 0 16px 0", lineHeight: 1.5 }}>
            Enter your dog?s name and breed. Our backend automatically syncs breed intelligence and vocal range.
          </p>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#7c2d12" }}>Manage Dogs ?</span>
        </Link>
      </div>

      {/* Clean Minimalist Recent Activity */}
      <div className="card" style={{ padding: 24, borderRadius: 16 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 18 }}>Recent Sessions</h3>
            <p className="muted" style={{ margin: "4px 0 0 0", fontSize: 13 }}>
              Your latest analyzed recordings
            </p>
          </div>
          <Link to="/app/history" className="btn btn-secondary btn-sm">
            View all ({recordings.length})
          </Link>
        </div>

        {loading ? (
          <div className="muted" style={{ padding: "20px 0", fontSize: 14 }}>Loading workspace...</div>
        ) : recentRecs.length === 0 ? (
          <div
            style={{
              padding: "28px 20px",
              textAlign: "center",
              background: "rgba(0,0,0,0.02)",
              borderRadius: 12,
              border: "1px dashed rgba(0,0,0,0.12)",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>No recordings analyzed yet</div>
            <p className="muted" style={{ fontSize: 13, margin: "0 0 14px 0" }}>
              Record a 3-second clip of your dog or upload an audio file to see instant results.
            </p>
            <Link to="/app/analyze" className="btn btn-primary btn-sm">
              Start First Analysis
            </Link>
          </div>
        ) : (
          <div className="stack" style={{ gap: 10 }}>
            {recentRecs.map((r) => (
              <div
                key={r.id}
                className="row"
                style={{
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "12px 16px",
                  borderRadius: 12,
                  background: "rgba(0,0,0,0.025)",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>
                    {r.analysis?.vocalization ? r.analysis.vocalization.toUpperCase() : r.original_filename}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {r.analysis?.behavior?.context?.replace(/_/g, " ") || "Processed audio"} ? {(r.duration_sec || 0).toFixed(1)}s
                  </div>
                </div>
                <span className="badge">
                  {r.analysis ? `${Math.round((r.analysis.confidence || 0) * 100)}% match` : "Saved"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
