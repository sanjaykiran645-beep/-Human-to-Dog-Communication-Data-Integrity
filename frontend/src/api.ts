export type User = { id: string; email: string; name: string };
export type Dog = {
  id: string;
  name: string;
  breed?: string | null;
  sex?: string | null;
  age_years?: number | null;
  weight_kg?: number | null;
  notes?: string | null;
};

const TOKEN = "cs_token";
const USER = "cs_user";

export function getToken() {
  return localStorage.getItem(TOKEN);
}
export function getUser(): User | null {
  const raw = localStorage.getItem(USER);
  return raw ? JSON.parse(raw) : null;
}
export function setSession(token: string, user: User) {
  localStorage.setItem(TOKEN, token);
  localStorage.setItem(USER, JSON.stringify(user));
}
export function clearSession() {
  localStorage.removeItem(TOKEN);
  localStorage.removeItem(USER);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    clearSession();
    if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/register")) {
      window.location.href = "/login";
    }
  }
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function mediaUrl(path: string): Promise<string> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let lastErr: Error | null = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt > 0) {
      await new Promise((r) => window.setTimeout(r, 220 * attempt));
    }
    try {
      const res = await fetch(path, { headers, cache: "no-store" });
      if (res.status === 401) {
        clearSession();
        if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/register")) {
          window.location.href = "/login";
        }
        throw new Error("Session expired. Please sign in again.");
      }
      if (!res.ok) {
        if ((res.status >= 500 || res.status === 429) && attempt < 2) {
          continue;
        }
        let detail = "Could not load media";
        try {
          const j = await res.json();
          if (typeof j?.detail === "string") detail = j.detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }
      const rawBlob = await res.blob();
      if (rawBlob.size === 0 && attempt < 2) {
        continue;
      }
      const ct = res.headers.get("content-type") || "";
      const inferredType =
        ct && ct !== "application/octet-stream"
          ? ct
          : path.includes("waveform") || path.includes("spectrogram")
            ? "image/png"
            : "audio/wav";
      const typedBlob = rawBlob.type === inferredType ? rawBlob : new Blob([rawBlob], { type: inferredType });
      return URL.createObjectURL(typedBlob);
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error("Could not load media");
      if (lastErr.message.includes("Session expired")) {
        throw lastErr;
      }
    }
  }
  throw lastErr || new Error("Could not load media");
}
