/**
 * Client-side Bioacoustic Engine & Local Storage Provider.
 * Allows the CanineSense AI application to function 100% interactively on static hosts
 * such as GitHub Pages (where no Python/FastAPI backend container is present).
 */

import { getUser, setSession, clearSession } from "./api";
import type { User, Dog } from "./api";

// Helper to generate a realistic waveform PNG via HTML5 Canvas
export function generateWaveformPng(): string {
  if (typeof document === "undefined") return "";
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 140;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  // Background
  ctx.fillStyle = "#F7F2E8";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Grid
  ctx.strokeStyle = "#E8DFD2";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = 40; x < canvas.width; x += 60) {
    ctx.moveTo(x, 10);
    ctx.lineTo(x, canvas.height - 20);
  }
  ctx.moveTo(40, canvas.height / 2);
  ctx.lineTo(canvas.width - 20, canvas.height / 2);
  ctx.stroke();

  // Waveform envelope
  ctx.strokeStyle = "#762F3D";
  ctx.lineWidth = 2;
  ctx.beginPath();
  const midY = canvas.height / 2;
  const numPoints = 120;
  for (let i = 0; i < numPoints; i++) {
    const x = 40 + (i / numPoints) * (canvas.width - 60);
    const env = Math.exp(-Math.pow((i - 40) / 25, 2)) * 0.9 + Math.exp(-Math.pow((i - 80) / 20, 2)) * 0.7;
    const amp = Math.sin(i * 0.8) * Math.cos(i * 0.25) * env * 50;
    if (i === 0) ctx.moveTo(x, midY + amp);
    else ctx.lineTo(x, midY + amp);
  }
  ctx.stroke();

  // Axis labels
  ctx.fillStyle = "#6E6256";
  ctx.font = "10px sans-serif";
  ctx.fillText("0.0s", 40, canvas.height - 6);
  ctx.fillText("0.5s", canvas.width / 2, canvas.height - 6);
  ctx.fillText("1.0s", canvas.width - 40, canvas.height - 6);

  return canvas.toDataURL("image/png");
}

// Helper to generate a realistic STFT Spectrogram PNG via Canvas
export function generateSpectrogramPng(): string {
  if (typeof document === "undefined") return "";
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 200;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  // Background
  ctx.fillStyle = "#1A1412";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw simulated harmonic spectrogram bands
  const imgData = ctx.createImageData(canvas.width, canvas.height);
  const data = imgData.data;

  for (let y = 0; y < canvas.height; y++) {
    const freq = (canvas.height - y) / canvas.height; // 0 to 1
    for (let x = 0; x < canvas.width; x++) {
      const t = x / canvas.width;
      const burst1 = Math.exp(-Math.pow((t - 0.35) / 0.12, 2));
      const burst2 = Math.exp(-Math.pow((t - 0.72) / 0.1, 2));
      const burst = burst1 + burst2;

      // Harmonics at multiples of F0 (~0.15, 0.3, 0.45, 0.6)
      const h1 = Math.exp(-Math.pow((freq - 0.14) / 0.03, 2));
      const h2 = Math.exp(-Math.pow((freq - 0.28) / 0.035, 2)) * 0.8;
      const h3 = Math.exp(-Math.pow((freq - 0.42) / 0.04, 2)) * 0.6;
      const h4 = Math.exp(-Math.pow((freq - 0.56) / 0.05, 2)) * 0.4;
      const noise = (Math.random() - 0.5) * 0.08;

      const intensity = Math.min(1, Math.max(0, (h1 + h2 + h3 + h4 + noise) * burst));
      const idx = (y * canvas.width + x) * 4;

      // Color mapping: dark purple -> terracotta -> gold -> cream
      data[idx] = Math.floor(intensity * 240); // R
      data[idx + 1] = Math.floor(intensity * intensity * 190); // G
      data[idx + 2] = Math.floor(Math.pow(intensity, 0.5) * 80 + 30); // B
      data[idx + 3] = 255;
    }
  }
  ctx.putImageData(imgData, 0, 0);

  // Overlay axes
  ctx.fillStyle = "#E8DFD2";
  ctx.font = "11px monospace";
  ctx.fillText("4 kHz", 10, 30);
  ctx.fillText("2 kHz", 10, 100);
  ctx.fillText("0 kHz", 10, 185);

  return canvas.toDataURL("image/png");
}

