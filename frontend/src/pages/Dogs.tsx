import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { Dog } from "../api";

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
  const [sex, setSex] = useState<"male" | "female">("male");
  const [age, setAge] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  async function load() {
    try {
      const list = await api<Dog[]>("/api/dogs");
      setDogs(list || []);
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
      const prevCount = dogs.length;
      await api<Dog>("/api/dogs", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          breed: breed.trim() || "Mixed Breed",
          sex,
          age_years: age ? Number(age) : null,
        }),
      });
      setName("");
      setBreed("");
      setAge("");
      if (prevCount >= 10) {
        setSavedMsg(
          `Profile saved with ${sex.toUpperCase()} acoustic calibration! Since your profiles exceeded 10, the starting 3 (oldest) profiles were automatically deleted.`
        );
      } else {
        setSavedMsg(
          `Profile saved! ${sex === "male" ? "Male (-10% deeper vocal fold pitch)" : "Female (+8% harmonic pitch)"} & breed intelligence synced.`
        );
      }
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
    <div className="grid-2" style={{ maxWidth: 1060, margin: "0 auto", gap: 24, alignItems: "start" }}>
      <form className="card stack" onSubmit={submit} style={{ padding: 28, borderRadius: 18 }}>
        <div>
          <h2 style={{ margin: "0 0 6px 0", fontSize: 22 }}>Add Canine Profile</h2>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Select your dog's name, sex (Male/Female), and breed. Automatically deletes the oldest 3 profiles whenever your list exceeds 10 profiles.
          </p>
        </div>

        {err && <div className="alert alert-error">{err}</div>}
        {savedMsg && (
          <div className="alert" style={{ background: "#ecfdf5", color: "#065f46", border: "1px solid #a7f3d0", fontWeight: 600 }}>
            {savedMsg}
          </div>
        )}

        <div className="field">
          <label>Dog's Name *</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Max, Bella, Bruno, Luna" />
        </div>

        <div className="field">
          <label>Canine Sex / Gender Differentiation *</label>
          <div className="grid-2" style={{ gap: 10 }}>
            <button
              type="button"
              onClick={() => setSex("male")}
              style={{
                padding: "12px 14px",
                borderRadius: 12,
                border: sex === "male" ? "2px solid #2563eb" : "1px solid rgba(0,0,0,0.15)",
                background: sex === "male" ? "rgba(37, 99, 235, 0.08)" : "#fff",
                fontWeight: 700,
                color: sex === "male" ? "#1d4ed8" : "#334155",
                cursor: "pointer",
              }}
            >
              Male Dog (Deeper F0 Pitch)
            </button>
            <button
              type="button"
              onClick={() => setSex("female")}
              style={{
                padding: "12px 14px",
                borderRadius: 12,
                border: sex === "female" ? "2px solid #db2777" : "1px solid rgba(0,0,0,0.15)",
                background: sex === "female" ? "rgba(219, 39, 119, 0.08)" : "#fff",
                fontWeight: 700,
                color: sex === "female" ? "#be185d" : "#334155",
                cursor: "pointer",
              }}
            >
              Female Dog (Higher F0 Pitch)
            </button>
          </div>
        </div>

        <div className="field">
          <label>Breed (Auto-Syncs Vocal & Behavioral Intelligence)</label>
          <input value={breed} onChange={(e) => setBreed(e.target.value)} placeholder="e.g. Golden Retriever, American Pit Bull..." />
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
          <input type="number" step="0.5" min="0" max="30" value={age} onChange={(e) => setAge(e.target.value)} placeholder="e.g. 3" />
        </div>

        <button className="btn btn-primary" disabled={busy} style={{ borderRadius: 999, padding: "12px 24px", fontWeight: 700 }}>
          {busy ? "Calibrating Gender & Breed Intelligence..." : "Save Dog Profile"}
        </button>
      </form>

      <div className="card stack" style={{ padding: 28, borderRadius: 18 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: 22 }}>Your Dogs ({dogs.length} / 10 Max)</h2>
          <span className="badge" style={{ fontSize: 11 }}>Auto-Deletes Oldest 3 at 11+</span>
        </div>

        {dogs.length === 0 ? (
          <p className="muted" style={{ fontSize: 14 }}>No dogs added yet. Add a Male or Female profile on the left.</p>
        ) : (
          <div className="stack" style={{ gap: 12 }}>
            {dogs.map((d) => {
              const isFemale = (d.sex || "").toLowerCase() === "female";
              return (
                <div
                  key={d.id}
                  className="row"
                  style={{
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "14px 18px",
                    borderRadius: 14,
                    background: "rgba(0,0,0,0.025)",
                    borderLeft: isFemale ? "4px solid #db2777" : "4px solid #2563eb",
                  }}
                >
                  <div>
                    <div className="row" style={{ gap: 8, alignItems: "center" }}>
                      <span style={{ fontWeight: 700, fontSize: 16 }}>{d.name}</span>
                      <span
                        style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          borderRadius: 999,
                          fontWeight: 700,
                          background: isFemale ? "rgba(219, 39, 119, 0.12)" : "rgba(37, 99, 235, 0.12)",
                          color: isFemale ? "#be185d" : "#1d4ed8",
                        }}
                      >
                        {isFemale ? "FEMALE" : "MALE"}
                      </span>
                    </div>
                    <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                      {d.breed || "Mixed Breed"} {d.age_years ? `· ${d.age_years} yrs` : ""} {d.weight_kg ? `· ${d.weight_kg} kg` : ""}
                    </div>
                  </div>
                  <button className="btn btn-danger btn-sm" onClick={() => remove(d.id)}>Delete</button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
