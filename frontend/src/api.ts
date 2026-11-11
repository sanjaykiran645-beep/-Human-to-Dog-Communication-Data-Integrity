export type User = { id: string; email: string; name: string; isDemo?: boolean };
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
const BACKEND_URL_KEY = "cs_backend_url";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN);
}

export function getUser(): User | null {
  const raw = localStorage.getItem(USER);
  return raw ? JSON.parse(raw) : null;
}

export function isDemoSession(): boolean {
  const user = getUser();
  return Boolean(user?.isDemo);
}

export function setSession(token: string, user: User) {
  localStorage.setItem(TOKEN, token);
  localStorage.setItem(USER, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN);
  localStorage.removeItem(USER);
}

export function startDemoSession() {
  const demoUser: User = {
    id: "demo_guest",
    email: "guest@preview.local",
    name: "Demo Preview Guest",
    isDemo: true,
  };
  setSession("cs_demo_token_offline_preview", demoUser);
}

export function getBackendUrl(): string {
  if (typeof window === "undefined") return "";
  const stored = localStorage.getItem(BACKEND_URL_KEY);
  if (stored) return stored.replace(/\/+$/, "");
  const envUrl = (import.meta as any).env?.VITE_API_URL;
  if (envUrl) return String(envUrl).replace(/\/+$/, "");
  // Default to the deployed production Render backend when accessed from GitHub Pages
  if (typeof window !== "undefined" && window.location.hostname.includes("github.io")) {
    return "https://caninesense-backend.onrender.com";
  }
  return "";
}

export function setBackendUrl(url: string) {
  if (!url || !url.trim()) {
    localStorage.removeItem(BACKEND_URL_KEY);
  } else {
    localStorage.setItem(BACKEND_URL_KEY, url.trim().replace(/\/+$/, ""));
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isAuthRoute =
    path === "/api/auth/login" ||
    path === "/api/auth/register" ||
    path === "/api/auth/change-password";

  // If in an explicit demo preview session and not an actual account auth attempt, use in-browser mock engine
  if (isDemoSession() && !isAuthRoute) {
    const { handleMockApi } = await import("./mockBackend");
    return handleMockApi<T>(path, init);
  }

  const baseUrl = getBackendUrl();
  const targetUrl = baseUrl ? `${baseUrl}${path}` : path;

  const headers = new Headers(init.headers || {});
  const token = getToken();
  if (token && !isDemoSession()) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const res = await fetch(targetUrl, { ...init, headers });

    // Detect static host without backend for authentication routes
    if (isAuthRoute && (res.status === 405 || res.status === 404)) {
      throw new Error(
        "Backend Authentication Service Unavailable: The CanineSense AI FastAPI server is unreachable or offline. Secure authentication requires a live backend service. Simulated login is disabled to protect your credentials. You can explore the interface using 'Offline Demo Tour' below."
      );
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
    // If backend connection failed or network error
    if (
      err instanceof TypeError &&
      (err.message.includes("Failed to fetch") ||
        err.message.includes("NetworkError") ||
        err.message.includes("Load failed"))
    ) {
      if (isAuthRoute) {
        throw new Error(
          "Backend Authentication Service Unavailable: The CanineSense AI FastAPI server is unreachable or offline. Secure authentication requires a live backend service. Simulated login is disabled to protect your credentials. You can explore the interface using 'Offline Demo Tour' below."
        );
      }
      // If user is in demo mode and an unexpected network call failed, fallback to mock
      if (isDemoSession()) {
        const { handleMockApi } = await import("./mockBackend");
        return handleMockApi<T>(path, init);
      }
      throw new Error(
        "Backend Connection Error: Unable to connect to the FastAPI bioacoustic backend server. Please verify network connectivity or backend status."
      );
    }
    throw err;
  }
}

export async function mediaUrl(path: string): Promise<string> {
  if (isDemoSession()) {
    const { getMockMediaUrl } = await import("./mockBackend");
    return getMockMediaUrl(path);
  }

  const baseUrl = getBackendUrl();
  const targetUrl = baseUrl ? `${baseUrl}${path}` : path;

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let lastErr: Error | null = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt > 0) {
      await new Promise((r) => window.setTimeout(r, 220 * attempt));
    }
    try {
      const res = await fetch(targetUrl, { headers, cache: "no-store" });
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
        if (isDemoSession()) {
          const { getMockMediaUrl } = await import("./mockBackend");
          return getMockMediaUrl(path);
        }
        throw new Error(`Media fetch failed (${res.status} ${res.statusText})`);
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

  if (isDemoSession()) {
    const { getMockMediaUrl } = await import("./mockBackend");
    return getMockMediaUrl(path);
  }
  throw lastErr || new Error("Failed to load media from backend service.");
}
