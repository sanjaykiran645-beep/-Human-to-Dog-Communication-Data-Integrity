import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import Logo from "../Logo";
import { api, getToken, setSession } from "../api";
import type { User } from "../api";

export default function Login() {
  const nav = useNavigate();
  const loc = useLocation();
  const [mode, setMode] = useState<"login" | "register">(loc.pathname === "/register" ? "register" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [audioNoticeAgreed, setAudioNoticeAgreed] = useState(false);
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
      if (!termsAgreed || !ageConfirmed || !audioNoticeAgreed) {
        setErr("Please review and agree to all required legal and privacy consents to create your account.");
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
      nav("/app");
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
            <Link to="/" className="row" style={{ textDecoration: "none", color: "inherit", gap: 12 }}>
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

              <div className="auth-feature-list">
                <div className="auth-feature-item">
                  <span className="auth-feature-dot">01</span>
                  <div>
                    <strong style={{ fontSize: "0.9rem" }}>Engine A · Acoustic Classifier</strong>
                    <div className="tiny">YIN fundamental frequency, spectral centroid, HNR &amp; abstention gate</div>
                  </div>
                </div>
                <div className="auth-feature-item">
                  <span className="auth-feature-dot">02</span>
                  <div>
                    <strong style={{ fontSize: "0.9rem" }}>Engine B · Reference-Driven Vocalizer</strong>
                    <div className="tiny">Authentic dog vocalization retrieval &amp; bounded acoustic variation</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="tiny" style={{ color: "var(--ink-2)" }}>
            Private per-user storage · Strict ownership isolation · No third-party audio sharing
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
          <p>
            {mode === "login"
              ? "Sign in to access your private recordings, dog profiles, and acoustic analyses."
              : "Register your private CanineSense AI workspace. All recordings and analyses stay under your account."}
          </p>

          {err && <div className="error">{err}</div>}

          <form onSubmit={onSubmit}>
            {mode === "register" && (
              <div className="field">
                <label htmlFor="auth-name">Name</label>
                <input
                  id="auth-name"
                  placeholder="Your name or lab handle"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="field">
              <label htmlFor="auth-email">Email address</label>
              <input
                id="auth-email"
                type="email"
                placeholder="researcher@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="field">
              <label htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </div>

            {mode === "register" && (
              <>
                <div className="field">
                  <label htmlFor="auth-confirm-password">Confirm password (optional check)</label>
                  <input
                    id="auth-confirm-password"
                    type="password"
                    placeholder="Re-enter password to verify"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 10, margin: "14px 0" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <input
                      id="auth-terms"
                      type="checkbox"
                      checked={termsAgreed}
                      onChange={(e) => setTermsAgreed(e.target.checked)}
                      required
                      style={{ marginTop: 3, accentColor: "var(--accent)" }}
                    />
                    <label htmlFor="auth-terms" className="tiny" style={{ color: "var(--ink-2)", lineHeight: 1.4 }}>
                      I agree to the <Link to="/terms-of-service" target="_blank">Terms of Service</Link> and{" "}
                      <Link to="/privacy-policy" target="_blank">Privacy Policy</Link>.
                    </label>
                  </div>

                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <input
                      id="auth-age"
                      type="checkbox"
                      checked={ageConfirmed}
                      onChange={(e) => setAgeConfirmed(e.target.checked)}
                      required
                      style={{ marginTop: 3, accentColor: "var(--accent)" }}
                    />
                    <label htmlFor="auth-age" className="tiny" style={{ color: "var(--ink-2)", lineHeight: 1.4 }}>
                      I confirm that I am at least 18 years old (or have parental/guardian consent).
                    </label>
                  </div>

                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <input
                      id="auth-audio-notice"
                      type="checkbox"
                      checked={audioNoticeAgreed}
                      onChange={(e) => setAudioNoticeAgreed(e.target.checked)}
                      required
                      style={{ marginTop: 3, accentColor: "var(--accent)" }}
                    />
                    <label htmlFor="auth-audio-notice" className="tiny" style={{ color: "var(--ink-2)", lineHeight: 1.4 }}>
                      I understand that uploaded audio is stored privately on this server and can be deleted at any time.
                    </label>
                  </div>
                </div>
              </>
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
        </div>
      </div>
    </div>
  );
}
