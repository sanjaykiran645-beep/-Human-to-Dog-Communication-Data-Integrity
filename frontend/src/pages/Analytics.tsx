import { useEffect, useState } from "react";
import { api } from "../api";

export default function Analytics() {
  const [data, setData] = useState<any>(null);
  const [models, setModels] = useState<any>(null);

  useEffect(() => {
    api("/api/analytics/summary").then(setData).catch(() => {});
    api("/api/models/current").then(setModels).catch(() => {});
  }, []);

  const counts: Record<string, number> = data?.vocalization_counts || {};
  const max = Math.max(1, ...Object.values(counts));

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="kicker">Analytics</div>
          <h1>Your corpus</h1>
          <p>Simple counts from your private analyses. Not a scientific accuracy report.</p>
        </div>
      </div>
      <div className="card">
        <h2>Vocalization frequency</h2>
        {!Object.keys(counts).length && <div className="empty">Analyze recordings to see frequencies.</div>}
        {Object.entries(counts).map(([k, v]) => (
          <div className="prob" key={k}>
            <span>{k}</span>
            <div className="bar">
              <span style={{ width: `${(Number(v) / max) * 100}%` }} />
            </div>
            <span>{v as number}</span>
          </div>
        ))}
        <p className="tiny" style={{ marginTop: 12 }}>
          Abstentions: {data?.abstentions ?? 0} · Recordings: {data?.recordings ?? 0}
        </p>
      </div>
      <div className="card">
        <h2>Model card</h2>
        <p>
          Vocalization model <strong>{models?.vocalization_model?.id}</strong> — {models?.vocalization_model?.type}
        </p>
        <p>
          Independent held-out accuracy: {String(models?.vocalization_model?.independent_held_out_accuracy)} · Target 90%
          met: {String(models?.vocalization_model?.target_met)}
        </p>
        <p>{models?.vocalization_model?.reason_target_unmet}</p>
        <p className="tiny">{models?.synth_model?.id} does not claim dog comprehension.</p>
      </div>
    </div>
  );
}
