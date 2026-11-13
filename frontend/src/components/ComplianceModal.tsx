import { useEffect, useState } from "react";

// Persistent key for TOS acceptance
const TOS_KEY = "cs_tos_accepted_v1";

export default function ComplianceModal() {
  const [accepted, setAccepted] = useState<boolean>(false);
  const [checks, setChecks] = useState({
    acoustic: false,
    accuracy: false,
    dsp: false,
  });

  // On mount, see if already accepted
  useEffect(() => {
    const stored = localStorage.getItem(TOS_KEY);
    if (stored) {
      setAccepted(true);
    }
  }, []);

  if (accepted) return null;

  const allChecked = checks.acoustic && checks.accuracy && checks.dsp;

  const handleAccept = () => {
    const iso = new Date().toISOString();
    localStorage.setItem(TOS_KEY, iso);
    setAccepted(true);
  };

  const toggle = (field: keyof typeof checks) => {
    setChecks((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="compliance-modal-title"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        className="compliance-modal"
        style={{
          background: "white",
          borderRadius: "8px",
          maxWidth: "480px",
          width: "90%",
          padding: "24px",
          boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
        }}
      >
        <h2 id="compliance-modal-title" style={{ marginTop: 0 }}>
          Terms of Service & Scientific Disclaimer
        </h2>
        <p>
          Please review and acknowledge the following statements before using the
          CanineSense AI Lab.
        </p>
        <ul style={{ listStyle: "none", paddingLeft: 0 }}>
          <li>
            <label>
              <input
                type="checkbox"
                checked={checks.acoustic}
                onChange={() => toggle("acoustic")}
              />{' '}
              <strong>Acoustic Event Analysis Only:</strong> CanineSense AI
              analyzes acoustic events; it does <em>not</em> translate a dog's mind,
              thoughts, or conscious intent.
            </label>
          </li>
          <li style={{ marginTop: "0.8rem" }}>
            <label>
              <input
                type="checkbox"
                checked={checks.accuracy}
                onChange={() => toggle("accuracy")}
              />{' '}
              <strong>Evaluation Accuracy Limitations:</strong> The 90% independent‑accuracy
              target is an evaluation goal and is <strong>not met</strong> in this build
              (no held‑out annotated corpus of sufficient size is bundled). Behavioral
              valence cannot be determined from audio alone.
            </label>
          </li>
          <li style={{ marginTop: "0.8rem" }}>
            <label>
              <input
                type="checkbox"
                checked={checks.dsp}
                onChange={() => toggle("dsp")}
              />{' '}
              <strong>Experimental DSP Synthesis:</strong> Engine B generates synthetic
              sounds; a dog's behavioral response is <strong>not</strong> proof that the
              dog understood the sound.
            </label>
          </li>
        </ul>
        <p style={{ marginTop: "1rem" }}>
          Review the full <a href="/terms-of-service" target="_blank" rel="noopener noreferrer">Terms of Service</a>
          {' '}and{' '}<a href="/privacy-policy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.
        </p>
        <button
          className="btn primary"
          disabled={!allChecked}
          onClick={handleAccept}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            backgroundColor: allChecked ? "#0070f3" : "#aaa",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: allChecked ? "pointer" : "not-allowed",
          }}
        >
          Accept &amp; Enter Lab
        </button>
      </div>
    </div>
  );
}
