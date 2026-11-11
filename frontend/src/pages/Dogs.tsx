import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { Dog } from "../api";

const empty = { name: "", breed: "", sex: "", age_years: "", weight_kg: "", notes: "" };

export default function Dogs() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [form, setForm] = useState(empty);
  const [err, setErr] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [editing, setEditing] = useState<string | null>(null);

  function load() {
    api<Dog[]>("/api/dogs").then(setDogs);
  }
  useEffect(load, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setSuccessMsg("");
    const body = {
      name: form.name,
      breed: form.breed || null,
      sex: form.sex || null,
      age_years: form.age_years ? Number(form.age_years) : null,
      weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
      notes: form.notes || null,
    };
    try {
      if (editing) await api(`/api/dogs/${editing}`, { method: "PATCH", body: JSON.stringify(body) });
      else await api("/api/dogs", { method: "POST", body: JSON.stringify(body) });
      setSuccessMsg(editing ? "Dog profile updated successfully!" : "Dog profile added successfully!");
      setForm(empty);
      setEditing(null);
      load();
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed");
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this profile?")) return;
    try {
      await api(`/api/dogs/${id}`, { method: "DELETE" });
      setSuccessMsg("Dog profile removed.");
      setTimeout(() => setSuccessMsg(""), 4000);
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to delete profile");
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="kicker">Profiles</div>
          <h1>Dogs</h1>
          <p>Profiles stay on your account. Weight is only used as a weak F0-size consistency note.</p>
        </div>
      </div>
      <div className="grid-2">
        <div className="card">
          <h2>{editing ? "Edit profile" : "Add a dog"}</h2>
          {err && <div className="error" role="alert">{err}</div>}
          {successMsg && (
            <div
              className="badge ok"
              role="status"
              style={{ padding: "8px 14px", marginBottom: 14, display: "block" }}
            >
              {successMsg}
            </div>
          )}
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="dog-name">Name</label>
              <input
                id="dog-name"
                placeholder="e.g. Barnaby"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="dog-breed">Breed</label>
              <input
                id="dog-breed"
                placeholder="e.g. Golden Retriever"
                value={form.breed}
                onChange={(e) => setForm({ ...form, breed: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="dog-sex">Sex</label>
              <select id="dog-sex" value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
                <option value="">Unknown</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
              </select>
            </div>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="dog-age">Age (years)</label>
                <input
                  id="dog-age"
                  type="number"
                  min={0}
                  step={0.1}
                  placeholder="e.g. 3.5"
                  value={form.age_years}
                  onChange={(e) => setForm({ ...form, age_years: e.target.value })}
                />
              </div>
              <div className="field">
                <label htmlFor="dog-weight">Weight (kg)</label>
                <input
                  id="dog-weight"
                  type="number"
                  min={0.2}
                  step={0.1}
                  placeholder="e.g. 28.5"
                  value={form.weight_kg}
                  onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="dog-notes">Acoustic &amp; Behavioral Notes</label>
              <textarea
                id="dog-notes"
                placeholder="Baseline acoustic pitch, typical barking triggers, or medical notes..."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </div>
            <div className="row">
              <button className="btn">{editing ? "Save" : "Add"}</button>
              {editing && (
                <button className="btn ghost" type="button" onClick={() => { setEditing(null); setForm(empty); }}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>
        <div className="card">
          <h2>Your dogs</h2>
          {!dogs.length && <div className="empty">No profiles yet.</div>}
          {dogs.map((d) => (
            <div key={d.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--line)" }}>
              <strong>{d.name}</strong>
              <div className="tiny">
                {[d.breed, d.sex, d.weight_kg ? `${d.weight_kg} kg` : null].filter(Boolean).join(" · ") || "No details"}
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <button
                  className="btn ghost"
                  type="button"
                  onClick={() => {
                    setEditing(d.id);
                    setForm({
                      name: d.name,
                      breed: d.breed || "",
                      sex: d.sex || "",
                      age_years: d.age_years?.toString() || "",
                      weight_kg: d.weight_kg?.toString() || "",
                      notes: d.notes || "",
                    });
                  }}
                >
                  Edit
                </button>
                <button className="btn danger" type="button" onClick={() => remove(d.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
