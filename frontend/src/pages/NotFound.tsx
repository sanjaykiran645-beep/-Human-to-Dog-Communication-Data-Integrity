import { Link } from "react-router-dom";
import Logo from "../Logo";
import { getToken } from "../api";

export default function NotFound() {
  const inLab = Boolean(getToken());

  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }} aria-label="CanineSense AI Home">
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Acoustic Lab</div>
          </div>
        </Link>
        <div className="row" style={{ gap: 12 }}>
          <Link to="/" className="btn ghost">
            Home
          </Link>
          <Link to={inLab ? "/app" : "/login"} className="btn accent">
            {inLab ? "Open Lab" : "Sign In"}
          </Link>
        </div>
      </header>

      <main style={{ maxWidth: 640, margin: "80px auto", padding: "0 24px", textAlign: "center", flex: 1 }}>
        <article className="card" style={{ padding: "48px 32px", background: "var(--paper)" }}>
          <div className="kicker" style={{ color: "var(--accent)" }}>404 · Acoustic Signal Lost</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.5rem", marginTop: 12, marginBottom: 12 }}>
            Page Not Found
          </h1>
          <p style={{ color: "var(--ink-2)", fontSize: "1.05rem", lineHeight: 1.6, marginBottom: 32 }}>
            We could not detect any bioacoustic signals at this address. The page may have been moved, renamed, or
            does not exist.
          </p>

          <div className="row" style={{ justifyContent: "center", gap: 14, flexWrap: "wrap" }}>
            <Link to="/" className="btn ghost">
              Return to Home
            </Link>
            <Link to={inLab ? "/app" : "/login"} className="btn accent">
              {inLab ? "Go to Dashboard" : "Sign In to Lab"}
            </Link>
          </div>

          <div style={{ marginTop: 40, borderTop: "1px solid var(--line)", paddingTop: 20 }}>
            <span className="tiny" style={{ color: "var(--muted)" }}>
              Need assistance? <Link to="/contact">Contact Support</Link> or view our <Link to="/privacy-policy">Privacy Policy</Link>.
            </span>
          </div>
        </article>
      </main>

      <footer className="land-foot" style={{ maxWidth: 960, margin: "0 auto 30px", width: "100%", padding: "0 24px" }}>
        <span>&copy; {new Date().getFullYear()} CanineSense AI Bioacoustics</span>
        <div className="row" style={{ gap: 16 }}>
          <Link to="/privacy-policy">Privacy Policy</Link>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/contact">Contact</Link>
        </div>
      </footer>
    </div>
  );
}
