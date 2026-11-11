import { Link } from "react-router-dom";
import Logo from "../Logo";
import { getToken } from "../api";

export default function Landing() {
  const inLab = Boolean(getToken());
  return (
    <div className="land">
      <header className="land-nav">
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Acoustic lab</div>
          </div>
        </Link>
        <div className="row">
          {inLab ? (
            <Link to="/app" className="btn accent">
              Open lab
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
      </header>

      <section className="land-hero">
        <div className="kicker">Private · Experimental · Honest</div>
        <h1>Acoustic intelligence for dogs. Not a mind reader.</h1>
        <p className="lede">
          CanineSense analyses barking, growling, whining, howling and related sounds from their acoustics.
          A bark is an event in air. Meaning still needs context.
        </p>
        <div className="row">
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
            Upload or record. The original is stored privately. Features are extracted on the server. Classification,
            confidence, unknown/abstain, and an evidence list come from live inference — not a canned demo.
          </p>
          <ul className="land-list">
            <li>Bark, growl, whine, howl, yip, grunt, other, unknown</li>
            <li>Behavioral context estimated separately, and often withheld</li>
            <li>Valence is not claimed from audio alone</li>
          </ul>
        </article>
        <article className="card engine-b">
          <div className="kicker">Engine B · experimental</div>
          <h2>Human → dog</h2>
          <p>
            Text or on-device speech becomes a coarse intent, then a synthetic canine-like sound. It is labeled
            experimental. A later bark from the dog is not proof of understanding.
          </p>
          <ul className="land-list">
            <li>Always synthetic DSP, never a real dog recording</li>
            <li>Ambiguous requests ask for clarification</li>
            <li>Optional response is scored by Engine A independently</li>
          </ul>
        </article>
      </section>

      <section className="card land-limits">
        <h2>What this product will not do</h2>
        <p>
          It does not diagnose illness. It does not translate thoughts. The 90% independent-accuracy target is an
          evaluation goal and is <strong>not met</strong> in this build — there is no dog-held-out annotated corpus
          bundled with the software.
        </p>
      </section>

      <footer className="land-foot" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, width: "100%" }}>
          <span>&copy; {new Date().getFullYear()} CanineSense AI Bioacoustics</span>
          <span className="tiny" style={{ color: "var(--muted)" }}>
            Recordings stay on your account. Zero third-party cloud AI transmission.
          </span>
        </div>
        <div className="row" style={{ gap: 16, flexWrap: "wrap", fontSize: "0.85rem" }}>
          <Link to="/privacy-policy">Privacy Policy</Link>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/refund-policy">Refund Policy</Link>
          <Link to="/cookie-policy">Cookie Policy</Link>
          <Link to="/cookie-settings">Cookie Settings</Link>
          <Link to="/data-deletion">Data Deletion</Link>
          <Link to="/contact">Contact</Link>
        </div>
      </footer>
    </div>
  );
}
