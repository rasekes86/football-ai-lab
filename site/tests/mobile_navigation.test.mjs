import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const read=name=>readFileSync(new URL("../"+name,import.meta.url),"utf8");
const html=read("index.html");
const js=read("app.js");
const css=read("styles.css");

test("mobile navigation has exactly four destinations in user order",()=>{
  const nav=html.match(/<nav class="score-bottom-nav"[^>]*>([\s\S]*?)<\/nav>/);
  assert.ok(nav,"mobile navigation exists");
  assert.deepEqual([...nav[1].matchAll(/data-view="([^"]+)"/g)].map(m=>m[1]),
    ["home","fixtures","performance","more"]);
  assert.match(nav[1],/>Inicio</);
  assert.match(nav[1],/>Partidos</);
  assert.match(nav[1],/>Resultados</);
  assert.match(nav[1],/>Más</);
});
test("all ten legacy views remain reachable through More or desktop advanced",()=>{
  const views=["overview","matches","radar","markets","history","odds",
    "realodds","model","fixtures","performance"];
  for(const view of views){
    assert.ok(html.includes('id="view-'+view+'"'),"view-"+view);
    assert.ok(html.includes('data-go="'+view+'"')||
      html.includes('data-view="'+view+'"'),"link to "+view);
  }
  assert.ok(html.includes('id="view-home"'));
  assert.ok(html.includes('id="view-more"'));
});
test("mobile Results starts with a compact summary and optional full audit",()=>{
  assert.ok(html.includes('id="performanceMobileSummary"'));
  assert.ok(html.includes('id="performanceExpandButton"'));
  assert.ok(html.includes('id="performanceAdvanced"'));
  assert.match(css,/\.performance-advanced\{display:none\}/);
  assert.match(css,/\.performance-advanced\.is-open\{display:block\}/);
  assert.match(js,/performanceExpandButton/);
});
test("root loads Inicio and preserves legacy hash deep links",()=>{
  assert.match(js,/view: "home"/);
  assert.match(js,/else changeView\("home"\)/);
  assert.match(js,/if\(VIEWS\.includes\(initial\)\)changeView\(initial\)/);
  assert.match(js,/if\(VIEWS\.includes\(view\)\)changeView\(view\)/);
});
test("all HTML element ids stay unique across the new and legacy pages",()=>{
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(new Set(ids).size,ids.length);
});
