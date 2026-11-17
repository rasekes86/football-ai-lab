/** Same-origin first for PWA, public raw GitHub as a read-only fallback.
 * Never cache live odds or predictions in the service worker.
 */
import {parseCsv} from "./data.mjs";

export const REPO_RAW_BASE =
  "https://raw.githubusercontent.com/rasekes86/football-ai-lab/main/output/";

export function feedSources(filename, token, localBase = new URL("./published/", import.meta.url)) {
  if (!/^[a-z0-9_-]+\.(csv|json)$/.test(filename)) {
    throw new Error("Archivo de feed no autorizado");
  }
  const local = new URL(filename, localBase);
  local.searchParams.set("v", String(token));
  const github = new URL(filename, REPO_RAW_BASE);
  github.searchParams.set("ref", String(token));
  return [local.href, github.href];
}

export async function fetchPublishedFeed(name, filename, token, {
  fetcher = fetch, localBase
} = {}) {
  const sources = feedSources(filename, token, localBase);
  const failures = [];
  for (let i = 0; i < sources.length; i++) {
    try {
      const response = await fetcher(sources[i], {cache: "no-store"});
      if (!response.ok) throw new Error("HTTP " + response.status);
      const body = await response.text();
      return filename.endsWith(".json") ? JSON.parse(body) : parseCsv(body);
    } catch (error) {
      // Not all Android browsers/networks allow raw.githubusercontent.com.
      // Do not persist a stale response after all sources fail.
      failures.push((i === 0 ? "Pages" : "GitHub raw") + ": " +
        (error instanceof Error ? error.message.slice(0, 120) : "No disponible"));
    }
  }
  throw new Error(name + " — " + failures.join(" / "));
}
