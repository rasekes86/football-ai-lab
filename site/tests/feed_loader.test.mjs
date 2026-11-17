import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { FEEDS } from "../data.mjs";
import { feedSources, fetchPublishedFeed } from "../feed_loader.mjs";

const ROOT = "https://rasekes86.github.io/football-ai-lab/published/";

test("all 17 feeds are safe public CSV/JSON names and mirrored explicitly", () => {
  const filenames = Object.values(FEEDS);
  assert.equal(filenames.length, 17);
  const source = readFileSync(fileURLToPath(new URL("../scripts/publish_feeds.py", import.meta.url)), "utf8");
  for (const filename of filenames) {
    assert.match(source, new RegExp('"' + filename.replaceAll(".", "\\.") + '"'));
  }
  assert.deepEqual(new Set(filenames).size, filenames.length);
});

test("first source uses the PWA's own origin and the fallback is raw GitHub", () => {
  const sources = feedSources("predicciones.csv", "20261117", ROOT);
  assert.equal(sources[0],
    "https://rasekes86.github.io/football-ai-lab/published/predicciones.csv?v=20261117");
  assert.match(sources[1], /^https:\/\/raw\.githubusercontent\.com\//);
  assert.throws(() => feedSources("../.env", "abc", ROOT), /no autorizado/);
});

test("PWA can load predictions when raw GitHub is completely blocked", async () => {
  const seen = [];
  const result = await fetchPublishedFeed("predicciones", "predicciones.csv", "123", {
    localBase: ROOT,
    fetcher: async (url, options) => {
      seen.push({url, cache:options.cache});
      if (url.includes("raw.githubusercontent.com")) throw Error("blocked");
      return {ok:true, text:async () =>
        "id,liga,local,visitante\n12,LaLiga,Athletic Club,Espanyol\n"};
    }
  });
  assert.equal(seen.length, 1);
  assert.equal(seen[0].cache, "no-store");
  assert.equal(result[0].local, "Athletic Club");
});

test("404 on Pages falls back to GitHub raw but does not invent data", async () => {
  const seen = [];
  const result = await fetchPublishedFeed("odds", "cuotas_reales_verificadas.json", "abc", {
    localBase: ROOT,
    fetcher: async url => {
      seen.push(url);
      if (url.includes("published")) return {ok:false,status:404};
      return {ok:true,text:async()=>JSON.stringify({estado:"CON_CUOTAS",cuotas:[]})};
    }
  });
  assert.equal(seen.length,2);
  assert.equal(result.estado,"CON_CUOTAS");
  await assert.rejects(() => fetchPublishedFeed("bad", "predicciones.csv", "abc", {
    localBase:ROOT,fetcher:async()=>{throw Error("NetworkError")}
  }), /Pages.*GitHub raw/);
});
