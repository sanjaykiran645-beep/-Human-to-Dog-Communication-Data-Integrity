import { Link } from "react-router-dom";
import Logo from "../Logo";

export default function RefundPolicy() {
  const lastUpdated = "November 11, 2026";

  return (
    <div className="land" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="land-nav" style={{ maxWidth: 960, margin: "0 auto", width: "100%" }}>
        <Link to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
          <Logo />
          <div>
            <div className="brand-name">CanineSense</div>
            <div className="brand-sub">Refund &amp; Billing Policy</div>
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
          <div className="kicker">Billing &amp; Payment Status</div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: "2.2rem", marginTop: 8, marginBottom: 8 }}>
            Refund &amp; Billing Policy
          </h1>
          <p className="tiny" style={{ color: "var(--muted)", marginBottom: 28 }}>
            Effective &amp; Last Updated: {lastUpdated} · Version 1.1
          </p>

          <section
            style={{
              marginBottom: 28,
              background: "rgba(61, 90, 76, 0.08)",
              padding: "24px",
              borderRadius: "var(--radius-sm)",
              borderLeft: "4px solid var(--forest)",
            }}
          >
            <h2 style={{ color: "var(--forest)", marginTop: 0 }}>
              1. Current Service Status: 100% Free Open-Access Tool
            </h2>
            <p style={{ fontWeight: 500, lineHeight: 1.7, margin: 0 }}>
              CanineSense AI is currently provided as a <strong>100% free open-access bioacoustics research tool</strong>.
              We do not charge subscription fees, we do not sell credits, and we do not collect credit card or payment
              information from any user.
            </p>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>2. Applicability of Refunds</h2>
            <p>
              Because CanineSense AI is completely free of charge, standard purchase refund policies are{" "}
              <strong>Not Applicable (N/A)</strong> at this time.
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>You will never be billed or asked for payment details to use the bioacoustic analysis or communication tools.</li>
              <li>There are no hidden charges, trial-period conversions, or surprise fees.</li>
              <li>No payment processor or credit card gateway is integrated into the application.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>3. Future Commercial Services Disclosure</h2>
            <p>
              Should CanineSense AI introduce optional paid tiers, specialized hardware integrations, or commercial API
              quotas in the future, this policy will be formally updated prior to billing activation with explicit terms
              specifying:
            </p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.7 }}>
              <li>Eligible purchase categories and refund request windows (e.g. 14-day statutory cooling-off periods).</li>
              <li>Clear cancellation procedures for recurring subscriptions with immediate billing cessation.</li>
              <li>Timelines for refund processing (standard 5-10 business days back to the original payment method).</li>
              <li>Exclusions for completed custom hardware shipments or consumed API compute resources.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 28 }}>
            <h2>4. Questions or Billing Inquiries</h2>
            <p>
              If you ever receive an unauthorized bill or communication claiming to charge on behalf of CanineSense AI,
              please report it immediately to our support team:
            </p>
            <p style={{ background: "var(--surface-soft)", padding: "16px 20px", borderRadius: "var(--radius-sm)" }}>
              <strong>CanineSense AI Billing &amp; Support</strong><br />
              Email: <a href="mailto:support@caninesense.ai">support@caninesense.ai</a><br />
              Response Time: Within 24-48 business hours
            </p>
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
