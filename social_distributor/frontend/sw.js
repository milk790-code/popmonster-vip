// Service worker for the Social Distributor dashboard.
//
// Caching strategy (B11): NETWORK-FIRST for the shell.
// - Shell (HTML, CSS, JS, icons): try the network first, update the cache,
//   and fall back to cache ONLY when offline. A control surface must never be
//   pinned to a stale build — the previous cache-first strategy meant a new
//   deploy never reached users whose browser had the old shell cached.
// - API / auth: never cached.
// - Offline navigation falls back to the cached index so the PWA still opens.

// SW_BUILD is bumped on each shell change so the byte-different sw.js is
// detected and installed by the browser even when CACHE_VERSION is constant
// (Railway renders CACHE_VERSION=prod every deploy). Network-first then keeps
// assets fresh without needing a per-deploy bump.
const SW_BUILD = "2026-06-28-netfirst-1";
const CACHE_VERSION = "${CACHE_VERSION}".startsWith("$")
  ? "dev-" + Date.now()
  : "${CACHE_VERSION}";
const CACHE = `distributor-shell-${CACHE_VERSION}-${SW_BUILD}`;
const SHELL = [
  "./index.html",
  "./css/app.css",
  "./js/app.js",
  "./manifest.json",
  "./icons/icon.svg",
  "./icons/icon-maskable.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never cache the API or auth flows.
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/auth/") ||
    url.pathname.startsWith("/healthz")
  ) {
    return; // let the request go to the network
  }

  // Network-first: always fetch the latest shell; refresh the cache; fall back
  // to cache (or the cached index for navigations) only when offline.
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res && res.ok && event.request.method === "GET") {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(event.request).then(
          (cached) =>
            cached ||
            (event.request.mode === "navigate"
              ? caches.match("./index.html")
              : undefined)
        )
      )
  );
});
