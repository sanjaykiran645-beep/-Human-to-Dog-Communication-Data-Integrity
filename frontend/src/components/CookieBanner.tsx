import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

export default function CookieBanner() {
  const [visible, setVisible] = useState<boolean>(false);

  useEffect(() => {
    try {
      const consent = localStorage.getItem("cs_cookie_consent");
      if (!consent) {
        setVisible(true);
      }
    } catch {
      setVisible(false);
    }
  }, []);

  function handleAcceptAll() {
    const prefs = {
      essential: true,
      functional: true,
      analytics: true,
      updatedAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem("cs_cookie_consent", JSON.stringify(prefs));
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  function handleRejectNonEssential() {
    const prefs = {
      essential: true,
      functional: false,
      analytics: false,
      updatedAt: new Date().toISOString(),
    };
    try {
      localStorage.setItem("cs_cookie_consent", JSON.stringify(prefs));
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <aside
      aria-label="Cookie and Privacy Consent"
      role="region"
      style={{
        position: "fixed",
        bottom: 20,
        left: 20,
        right: 20,
        maxWidth: 720,
        margin: "0 auto",
        zIndex: 9999,
        background: "var(--paper)",
        color: "var(--ink)",
        borderRadius: "var(--radius)",
        boxShadow: "var(--shadow-lg)",
        border: "1px solid var(--line-strong)",
        padding: "20px 24px",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: "1.2rem" }} aria-hidden="true">🍪</span>
            <strong style={{ fontSize: "1.05rem" }}>Privacy &amp; Browser Storage Notice</strong>
          </div>
          <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--ink-2)", lineHeight: 1.5 }}>
            CanineSense AI uses strictly necessary browser storage (<code>localStorage</code>) to maintain your secure
            login session. We use <strong>zero advertising cookies</strong> and zero third-party analytics trackers.
            Your canine audio recordings stay private on our server. Learn more in our{" "}
            <Link to="/cookie-policy" style={{ textDecoration: "underline" }}>Cookie Policy</Link> and{" "}
            <Link to="/privacy-policy" style={{ textDecoration: "underline" }}>Privacy Policy</Link>.
          </p>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <Link
            to="/cookie-settings"
            className="btn ghost"
            style={{ fontSize: "0.85rem", padding: "6px 14px" }}
            onClick={() => setVisible(false)}
          >
            Customize
          </Link>
          <button
            type="button"
            className="btn ghost"
            style={{ fontSize: "0.85rem", padding: "6px 14px" }}
            onClick={handleRejectNonEssential}
          >
            Reject Non-Essential
          </button>
          <button
            type="button"
            className="btn accent"
            style={{ fontSize: "0.85rem", padding: "6px 16px" }}
            onClick={handleAcceptAll}
          >
            Accept All
          </button>
        </div>
      </div>
    </aside>
  );
}
