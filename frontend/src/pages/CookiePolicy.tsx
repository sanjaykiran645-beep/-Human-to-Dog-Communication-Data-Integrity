import { Link } from "react-router-dom";
import Logo from "../Logo";

export default function CookiePolicy() {
  const lastUpdated = "November 11, 2026";

  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Cookie Policy</div>
          </div>
        </Link>
        <div className="row" style={{ gap: 12 }}>
          <Link to="/" className="btn ghost">
            Back to Home
          </Link>
          <Link to="/cookie-settings" className="btn accent">
            Cookie Settings
          </Link>
        </div>
      </header>

      <main style={{ maxWidth: 840, margin: "40px auto 60px", padding: "0 24px", width: "100%", flex: 1 }}>
        <article className="card" style={{ padding: "40px 36px", background: "var(--paper)" }}>
          <div className="kicker">Browser Storage &amp; Cookies</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.2rem", marginTop: 8, marginBottom: 8 }}>
            Cookie Policy
          </h1>
          <p className="tiny" style={{ color: "var(--muted)", marginBottom: 28 }}>
            Effective &amp; Last Updated: {lastUpdated} · Version 1.1
          </p>

          <section style={{ marginBottom: 28 }}>
            <h2>1. What Are Cookies &amp; Browser Storage?</h2>
            <p>
              Cookies and browser storage (such as HTML5 <code>localStorage</code> and <code>sessionStorage</code>) are
              small data files stored directly on your computer or mobile device by your web browser when you visit a
              website. They allow websites to remember user authentication states and operational preferences.
            </p>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>2. Our Zero-Tracker Architecture</h2>
            <p>
              Unlike many modern web platforms, CanineSense AI operates on a <strong>privacy-first model</strong>:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>We do <strong>not</strong> use advertising cookies.</li>
              <li>We do <strong>not</strong> use third-party analytics cookies (e.g. Google Analytics, Meta Pixels).</li>
              <li>We do <strong>not</strong> engage in cross-site tracking or behavioral fingerprinting.</li>
              <li>All browser storage is strictly limited to first-party functional and essential authentication keys.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>3. Detailed Inventory of Browser Storage</h2>
            <div style={{ overflowX: "auto", margin: "20px 0" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid var(--line-strong)", textAlign: "left" }}>
                    <th style={{ padding: "10px 8px" }}>Key Name</th>
                    <th style={{ padding: "10px 8px" }}>Type</th>
                    <th style={{ padding: "10px 8px" }}>Category</th>
                    <th style={{ padding: "10px 8px" }}>Purpose</th>
                    <th style={{ padding: "10px 8px" }}>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 8px" }}><code>cs_token</code></td>
                    <td style={{ padding: "10px 8px" }}>localStorage</td>
                    <td style={{ padding: "10px 8px" }}><strong>Strictly Essential</strong></td>
                    <td style={{ padding: "10px 8px" }}>Stores your cryptographically signed JWT session token for API authentication.</td>
                    <td style={{ padding: "10px 8px" }}>Session / Until Logout</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 8px" }}><code>cs_user</code></td>
                    <td style={{ padding: "10px 8px" }}>localStorage</td>
                    <td style={{ padding: "10px 8px" }}><strong>Strictly Essential</strong></td>
                    <td style={{ padding: "10px 8px" }}>Caches basic user profile info (name, email, ID) for UI navigation display.</td>
                    <td style={{ padding: "10px 8px" }}>Session / Until Logout</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 8px" }}><code>cs_cookie_consent</code></td>
                    <td style={{ padding: "10px 8px" }}>localStorage</td>
                    <td style={{ padding: "10px 8px" }}><strong>Strictly Essential</strong></td>
                    <td style={{ padding: "10px 8px" }}>Records your cookie preference choices (essential vs optional).</td>
                    <td style={{ padding: "10px 8px" }}>1 Year</td>
                  </tr>
                  <tr style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 8px" }}><code>cs_onboarding_done_*</code></td>
                    <td style={{ padding: "10px 8px" }}>localStorage</td>
                    <td style={{ padding: "10px 8px" }}><strong>Functional</strong></td>
                    <td style={{ padding: "10px 8px" }}>Remembers whether you have viewed or dismissed the acoustic lab welcome guide.</td>
                    <td style={{ padding: "10px 8px" }}>Persistent</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>4. Managing and Controlling Cookies</h2>
            <p>
              You have complete control over how browser storage is used on your device:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>
                <strong>In-App Settings:</strong> You can review and update your storage preferences at any time on our{" "}
                <Link to="/cookie-settings">Cookie Settings page</Link>.
              </li>
              <li>
                <strong>Browser Settings:</strong> You can clear all cookies and site data through your browser settings
                (Chrome: Settings &rarr; Privacy and security &rarr; Clear browsing data; Firefox: Settings &rarr;
                Privacy &amp; Security; Safari: Preferences &rarr; Privacy).
              </li>
              <li>
                <strong>Note on Essential Storage:</strong> Disabling or clearing <code>cs_token</code> will sign you out
                of the acoustic lab workspace, as the token is required to authenticate API calls to your private
                recordings.
              </li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>5. Contact Us</h2>
            <p>If you have any questions regarding our storage practices or Cookie Policy, contact us:</p>
            <p style={{ background: "var(--surface-soft)", padding: "16px 20px", borderRadius: "var(--radius-sm)" }}>
              <strong>CanineSense AI Privacy Office</strong><br />
              Email: <a href="mailto:privacy@caninesense.ai">privacy@caninesense.ai</a>
            </p>
          </section>
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
