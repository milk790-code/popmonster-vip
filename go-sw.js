/* go-sw.js — POP 宇宙離線殼。保守策略：
 * - 只處理同網域 GET。
 * - 預快取 /go 殼與 App 資源；導覽請求離線時回退到快取的 /go。
 * - 其他資源一律「先網路、失敗才用快取」，永遠不讓快取蓋掉新版。
 */
var CACHE = "pm-universe-v20260801";
var SHELL = [
  "/go",
  "/go.html",
  "/css/go.css",
  "/css/go-app.css",
  "/js/go.js",
  "/js/go-app.js",
  "/js/go-analytics.js",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/assets/app/icon-192.png",
  "/assets/app/icon-512.png",
  "/universe-map.json"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches
      .open(CACHE)
      .then(function (cache) {
        return Promise.allSettled(
          SHELL.map(function (url) {
            return cache.add(url);
          })
        );
      })
      .then(function () {
        return self.skipWaiting();
      })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys
            .filter(function (key) {
              return key.indexOf("pm-universe-") === 0 && key !== CACHE;
            })
            .map(function (key) {
              return caches.delete(key);
            })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url;
  try {
    url = new URL(request.url);
  } catch (_e) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(request)
      .then(function (response) {
        if (response && response.ok && response.type === "basic") {
          var copy = response.clone();
          caches.open(CACHE).then(function (cache) {
            cache.put(request, copy);
          });
        }
        return response;
      })
      .catch(function () {
        return caches.match(request, { ignoreSearch: request.mode === "navigate" }).then(function (hit) {
          if (hit) return hit;
          if (request.mode === "navigate") {
            return caches.match("/go", { ignoreSearch: true });
          }
          return Response.error();
        });
      })
  );
});
