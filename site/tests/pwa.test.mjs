import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname,join} from "node:path";
import {fileURLToPath} from "node:url";
import vm from "node:vm";

const SITE=dirname(fileURLToPath(new URL("../pwa.js",import.meta.url)));
const read=name=>readFileSync(join(SITE,name),"utf8");

test("PWA manifest is valid and scoped to this GitHub Pages project",()=>{
  const manifest=JSON.parse(read("manifest.webmanifest"));
  assert.equal(manifest.name,"Football AI Lab");
  assert.equal(manifest.lang,"es-ES");
  assert.equal(manifest.start_url,"./#fixtures");
  assert.equal(manifest.scope,"./");
  assert.equal(manifest.display,"standalone");
  assert.deepEqual(manifest.icons.filter(x=>x.type==="image/png").map(x=>x.sizes),["192x192","512x512"]);
  assert.ok(manifest.icons.filter(x=>x.type==="image/png").every(x=>x.purpose.includes("maskable")));
  assert.ok(manifest.shortcuts.some(x=>x.url==="./#realodds"));
});
test("site retains all existing sections and adds install controls",()=>{
  const html=read("index.html");
  assert.match(html,/rel="manifest" href="\.\/manifest\.webmanifest"/);
  assert.match(html,/id="pwaInstallButton"/);
  assert.match(html,/id="pwaOfflineBanner"/);
  assert.match(html,/<script type="module" src="\.\/pwa\.js"><\/script>/);
  for(const view of ["fixtures","overview","matches","radar","markets","history","odds","realodds","model"]){
    assert.ok(html.includes('id="view-'+view+'"'),view);
  }
});
test("service worker ignores third-party odds and data requests",async()=>{
  const handlers=new Map();
  const scope="https://rasekes86.github.io/football-ai-lab/";
  const self={
    registration:{scope},
    clients:{claim:()=>Promise.resolve()},
    skipWaiting:()=>Promise.resolve(),
    addEventListener:(name,fn)=>handlers.set(name,fn)
  };
  vm.runInNewContext(read("sw.js"),{
    self,URL,Set,Response,
    caches:{open:async()=>({match:async()=>new Response("offline copy"),put:async()=>{}}),keys:async()=>[]},
    fetch:async()=>new Response("online copy")
  },{filename:"sw.js"});
  let intercepted=0;
  const tasks=[];
  function fire(url,mode="cors"){
    const event={
      request:{method:"GET",url,mode},
      respondWith:promise=>{intercepted++;tasks.push(promise)}
    };
    handlers.get("fetch")(event);
  }
  fire("https://raw.githubusercontent.com/rasekes86/football-ai-lab/main/output/comparacion_cuotas_reales.json");
  fire("https://a.espncdn.com/i/teamlogos/soccer/500/86.png");
  fire(scope+"crests.json?v=12345");
  assert.equal(intercepted,0,"data feeds, external logos and dynamic crests must not be cached");
  fire(scope+"styles.css");
  fire(scope+"#fixtures","navigate");
  assert.equal(intercepted,2,"same-origin app shell should use the service worker");
  const settled=await Promise.allSettled(tasks);
  assert.ok(settled.every(x=>x.status==="fulfilled"));
});
