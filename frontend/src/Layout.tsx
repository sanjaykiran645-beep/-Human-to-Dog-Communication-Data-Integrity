import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import Logo from "./Logo";
import { api, clearSession, getUser, isDemoSession } from "./api";

const links = [
  { to: "/app", label: "Dashboard", icon: IconHome, end: true, group: "core" },
  { to: "/app/analyze", label: "Analyze", icon: IconWave, end: false, group: "core" },
  { to: "/app/communicate", label: "Communicate", icon: IconSpeak, end: false, group: "core" },
  { to: "/app/dogs", label: "Dog profiles", icon: IconDog, end: false, group: "library" },
  { to: "/app/history", label: "History", icon: IconClock, end: false, group: "library" },
  { to: "/app/analytics", label: "Analytics", icon: IconChart, end: false, group: "library" },
  { to: "/app/settings", label: "Settings", icon: IconGear, end: false, group: "account" },
];

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/app": {
    title: "Acoustic Lab Overview",
    subtitle: "Private bioacoustic workspace, corpus metrics, and dual-engine telemetry",
  },
  "/app/analyze": {
    title: "Engine A · Acoustic Analysis",
    subtitle: "Upload or record dog vocalizations for STFT spectrogram & feature extraction",
  },
  "/app/communicate": {
    title: "Engine B · Vocalization Lab",
    subtitle: "Reference-driven canine audio retrieval, controlled variation & comparison",
  },
  "/app/dogs": {
    title: "Canine Profiles",
    subtitle: "Manage private dog profiles for F0-size consistency context",
  },
  "/app/history": {
    title: "Recording Archive",
    subtitle: "Inspect historical recordings, spectrograms, waveforms, and acoustic evidence",
  },
  "/app/analytics": {
    title: "Corpus Analytics & Model Card",
    subtitle: "Vocalization frequency breakdown and transparent model documentation",
  },
  "/app/settings": {
    title: "Account & Privacy Settings",
    subtitle: "Security credentials, full JSON data export, and account management",
  },
};

