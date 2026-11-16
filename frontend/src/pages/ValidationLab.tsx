import { useEffect, useState } from "react";
import { api, getBackendUrl, getToken } from "../api";
import type { BehaviouralTrial, ExperimentalCue, ExperimentalMetrics, StudyParticipant, TrialSchedule } from "../api";

export default function ValidationLab() {
  const [tab, setTab] = useState<"participants" | "cues" | "schedule" | "trials" | "metrics">("metrics");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data states
  const [participants, setParticipants] = useState<StudyParticipant[]>([]);
  const [cues, setCues] = useState<ExperimentalCue[]>([]);
  const [trials, setTrials] = useState<BehaviouralTrial[]>([]);
  const [metrics, setMetrics] = useState<ExperimentalMetrics | null>(null);

  // Form states: Participant
  const [pseudonym, setPseudonym] = useState("");
  const [pBreed, setPBreed] = useState("Border Collie");
  const [pSex, setPSex] = useState("female");
  const [pAge, setPAge] = useState("3.0");
  const [pFamiliarity, setPFamiliarity] = useState("emerging");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [welfareConfirmed, setWelfareConfirmed] = useState(false);
  const [trainingNotes, setTrainingNotes] = useState("");

  // Form states: Cue Setup
  const [cueLabel, setCueLabel] = useState("Standard Recall Cue");
  const [cueIntent, setCueIntent] = useState("come");
  const [cueActionDesc, setCueActionDesc] = useState("Dog approaches handler position within 2.5s without physical gesture or verbal command");
  const [cueCategory, setCueCategory] = useState("learned_action");
  const [cueF0, setCueF0] = useState(420);
  const [cueSpl, setCueSpl] = useState(65.0);
  const [cueDuration, setCueDuration] = useState(1.5);

  // Form states: Schedule Setup
  const [selectedParticipantId, setSelectedParticipantId] = useState("");
  const [selectedCueId, setSelectedCueId] = useState("");
  const [sessionNum, setSessionNum] = useState(1);
  const [randomSeed, setRandomSeed] = useState(Math.floor(Math.random() * 899999 + 100000));
  const [totalScheduleTrials, setTotalScheduleTrials] = useState(10);
  const [activeSchedule, setActiveSchedule] = useState<TrialSchedule | null>(null);

  // Form states: Trial Logging
  const [currentSessionId, setCurrentSessionId] = useState("SESS-01");
  const [trialOrder, setTrialOrder] = useState(1);
  const [selectedCondition, setSelectedCondition] = useState("target_engine_b_cue");
  const [measuredSpl, setMeasuredSpl] = useState(64.0);
  const [preCueState, setPreCueState] = useState("resting");
  const [orientLatency, setOrientLatency] = useState<string>("350");
  const [actionLatency, setActionLatency] = useState<string>("1400");
  const [trialOutcome, setTrialOutcome] = useState("correct_target_action");
  const [freezingObserved, setFreezingObserved] = useState(false);
  const [abortTriggered, setAbortTriggered] = useState(false);
  const [abortReason, setAbortReason] = useState("");
  const [stressLipLicking, setStressLipLicking] = useState(false);
  const [stressWhaleEye, setStressWhaleEye] = useState(false);
  const [stressPacing, setStressPacing] = useState(false);

  // Review state
  const [reviewTrialId, setReviewTrialId] = useState<string | null>(null);
  const [reviewerName, setReviewerName] = useState("Dr. Ethologist");
  const [reviewOutcome, setReviewOutcome] = useState("correct_target_action");
  const [reviewNotes, setReviewNotes] = useState("");

  const backendUrl = getBackendUrl() || "";

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setErr(null);
    try {
      const [pRes, cRes, tRes, mRes] = await Promise.all([
        api<StudyParticipant[]>("/api/experiments/participants").catch(() => []),
        api<ExperimentalCue[]>("/api/experiments/cues").catch(() => []),
        api<BehaviouralTrial[]>("/api/experiments/trials").catch(() => []),
        api<ExperimentalMetrics>("/api/experiments/metrics").catch(() => null),
      ]);
      setParticipants(pRes || []);
      setCues(cRes || []);
      setTrials(tRes || []);
      setMetrics(mRes);
      if (pRes?.length > 0 && !selectedParticipantId) {
        setSelectedParticipantId(pRes[0].id);
      }
      if (cRes?.length > 0 && !selectedCueId) {
        setSelectedCueId(cRes[0].id);
      }
    } catch (e: any) {
      setErr(e.message || "Failed to load experimental telemetry");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegisterParticipant(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSuccessMsg(null);
    if (!consentConfirmed || !welfareConfirmed) {
      setErr("Both owner consent and animal welfare screening must be affirmed.");
      return;
    }
    try {
      await api("/api/experiments/participants", {
        method: "POST",
        body: JSON.stringify({
          pseudonym,
          breed: pBreed,
          sex: pSex,
          age_years: parseFloat(pAge) || 3.0,
          familiarity_with_target_action: pFamiliarity,
          owner_consent_confirmed: true,
          welfare_review_confirmed: true,
          training_history_notes: trainingNotes,
        }),
      });
      setSuccessMsg(`Participant ${pseudonym} successfully enrolled.`);
      setPseudonym("");
      setConsentConfirmed(false);
      setWelfareConfirmed(false);
      await loadAll();
    } catch (err: any) {
      setErr(err.message || "Registration failed");
    }
  }

  async function handleCreateCue(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSuccessMsg(null);
    if (cueSpl > 75.0) {
      setErr("Volume level exceeds the 75.0 dBA veterinary animal welfare hard cap.");
      return;
    }
    try {
      await api("/api/experiments/cues", {
        method: "POST",
        body: JSON.stringify({
          cue_label: cueLabel,
          target_intention: cueIntent,
          target_action_description: cueActionDesc,
          action_category: cueCategory,
          f0_hz: cueF0,
          peak_spl_dba: cueSpl,
          duration_sec: cueDuration,
          synthesis_method: "method_d_parametric_glottal",
        }),
      });
      setSuccessMsg(`Experimental cue '${cueLabel}' registered with verifiable SHA-256.`);
      await loadAll();
    } catch (err: any) {
      setErr(err.message || "Cue registration failed");
    }
  }

  async function handleGenerateSchedule(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSuccessMsg(null);
    try {
      const res = await api<TrialSchedule>("/api/experiments/schedules", {
        method: "POST",
        body: JSON.stringify({
          participant_id: selectedParticipantId,
          cue_id: selectedCueId,
          session_number: sessionNum,
          randomization_seed: randomSeed,
          total_trials: totalScheduleTrials,
          include_familiar_command: true,
        }),
      });
      setActiveSchedule(res);
      setSuccessMsg(`Generated Latin square counterbalanced schedule (Seed: ${randomSeed}).`);
    } catch (err: any) {
      setErr(err.message || "Failed to generate schedule");
    }
  }

  async function handleLogTrial(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSuccessMsg(null);
    if (measuredSpl > 75.0) {
      setErr("Volume level exceeds 75.0 dBA veterinary animal welfare hard cap.");
      return;
    }
    const welfareFlags: string[] = [];
    if (stressLipLicking) welfareFlags.push("lip_licking");
    if (stressWhaleEye) welfareFlags.push("whale_eye");
    if (stressPacing) welfareFlags.push("pacing");

    try {
      await api("/api/experiments/trials", {
        method: "POST",
        body: JSON.stringify({
          participant_id: selectedParticipantId,
          session_id: currentSessionId,
          trial_order_in_session: trialOrder,
          experimental_condition: selectedCondition,
          cue_id: selectedCueId || undefined,
          schedule_id: activeSchedule?.id || undefined,
          pre_cue_state: preCueState,
          measured_spl_dba: measuredSpl,
          latency_to_orient_ms: orientLatency ? parseFloat(orientLatency) : null,
          latency_to_action_ms: actionLatency ? parseFloat(actionLatency) : null,
          outcome_category: abortTriggered ? "welfare_terminated" : trialOutcome,
          freezing_observed: freezingObserved,
          abort_triggered: abortTriggered,
          abort_reason: abortTriggered ? (abortReason || "Distress indicators observed") : null,
          welfare_flags: welfareFlags,
          is_valid: true,
        }),
      });
      setSuccessMsg(`Trial #${trialOrder} successfully recorded.`);
      setTrialOrder((prev) => prev + 1);
      setFreezingObserved(false);
      setAbortTriggered(false);
      setAbortReason("");
      setStressLipLicking(false);
      setStressWhaleEye(false);
      setStressPacing(false);
      await loadAll();
    } catch (err: any) {
      setErr(err.message || "Failed to record trial");
    }
  }

  async function handleReviewSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!reviewTrialId) return;
    setErr(null);
    setSuccessMsg(null);
    try {
      await api(`/api/experiments/trials/${reviewTrialId}/reviews`, {
        method: "POST",
        body: JSON.stringify({
          reviewer_name: reviewerName,
          is_blind_to_condition: true,
          scored_outcome_category: reviewOutcome,
          review_notes: reviewNotes,
        }),
      });
      setSuccessMsg("Independent blind video review recorded.");
      setReviewTrialId(null);
      await loadAll();
    } catch (err: any) {
      setErr(err.message || "Review submission failed");
    }
  }

  function triggerExport(format: "json" | "csv") {
    const token = getToken();
    const url = `${backendUrl}/api/experiments/export?format=${format}`;
    const a = document.createElement("a");
    a.href = url;
    // fetch with auth to download blob
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((res) => res.blob())
      .then((blob) => {
        const u = window.URL.createObjectURL(blob);
        a.href = u;
        a.download = `caninesense_pseudonymous_export.${format}`;
        a.click();
        window.URL.revokeObjectURL(u);
      })
      .catch((e) => setErr(e.message || "Export download failed"));
  }

  return (
    <div className="stack-lg" style={{ maxWidth: 1040, margin: "0 auto", paddingBottom: 60 }}>
      {/* Title & Scientific Transparency Notice */}
      <div className="card stack" style={{ padding: 28, borderRadius: 20 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div className="row" style={{ gap: 8, alignItems: "center", marginBottom: 6 }}>
              <span style={{ background: "#059669", color: "#fff", padding: "4px 10px", borderRadius: 999, fontSize: 11, fontWeight: 800 }}>
                ENGINE B
              </span>
              <span style={{ background: "#0284c7", color: "#fff", padding: "4px 10px", borderRadius: 999, fontSize: 11, fontWeight: 800 }}>
                EVIDENCE LAB
              </span>
              <span style={{ background: "#475569", color: "#fff", padding: "4px 10px", borderRadius: 999, fontSize: 11, fontWeight: 800 }}>
                PROTOCOL v2.0
              </span>
            </div>
            <h2 style={{ margin: "0 0 6px 0", fontSize: 24 }}>Behavioural Validation & Controlled Field Trials</h2>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Scientific stimulus-response framework to test whether dogs learn, distinguish, and execute intended actions to generated canine-inspired vocal cues.
            </p>
          </div>

          <div className="row" style={{ gap: 8 }}>
            <button className="btn" type="button" onClick={() => triggerExport("json")} style={{ fontSize: 13 }}>
              Export Research JSON
            </button>
            <button className="btn" type="button" onClick={() => triggerExport("csv")} style={{ fontSize: 13 }}>
              Export CSV
            </button>
          </div>
        </div>

        {/* Evidence Status Grid */}
        <div
          style={{
            marginTop: 16,
            padding: "16px 20px",
            borderRadius: 14,
            background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
            color: "#e2e8f0",
            fontSize: 12.5,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
            <div>
              <div style={{ color: "#38bdf8", fontWeight: 700, textTransform: "uppercase", fontSize: 11 }}>Cue Synthesis</div>
              <div style={{ fontWeight: 600, marginTop: 2 }}>FUNCTIONALLY IMPLEMENTED</div>
              <div style={{ color: "#94a3b8", fontSize: 11 }}>Rosenberg Glottal + Formant Resonators</div>
            </div>
            <div>
              <div style={{ color: "#f59e0b", fontWeight: 700, textTransform: "uppercase", fontSize: 11 }}>Canine Comprehension</div>
              <div style={{ fontWeight: 600, marginTop: 2 }}>REQUIRES CONTROLLED TRIALS</div>
              <div style={{ color: "#94a3b8", fontSize: 11 }}>No Innate Semantic Meaning Assumed</div>
            </div>
            <div>
              <div style={{ color: "#10b981", fontWeight: 700, textTransform: "uppercase", fontSize: 11 }}>Acoustic Safety Limit</div>
              <div style={{ fontWeight: 600, marginTop: 2 }}>STRICTLY CAPPED &lt; 75 dBA</div>
              <div style={{ color: "#94a3b8", fontSize: 11 }}>Veterinary SPL Hard Cap Active</div>
            </div>
            <div>
              <div style={{ color: "#ef4444", fontWeight: 700, textTransform: "uppercase", fontSize: 11 }}>Ethological Safeguard</div>
              <div style={{ fontWeight: 600, marginTop: 2 }}>SILENCE ≠ CALMNESS</div>
              <div style={{ color: "#94a3b8", fontSize: 11 }}>Freezing Is An Inhibition Response</div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="row" style={{ gap: 8, marginTop: 16, borderBottom: "1px solid rgba(0,0,0,0.1)", paddingBottom: 10, overflowX: "auto" }}>
          {[
            { id: "metrics", label: "Scientific Telemetry & Metrics" },
            { id: "trials", label: "Trial Logger & Controls" },
            { id: "schedule", label: "Counterbalanced Schedules" },
            { id: "cues", label: "Cue & Action Taxonomy" },
            { id: "participants", label: "Study Participants & Consent" },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? "btn-primary" : "btn"}
              style={{ padding: "6px 14px", fontSize: 13, borderRadius: 999 }}
              onClick={() => setTab(t.id as any)}
            >
              {t.label}
            </button>
          ))}
          {loading && <span style={{ fontSize: 12, color: "#64748b", alignSelf: "center", marginLeft: 8 }}>Updating...</span>}
        </div>
      </div>

      {err && <div className="card" style={{ padding: 14, background: "#fee2e2", color: "#991b1b", borderRadius: 12 }}>{err}</div>}
      {successMsg && <div className="card" style={{ padding: 14, background: "#dcfce7", color: "#166534", borderRadius: 12 }}>{successMsg}</div>}

      {/* TAB 1: Scientific Telemetry & Metrics */}
      {tab === "metrics" && (
        <div className="stack">
          <div className="grid-3" style={{ gap: 16 }}>
            <div className="card stack" style={{ padding: 22, borderRadius: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>Target Intention Congruence</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: "#0f172a" }}>
                {metrics ? `${(metrics.target_cue_metrics.correct_action_rate * 100).toFixed(1)}%` : "0.0%"}
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Target threshold: &ge; 75% for verified communication
              </div>
            </div>

            <div className="card stack" style={{ padding: 22, borderRadius: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>Acoustic Discrimination Ratio</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: (metrics?.discrimination_and_controls?.acoustic_discrimination_ratio || 0) > 0.5 ? "#059669" : "#d97706" }}>
                {metrics ? metrics.discrimination_and_controls.acoustic_discrimination_ratio.toFixed(2) : "0.00"}
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Range: [-1.0, 1.0] (Target vs C1–C4 Control Sounds)
              </div>
            </div>

            <div className="card stack" style={{ padding: 22, borderRadius: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", color: "#64748b" }}>Attention-Only Rate</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: "#2563eb" }}>
                {metrics ? `${(metrics.target_cue_metrics.attention_only_rate * 100).toFixed(1)}%` : "0.0%"}
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>
                Head turn / orient without action (Not comprehension)
              </div>
            </div>
          </div>

          {/* Sample Size & Controls Breakdown */}
          <div className="card stack" style={{ padding: 24, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 17 }}>Trial Controls & False-Positive Breakdown</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: "8px 12px" }}>Condition</th>
                    <th style={{ padding: "8px 12px" }}>Stimulus Type</th>
                    <th style={{ padding: "8px 12px" }}>Presentations</th>
                    <th style={{ padding: "8px 12px" }}>Target Action False-Positives</th>
                    <th style={{ padding: "8px 12px" }}>Orienting Rate</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "10px 12px", fontWeight: 700, color: "#059669" }}>Target Engine B Cue</td>
                    <td style={{ padding: "10px 12px" }}>Canine-Inspired Prosody</td>
                    <td style={{ padding: "10px 12px" }}>{metrics?.target_cue_metrics.target_presentations || 0}</td>
                    <td style={{ padding: "10px 12px" }}>{metrics ? `${(metrics.target_cue_metrics.correct_action_rate * 100).toFixed(1)}% (Target Action)` : "0%"}</td>
                    <td style={{ padding: "10px 12px" }}>{metrics ? `${((metrics.target_cue_metrics.correct_action_rate + metrics.target_cue_metrics.attention_only_rate) * 100).toFixed(1)}%` : "0%"}</td>
                  </tr>
                  {metrics?.discrimination_and_controls.control_breakdown &&
                    Object.entries(metrics.discrimination_and_controls.control_breakdown).map(([k, v]: [string, any]) => (
                      <tr key={k} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "10px 12px", fontWeight: 600 }}>{k.replace(/_/g, " ")}</td>
                        <td style={{ padding: "10px 12px" }}>
                          {k.includes("silent") ? "0.0 Amplitude Baseline" : k.includes("tone") ? "500 Hz Pure Sine Tone" : k.includes("noise") ? "Formant-Shaped Pink Noise" : "Familiar Voice Audio"}
                        </td>
                        <td style={{ padding: "10px 12px" }}>{v.total_presentations}</td>
                        <td style={{ padding: "10px 12px" }}>{(v.false_positive_action_rate * 100).toFixed(1)}%</td>
                        <td style={{ padding: "10px 12px" }}>{(v.orienting_rate * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Welfare & Safety Compliance */}
          <div className="card stack" style={{ padding: 24, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 8px 0", fontSize: 17 }}>Veterinary Welfare & Ethical Compliance</h3>
            <div className="row" style={{ gap: 20, flexWrap: "wrap", fontSize: 13.5 }}>
              <div>
                <strong>Welfare Aborts:</strong> {metrics?.animal_welfare_and_safety.welfare_aborts_count || 0} (
                {metrics ? `${(metrics.animal_welfare_and_safety.welfare_abort_rate * 100).toFixed(1)}%` : "0%"})
              </div>
              <div>
                <strong>Freezing / Tonic Immobility:</strong> {metrics?.animal_welfare_and_safety.freezing_episodes_count || 0} (
                {metrics ? `${(metrics.animal_welfare_and_safety.freezing_rate * 100).toFixed(1)}%` : "0%"})
              </div>
              <div>
                <strong>Volume Safety:</strong> Max Cap &le; 75.0 dBA SPL (Active)
              </div>
            </div>
            <div style={{ marginTop: 8, fontSize: 12.5, color: "#475569" }}>
              {metrics?.animal_welfare_and_safety.safety_assessment || "No trials recorded yet."}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Trial Logger & Controls */}
      {tab === "trials" && (
        <div className="stack">
          <div className="card stack" style={{ padding: 26, borderRadius: 18 }}>
            <h3 style={{ margin: "0 0 14px 0", fontSize: 18 }}>Log Behavioural Trial Observation</h3>
            <form onSubmit={handleLogTrial} className="stack">
              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Participant Pseudonym</label>
                  <select
                    value={selectedParticipantId}
                    onChange={(e) => setSelectedParticipantId(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    {participants.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.pseudonym} ({p.breed || "unknown"})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Session ID</label>
                  <input
                    type="text"
                    value={currentSessionId}
                    onChange={(e) => setCurrentSessionId(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Trial Order in Session</label>
                  <input
                    type="number"
                    min={1}
                    max={24}
                    value={trialOrder}
                    onChange={(e) => setTrialOrder(parseInt(e.target.value) || 1)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
              </div>

              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Trial Condition</label>
                  <select
                    value={selectedCondition}
                    onChange={(e) => setSelectedCondition(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    <option value="target_engine_b_cue">Target Engine B Cue</option>
                    <option value="control_silent_baseline">C1: Silent Baseline (0.0 SPL)</option>
                    <option value="control_neutral_pure_tone">C2: Neutral Pure Tone (500 Hz)</option>
                    <option value="control_spectrally_matched_noise">C3: Spectrally Matched Noise</option>
                    <option value="control_familiar_human_verbal_command">C4: Familiar Owner Command</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Measured SPL (dBA)</label>
                  <input
                    type="number"
                    step="0.5"
                    max={75.0}
                    value={measuredSpl}
                    onChange={(e) => setMeasuredSpl(parseFloat(e.target.value) || 64.0)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                  <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Must not exceed 75.0 dBA</div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Pre-Cue Baseline State</label>
                  <select
                    value={preCueState}
                    onChange={(e) => setPreCueState(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    <option value="resting">Resting / Lying Down</option>
                    <option value="exploring">Exploring / Sniffing Ground</option>
                    <option value="standing_relaxed">Standing Relaxed</option>
                    <option value="attentive">Attentive to Environment</option>
                  </select>
                </div>
              </div>

              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Latency to Orient (ms)</label>
                  <input
                    type="number"
                    value={orientLatency}
                    onChange={(e) => setOrientLatency(e.target.value)}
                    placeholder="e.g. 350"
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Latency to Action (ms)</label>
                  <input
                    type="number"
                    value={actionLatency}
                    onChange={(e) => setActionLatency(e.target.value)}
                    placeholder="e.g. 1400"
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Observed Outcome Category</label>
                  <select
                    value={trialOutcome}
                    onChange={(e) => setTrialOutcome(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8, fontWeight: 700 }}
                  >
                    <option value="correct_target_action">1. Correct Target Action</option>
                    <option value="attention_only">2. Attention / Orientation Only</option>
                    <option value="incorrect_action">3. Incorrect Action</option>
                    <option value="alternative_behaviour">4. Alternative Behaviour</option>
                    <option value="no_observable_response">5. No Observable Response</option>
                    <option value="invalid_or_confounded">6. Invalid / Confounded Trial</option>
                    <option value="welfare_terminated">7. Welfare-Terminated Trial</option>
                  </select>
                </div>
              </div>

              {/* Welfare Checklist */}
              <div style={{ padding: 14, borderRadius: 12, background: "rgba(0,0,0,0.03)", border: "1px solid rgba(0,0,0,0.08)" }}>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8, color: "#0f172a" }}>
                  Animal Welfare & Behavioural State Observations
                </div>
                <div className="row" style={{ gap: 16, flexWrap: "wrap", fontSize: 13 }}>
                  <label className="row" style={{ gap: 6, cursor: "pointer" }}>
                    <input type="checkbox" checked={stressLipLicking} onChange={(e) => setStressLipLicking(e.target.checked)} />
                    Lip Licking / Yawning
                  </label>
                  <label className="row" style={{ gap: 6, cursor: "pointer" }}>
                    <input type="checkbox" checked={stressWhaleEye} onChange={(e) => setStressWhaleEye(e.target.checked)} />
                    Whale Eye / Tense Gaze
                  </label>
                  <label className="row" style={{ gap: 6, cursor: "pointer" }}>
                    <input type="checkbox" checked={stressPacing} onChange={(e) => setStressPacing(e.target.checked)} />
                    Pacing / Avoidance
                  </label>
                  <label className="row" style={{ gap: 6, cursor: "pointer", color: "#b91c1c", fontWeight: 700 }}>
                    <input type="checkbox" checked={freezingObserved} onChange={(e) => setFreezingObserved(e.target.checked)} />
                    Freezing / Immobility (Not Calm)
                  </label>
                  <label className="row" style={{ gap: 6, cursor: "pointer", color: "#dc2626", fontWeight: 700 }}>
                    <input type="checkbox" checked={abortTriggered} onChange={(e) => setAbortTriggered(e.target.checked)} />
                    Trigger Welfare Abort
                  </label>
                </div>
              </div>

              <div className="row" style={{ justifyContent: "flex-end", gap: 10 }}>
                <button type="submit" className="btn-primary" style={{ padding: "10px 24px" }}>
                  Record Trial #{trialOrder}
                </button>
              </div>
            </form>
          </div>

          {/* Recent Trials Table */}
          <div className="card stack" style={{ padding: 24, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 17 }}>Recent Behavioural Trials ({trials.length})</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: 8 }}>Order</th>
                    <th style={{ padding: 8 }}>Session</th>
                    <th style={{ padding: 8 }}>Condition</th>
                    <th style={{ padding: 8 }}>Outcome</th>
                    <th style={{ padding: 8 }}>Orient ms</th>
                    <th style={{ padding: 8 }}>Action ms</th>
                    <th style={{ padding: 8 }}>SPL dBA</th>
                    <th style={{ padding: 8 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {trials.slice(0, 15).map((t) => (
                    <tr key={t.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: 8 }}>#{t.trial_order}</td>
                      <td style={{ padding: 8 }}>{t.session_id}</td>
                      <td style={{ padding: 8 }}>{t.experimental_condition.replace(/_/g, " ")}</td>
                      <td style={{ padding: 8, fontWeight: 700, color: t.outcome_category === "correct_target_action" ? "#059669" : t.outcome_category === "welfare_terminated" ? "#dc2626" : "#475569" }}>
                        {t.outcome_category.replace(/_/g, " ")}
                      </td>
                      <td style={{ padding: 8 }}>{t.latency_to_orient_ms ? `${t.latency_to_orient_ms} ms` : "-"}</td>
                      <td style={{ padding: 8 }}>{t.latency_to_action_ms ? `${t.latency_to_action_ms} ms` : "-"}</td>
                      <td style={{ padding: 8 }}>{t.measured_spl_dba} dBA</td>
                      <td style={{ padding: 8 }}>
                        <button
                          type="button"
                          className="btn"
                          style={{ padding: "3px 8px", fontSize: 11 }}
                          onClick={() => setReviewTrialId(t.id)}
                        >
                          Review Blind
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Review Modal */}
      {reviewTrialId && (
        <div className="card stack" style={{ padding: 24, borderRadius: 16, border: "2px solid #0284c7", background: "#f8fafc" }}>
          <h3 style={{ margin: 0, fontSize: 17 }}>Independent Blind Video Review</h3>
          <p className="muted" style={{ margin: "4px 0 12px 0", fontSize: 13 }}>
            Scoring trial {reviewTrialId.slice(0, 8)} independently from multi-angle video recording.
          </p>
          <form onSubmit={handleReviewSubmit} className="stack">
            <div className="grid-2" style={{ gap: 14 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Reviewer Identifier</label>
                <input
                  type="text"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  style={{ width: "100%", padding: 8, borderRadius: 8 }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Independent Outcome Category</label>
                <select
                  value={reviewOutcome}
                  onChange={(e) => setReviewOutcome(e.target.value)}
                  style={{ width: "100%", padding: 8, borderRadius: 8, fontWeight: 700 }}
                >
                  <option value="correct_target_action">1. Correct Target Action</option>
                  <option value="attention_only">2. Attention / Orientation Only</option>
                  <option value="incorrect_action">3. Incorrect Action</option>
                  <option value="alternative_behaviour">4. Alternative Behaviour</option>
                  <option value="no_observable_response">5. No Observable Response</option>
                  <option value="invalid_or_confounded">6. Invalid / Confounded Trial</option>
                  <option value="welfare_terminated">7. Welfare-Terminated Trial</option>
                </select>
              </div>
            </div>
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Review Notes & Behavioral Criteria</label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Observed video markers confirming or disconfirming the response..."
                style={{ width: "100%", padding: 8, borderRadius: 8, minHeight: 60 }}
              />
            </div>
            <div className="row" style={{ justifyContent: "flex-end", gap: 10 }}>
              <button type="button" className="btn" onClick={() => setReviewTrialId(null)}>Cancel</button>
              <button type="submit" className="btn-primary">Submit Independent Review</button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 3: Counterbalanced Schedules */}
      {tab === "schedule" && (
        <div className="stack">
          <div className="card stack" style={{ padding: 26, borderRadius: 18 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 18 }}>Generate Latin Square Counterbalanced Schedule</h3>
            <form onSubmit={handleGenerateSchedule} className="stack">
              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Participant</label>
                  <select
                    value={selectedParticipantId}
                    onChange={(e) => setSelectedParticipantId(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    {participants.map((p) => (
                      <option key={p.id} value={p.id}>{p.pseudonym}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Target Cue</label>
                  <select
                    value={selectedCueId}
                    onChange={(e) => setSelectedCueId(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    {cues.map((c) => (
                      <option key={c.id} value={c.id}>{c.cue_label} ({c.target_intention})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Randomization Seed</label>
                  <input
                    type="number"
                    value={randomSeed}
                    onChange={(e) => setRandomSeed(parseInt(e.target.value) || 12345)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
              </div>

              <div className="grid-2" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Session Number</label>
                  <input
                    type="number"
                    min={1}
                    value={sessionNum}
                    onChange={(e) => setSessionNum(parseInt(e.target.value) || 1)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Total Trials in Schedule</label>
                  <input
                    type="number"
                    min={4}
                    max={24}
                    step={2}
                    value={totalScheduleTrials}
                    onChange={(e) => setTotalScheduleTrials(parseInt(e.target.value) || 10)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
              </div>

              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button type="submit" className="btn-primary" style={{ padding: "10px 22px" }}>
                  Generate Balanced Sequence
                </button>
              </div>
            </form>
          </div>

          {activeSchedule && (
            <div className="card stack" style={{ padding: 24, borderRadius: 16, background: "#f8fafc" }}>
              <h3 style={{ margin: "0 0 8px 0", fontSize: 17 }}>Planned Trial Schedule (Seed: {activeSchedule.randomization_seed})</h3>
              <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13.5, lineHeight: 1.8 }}>
                {activeSchedule.planned_conditions.map((cond, idx) => (
                  <li key={idx}>
                    <strong style={{ color: cond === "target_engine_b_cue" ? "#059669" : "#475569" }}>
                      {cond.replace(/_/g, " ").toUpperCase()}
                    </strong>
                    {" — "}
                    {cond === "target_engine_b_cue"
                      ? "Play generated Engine B cue"
                      : cond.includes("silent")
                      ? "2.5s unmodulated silence"
                      : cond.includes("tone")
                      ? "500 Hz pure sine tone"
                      : cond.includes("noise")
                      ? "Formant-shaped pink noise"
                      : "Familiar owner voice command"}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Cue Setup */}
      {tab === "cues" && (
        <div className="stack">
          <div className="card stack" style={{ padding: 26, borderRadius: 18 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 18 }}>Configure Reproducible Experimental Cue</h3>
            <form onSubmit={handleCreateCue} className="stack">
              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Cue Label</label>
                  <input
                    type="text"
                    value={cueLabel}
                    onChange={(e) => setCueLabel(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Target Intention</label>
                  <select
                    value={cueIntent}
                    onChange={(e) => setCueIntent(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    <option value="come">Come / Recall</option>
                    <option value="play">Play / Retrieve</option>
                    <option value="stop">Stop / Boundary</option>
                    <option value="calm">Calm / Settle</option>
                    <option value="stay">Stay / Hold</option>
                    <option value="positive_reinforcement">Positive Reward</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Action Category (Taxonomy)</label>
                  <select
                    value={cueCategory}
                    onChange={(e) => setCueCategory(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    <option value="attention">1. Attention & Orienting</option>
                    <option value="learned_action">2. Learned Motor Action (Recall/Stay/Stop)</option>
                    <option value="object_directed">3. Object-Directed (Retrieve/Drop)</option>
                    <option value="location_directed">4. Location-Directed (Place/Mat)</option>
                    <option value="multi_step">5. Multi-Step Chain (Experimental)</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Target Action Description</label>
                <textarea
                  value={cueActionDesc}
                  onChange={(e) => setCueActionDesc(e.target.value)}
                  style={{ width: "100%", padding: 8, borderRadius: 8, minHeight: 60 }}
                />
              </div>

              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Fundamental Frequency (Hz)</label>
                  <input
                    type="number"
                    value={cueF0}
                    onChange={(e) => setCueF0(parseFloat(e.target.value) || 350)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Peak SPL (dBA) &le; 75.0</label>
                  <input
                    type="number"
                    step="0.5"
                    max={75.0}
                    value={cueSpl}
                    onChange={(e) => setCueSpl(parseFloat(e.target.value) || 65.0)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Duration (sec)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={cueDuration}
                    onChange={(e) => setCueDuration(parseFloat(e.target.value) || 1.5)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
              </div>

              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button type="submit" className="btn-primary" style={{ padding: "10px 22px" }}>
                  Register Experimental Cue
                </button>
              </div>
            </form>
          </div>

          <div className="card stack" style={{ padding: 24, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 17 }}>Registered Experimental Cues ({cues.length})</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: 8 }}>Label</th>
                    <th style={{ padding: 8 }}>Target Intention</th>
                    <th style={{ padding: 8 }}>Taxonomy Category</th>
                    <th style={{ padding: 8 }}>F0 (Hz)</th>
                    <th style={{ padding: 8 }}>SPL (dBA)</th>
                    <th style={{ padding: 8 }}>SHA-256</th>
                  </tr>
                </thead>
                <tbody>
                  {cues.map((c) => (
                    <tr key={c.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: 8, fontWeight: 700 }}>{c.cue_label}</td>
                      <td style={{ padding: 8 }}>{c.target_intention}</td>
                      <td style={{ padding: 8 }}>{c.action_category}</td>
                      <td style={{ padding: 8 }}>{c.f0_hz} Hz</td>
                      <td style={{ padding: 8 }}>{c.peak_spl_dba} dBA</td>
                      <td style={{ padding: 8, fontFamily: "monospace", fontSize: 11 }}>{c.sha256.slice(0, 12)}...</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: Participant Enrolment */}
      {tab === "participants" && (
        <div className="stack">
          <div className="card stack" style={{ padding: 26, borderRadius: 18 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 18 }}>Enrol Study Participant Dog</h3>
            <form onSubmit={handleRegisterParticipant} className="stack">
              <div className="grid-3" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Participant Pseudonym</label>
                  <input
                    type="text"
                    value={pseudonym}
                    onChange={(e) => setPseudonym(e.target.value)}
                    placeholder="e.g. DOG-STUDY-01"
                    required
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Breed (or Mixed / Unknown)</label>
                  <input
                    type="text"
                    value={pBreed}
                    onChange={(e) => setPBreed(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Biological Sex</label>
                  <select
                    value={pSex}
                    onChange={(e) => setPSex(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </div>
              </div>

              <div className="grid-2" style={{ gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Age (Years)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={pAge}
                    onChange={(e) => setPAge(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Target Action Familiarity</label>
                  <select
                    value={pFamiliarity}
                    onChange={(e) => setPFamiliarity(e.target.value)}
                    style={{ width: "100%", padding: 8, borderRadius: 8 }}
                  >
                    <option value="naive">Naive (Unfamiliar)</option>
                    <option value="emerging">Emerging (Some Practice)</option>
                    <option value="proficient">Proficient (Reliable Response)</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4 }}>Prior Training & Environmental Context</label>
                <textarea
                  value={trainingNotes}
                  onChange={(e) => setTrainingNotes(e.target.value)}
                  placeholder="Describe previous obedience training or cue familiarity..."
                  style={{ width: "100%", padding: 8, borderRadius: 8, minHeight: 60 }}
                />
              </div>

              {/* Mandatory Consent Checks */}
              <div style={{ padding: 14, borderRadius: 12, background: "#f0fdf4", border: "1px solid #bbf7d0" }}>
                <label className="row" style={{ gap: 8, cursor: "pointer", fontWeight: 600, fontSize: 13, color: "#166534" }}>
                  <input
                    type="checkbox"
                    checked={consentConfirmed}
                    onChange={(e) => setConsentConfirmed(e.target.checked)}
                  />
                  I affirm that informed owner consent has been signed and archived for this participant.
                </label>
                <label className="row" style={{ gap: 8, cursor: "pointer", fontWeight: 600, fontSize: 13, color: "#166534", marginTop: 8 }}>
                  <input
                    type="checkbox"
                    checked={welfareConfirmed}
                    onChange={(e) => setWelfareConfirmed(e.target.checked)}
                  />
                  I affirm that animal welfare and hearing screening have been completed without sound-phobia history.
                </label>
              </div>

              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button type="submit" className="btn-primary" style={{ padding: "10px 22px" }}>
                  Enrol Participant
                </button>
              </div>
            </form>
          </div>

          <div className="card stack" style={{ padding: 24, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 12px 0", fontSize: 17 }}>Enrolled Study Participants ({participants.length})</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: 8 }}>Pseudonym</th>
                    <th style={{ padding: 8 }}>Breed</th>
                    <th style={{ padding: 8 }}>Sex</th>
                    <th style={{ padding: 8 }}>Action Familiarity</th>
                    <th style={{ padding: 8 }}>Consent Status</th>
                    <th style={{ padding: 8 }}>Enrolled Date</th>
                  </tr>
                </thead>
                <tbody>
                  {participants.map((p) => (
                    <tr key={p.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: 8, fontWeight: 700 }}>{p.pseudonym}</td>
                      <td style={{ padding: 8 }}>{p.breed}</td>
                      <td style={{ padding: 8 }}>{p.sex}</td>
                      <td style={{ padding: 8 }}>{p.familiarity_with_target_action}</td>
                      <td style={{ padding: 8, color: "#059669", fontWeight: 600 }}>Consent Verified</td>
                      <td style={{ padding: 8 }}>{p.created_at.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
