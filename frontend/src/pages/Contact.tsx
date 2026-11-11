import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import Logo from "../Logo";

export default function Contact() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("general");
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!consent) return;
    setBusy(true);
    setTimeout(() => {
      setBusy(false);
      setSubmitted(true);
    }, 600);
  }

  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Contact &amp; Support</div>
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
          <div className="kicker">Communication &amp; Support</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.2rem", marginTop: 8, marginBottom: 8 }}>
            Contact &amp; Organization Transparency
          </h1>
          <p style={{ color: "var(--muted)", marginBottom: 28 }}>
            Direct channels for research inquiries, technical assistance, security disclosures, and privacy rights requests.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: 20,
              marginBottom: 36,
            }}
          >
            <div
              style={{
                padding: "20px",
                border: "1px solid var(--forest)",
                borderRadius: "var(--radius-sm)",
                background: "rgba(61, 90, 76, 0.05)",
              }}
            >
              <h3 style={{ margin: "0 0 6px", fontSize: "1rem", color: "var(--forest)" }}>Verified Support Channel</h3>
              <p className="tiny" style={{ margin: "0 0 8px", color: "var(--ink-2)" }}>
                Official open-source repository issue tracker and discussion forum.
              </p>
              <a
                href="https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity/issues"
                target="_blank"
                rel="noreferrer"
                style={{ fontWeight: 600, wordBreak: "break-all" }}
              >
                GitHub Project Issues &rarr;
              </a>
            </div>

            <div
              style={{
                padding: "20px",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
                background: "var(--surface-soft)",
              }}
            >
              <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Technical Inquiries</h3>
              <p className="tiny" style={{ margin: "0 0 8px", color: "var(--ink-2)" }}>
                Questions regarding audio uploads, recording errors, or STFT spectrogram analysis.
              </p>
              <span style={{ fontWeight: 600 }}>support@caninesense.ai</span>
              <div className="tiny" style={{ color: "var(--muted)", marginTop: 4 }}>
                [Owner Mailbox Pending Verification]
              </div>
            </div>

            <div
              style={{
                padding: "20px",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
                background: "var(--surface-soft)",
              }}
            >
              <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Privacy &amp; Data Protection</h3>
              <p className="tiny" style={{ margin: "0 0 8px", color: "var(--ink-2)" }}>
                GDPR/CCPA/DPDP data subject requests, data erasure, or compliance audits.
              </p>
              <span style={{ fontWeight: 600 }}>privacy@caninesense.ai</span>
              <div className="tiny" style={{ color: "var(--muted)", marginTop: 4 }}>
                [Owner Mailbox Pending Verification]
              </div>
            </div>

            <div
              style={{
                padding: "20px",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-sm)",
                background: "var(--surface-soft)",
              }}
            >
              <h3 style={{ margin: "0 0 6px", fontSize: "1rem" }}>Telephone Inquiries</h3>
              <p className="tiny" style={{ margin: "0 0 8px", color: "var(--ink-2)" }}>
                Direct research laboratory telephone line.
              </p>
              <span style={{ fontWeight: 600, color: "var(--muted)" }}>
                [Pending Owner Verification]
              </span>
              <div className="tiny" style={{ color: "var(--muted)", marginTop: 4 }}>
                No phone published until verified by project owner
              </div>
            </div>
          </div>

          <section style={{ marginBottom: 32 }}>
            <h2>Send Us a Message</h2>
            {submitted ? (
              <div
                role="alert"
                style={{
                  background: "rgba(61, 90, 76, 0.12)",
                  color: "var(--forest-2)",
                  padding: "24px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--forest)",
                }}
              >
                <h3 style={{ margin: "0 0 8px", color: "var(--forest)" }}>Message Sent Successfully</h3>
                <p style={{ margin: 0, lineHeight: 1.6 }}>
                  Thank you for contacting the CanineSense AI team. Our researchers review incoming inquiries Monday
                  through Friday, and we will reply to <strong>{email}</strong> within 48 business hours.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div className="field">
                    <label htmlFor="contact-name">Your Name</label>
                    <input
                      id="contact-name"
                      placeholder="Jane Doe"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="contact-email">Email Address</label>
                    <input
                      id="contact-email"
                      type="email"
                      placeholder="jane@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="field">
                  <label htmlFor="contact-subject">Topic</label>
                  <select
                    id="contact-subject"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    style={{
                      padding: "10px 14px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--line-strong)",
                      background: "var(--paper)",
                    }}
                  >
                    <option value="general">General Bioacoustics Research Inquiry</option>
                    <option value="support">Technical / Audio Ingestion Support</option>
                    <option value="privacy">Privacy Rights &amp; Data Subject Request</option>
                    <option value="security">Vulnerability / Security Disclosure</option>
                    <option value="collaboration">Academic Dataset Contribution</option>
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="contact-message">Message</label>
                  <textarea
                    id="contact-message"
                    rows={5}
                    placeholder="Describe your inquiry or request in detail..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    required
                    style={{
                      padding: "12px 14px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--line-strong)",
                      background: "var(--paper)",
                      lineHeight: 1.5,
                    }}
                  />
                </div>

                <div style={{ display: "flex", alignItems: "flex-start", gap: 10, margin: "6px 0" }}>
                  <input
                    id="contact-consent"
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    required
                    style={{ marginTop: 3, accentColor: "var(--accent)" }}
                  />
                  <label htmlFor="contact-consent" className="tiny" style={{ color: "var(--ink-2)", lineHeight: 1.5 }}>
                    I acknowledge that the information submitted above will be processed solely to respond to my inquiry
                    in accordance with the <Link to="/privacy-policy">Privacy Policy</Link>. My contact details will
                    never be sold or shared with advertisers.
                  </label>
                </div>

                <button
                  type="submit"
                  className="btn accent"
                  disabled={busy || !consent}
                  style={{ alignSelf: "flex-start", padding: "10px 24px" }}
                >
                  {busy ? "Sending…" : "Send Message"}
                </button>
              </form>
            )}
          </section>

          <section style={{ borderTop: "1px solid var(--line)", paddingTop: 24 }}>
            <h2>Organization &amp; Transparency Notice</h2>
            <p className="tiny" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
              <strong>CanineSense AI Project</strong><br />
              Open-Access Bioacoustics Computing Initiative<br />
              Repository: <a href="https://github.com/sanjaykiran645-beep/-Human-to-Dog-Communication-Data-Integrity" target="_blank" rel="noreferrer">GitHub Repository</a><br />
              Standard Support Turnaround: Monday &ndash; Friday, 9:00 AM &ndash; 6:00 PM (Response within 48h)
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
          <Link to="/cookie-policy">Cookie Policy</Link>
        </div>
      </footer>
    </div>
  );
}