export default function Layout() {
  const user = getUser();
  const loc = useLocation();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const onboardingKey = user?.id ? `cs_onboarding_done_${user.id}` : "cs_onboarding_done";
  const [showWelcome, setShowWelcome] = useState<boolean>(() => {
    const done = localStorage.getItem(onboardingKey) === "1" || localStorage.getItem("cs_onboarding_done") === "1";
    const isDashboard = loc.pathname === "/app" || loc.pathname === "/app/";
    return !done && isDashboard;
  });

  useEffect(() => {
    const done = localStorage.getItem(onboardingKey) === "1" || localStorage.getItem("cs_onboarding_done") === "1";
    const isDashboard = loc.pathname === "/app" || loc.pathname === "/app/";
    if (!done && isDashboard) {
      setShowWelcome(true);
    }
  }, [onboardingKey, loc.pathname]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && showWelcome) {
        dismissWelcome();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showWelcome]);

  function dismissWelcome() {
    localStorage.setItem(onboardingKey, "1");
    localStorage.setItem("cs_onboarding_done", "1");
    setShowWelcome(false);
  }

  async function handleLogout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    clearSession();
    nav("/login");
  }

  function handleHeaderSearch(e: FormEvent) {
    e.preventDefault();
    const q = searchText.trim();
    if (q) {
      nav(`/app/history?q=${encodeURIComponent(q)}`);
    } else {
      nav("/app/history");
    }
  }

  const meta = PAGE_META[loc.pathname] || PAGE_META["/app"];
  const initials = (user?.name || user?.email || "CS")
    .trim()
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const coreLinks = links.filter((l) => l.group === "core");
  const libLinks = links.filter((l) => l.group === "library");
  const accLinks = links.filter((l) => l.group === "account");

  return (
    <div className="app">
      {open && <button className="scrim" aria-label="Close menu" type="button" onClick={() => setOpen(false)} />}

      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <Link
            to="/app"
            className="brand"
            style={{ textDecoration: "none", color: "inherit" }}
            aria-label="CanineSense AI Dashboard"
            onClick={() => setOpen(false)}
          >
            <Logo size={36} />
            <div>
              <div className="brand-name">CanineSense</div>
              <div className="brand-sub">Acoustic Lab</div>
            </div>
          </Link>
          <button
            type="button"
            className="mobile-close-btn"
            aria-label="Close navigation menu"
            onClick={() => setOpen(false)}
            style={{
              background: "none",
              border: "none",
              fontSize: "1.5rem",
              lineHeight: 1,
              cursor: "pointer",
              color: "var(--ink)",
              padding: "4px 8px",
            }}
          >
            ×
          </button>
        </div>

        <nav aria-label="Primary navigation">
          <div className="sidebar-section-label">Acoustic Engines</div>
          {coreLinks.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <l.icon />
              {l.label}
            </NavLink>
          ))}

          <div className="sidebar-section-label">Corpus &amp; Profiles</div>
          {libLinks.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <l.icon />
              {l.label}
            </NavLink>
          ))}

          <div className="sidebar-section-label">System</div>
          {accLinks.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <l.icon />
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="side-foot">
          <div className="side-user-row">
            <div className="side-avatar" aria-hidden="true">
              {initials}
            </div>
            <div className="side-user-meta">
              <strong>{isDemoSession() ? "Demo Preview Guest" : user?.name || "Researcher"}</strong>
              {isDemoSession() ? (
                <span className="badge warn" style={{ fontSize: "0.68rem", padding: "2px 6px" }}>
                  Simulated Session
                </span>
              ) : user?.email ? (
                <a href={`mailto:${user.email}`} style={{ color: "inherit", textDecoration: "none" }}>
                  {user.email}
                </a>
              ) : (
                <span>Private workspace</span>
              )}
            </div>
          </div>
          <div className="side-actions">
            <Link to="/app/settings" className="btn ghost" onClick={() => setOpen(false)}>
              Settings
            </Link>
            <button type="button" className="btn ghost" onClick={handleLogout}>
              {isDemoSession() ? "Exit Demo" : "Sign out"}
            </button>
          </div>
          <div className="side-legal-links" style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap", fontSize: "0.75rem", color: "var(--muted)" }}>
            <Link to="/privacy-policy" onClick={() => setOpen(false)} style={{ color: "inherit" }}>Privacy</Link>
            <span>·</span>
            <Link to="/terms-of-service" onClick={() => setOpen(false)} style={{ color: "inherit" }}>Terms</Link>
            <span>·</span>
            <Link to="/cookie-settings" onClick={() => setOpen(false)} style={{ color: "inherit" }}>Cookies</Link>
            <span>·</span>
            <Link to="/contact" onClick={() => setOpen(false)} style={{ color: "inherit" }}>Contact</Link>
          </div>
        </div>
      </aside>

      <main className="main">
        {/* Top Header Bar */}
        <header className="app-header">
          <div className="app-header-left">
            <button className="menu-btn" type="button" onClick={() => setOpen(true)} aria-label="Open menu">
              Menu
            </button>
            <div>
              <div className="app-header-crumb">CanineSense AI · {meta.subtitle}</div>
              <div className="app-header-title">{meta.title}</div>
            </div>
          </div>

          <div className="app-header-right">
            <form className="header-search" onSubmit={handleHeaderSearch} role="search">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-3.5-3.5" />
              </svg>
              <input
                type="search"
                placeholder="Search recordings in archive…"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                aria-label="Search recordings in archive"
              />
            </form>

            <a
              href="/api/download/apk"
              download="CanineSense_AI_v1.0.0.apk"
              className="btn ghost"
              style={{ padding: "6px 12px", fontSize: "0.78rem", whiteSpace: "nowrap" }}
              title="Download CanineSense AI Android APK package"
            >
              Download APK
            </a>

            <button
              type="button"
              className="header-icon-btn"
              title="Open CanineSense AI Welcome Guide"
              aria-label="Open CanineSense AI Welcome Guide"
              onClick={() => setShowWelcome(true)}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
                <circle cx="12" cy="12" r="9" />
                <path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 3.5M12 16.5h.01" />
              </svg>
            </button>

            <Link to="/app/settings" className="header-user-chip" title="Account & Privacy Settings">
              <span className="header-user-avatar">{initials}</span>
              <span>{user?.name || "Account"}</span>
            </Link>
          </div>
        </header>

        {isDemoSession() && (
          <div
            role="status"
            style={{
              background: "#FFF4E5",
              color: "#663C00",
              border: "1px solid #FFE2B3",
              borderRadius: "var(--radius-sm)",
              padding: "10px 16px",
              marginBottom: 18,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 10,
              fontSize: "0.85rem",
              fontWeight: 500,
            }}
          >
            <div>
              <strong>OFFLINE DEMO PREVIEW MODE:</strong> You are exploring an in-browser interface preview with synthetic audio. Real bioacoustic ML classification, authentic reference streaming, and secure user accounts require a connected FastAPI backend.
            </div>
            <button
              type="button"
              className="btn ghost"
              style={{
                padding: "4px 12px",
                fontSize: "0.78rem",
                color: "#663C00",
                borderColor: "#D4A373",
                fontWeight: 600,
              }}
              onClick={() => {
                clearSession();
                nav("/login");
              }}
            >
              Exit Demo
            </button>
          </div>
        )}

        <Outlet />
      </main>

      {/* Onboarding Welcome Modal */}
      {showWelcome && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="welcome-modal-title"
          data-testid="welcome-modal"
        >
          <div className="welcome-modal">
            <div className="welcome-modal-hero">
              <div>
                <div className="kicker">Welcome to CanineSense AI</div>
                <h2 id="welcome-modal-title" style={{ fontSize: "1.65rem", margin: "4px 0 8px" }}>
                  Hello{user?.name ? `, ${user.name}` : ""} — your private bioacoustic lab is ready
                </h2>
                <p style={{ margin: 0, maxWidth: "56ch", fontSize: "0.93rem" }}>
                  CanineSense AI combines conservative canine vocalization analysis with a reference-driven dog audio
                  laboratory. Explore your workspace capabilities below.
                </p>
              </div>
              <button
                type="button"
                className="welcome-close-btn"
                aria-label="Close welcome dialog"
                data-testid="welcome-close"
                onClick={dismissWelcome}
              >
                ×
              </button>
            </div>

            <div className="welcome-modal-body">
              <div className="welcome-steps">
                <div className="welcome-step">
                  <div className="welcome-step-num">01 · ENGINE A</div>
                  <h3>Analyze Dog Audio</h3>
                  <p>
                    Upload or record WAV, MP3, M4A, OGG, WEBM, or FLAC clips. Inspect STFT spectrograms, F0 contours,
                    and heuristic vocalization scores with abstention safeguards.
                  </p>
                </div>
                <div className="welcome-step">
                  <div className="welcome-step-num">02 · ENGINE B</div>
                  <h3>Reference Vocalizer</h3>
                  <p>
                    Generate authentic canine vocalizations from 128 validated dog reference clips across 11 categories,
                    or apply bounded pitch/time variations with side-by-side comparison.
                  </p>
                </div>
                <div className="welcome-step">
                  <div className="welcome-step-num">03 · PRIVATE CORPUS</div>
                  <h3>Dog Profiles &amp; Archive</h3>
                  <p>
                    Link recordings to your dog profiles, review historical spectrograms, and export your complete JSON
                    research archive anytime from Settings.
                  </p>
                </div>
              </div>

              <div className="welcome-modal-foot">
                <span className="tiny">
                  Tip: You can reopen this guide anytime using the <strong>?</strong> button in the top header.
                </span>
                <div className="row" style={{ gap: 10 }}>
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={() => {
                      dismissWelcome();
                      nav("/app/analyze");
                    }}
                  >
                    Analyze First Recording
                  </button>
                  <button
                    type="button"
                    className="btn accent"
                    data-testid="welcome-get-started"
                    onClick={dismissWelcome}
                  >
                    Get Started
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Ico({ d }: { d: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d={d} />
    </svg>
  );
}
function IconHome() {
  return <Ico d="M4 11l8-7 8 7v9H4z" />;
}
function IconWave() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 12h3l2-6 4 12 3-8 2 2h4" />
    </svg>
  );
}
function IconSpeak() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 8h8v8H4l-2 3V8h2zM14 9c1.5 1 1.5 5 0 6M17 7c2.5 2 2.5 8 0 10" />
    </svg>
  );
}
function IconDog() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 11c2-5 6-6 8-6 2 0 3 1 5 1 2 0 3-2 3-2v6c0 5-3 9-8 9s-8-4-8-8z" />
    </svg>
  );
}
function IconClock() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5l3 2" />
    </svg>
  );
}
function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M5 19V9M12 19V5M19 19v-7" />
    </svg>
  );
}
function IconGear() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.5 5.5l1.5 1.5M17 17l1.5 1.5M18.5 5.5 17 7M7 17l-1.5 1.5" />
    </svg>
  );
}
