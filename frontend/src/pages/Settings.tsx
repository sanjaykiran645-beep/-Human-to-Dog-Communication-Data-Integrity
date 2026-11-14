import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, clearAuth, getUser } from "../api";
import { useNavigate } from "react-router-dom";

const COLOR_THEMES = [
  { id: "default", name: "Studio Warm (Default)", desc: "Balanced warm acoustic studio palette", previewBg: "#f8f5f0", previewAccent: "#7c2d12" },
  { id: "white-black", name: "White & Black (Stark Monochrome)", desc: "Pure white surfaces with crisp black typography & borders", previewBg: "#ffffff", previewAccent: "#000000" },
  { id: "red-blue", name: "Red & Blue (Crimson & Cobalt)", desc: "Vibrant crimson primary actions with royal cobalt cards", previewBg: "#eff6ff", previewAccent: "#dc2626" },
  { id: "yellow-green", name: "Yellow & Green (Solar & Emerald)", desc: "Bright solar yellow highlights with deep emerald green cards", previewBg: "#fefce8", previewAccent: "#15803d" },
];

export default function Settings() {
  const user = getUser();
  const nav = useNavigate();
  const [theme, setTheme] = useState<string>(() => localStorage.getItem("cs_color_theme") || "default");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem("cs_color_theme", theme);
    document.body.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  async function updatePassword(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setMsg("Password updated successfully.");
    } catch (e: any) {
      setErr(e.message || "Could not update password.");
    }
  }

  return (
    <div className="stack-lg" style={{ maxWidth: 960, margin: "0 auto" }}>
      <div className="card stack" style={{ padding: 28, borderRadius: 20 }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: 24 }}>Appearance & Color Theme Studio</h2>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Switch your workspace color scheme instantly (White & Black, Red & Blue, Yellow & Green).
          </p>
        </div>

        <div className="grid-2" style={{ gap: 14, marginTop: 8 }}>
          {COLOR_THEMES.map((t) => {
            const active = theme === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTheme(t.id)}
                style={{
                  textAlign: "left",
                  padding: 18,
                  borderRadius: 16,
                  border: active ? `3px solid ${t.previewAccent}` : "1px solid rgba(0,0,0,0.15)",
                  background: t.previewBg,
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontWeight: 800, fontSize: 16, color: "#0f172a" }}>
                    {t.name} {active ? "[ACTIVE]" : ""}
                  </div>
                  <div style={{ fontSize: 12.5, color: "#475569", marginTop: 4 }}>{t.desc}</div>
                </div>
                <div style={{ width: 34, height: 34, borderRadius: 999, background: t.previewAccent, border: "2px solid #fff" }} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid-2" style={{ gap: 20 }}>
        <div className="card stack" style={{ padding: 28, borderRadius: 20 }}>
          <h3 style={{ margin: 0, fontSize: 20 }}>Account & Profile Rules</h3>
          <div style={{ fontSize: 14 }}>
            <div><strong>Name:</strong> {user?.name || "Active User"}</div>
            <div style={{ marginTop: 6 }}><strong>Email:</strong> {user?.email || "local@caninesense.ai"}</div>
            <div style={{ marginTop: 6 }}><strong>Auto-Prune Rule:</strong> Max 10 dogs (deletes starting 3 profiles at 11+)</div>
          </div>
          <div className="row" style={{ gap: 10, marginTop: 12 }}>
            <button type="button" className="btn btn-danger btn-sm" onClick={() => { clearAuth(); nav("/login"); }}>
              Sign Out
            </button>
          </div>
        </div>

        <form className="card stack" onSubmit={updatePassword} style={{ padding: 28, borderRadius: 20 }}>
          <h3 style={{ margin: 0, fontSize: 20 }}>Change Password</h3>
          {msg && <div className="alert" style={{ background: "#ecfdf5", color: "#065f46" }}>{msg}</div>}
          {err && <div className="alert alert-error">{err}</div>}
          <div className="field">
            <label>Current Password</label>
            <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required />
          </div>
          <div className="field">
            <label>New Password (8+ chars)</label>
            <input type="password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
          </div>
          <button className="btn btn-primary btn-sm" type="submit" style={{ borderRadius: 999, padding: "10px 20px" }}>
            Update Password
          </button>
        </form>
      </div>
    </div>
  );
}
