import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import Logo from "../Logo";
import { api, getToken, setSession, startDemoSession } from "../api";
import type { User } from "../api";

export default function Login() {
  const nav = useNavigate();
  const loc = useLocation();
  const [mode, setMode] = useState<"login" | "register">(
    loc.pathname === "/register" ? "register" : "login"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setMode(loc.pathname === "/register" ? "register" : "login");
    setErr("");
  }, [loc.pathname]);

  if (getToken()) return <Navigate to="/app" replace />;

  function switchMode(next: "login" | "register") {
    setMode(next);
    setErr("");
    nav(next === "register" ? "/register" : "/login");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    if (mode === "register") {
      if (confirmPassword && confirmPassword !== password) {
        setErr("Passwords do not match. Please confirm your password.");
        return;
      }
    }
    setBusy(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body = mode === "login" ? { email, password } : { email, password, name };
      const data = await api<{ access_token: string; user: User }>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSession(data.access_token, data.user);
      setSuccessMsg(
        mode === "login" ? "Signed in successfully!" : "Account created successfully!"
      );
      setTimeout(() => nav("/app"), 200);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-split-shell">
        {/* Left Bioacoustic Visual Showcase Panel */}
        <div className="auth-showcase">
          <div>
            <Link
              to="/"
              className="row"
              style={{ textDecoration: "none", color: "inherit", gap: 12 }}
              aria-label="CanineSense AI Home"
            >
              <Logo size={42} />
              <div>
                <div className="kicker">CanineSense AI</div>
                <div className="brand-name" style={{ fontSize: "1.2rem" }}>
                  Acoustic Lab
                </div>
              </div>
            </Link>

            <div className="auth-showcase-hero">
              <div className="kicker">Bioacoustic Analysis &amp; Reference Synthesis</div>
              <h2>Scientific rigor for canine vocalization intelligence.</h2>
              <p>
                Inspect Short-Time Fourier Transform (STFT) spectrograms, classify canine vocalizations with
                conservative abstention safeguards, and explore 128 genuine dog reference recordings.
              </p>

              {/* Warm Minimalist Acoustic Illustration Card */}
              <div className="auth-wave-graphic" aria-hidden="true">
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                  <span className="tiny" style={{ fontWeight: 600, color: "var(--ink)" }}>
                    STFT HARMONIC PROFILE · 22.05 kHz
                  </span>
                  <span className="badge ok">128 Validated Clips</span>
                </div>
                <svg viewBox="0 0 360 76" width="100%" height="76" fill="none">
                  <path
                    d="M4 38 C 28 38, 36 10, 54 38 C 72 66, 84 14, 104 38 C 124 62, 136 8, 156 38 C 176 68, 192 18, 212 38 C 232 58, 248 12, 268 38 C 288 64, 308 24, 356 38"
                    stroke="#762F3D"
                    strokeWidth="2.4"
                    strokeLinecap="round"
                  />
                  <path
                    d="M4 38 C 32 38, 44 24, 66 38 C 88 52, 102 22, 126 38 C 150 54, 168 20, 194 38 C 220 56, 240 26, 268 38 C 296 50, 320 30, 356 38"
                    stroke="#A66B55"
                    strokeWidth="1.6"
                    strokeDasharray="4 4"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
            </div>

            <div className="tiny" style={{ color: "var(--ink-2)" }}>
              Private per-user storage · Strict ownership isolation · No third-party audio sharing
            </div>
          </div>
        </div>

        {/* Right Authentication Form Panel */}
        <div className="auth-card">
          <div className="auth-mode-tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={`auth-mode-tab ${mode === "login" ? "active" : ""}`}
              onClick={() => switchMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              className={`auth-mode-tab ${mode === "register" ? "active" : ""}`}
              onClick={() => switchMode("register")}
            >
              Create account
            </button>
          </div>

          <h1>{mode === "login" ? "Welcome back" : "Create your lab"}</h1>
          <p>{mode === "login"
            ? "Sign in to access your private recordings, dog profiles, and acoustic analyses."
            : "Register your private CanineSense AI workspace. All recordings and analyses stay under your account."}
          </p>

          {err && (
            <div className="error" role="alert">
              {err}
            </div>
          )}
          {successMsg && (
            <div
              className="badge ok"
              role="status"
              style={{ padding: "10px 14px", marginBottom: 14, display: "block" }}
            >
              {successMsg}
            </div>
          )}

          <form onSubmit={onSubmit}>
            {mode === "register" && (
              <div className="field">
                <label htmlFor="auth-name">Name</label>
                <input
                  id="auth-name"
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                />
              </div>
            )}
            <div className="field">
              <label htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>
            {mode === "register" && (
              <div className="field">
                <label htmlFor="auth-confirm-password">Confirm Password</label>
                <input
                  id="auth-confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
            )}
            <button className="btn accent wide" type="submit" disabled={busy} style={{ marginTop: 6 }}>
              {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="tiny" style={{ marginTop: 18, textAlign: "center" }}>
            {mode === "login" ? "No account yet? " : "Already registered? "}
            <button
              className="btn ghost"
              type="button"
              style={{ padding: "5px 12px", marginLeft: 4 }}
              onClick={() => switchMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Create one" : "Sign in"}
            </button>
          </p>

          <div
            style={{
              marginTop: 22,
              paddingTop: 16,
              borderTop: "1px dashed var(--line-strong)",
              textAlign: "center",
            }}
          >
            <div className="kicker" style={{ fontSize: "0.72rem", marginBottom: 6 }}>
              Interface Demonstration (No Backend Required)
            </div>
            <p className="tiny" style={{ color: "var(--muted)", margin: "0 0 10px", lineHeight: 1.4 }}>
              Preview the bioacoustic lab interface in isolated offline mode using browser simulation. Real accounts and ML inference require a live FastAPI server.
            </p>
            <button
              className="btn ghost wide"
              type="button"
              style={{ fontSize: "0.85rem", borderColor: "var(--taupe)" }}
              onClick={() => {
                startDemoSession();
                nav("/app");
              }}
            >
              Explore Offline Demo Tour (Simulated Preview)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
