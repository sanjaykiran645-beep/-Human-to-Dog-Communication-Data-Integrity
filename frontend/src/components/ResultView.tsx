export default function ResultView({ analysis, quality }: { analysis: any; quality?: any }) {
  const probs = analysis.probabilities || {};
  const ranked = Object.entries(probs)
    .map(([label, p]) => ({ label, p: Number(p) }))
    .sort((a, b) => b.p - a.p);
  const behavior = analysis.behavior || {};
  const expl = analysis.explanation || {};
  const feats = analysis.features || {};
  const q = quality || expl.quality || {};
  const alternatives = analysis.alternatives || [];
  const sizeNote = behavior.size_consistency;
  const abstainReason = expl.abstain_reason || analysis.abstain_reason;

  const hasBands =
    feats.low_energy_ratio != null ||
    feats.mid_energy_ratio != null ||
    feats.high_energy_ratio != null ||
    feats.very_high_energy_ratio != null;

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="result-hero">
        <div>
          <div className="kicker">Engine A · Acoustic profile</div>
          <div className="class-name">{analysis.vocalization}</div>
          <div className="row" style={{ marginTop: 8 }}>
            <span className={`badge ${analysis.abstained ? "warn" : "ok"}`}>
              {analysis.abstained
                ? "Abstained / unknown"
                : `Heuristic score ${Math.round(analysis.confidence * 100)}%`}
            </span>
            <span className="badge">{analysis.model_version}</span>
            <span className="badge warn">Unvalidated heuristic (90% target not met)</span>
            <span className={`badge ${q.status === "ok" ? "ok" : q.status === "reject" ? "bad" : "warn"}`}>
              quality {q.status || "n/a"}
            </span>
            {q.snr_db != null && <span className="badge">SNR {Number(q.snr_db).toFixed(1)} dB</span>}
          </div>
        </div>
      </div>

      {analysis.abstained && abstainReason && (
        <div
          className="error"
          style={{ marginTop: 14, background: "#f8e4c6", color: "#6b2b12", border: "1px solid #e4c99e" }}
        >
          <strong>Why classification abstained:</strong> {abstainReason}
        </div>
      )}

      <p className="callout" style={{ marginTop: 16 }}>
        {expl.plain_language}
        {expl.why_this_class && (
          <span style={{ display: "block", marginTop: 6, fontSize: "0.86rem", opacity: 0.88 }}>
            <strong>Acoustic signature:</strong> {expl.why_this_class}
          </span>
        )}
      </p>

      <div className="grid-2" style={{ marginTop: 18 }}>
        <div>
          <h2>Heuristic class similarity scores</h2>
          <p className="tiny" style={{ marginTop: -4, marginBottom: 8 }}>
            Relative acoustic membership scores across candidate vocalization classes (not calibrated empirical probabilities).
          </p>
          {ranked.map((r) => (
            <div className="prob" key={r.label}>
              <span>{r.label}</span>
              <div className="bar">
                <span style={{ width: `${Math.round(r.p * 100)}%` }} />
              </div>
              <span>{Math.round(r.p * 100)}%</span>
            </div>
          ))}
          {alternatives.length > 0 && (
            <p className="tiny" style={{ marginTop: 10 }}>
              Runner-up candidates:{" "}
              {alternatives.map((a: any) => `${a.label} (${Math.round(Number(a.probability) * 100)}%)`).join(", ")}
            </p>
          )}
        </div>
        <div>
          <h2>Conservative behavioral context</h2>
          <p>
            <strong>{String(behavior.context || "insufficient_evidence").replace(/_/g, " ")}</strong>
            {behavior.insufficient_evidence
              ? " — insufficient evidence"
              : ` (tentative prior ${Math.round((behavior.context_confidence || 0) * 100)}%)`}
          </p>
          <p className="tiny">
            Valence: <strong>{behavior.valence_label || "undetermined"}</strong> · Arousal:{" "}
            <strong>{behavior.arousal_label || "n/a"}</strong> ({behavior.arousal ?? "—"})
          </p>
          <p>{behavior.rationale}</p>
          {sizeNote && (
            <p className="tiny" style={{ marginTop: 8 }}>
              <strong>Profile size check ({sizeNote.dog_weight_kg} kg):</strong> observed F0 {sizeNote.observed_f0} Hz vs
              expected ~{sizeNote.rough_size_expected_f0} Hz. {sizeNote.note}
            </p>
          )}
        </div>
      </div>

      {hasBands && (
        <div style={{ marginTop: 14 }}>
          <h2>Spectral band energy distribution</h2>
          <div className="grid-2" style={{ gap: 10 }}>
            <div className="prob">
              <span>Low (&lt;400 Hz)</span>
              <div className="bar">
                <span style={{ width: `${Math.round(Number(feats.low_energy_ratio || 0) * 100)}%` }} />
              </div>
              <span>{Math.round(Number(feats.low_energy_ratio || 0) * 100)}%</span>
            </div>
            <div className="prob">
              <span>Mid (0.4–2 kHz)</span>
              <div className="bar">
                <span style={{ width: `${Math.round(Number(feats.mid_energy_ratio || 0) * 100)}%` }} />
              </div>
              <span>{Math.round(Number(feats.mid_energy_ratio || 0) * 100)}%</span>
            </div>
            <div className="prob">
              <span>High (2–5 kHz)</span>
              <div className="bar">
                <span style={{ width: `${Math.round(Number(feats.high_energy_ratio || 0) * 100)}%` }} />
              </div>
              <span>{Math.round(Number(feats.high_energy_ratio || 0) * 100)}%</span>
            </div>
            <div className="prob">
              <span>Upper (&gt;5 kHz)</span>
              <div className="bar">
                <span style={{ width: `${Math.round(Number(feats.very_high_energy_ratio || 0) * 100)}%` }} />
              </div>
              <span>{Math.round(Number(feats.very_high_energy_ratio || 0) * 100)}%</span>
            </div>
          </div>
        </div>
      )}

      <h2 style={{ marginTop: 14 }}>Measured acoustic evidence</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Feature</th>
            <th>Measured value</th>
            <th>Acoustic reading</th>
          </tr>
        </thead>
        <tbody>
          {(expl.acoustic_evidence || []).map((e: any) => (
            <tr key={e.feature}>
              <td>
                <code>{e.feature}</code>
              </td>
              <td>
                {e.available === false || e.value === "Unavailable" || e.value == null ? (
                  <span className="badge warn">Unavailable</span>
                ) : typeof e.value === "number" ? (
                  Number(e.value).toPrecision(4)
                ) : (
                  String(e.value)
                )}
              </td>
              <td>{e.interpretation}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 style={{ marginTop: 16 }}>Scientific limitations &amp; safeguards</h2>
      <ul className="limitations">
        {(analysis.limitations || expl.limitations || []).map((l: string, i: number) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </div>
  );
}
