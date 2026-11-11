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

function isStaticHost(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname.toLowerCase();
  return host.includes("github.io") || window.location.protocol === "file:" || host.endsWith(".pages.dev");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  // If running on a static host (like GitHub Pages where no Python backend container runs),
  // immediately process with client-side bioacoustic storage engine
  if (isStaticHost()) {
    const { handleMockApi } = await import("./mockBackend");
    return handleMockApi<T>(path, init);
  }

  const headers = new Headers(init.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const res = await fetch(path, { ...init, headers });
    // If backend returns 405 Method Not Allowed or 404 Not Found on static host
    if (res.status === 405 || res.status === 404) {
      const { handleMockApi } = await import("./mockBackend");
      return handleMockApi<T>(path, init);
    }
    if (res.status === 401) {
      clearSession();
      if (!window.location.hash.includes("login") && !window.location.hash.includes("register")) {
        window.location.hash = "#/login";
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
  } catch (err) {
    // If connection refused / network error (e.g. backend server is not running locally)
    if (
      err instanceof TypeError &&
      (err.message.includes("Failed to fetch") || err.message.includes("NetworkError") || err.message.includes("Load failed"))
    ) {
      const { handleMockApi } = await import("./mockBackend");
      return handleMockApi<T>(path, init);
    }
    throw err;
  }
}

export async function mediaUrl(path: string): Promise<string> {
  if (isStaticHost()) {
    const { getMockMediaUrl } = await import("./mockBackend");
    return getMockMediaUrl(path);
  }

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
        if (!window.location.hash.includes("login") && !window.location.hash.includes("register")) {
          window.location.hash = "#/login";
        }
        throw new Error("Session expired. Please sign in again.");
      }
      if (!res.ok) {
        if ((res.status >= 500 || res.status === 429) && attempt < 2) {
          continue;
        }
        const { getMockMediaUrl } = await import("./mockBackend");
        return getMockMediaUrl(path);
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

  const { getMockMediaUrl } = await import("./mockBackend");
  return getMockMediaUrl(path);
}