// Generate simple audible synthetic WAV data URL
export function generateSyntheticWavUrl(freq = 260, duration = 0.8): string {
  const sampleRate = 22050;
  const numSamples = Math.floor(sampleRate * duration);
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  function writeString(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  // RIFF chunk descriptor
  writeString(0, "RIFF");
  view.setUint32(4, 36 + numSamples * 2, true);
  writeString(8, "WAVE");

  // FMT sub-chunk
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (1 = PCM)
  view.setUint16(22, 1, true); // NumChannels (1 = mono)
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // ByteRate
  view.setUint16(32, 2, true); // BlockAlign
  view.setUint16(34, 16, true); // BitsPerSample

  // DATA sub-chunk
  writeString(36, "data");
  view.setUint32(40, numSamples * 2, true);

  // PCM samples: synthesized canine acoustic bark envelope
  for (let i = 0; i < numSamples; i++) {
    const t = i / sampleRate;
    const decay = Math.exp(-t * 8);
    const mod = Math.sin(2 * Math.PI * 12 * t);
    const sample = Math.sin(2 * Math.PI * (freq + mod * 40) * t) * decay * 0.7;
    const s = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  const blob = new Blob([buffer], { type: "audio/wav" });
  return URL.createObjectURL(blob);
}

// Client-side storage keys
const KEY_USERS = "cs_registered_users";
const KEY_DOGS = "cs_dogs_v1";
const KEY_RECS = "cs_recs_v1";
const KEY_COMM = "cs_comm_v1";

function getStoredUsers(): any[] {
  try {
    return JSON.parse(localStorage.getItem(KEY_USERS) || "[]");
  } catch {
    return [];
  }
}

function saveUsers(users: any[]) {
  try {
    localStorage.setItem(KEY_USERS, JSON.stringify(users));
  } catch {
    /* ignore */
  }
}

export function getMockMediaUrl(path: string): string {
  if (path.includes("waveform")) {
    return generateWaveformPng();
  }
  if (path.includes("spectrogram")) {
    return generateSpectrogramPng();
  }
  return generateSyntheticWavUrl(260, 0.8);
}

export async function handleMockApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const cleanPath = path.split("?")[0];

  // Helper to parse JSON body
  let body: any = {};
  if (init.body && typeof init.body === "string") {
    try {
      body = JSON.parse(init.body);
    } catch {
      body = {};
    }
  }

  // Current session user
  const currentUser = getUser();

  // 1. AUTH: REGISTER
  if (cleanPath === "/api/auth/register" && method === "POST") {
    const email = (body.email || "").trim().toLowerCase();
    const name = (body.name || "").trim() || email.split("@")[0] || "Researcher";
    const password = body.password || "";

    if (!email || !email.includes("@")) {
      throw new Error("A valid email address is required.");
    }
    if (password.length < 8) {
      throw new Error("Password must be at least 8 characters.");
    }

    const users = getStoredUsers();
    let existing = users.find((u) => u.email === email);
    if (!existing) {
      existing = {
        id: "usr_" + Math.random().toString(36).slice(2, 10),
        email,
        name,
        password,
        created_at: new Date().toISOString(),
      };
      users.push(existing);
      saveUsers(users);
    }

    const token = "cs_token_" + btoa(email) + "_" + Date.now();
    const userObj: User = { id: existing.id, email: existing.email, name: existing.name };
    setSession(token, userObj);
    return { access_token: token, user: userObj } as unknown as T;
  }

  // 2. AUTH: LOGIN
  if (cleanPath === "/api/auth/login" && method === "POST") {
    const email = (body.email || "").trim().toLowerCase();
    const password = body.password || "";

    if (!email) {
      throw new Error("Email is required.");
    }

    const users = getStoredUsers();
    let user = users.find((u) => u.email === email);
    // Auto-create to guarantee user can sign in immediately
    if (!user) {
      user = {
        id: "usr_" + Math.random().toString(36).slice(2, 10),
        email,
        name: email.split("@")[0],
        password: password || "password123",
        created_at: new Date().toISOString(),
      };
      users.push(user);
      saveUsers(users);
    }

    const token = "cs_token_" + btoa(email) + "_" + Date.now();
    const userObj: User = { id: user.id, email: user.email, name: user.name };
    setSession(token, userObj);
    return { access_token: token, user: userObj } as unknown as T;
  }

  // 3. AUTH: LOGOUT
  if (cleanPath === "/api/auth/logout" && method === "POST") {
    clearSession();
    return { status: "ok" } as unknown as T;
  }

  // 4. HEALTH CHECK
  if (cleanPath === "/api/health") {
    return {
      status: "ok",
      version: "1.0.0",
      decoder: {
        ffmpeg_available: true,
        ffmpeg_version: "WebAudio/DSP Native Simulation",
        soundfile_wav: true,
        supported_with_ffmpeg: ["wav", "mp3", "m4a", "ogg", "webm", "flac"],
      },
    } as unknown as T;
  }

  // 5. DOGS (Canine Profiles)
  const dogKey = `${KEY_DOGS}_${currentUser?.id || "demo"}`;
  if (cleanPath === "/api/dogs") {
    if (method === "GET") {
      let dogs: Dog[] = [];
      try {
        dogs = JSON.parse(localStorage.getItem(dogKey) || "[]");
      } catch {
        dogs = [];
      }
      if (dogs.length === 0) {
        dogs = [
          {
            id: "dog_barnaby",
            name: "Barnaby",
            breed: "Golden Retriever",
            sex: "Male",
            age_years: 3,
            weight_kg: 28,
            notes: "Healthy adult baseline. Typical bark fundamental frequency range: 210-260 Hz.",
          },
        ];
        localStorage.setItem(dogKey, JSON.stringify(dogs));
      }
      return dogs as unknown as T;
    }

    if (method === "POST") {
      let dogs: Dog[] = [];
      try {
        dogs = JSON.parse(localStorage.getItem(dogKey) || "[]");
      } catch {
        dogs = [];
      }
      const newDog: Dog = {
        id: "dog_" + Math.random().toString(36).slice(2, 9),
        name: body.name || "Canine",
        breed: body.breed || null,
        sex: body.sex || null,
        age_years: body.age_years ? Number(body.age_years) : null,
        weight_kg: body.weight_kg ? Number(body.weight_kg) : null,
        notes: body.notes || null,
      };
      dogs.push(newDog);
      localStorage.setItem(dogKey, JSON.stringify(dogs));
      return newDog as unknown as T;
    }
  }

  if (cleanPath.startsWith("/api/dogs/") && method === "DELETE") {
    const dogId = cleanPath.replace("/api/dogs/", "");
    let dogs: Dog[] = [];
    try {
      dogs = JSON.parse(localStorage.getItem(dogKey) || "[]");
    } catch {
      dogs = [];
    }
    dogs = dogs.filter((d) => d.id !== dogId);
    localStorage.setItem(dogKey, JSON.stringify(dogs));
    return undefined as unknown as T;
  }

  // 6. RECORDINGS (Engine A Analysis)
  const recKey = `${KEY_RECS}_${currentUser?.id || "demo"}`;
  if (cleanPath === "/api/recordings" && method === "GET") {
    let recs: any[] = [];
    try {
      recs = JSON.parse(localStorage.getItem(recKey) || "[]");
    } catch {
      recs = [];
    }
    return recs as unknown as T;
  }

  if (cleanPath === "/api/recordings/analyze" && method === "POST") {
    const recId = "rec_" + Math.random().toString(36).slice(2, 10);
    const categories = ["BARK", "GROWL", "WHINE", "HOWL", "YIP", "PANT"];
    const chosenCat = categories[Math.floor(Math.random() * categories.length)];
    const conf = 0.82 + Math.random() * 0.14;

    const analysis = {
      id: "an_" + Math.random().toString(36).slice(2, 10),
      recording_id: recId,
      dog_id: null,
      model_version: "2.1.0-rf",
      behavior_model_version: "1.4.0",
      vocalization: chosenCat,
      confidence: Math.round(conf * 100) / 100,
      abstained: false,
      probabilities: {
        [chosenCat]: Math.round(conf * 100) / 100,
        BARK: chosenCat === "BARK" ? conf : 0.08,
        GROWL: chosenCat === "GROWL" ? conf : 0.04,
        WHINE: chosenCat === "WHINE" ? conf : 0.03,
      },
      alternatives: [
        { vocalization: "BARK", probability: 0.12 },
        { vocalization: "GROWL", probability: 0.05 },
      ],
      features: {
        f0_hz: 242.5,
        spectral_centroid_hz: 1840.2,
        spectral_bandwidth_hz: 1120.4,
        hnr_db: 15.6,
        zero_crossing_rate: 0.084,
        rms_energy: 0.21,
        peak_amplitude: 0.78,
      },
      behavior: {
        estimated_context: "ALERT_OR_PLAYFUL",
        confidence: 0.74,
        withheld: false,
        rationale: "Harmonic structure indicates non-distressed vocalization event with low entropy.",
      },
      explanation: {
        summary: `Acoustic features strongly align with canonical ${chosenCat.toLowerCase()} vocalization profile.`,
        key_indicators: [
          "Dominant fundamental frequency (F0) at 242.5 Hz aligns with medium-large canine baseline.",
          "Harmonic-to-noise ratio (15.6 dB) indicates structured tonal voicing.",
          "Moderate spectral centroid indicates energetic vocal tract excitation without high-stress squeal.",
        ],
        limitations: [
          "Acoustic classification is probabilistic and reflects acoustic similarity, not cognitive intent.",
          "Microphone placement and room reverberation affect spectral shape.",
        ],
      },
      limitations: [
        "Not veterinary medical advice.",
        "Classification is experimental and does not replace behavioral evaluation.",
      ],
    };

    const newRec = {
      id: recId,
      dog_id: null,
      original_filename: "vocalization_sample.wav",
      duration_sec: 1.45,
      sample_rate: 22050,
      channels: 1,
      sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      file_size: 64120,
      quality_status: "good",
      quality: { is_clipped: false, is_silent: false, clipping_ratio: 0.0, silence_ratio: 0.02 },
      source: "upload",
      created_at: new Date().toISOString(),
      has_analysis: true,
      media_urls: {
        processed: `/api/recordings/${recId}/media/processed`,
        original: `/api/recordings/${recId}/media/original`,
        waveform: `/api/recordings/${recId}/media/waveform`,
        spectrogram: `/api/recordings/${recId}/media/spectrogram`,
        spectrogram_data: `/api/recordings/${recId}/spectrogram-data`,
      },
      analysis,
    };

    let recs: any[] = [];
    try {
      recs = JSON.parse(localStorage.getItem(recKey) || "[]");
    } catch {
      recs = [];
    }
    recs.unshift(newRec);
    localStorage.setItem(recKey, JSON.stringify(recs));
    return newRec as unknown as T;
  }

  // 7. SPECTROGRAM DATA
  if (cleanPath.includes("/spectrogram-data")) {
    const times = Array.from({ length: 60 }, (_, i) => Math.round(i * 0.025 * 100) / 100);
    const frequencies = Array.from({ length: 40 }, (_, i) => Math.round(i * 120));
    const matrix = Array.from({ length: 40 }, (_, row) =>
      Array.from({ length: 60 }, () => Math.round((-40 - Math.random() * 30 + (row < 8 ? 25 : 0)) * 10) / 10)
    );
    const f0_contour = times.map((t) => 230 + Math.sin(t * 10) * 20);

    return {
      times,
      frequencies,
      matrix,
      f0_contour,
      metrics: {
        f0_hz: 242.5,
        spectral_centroid_hz: 1840.2,
        hnr_db: 15.6,
        is_near_silent: false,
        is_clipped: false,
        clipping_ratio: 0.0,
      },
    } as unknown as T;
  }

  // 8. COMMUNICATE (Engine B)
  const commKey = `${KEY_COMM}_${currentUser?.id || "demo"}`;
  if (cleanPath === "/api/communicate") {
    if (method === "GET") {
      let items: any[] = [];
      try {
        items = JSON.parse(localStorage.getItem(commKey) || "[]");
      } catch {
        items = [];
      }
      return items as unknown as T;
    }
  }

  if (cleanPath === "/api/communicate/intent" && method === "POST") {
    const text = (body.text || "").toLowerCase();
    let cat = "BARK";
    let intent = "ATTENTION_PLAY";
    if (text.includes("play") || text.includes("happy")) {
      cat = "BARK";
      intent = "PLAYFUL_INVITATION";
    } else if (text.includes("quiet") || text.includes("stop")) {
      cat = "GROWL";
      intent = "FIRM_DISSUASION";
    } else if (text.includes("come") || text.includes("here")) {
      cat = "WHINE";
      intent = "AFFILIATIVE_CALL";
    }

    return {
      intent,
      selected_synthesis_profile: cat,
      target_duration_sec: 1.2,
      target_pitch_hz: 240,
      needs_clarification: false,
      reference_category: cat,
      reference_candidates: [
        {
          asset_id: `ref_${cat.toLowerCase()}_01`,
          effective_category: cat,
          duration_sec: 1.15,
          provenance: "Canine bioacoustic reference library",
          technical_validation_status: "valid_canine_reference",
        },
        {
          asset_id: `ref_${cat.toLowerCase()}_02`,
          effective_category: cat,
          duration_sec: 1.35,
          provenance: "Canine bioacoustic reference library",
          technical_validation_status: "valid_canine_reference",
        },
      ],
    } as unknown as T;
  }

  if (cleanPath === "/api/communicate/generate" && method === "POST") {
    const genId = "gen_" + Math.random().toString(36).slice(2, 10);
    const cat = body.vocalization_target || "BARK";
    const newGen = {
      id: genId,
      intent_text: body.text || "Hello",
      vocalization_target: cat,
      generation_method: "METHOD_B_CROSS_SYNTHESIS",
      duration_sec: 1.2,
      f0_hz: 245.0,
      audio_url: `/api/communicate/${genId}/audio`,
      waveform_url: `/api/communicate/${genId}/waveform`,
      spectrogram_url: `/api/communicate/${genId}/spectrogram`,
      created_at: new Date().toISOString(),
      validation_status: "CANINE_ACCEPTABLE",
      feedback: null,
      responses: [],
    };

    let items: any[] = [];
    try {
      items = JSON.parse(localStorage.getItem(commKey) || "[]");
    } catch {
      items = [];
    }
    items.unshift(newGen);
    localStorage.setItem(commKey, JSON.stringify(items));
    return newGen as unknown as T;
  }

  if (cleanPath === "/api/communicate/references") {
    return {
      total_assets: 134,
      categories: ["BARK", "GROWL", "HOWL", "WHINE", "YIP", "YELP", "WHIMPER", "CRY", "GRUNT", "GROAN", "PANT"],
      assets: [
        {
          asset_id: "ref_bark_01",
          effective_category: "BARK",
          duration_sec: 1.25,
          technical_validation_status: "valid_canine_reference",
          provenance: "Canine bioacoustic reference archive",
        },
        {
          asset_id: "ref_growl_01",
          effective_category: "GROWL",
          duration_sec: 1.8,
          technical_validation_status: "valid_canine_reference",
          provenance: "Canine bioacoustic reference archive",
        },
        {
          asset_id: "ref_whine_01",
          effective_category: "WHINE",
          duration_sec: 0.95,
          technical_validation_status: "valid_canine_reference",
          provenance: "Canine bioacoustic reference archive",
        },
      ],
    } as unknown as T;
  }

  // 9. BLIND TEST PROTOCOL
  if (cleanPath === "/api/communicate/blind-test") {
    return {
      protocol_version: "1.0",
      human_listening_evaluation_status: "PENDING",
      total_blind_samples: 44,
      total_submissions: 0,
      unique_reviewers_count: 0,
      samples: Array.from({ length: 44 }, (_, i) => ({
        sample_id: `blind_${String(i + 1).padStart(3, "0")}`,
        blind_code: `BLD-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
        duration_sec: 1.25,
        audio_url: `/api/communicate/blind-test/blind_${String(i + 1).padStart(3, "0")}/audio`,
      })),
      submissions: [],
    } as unknown as T;
  }

  if (cleanPath === "/api/communicate/blind-test/submit" && method === "POST") {
    return {
      submission_id: "sub_" + Math.random().toString(36).slice(2, 9),
      sample_id: body.sample_id,
      revealed_ground_truth: {
        intended_category: body.perceived_category || "BARK",
        generation_method: "GENUINE_CANINE_CONTROL",
        output_classification: "CANINE_ACCEPTABLE",
        category_matched: true,
      },
    } as unknown as T;
  }

  // 10. ANALYTICS SUMMARY
  if (cleanPath === "/api/analytics/summary") {
    let recs: any[] = [];
    try {
      recs = JSON.parse(localStorage.getItem(recKey) || "[]");
    } catch {
      recs = [];
    }
    return {
      total_recordings: recs.length || 8,
      total_dogs: 1,
      vocalization_distribution: {
        BARK: 4,
        GROWL: 2,
        WHINE: 1,
        PANT: 1,
      },
      model_version: "2.1.0-rf",
      behavior_model_version: "1.4.0",
      synth_model_version: "2.0.0",
    } as unknown as T;
  }

  // 11. ACCOUNT EXPORT
  if (cleanPath === "/api/account/export") {
    const dogs = JSON.parse(localStorage.getItem(dogKey) || "[]");
    const recs = JSON.parse(localStorage.getItem(recKey) || "[]");
    const comm = JSON.parse(localStorage.getItem(commKey) || "[]");
    return {
      export_version: "1.0",
      user: currentUser,
      dogs,
      recordings: recs,
      generated_audio: comm,
      exported_at: new Date().toISOString(),
    } as unknown as T;
  }

  // 12. ACCOUNT DELETION
  if (cleanPath === "/api/account" && method === "DELETE") {
    localStorage.removeItem(dogKey);
    localStorage.removeItem(recKey);
    localStorage.removeItem(commKey);
    clearSession();
    return { status: "deleted" } as unknown as T;
  }

  // Fallback generic response
  return {} as unknown as T;
}
