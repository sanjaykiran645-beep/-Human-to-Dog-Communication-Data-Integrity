import { Link } from "react-router-dom";
import Logo from "../Logo";

export default function DataDeletion() {
  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Data Deletion</div>
          </div>
        </Link>
        <div className="row" style={{ gap: 12 }}>
          <Link to="/" className="btn ghost">
            Back to Home
          </Link>
          <Link to="/login" className="btn accent">
            Sign In
          </Link>
        </div>
      </header>

      <main style={{ maxWidth: 840, margin: "40px auto 60px", padding: "0 24px", width: "100%", flex: 1 }}>
        <article className="card" style={{ padding: "40px 36px", background: "var(--paper)" }}>
          <div className="kicker">User Sovereignty &amp; Right to Erasure</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.2rem", marginTop: 8, marginBottom: 8 }}>
            Data Deletion &amp; Account Purge Instructions
          </h1>
          <p style={{ color: "var(--muted)", marginBottom: 28 }}>
            Under GDPR (Article 17), CCPA/CPRA, and India DPDP Act 2023, you hold the absolute right to have all your
            personal data and audio recordings permanently erased from CanineSense AI.
          </p>

          <section
            style={{
              marginBottom: 32,
              background: "rgba(118, 47, 61, 0.06)",
              padding: "24px",
              borderRadius: "var(--radius-sm)",
              borderLeft: "4px solid var(--accent)",
            }}
          >
            <h2 style={{ color: "var(--accent)", marginTop: 0 }}>Method 1: Instant Self-Service Deletion (Recommended)</h2>
            <p style={{ lineHeight: 1.6 }}>
              You do not need to wait for manual email processing or support approval. You can permanently erase your
              account and all associated audio data yourself in seconds:
            </p>
            <ol style={{ paddingLeft: 20, lineHeight: 1.8, margin: 0 }}>
              <li>
                <strong>Sign in</strong> to your CanineSense AI account.
              </li>
              <li>
                Navigate to <Link to="/app/settings"><strong>Settings &amp; Privacy</strong></Link> in the main sidebar.
              </li>
              <li>
                Scroll to the <strong>Danger Zone</strong> panel at the bottom of the page.
              </li>
              <li>
                Click <strong>Delete Account &amp; All Data</strong> and confirm the confirmation prompt.
              </li>
            </ol>
            <p className="tiny" style={{ marginTop: 12, marginBottom: 0, color: "var(--ink-2)" }}>
              The system immediately issues a cryptographically authenticated <code>DELETE /api/account</code> request,
              which wipes your user record, associated dog profiles, uploaded recordings, generated audio files, and
              derived spectrogram images directly from the server disk.
            </p>
          </section>

          <section style={{ marginBottom: 32 }}>
            <h2>Method 2: Manual Data Subject Deletion Request</h2>
            <p>
              If you are unable to access your account or have forgotten your password, you may submit a manual data
              erasure request:
            </p>
            <div
              style={{
                background: "var(--surface-soft)",
                padding: "20px 24px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--line)",
              }}
            >
              <p style={{ margin: "0 0 10px", lineHeight: 1.6 }}>
                Send an email from your registered account address to:
              </p>
              <p style={{ margin: "0 0 14px", fontSize: "1.1rem" }}>
                <a href="mailto:privacy@caninesense.ai?subject=Data%20Deletion%20Request" style={{ fontWeight: 600 }}>
                  privacy@caninesense.ai
                </a>
              </p>
              <p className="tiny" style={{ margin: 0, color: "var(--muted)", lineHeight: 1.5 }}>
                Subject: <code>Data Deletion Request - [Your Registered Email]</code><br />
                Include: Your full registered email address and confirmation that you request full erasure.<br />
                Processing Timeline: Completed within 30 days at zero charge.
              </p>
            </div>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>What Gets Deleted?</h2>
            <p>Upon triggering account deletion, the following data is permanently purged:</p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li><strong>User Record:</strong> Email, salted password hash, name, and profile timestamps.</li>
              <li><strong>Canine Profiles:</strong> All dog profiles, weights, breeds, and age metrics.</li>
              <li><strong>Audio Recordings:</strong> All original uploaded audio files (WAV, MP3, FLAC, WEBM, OGG).</li>
              <li><strong>Spectrogram Assets:</strong> All PNG spectrogram plots and STFT arrays generated on the server.</li>
              <li><strong>Engine B Audio:</strong> All synthesized or retrieved audio soundscapes created in your account.</li>
              <li><strong>Audit Logs:</strong> All security event and access logs referencing your account ID.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>Export Before You Delete</h2>
            <p>
              Account deletion is <strong>permanent and irreversible</strong>. If you wish to save your historical
              research data before deleting, download your complete JSON archive first:
            </p>
            <Link to="/app/settings" className="btn ghost" style={{ marginTop: 6 }}>
              Export Research Archive (JSON)
            </Link>
          </section>
        </article>
      </main>

      <footer className="land-foot" style={{ maxWidth: 960, margin: "0 auto 30px", width: "100%", padding: "0 24px" }}>
        <span>&copy; {new Date().getFullYear()} CanineSense AI Bioacoustics</span>
        <div className="row" style={{ gap: 16 }}>
          <Link to="/privacy-policy">Privacy Policy</Link>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/cookie-policy">Cookie Policy</Link>
          <Link to="/contact">Contact</Link>
        </div>
      </footer>
    </div>
  );
}
