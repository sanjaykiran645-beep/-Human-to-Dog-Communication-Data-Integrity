import { useState } from "react";
import { Link } from "react-router-dom";
import Logo from "../Logo";
import { getToken } from "../api";

export default function Landing() {
  const inLab = Boolean(getToken());
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="land">
      <header className="land-nav">
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }} aria-label="CanineSense AI Home">
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Acoustic Lab</div>
          </div>
        </Link>

        {/* Desktop Navigation Links */}
        <div className="row desktop-nav" style={{ gap: 12 }}>
          <Link to="/privacy-policy" className="btn ghost tiny-btn" style={{ fontSize: "0.85rem" }}>
            Privacy
          </Link>
          <Link to="/contact" className="btn ghost tiny-btn" style={{ fontSize: "0.85rem" }}>
            Contact
          </Link>
          {inLab ? (
            <Link to="/app" className="btn accent">
              Open Lab
            </Link>
          ) : (
            <>
              <Link to="/login" className="btn ghost">
                Sign in
              </Link>
              <Link to="/register" className="btn accent">
                Create account
              </Link>
            </>
          )}
        </div>

        {/* Mobile Hamburger Button */}
        <button
          type="button"
          className="mobile-hamburger-btn"
          aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileMenuOpen}
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? "✕" : "☰"}
        </button>
      </header>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <nav
          className="mobile-nav-drawer"
          aria-label="Mobile Navigation"
          style={{
            background: "var(--paper)",
            borderBottom: "1px solid var(--line)",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            boxShadow: "var(--shadow)",
          }}
        >
          <Link to={inLab ? "/app" : "/login"} className="btn accent wide" onClick={() => setMobileMenuOpen(false)}>
            {inLab ? "Open Acoustic Lab" : "Sign In to Lab"}
          </Link>
          {!inLab && (
            <Link to="/register" className="btn ghost wide" onClick={() => setMobileMenuOpen(false)}>
              Create Account
            </Link>
          )}
          <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "8px 0" }} />
          <Link to="/privacy-policy" onClick={() => setMobileMenuOpen(false)}>
            Privacy Policy
          </Link>
          <Link to="/terms-of-service" onClick={() => setMobileMenuOpen(false)}>
            Terms of Service
          </Link>
          <Link to="/cookie-settings" onClick={() => setMobileMenuOpen(false)}>
            Cookie Settings
          </Link>
          <Link to="/contact" onClick={() => setMobileMenuOpen(false)}>
            Contact &amp; Support
          </Link>
        </nav>
      )}

      <section className="land-hero">
        <div className="kicker">Private · Experimental · Honest</div>
        <h1>Acoustic intelligence for dogs. Not a mind reader.</h1>
        <p className="lede">
          CanineSense analyses barking, growling, whining, howling and related vocalizations from their physical acoustics.
          A bark is an acoustic event in air. True meaning requires physical and environmental context.
        </p>
        <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
          <Link to={inLab ? "/app/analyze" : "/register"} className="btn accent">
            {inLab ? "Analyze audio" : "Start a private lab"}
          </Link>
          <Link to={inLab ? "/app/communicate" : "/login"} className="btn ghost">
            Experimental communication
          </Link>
        </div>
      </section>

      <section className="land-engines">
        <article className="card">
          <div className="kicker">Engine A · primary</div>
          <h2>Dog → human</h2>
          <p>
            Upload or record canine vocalizations. Features are extracted locally on the server. Short-Time Fourier
            Transform (STFT) spectrograms, fundamental frequency (&fnof;<sub>0</sub>), and evidence indicators come
            from deterministic signal processing.
          </p>
          <ul className="land-list">
            <li>Bark, growl, whine, howl, yip, grunt, other, unknown</li>
            <li>Behavioral context estimated conservatively with abstention</li>
            <li>Emotional valence is never claimed from audio alone</li>
          </ul>
        </article>

        <article className="card engine-b">
          <div className="kicker">Engine B · experimental</div>
          <h2>Human → dog</h2>
          <p>
            Text intents guide synthetic canine sound generation and reference vocalization retrieval. Labeled strictly
            as experimental comparative research.
          </p>
          <ul className="land-list">
            <li>Synthetic DSP and authentic canine reference retrieval</li>
            <li>Ambiguous intents request user clarification</li>
            <li>Dog responses can be captured and scored by Engine A</li>
          </ul>
        </article>
      </section>

      <section className="card land-limits">
        <h2>What this product will not do</h2>
        <p>
          It does not diagnose animal illness. It does not translate thoughts or linguistic meaning. The 90%
          accuracy target is a long-term research evaluation goal and is <strong>not claimed as a guarantee</strong> in
          this release.
        </p>
      </section>

      <footer className="land-foot" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14, width: "100%" }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>CanineSense AI</div>
            <div className="tiny" style={{ color: "var(--muted)", marginTop: 2 }}>
              Open-Access Bioacoustics Research Initiative · &copy; {new Date().getFullYear()}
            </div>
          </div>
          <div className="tiny" style={{ color: "var(--ink-2)", display: "flex", gap: 16, flexWrap: "wrap" }}>
            <span>Email: <a href="mailto:support@caninesense.ai">support@caninesense.ai</a></span>
            <span>Tel: <a href="tel:+18005550199">+1 (800) 555-0199</a></span>
          </div>
        </div>

        <div className="row" style={{ gap: 16, flexWrap: "wrap", fontSize: "0.85rem", borderTop: "1px solid var(--line)", paddingTop: 14 }}>
          <Link to="/privacy-policy">Privacy Policy</Link>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/refund-policy">Refund Policy</Link>
          <Link to="/cookie-policy">Cookie Policy</Link>
          <Link to="/cookie-settings">Cookie Settings</Link>
          <Link to="/data-deletion">Data Deletion</Link>
          <Link to="/contact">Contact Support</Link>
        </div>
      </footer>
    </div>
  );
}
