import { FormEvent, useEffect, useState } from "react";
import { api, Dog } from "../api";

const POPULAR_BREEDS = [
  "Golden Retriever",
  "American Pit Bull Terrier",
  "German Shepherd",
  "Labrador Retriever",
  "Siberian Husky",
  "Indian Pariah Dog (Indie)",
  "Beagle",
  "Rottweiler",
  "Pug",
  "Chihuahua",
];

export default function Dogs() {
  const [dogs, setDogs] = useState<Dog[]>([]);
  const [name, setName] = useState("");
  const [breed, setBreed] = useState("");
  const [age, setAge] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  async function load() {
    try {
      localStorage.removeItem("cs_demo_mode");
      setDogs(await api<Dog[]>("/api/dogs"));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setErr(null);
    setSavedMsg(null);
    setBusy(true);
    try {
      await api<Dog>("/api/dogs", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          breed: breed.trim() || "Mixed Breed",
          age_years: age ? Number(age) : null,
        }),
      });
      setName("");
      setBreed("");
      setAge("");
      setSavedMsg("Profile saved. Breed intelligence and vocal pitch automatically calibrated in backend.");
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/api/dogs/${id}`, { method: "DELETE" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="grid-2" style={{ maxWidth: 1040, margin: "0 auto", gap: 24, alignItems: "start" }}>
      <form className="card stack" onSubmit={submit} style={{ padding: 28, borderRadius: 18 }}>
        <div>
          <h2 style={{ margin: "0 0 6px 0", fontSize: 22 }}>Add Your Dog</h2>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Just enter your dog?s name and breed. Behavioral traits, intelligence profile, and vocal frequencies are synced automatically in the background.
          </p>
        </div>

        {err && <div className="alert alert-error">{err}</div>}
        {savedMsg && (
          <div className="alert" style={{ background: "#ecfdf5", color: "#065f46", border: "1px solid #a7f3d0" }}>
            {savedMsg}
          </div>
        )}

        <div className="field">
          <label>Dog?s Name *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Max, Bruno, Bella"
          />
        </div>

        <div className="field">
          <label>Breed (Auto-Syncs Vocal & Behavioral Intelligence)</label>
          <input
            value={breed}
            onChange={(e) => setBreed(e.target.value)}
            placeholder="e.g. Golden Retriever, American Pit Bull..."
          />
          <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 8 }}>
            {POPULAR_BREEDS.map((b) => (
              <button
                key={b}
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ fontSize: 11, padding: "4px 10px", borderRadius: 999 }}
                onClick={() => setBreed(b)}
              >
                {b}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Age in Years (Optional)</label>
          <input
            type="number"
            step="0.5"
            min="0"
            max="30"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            placeholder="e.g. 3"
          />
        </div>

        <button className="btn btn-primary" disabled={busy} style={{ borderRadius: 999, padding: "10px 24px" }}>
          {busy ? "Syncing Breed Intelligence..." : "Save Dog Profile"}
        </button>
      </form>

      <div className="card stack" style={{ padding: 28, borderRadius: 18 }}>
        <h2 style={{ margin: "0 0 6px 0", fontSize: 22 }}>Your Dogs ({dogs.length})</h2>
        {dogs.length === 0 ? (
          <p className="muted" style={{ fontSize: 14 }}>
            No dogs added yet. Add a profile on the left to calibrate analysis and communication.
          </p>
        ) : (
          <div className="stack" style={{ gap: 12 }}>
            {dogs.map((d) => (
              <div
                key={d.id}
                className="row"
                style={{
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "14px 18px",
                  borderRadius: 14,
                  background: "rgba(0,0,0,0.025)",
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: 16 }}>{d.name}</div>
                  <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                    {d.breed || "Mixed Breed"} {d.age_years ? `? ${d.age_years} yrs` : ""}
                  </div>
                  <span
                    style={{
                      display: "inline-block",
                      marginTop: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 999,
                      background: "rgba(124, 45, 18, 0.1)",
                      color: "#7c2d12",
                      fontWeight: 600,
                    }}
                  >
                    ? Backend Breed Intelligence Synced
                  </span>
                </div>
                <button className="btn btn-danger btn-sm" onClick={() => remove(d.id)}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
