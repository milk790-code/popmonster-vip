// Service worker for the Social Distributor dashboard.
//
// Caching strategy:
// - Static shell (HTML, CSS, JS, icons): cache-first, refreshed in the
//   background so the dashboard opens instantly even on flaky links.
// - API calls: never cached. The dashboard is a control surface — stale data
//   is worse than a brief offline error.
// - Navigation requests fall back to the cached index when offline so PWA
//   launches don't show a browser error page.

const CACHE = "distributor-shell-v3";
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

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("./index.html"))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((res) => {
          if (res && res.ok && event.request.method === "GET") {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(event.request, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});
