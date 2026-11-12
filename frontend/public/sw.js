// CanineSense AI - Safe PWA Service Worker (v2)
// Strictly caches only immutable static shell assets (CSS, JS, branding icon).
// NEVER caches private recordings, user data, or /api requests.

const CACHE_NAME = "caninesense-shell-v2";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // 1. Bypass all API and dynamic data calls immediately to network - NO CACHING
  if (url.pathname.includes("/api/") || event.request.method !== "GET") {
    return;
  }

  // 2. Navigation / SPA shell requests - Network-first so deployments update immediately
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request);
      })
    );
    return;
  }

  // 3. Content-hashed static assets (assets/*) - Cache first, network fallback
  if (url.pathname.includes("/assets/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // 4. Default - Network first with cache fallback
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});
