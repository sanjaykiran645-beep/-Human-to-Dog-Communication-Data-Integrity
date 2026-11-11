import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearSession, getUser } from "../api";

export default function Settings() {
  const user = getUser();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setMsg("Password updated.");
      setCurrent("");
      setNext("");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed");
    }
  }

  async function logout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      /* still leave */
    }
    clearSession();
    nav("/login");
  }

  async function exportData() {
    setErr("");
    try {
      const data = await api<unknown>("/api/account/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "caninesense-export.json";
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMsg("Account research archive exported successfully as JSON.");
      setTimeout(() => setMsg(""), 5000);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to export data");
    }
  }

  async function destroy() {
    if (!confirm("Permanently delete your account, recordings, and analyses?")) return;
    await api("/api/account", { method: "DELETE" });
    clearSession();
    nav("/login");
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="kicker">Account</div>
          <h1>Settings</h1>
          <p>Recordings never leave this server to a third-party AI provider.</p>
        </div>
        <button className="btn ghost" onClick={logout}>
          Log out
        </button>
      </div>
      <div className="card">
        <h2>Profile</h2>
        <p>
          {user?.name} · {user?.email}
        </p>
      </div>
      <div className="card">
        <h2>Change password</h2>
        {err && (
          <div className="error" role="alert" style={{ marginBottom: 12 }}>
            {err}
          </div>
        )}
        {msg && (
          <div
            className="badge ok"
            role="status"
            style={{ padding: "8px 14px", marginBottom: 12, display: "block" }}
          >
            {msg}
          </div>
        )}
        <form onSubmit={changePassword}>
          <div className="field">
            <label>Current</label>
            <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </div>
          <div className="field">
            <label>New (8+ characters)</label>
            <input type="password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} required />
          </div>
          <button className="btn">Update password</button>
        </form>
      </div>
      <div className="card">
        <h2>Privacy</h2>
        <p className="tiny">
          Audio is stored under your user id, served only with your token, and excluded from other accounts by server-side
          ownership checks. Engine B is experimental. Do not use this product as a veterinary diagnostic.
        </p>
        <div className="row">
          <button className="btn ghost" type="button" onClick={exportData}>
            Export my data
          </button>
          <button className="btn danger" type="button" onClick={destroy}>
            Delete account
          </button>
        </div>
      </div>
    </div>
  );
}
