import { useEffect, useState } from "react";
import { api } from "../api";
import type { Dog } from "../api";

export default function Analytics() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [recs, setRecs] = useState<any[]>([]);
  const [comms, setComms] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<Dog[]>("/api/dogs").catch(() => []),
      api<any[]>("/api/recordings").catch(() => []),
      api<any[]>("/api/communicate").catch(() => []),
    ]).then(([d, r, c]) => {
      const localRecs = JSON.parse(localStorage.getItem("cs_saved_history_v1") || "[]");
      const seen = new Set<string>();
      const mergedRecs: any[] = [];
      for (const item of [...(r || []), ...localRecs]) {
        if (item?.id && !seen.has(item.id)) {
          seen.add(item.id);
          mergedRecs.push(item);
        }
      }
      setDogs(d || []);
      setRecs(mergedRecs);
      setComms(c || []);
      setLoading(false);
    });
  }, []);

  const counts: Record<string, number> = { BARK: 0, WHINE: 0, GROWL: 0, HOWL: 0, YIP: 0 };
  let totalF0 = 0;
  let f0Count = 0;

  for (const r of recs) {
    const v = String(r.analysis?.vocalization || "bark").toUpperCase();
    counts[v] = (counts[v] || 0) + 1;
    const f0 = Number(r.analysis?.features?.f0_mean || 0);
    if (f0 > 0) {
      totalF0 += f0;
      f0Count++;
    }
  }

  const avgF0 = f0Count > 0 ? Math.round(totalF0 / f0Count) : 325;
  const maleCount = dogs.filter((d) => (d.sex || "").toLowerCase() !== "female").length;
  const femaleCount = dogs.filter((d) => (d.sex || "").toLowerCase() === "female").length;
  const totalAnalyses = recs.length;

  return (
    <div className="stack-lg" style={{ maxWidth: 1040, margin: "0 auto" }}>
      <div className="card stack" style={{ padding: 28, borderRadius: 20 }}>
        <h2 style={{ margin: 0, fontSize: 24 }}>Bioacoustic & Behavioral Analytics</h2>
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          Live telemetry across your saved dog analyses, vocal frequency distributions, and gender-calibrated profiles.
        </p>

        {loading ? (
          <p className="muted">Calculating analytics...</p>
        ) : (
          <>
            <div className="grid-4" style={{ gap: 14, marginTop: 8 }}>
              <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
                <div className="muted" style={{ fontSize: 12 }}>Total Saved Analyses</div>
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>{totalAnalyses}</div>
              </div>
              <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
                <div className="muted" style={{ fontSize: 12 }}>Active Dog Profiles</div>
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>
                  {dogs.length} <span style={{ fontSize: 13, fontWeight: 600 }}>({maleCount}♂ / {femaleCount}♀)</span>
                </div>
              </div>
              <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
                <div className="muted" style={{ fontSize: 12 }}>Average Vocal Pitch (F0)</div>
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>{avgF0} Hz</div>
              </div>
              <div style={{ padding: 18, borderRadius: 14, background: "rgba(0,0,0,0.03)" }}>
                <div className="muted" style={{ fontSize: 12 }}>Translator Signals Sent</div>
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>
                  {comms.length + Number(localStorage.getItem("cs_comm_count") || 0)}
                </div>
              </div>
            </div>

            <div className="card" style={{ padding: 22, borderRadius: 16, marginTop: 12 }}>
              <h3 style={{ margin: "0 0 14px 0", fontSize: 18 }}>Vocalization Class Breakdown</h3>
              <div className="stack" style={{ gap: 12 }}>
                {Object.entries(counts).map(([label, cnt]) => {
                  const pct = totalAnalyses > 0 ? Math.round((cnt / totalAnalyses) * 100) : 0;
                  return (
                    <div key={label}>
                      <div className="row" style={{ justifyContent: "space-between", fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
                        <span>{label}</span>
                        <span>{cnt} clips ({pct}%)</span>
                      </div>
                      <div style={{ width: "100%", height: 10, borderRadius: 999, background: "rgba(0,0,0,0.08)", overflow: "hidden" }}>
                        <div style={{ width: `${Math.max(pct, cnt > 0 ? 8 : 0)}%`, height: "100%", background: "#059669", borderRadius: 999 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
