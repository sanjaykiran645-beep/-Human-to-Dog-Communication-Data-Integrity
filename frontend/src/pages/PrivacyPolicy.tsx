import { Link } from "react-router-dom";
import Logo from "../Logo";

export default function PrivacyPolicy() {
  const lastUpdated = "November 11, 2026";

  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Privacy Policy</div>
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
          <div className="kicker">Legal &amp; Privacy Compliance</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.2rem", marginTop: 8, marginBottom: 8 }}>
            Privacy Policy
          </h1>
          <p className="tiny" style={{ color: "var(--muted)", marginBottom: 28 }}>
            Effective &amp; Last Updated: {lastUpdated} · Version 1.1
          </p>

          <section style={{ marginBottom: 28 }}>
            <h2>1. Introduction &amp; Commitment</h2>
            <p>
              CanineSense AI (&ldquo;CanineSense&rdquo;, &ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;) is an
              open-access bioacoustic research platform designed to analyze canine vocalization acoustics. We operate
              on principles of strict data minimization, user sovereignty, and transparent local processing.
            </p>
            <p>
              This Privacy Policy details how we collect, process, store, and safeguard your personal information and
              audio data when you use the CanineSense AI platform and API.
            </p>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>2. Information We Collect</h2>
            <p>We collect only the minimum information necessary to provide bioacoustic analysis services:</p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>
                <strong>Account Credentials:</strong> Email address, user display name, and securely salted bcrypt
                password hash. We never store plaintext passwords.
              </li>
              <li>
                <strong>Canine Profiles:</strong> Dog name, breed, age, estimated weight, and sex, provided voluntarily
                by you to establish acoustic baseline parameters (e.g. expected fundamental frequency range).
              </li>
              <li>
                <strong>Audio Recordings &amp; Files:</strong> Audio recordings uploaded directly or recorded via browser
                microphone (WAV, MP3, M4A, OGG, WEBM, FLAC formats up to 15 MB).
              </li>
              <li>
                <strong>Acoustic Analysis Telemetry:</strong> Computed bioacoustic features including Short-Time Fourier
                Transform (STFT) spectrogram arrays, YIN fundamental frequency (&fnof;<sub>0</sub>), spectral centroid,
                harmonic-to-noise ratio (HNR), and classification confidence scores.
              </li>
              <li>
                <strong>Technical Logs:</strong> Server access timestamps, HTTP status codes, and error telemetry for
                system health and security rate limiting.
              </li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>3. Microphone Access &amp; Device Permissions</h2>
            <p>
              When you record audio directly inside the CanineSense web application, your browser will request explicit
              microphone permission via the standard HTML5 Web Audio API:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>Microphone access is requested <em>only</em> when you click the &ldquo;Record&rdquo; button.</li>
              <li>Audio is captured strictly in temporary browser memory during recording.</li>
              <li>Audio is transmitted to the server for processing <em>only</em> after you stop and submit the recording.</li>
              <li>CanineSense never listens in the background, never records continuously, and never activates hardware without user initiation.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>4. How Your Audio &amp; Data Are Processed</h2>
            <p>
              <strong>Zero External Cloud AI Transmission:</strong> All audio processing, digital signal processing (DSP),
              feature extraction, spectrogram computation, and random forest classification are performed locally on the
              CanineSense backend server using Python (librosa, soundfile, scipy, scikit-learn).
            </p>
            <p>
              Your canine audio recordings and transcripts are <strong>never</strong> transmitted to third-party AI APIs
              (such as OpenAI, Google Gemini, Anthropic, or external telemetry aggregators) for inference or model training.
            </p>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>5. Storage &amp; Data Retention</h2>
            <p>
              <strong>Storage Location:</strong> All data is stored in the self-contained SQLite database
              (<code>data/caninesense.db</code>) and local file storage directory (<code>data/recordings/</code>) on our
              secured server infrastructure.
            </p>
            <p>
              <strong>Retention Schedule:</strong>
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>
                <strong>User Audio Recordings:</strong> Retained for the lifetime of your account to allow historical
                spectrogram review and tracking, until you delete the individual recording or delete your account.
              </li>
              <li>
                <strong>Temporary Conversion Files:</strong> Audio conversion buffers created during FFmpeg transcoding
                are purged immediately upon request completion.
              </li>
              <li>
                <strong>Account Deletion:</strong> Initiating an account deletion permanently and irreversibly purges all
                associated dog profiles, audio recordings, spectrogram files, and audit records from the disk immediately.
              </li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>6. Third-Party Services &amp; Trackers</h2>
            <p>
              CanineSense AI uses <strong>zero third-party tracking scripts, analytics cookies, or advertising SDKs</strong>.
              Specifically:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>No Google Analytics, Google Tag Manager, or Meta Pixels.</li>
              <li>No third-party payment processors or credit card aggregators.</li>
              <li>No social media tracking widgets or fingerprinting scripts.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>7. Security Safeguards</h2>
            <p>We employ multi-layered technical controls to defend user data and system integrity:</p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li><strong>Password Hashing:</strong> Industry-standard bcrypt hashing with adaptive work factor salts.</li>
              <li><strong>Authentication:</strong> Cryptographically signed JSON Web Tokens (JWT) with standard expiry.</li>
              <li><strong>Insecure Direct Object Reference (IDOR) Protection:</strong> Strict database-level user isolation checks preventing users from accessing or modifying recordings, dogs, or synthesis profiles belonging to other accounts.</li>
              <li><strong>Path Traversal Defense:</strong> All audio storage paths are validated with canonical path resolution to prevent directory traversal exploits.</li>
              <li><strong>Rate Limiting:</strong> SlowAPI IP-based rate limiting defends against brute-force authentication and denial of service attacks.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>8. User Rights &amp; Privacy Procedures</h2>
            <p>
              Regardless of your physical location, CanineSense guarantees comprehensive data subject rights:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li><strong>Right of Access &amp; Portability:</strong> You can download a complete JSON archive of all your dogs, audio recordings, and acoustic analyses at any time via <Link to="/app/settings">Settings &rarr; Export Data</Link>.</li>
              <li><strong>Right to Rectification:</strong> You may edit dog profiles, rename recordings, or update your account information directly in the application.</li>
              <li><strong>Right to Erasure (&ldquo;Right to be Forgotten&rdquo;):</strong> You can delete any individual audio recording instantly, or delete your entire account and all associated data via <Link to="/data-deletion">Self-Service Account Deletion</Link>.</li>
              <li><strong>Right to Withdraw Consent:</strong> You may revoke microphone access in your browser settings and manage local storage cookies at any time via <Link to="/cookie-settings">Cookie Settings</Link>.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>9. Regulatory Compliance</h2>
            <p>
              CanineSense AI is architected to adhere to international privacy legislation and core privacy frameworks:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li><strong>General Data Protection Regulation (GDPR / UK GDPR):</strong> Lawful basis of contract fulfillment and explicit user consent; full data portability and erasure mechanisms.</li>
              <li><strong>California Consumer Privacy Act (CCPA / CPRA):</strong> We do not sell or share personal information with third parties for cross-context behavioral advertising.</li>
              <li><strong>Digital Personal Data Protection Act (DPDP Act 2023, India):</strong> Purpose-limited processing, explicit consent mechanisms, and transparent grievance redressal.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>10. Contact &amp; Privacy Officer</h2>
            <p>
              If you have any questions, concerns, or requests regarding this Privacy Policy or your personal data,
              contact our Data Protection Officer:
            </p>
            <p style={{ background: "var(--surface-soft)", padding: "16px 20px", borderRadius: "var(--radius-sm)" }}>
              <strong>CanineSense AI Privacy Office</strong><br />
              Official Inquiries: <a href="https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity/issues" target="_blank" rel="noreferrer">GitHub Project Issue Tracker</a><br />
              Privacy Email: privacy@caninesense.ai [Pending Owner Mailbox Setup]<br />
              Response Time: Within 48 business hours
            </p>
          </section>
        </article>
      </main>

      <footer className="land-foot" style={{ maxWidth: 960, margin: "0 auto 30px", width: "100%", padding: "0 24px" }}>
        <span>&copy; {new Date().getFullYear()} CanineSense AI Bioacoustics</span>
        <div className="row" style={{ gap: 16 }}>
          <Link to="/terms-of-service">Terms of Service</Link>
          <Link to="/refund-policy">Refund Policy</Link>
          <Link to="/cookie-policy">Cookie Policy</Link>
          <Link to="/contact">Contact</Link>
        </div>
      </footer>
    </div>
  );
}
