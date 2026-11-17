/* Football AI Lab · PWA shell only.
 * Never cache GitHub raw feeds, odds, predictions, personal data or external URLs.
 * No push subscriptions or background data reads.
 */
const CACHE_PREFIX = "football-ai-lab-shell-";
const CACHE_NAME = CACHE_PREFIX + "v8-20261117-result-status-colors";
const ROOT = new URL(self.registration.scope);

const SHELL_FILES = [
  "./", "index.html", "styles.css", "app.js",
  "data.mjs", "feed_loader.mjs", "markets.mjs", "future_markets.mjs",
  "reliability.mjs", "radar.mjs", "real_odds.mjs",
  "performance.mjs", "performance_view.mjs", "home.mjs", "match_detail.mjs", "results_mobile.mjs",
  "schedule.mjs", "agenda.mjs", "pwa.js",
  "manifest.webmanifest", "pwa-icon.svg", "favicon.svg",
  "icon-192.png", "icon-512.png"
];
const SHELL_URLS = SHELL_FILES.map(path => new URL(path, ROOT).href);
const SHELL_PATHS = new Set(SHELL_URLS.map(link => new URL(link).pathname));

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(SHELL_URLS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
      .map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

async function fetchShell(request, fallbackURL) {
  const cache = await caches.open(CACHE_NAME);
  try {
    // Network-first means updated Pages deployments are not frozen on the phone.
    const live = await fetch(request);
    if (live.ok && live.type === "basic") {
      await cache.put(fallbackURL, live.clone());
    }
    return live;
  } catch {
    const cached = await cache.match(fallbackURL);
    return cached || Response.error();
  }
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Critical: all prediction, result and bookmaker feeds live on a DIFFERENT
  // host; do not intercept them or display an expired quote as live.
  if (url.origin !== ROOT.origin || !url.pathname.startsWith(ROOT.pathname)) return;

  if (request.mode === "navigate") {
    event.respondWith(fetchShell(request, new URL("index.html", ROOT).href));
  } else if (SHELL_PATHS.has(url.pathname) && !url.search) {
    event.respondWith(fetchShell(request, url.href));
  }
  // All site/published/* files, crests.json and other data remain network-only.
  // Only the static application shell may be cached.
});
