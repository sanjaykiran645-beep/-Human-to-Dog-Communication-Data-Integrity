import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Logo from "../Logo";

interface CookiePreferences {
  essential: boolean;
  functional: boolean;
  analytics: boolean;
  updatedAt: string;
}

export default function CookieSettings() {
  const [prefs, setPrefs] = useState<CookiePreferences>(() => {
    try {
      const saved = localStorage.getItem("cs_cookie_consent");
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {
      /* ignore */
    }
    return {
      essential: true,
      functional: true,
      analytics: false,
      updatedAt: new Date().toISOString(),
    };
  });

  const [savedStatus, setSavedStatus] = useState<string>("");

  useEffect(() => {
    if (savedStatus) {
      const timer = setTimeout(() => setSavedStatus(""), 4000);
      return () => clearTimeout(timer);
    }
  }, [savedStatus]);

  function save(newPrefs: CookiePreferences, msg = "Preferences saved successfully!") {
    setPrefs(newPrefs);
    try {
      localStorage.setItem("cs_cookie_consent", JSON.stringify(newPrefs));
    } catch {
      /* ignore */
    }
    setSavedStatus(msg);
  }

  function handleSaveCurrent() {
    save({
      ...prefs,
      essential: true,
      updatedAt: new Date().toISOString(),
    });
  }

  function handleAcceptAll() {
    save(
      {
        essential: true,
        functional: true,
        analytics: true,
        updatedAt: new Date().toISOString(),
      },
      "All preferences accepted and saved!"
    );
  }

  function handleRejectNonEssential() {
    save(
      {
        essential: true,
        functional: false,
        analytics: false,
        updatedAt: new Date().toISOString(),
      },
      "Optional storage disabled. Only strictly necessary storage active."
    );
  }

  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Cookie Settings</div>
          </div>
        </Link>
        <div className="row" style={{ gap: 12 }}>
          <Link to="/cookie-policy" className="btn ghost">
            View Cookie Policy
          </Link>
          <Link to="/" className="btn ghost">
            Back to Home
          </Link>
        </div>
      </header>

      <main style={{ maxWidth: 840, margin: "40px auto 60px", padding: "0 24px", width: "100%", flex: 1 }}>
        <article className="card" style={{ padding: "40px 36px", background: "var(--paper)" }}>
          <div className="kicker">Privacy Preferences</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.2rem", marginTop: 8, marginBottom: 8 }}>
            Cookie &amp; Storage Preferences
          </h1>
          <p style={{ color: "var(--muted)", marginBottom: 24 }}>
            Control how CanineSense AI uses cookies and browser storage on this device. You can adjust your choices
            at any time.
          </p>

          {savedStatus && (
            <div
              role="alert"
              style={{
                background: "rgba(61, 90, 76, 0.12)",
                color: "var(--forest-2)",
                padding: "12px 18px",
                borderRadius: "var(--radius-sm)",
                marginBottom: 24,
                fontWeight: 500,
                border: "1px solid var(--forest)",
              }}
            >
              ✓ {savedStatus}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 20, marginBottom: 32 }}>
            {/* Category 1: Essential */}
            <div
              style={{
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
                padding: "20px 24px",
                background: "var(--surface-soft)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem" }}>1. Strictly Necessary Storage (Required)</h3>
                  <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)", lineHeight: 1.5 }}>
                    Essential for secure authentication, account login sessions, and basic platform operation. Without
                    these, the acoustic lab cannot function.
                  </p>
                  <div className="tiny" style={{ marginTop: 8, color: "var(--muted)" }}>
                    Keys: <code>cs_token</code>, <code>cs_user</code>, <code>cs_cookie_consent</code>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                  <span className="badge ok" style={{ fontSize: "0.75rem" }}>Always Active</span>
                  <input
                    type="checkbox"
                    checked={true}
                    disabled
                    aria-label="Strictly Necessary Storage (Always Active)"
                    style={{ width: 18, height: 18, accentColor: "var(--forest)" }}
                  />
                </div>
              </div>
            </div>

            {/* Category 2: Functional */}
            <div
              style={{
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
                padding: "20px 24px",
                background: "var(--paper)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem" }}>2. Functional Preferences</h3>
                  <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)", lineHeight: 1.5 }}>
                    Remembers user interface settings, such as dismissed onboarding guides and audio player volume
                    levels, so you do not have to reset them every visit.
                  </p>
                  <div className="tiny" style={{ marginTop: 8, color: "var(--muted)" }}>
                    Keys: <code>cs_onboarding_done_*</code>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                  <input
                    id="pref-functional"
                    type="checkbox"
                    checked={prefs.functional}
                    onChange={(e) => setPrefs({ ...prefs, functional: e.target.checked })}
                    aria-label="Enable Functional Preferences"
                    style={{ width: 20, height: 20, accentColor: "var(--accent)", cursor: "pointer" }}
                  />
                </div>
              </div>
            </div>

            {/* Category 3: Analytics */}
            <div
              style={{
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
                padding: "20px 24px",
                background: "var(--paper)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem" }}>3. Research &amp; Diagnostic Telemetry (Opt-in)</h3>
                  <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)", lineHeight: 1.5 }}>
                    Anonymous system error telemetry to help researchers debug audio synthesis DSP pipelines. No personal
                    information or audio files are ever included.
                  </p>
                  <div className="tiny" style={{ marginTop: 8, color: "var(--muted)" }}>
                    Note: CanineSense AI currently uses zero third-party tracking scripts.
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                  <input
                    id="pref-analytics"
                    type="checkbox"
                    checked={prefs.analytics}
                    onChange={(e) => setPrefs({ ...prefs, analytics: e.target.checked })}
                    aria-label="Enable Research and Diagnostic Telemetry"
                    style={{ width: 20, height: 20, accentColor: "var(--accent)", cursor: "pointer" }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="row" style={{ gap: 12, flexWrap: "wrap", justifyContent: "flex-end" }}>
            <button type="button" className="btn ghost" onClick={handleRejectNonEssential}>
              Reject Non-Essential
            </button>
            <button type="button" className="btn ghost" onClick={handleSaveCurrent}>
              Save My Preferences
            </button>
            <button type="button" className="btn accent" onClick={handleAcceptAll}>
              Accept All
            </button>
          </div>
        </article>
      </main>

      <footer className="land-foot" style={{ maxWidth: 960, margin: "0 auto 30px", width: "100%", padding: "0 24px" }}>
        <span>&copy; {new Date().getFullYear()} CanineSense AI Bioacoustics</span>
        <div className="row" style={{ gap: 16 }}>
          <Link to="/privacy-policy">Privacy Policy</Link>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/refund-policy">Refund Policy</Link>
          <Link to="/contact">Contact</Link>
        </div>
      </footer>
    </div>
  );
}
