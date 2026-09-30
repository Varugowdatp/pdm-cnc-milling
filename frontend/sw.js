/* ==================================================================
   SERVICE WORKER  —  makes the HMI an installable PWA
   ==================================================================
   Lives at the site root so its scope covers every screen.

   Strategy:
   - /api/* and /artifacts/* are NEVER cached. Sensor readings, health
     scores and alarms must always be live; a stale prediction on a
     maintenance screen is worse than an error.
   - The app shell (HTML/CSS/JS/icons) is network-first with a cache
     fallback, so a normal reload always gets the latest code, and the
     shell still opens (showing "backend offline") without a network.

   Bump CACHE_VERSION whenever the shell file list changes.
   ================================================================== */

const CACHE_VERSION = "pdm-shell-v1";

const SHELL = [
  "/",
  "/index.html",
  "/manifest.json",
  "/css/style.css",
  "/js/api.js",
  "/js/widgets.js",
  "/js/app.js",
  "/js/pwa.js",
  "/js/screens/overview.js",
  "/js/screens/machine.js",
  "/js/screens/manual.js",
  "/js/screens/batch.js",
  "/js/screens/alarms.js",
  "/js/screens/model.js",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin GETs for the shell; everything else goes straight to the network.
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/artifacts/")) return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((hit) => hit || (req.mode === "navigate" ? caches.match("/index.html") : undefined))
      )
  );
});
