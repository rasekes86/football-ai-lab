import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { orderMatchesByKickoff } from "../schedule.mjs";

const NOW=new Date("2026-11-16T19:00:00Z");
const games=[
  {id:"past-old",fecha_utc:"2026-10-31T17:00:00Z"},
  {id:"far",fecha_utc:"2026-11-30T20:00:00Z"},
  {id:"past-near",fecha_utc:"2026-11-15T19:00:00Z"},
  {id:"near-b",fecha_utc:"2026-11-17T19:00:00Z"},
  {id:"middle",fecha_utc:"2026-11-21T18:00:00Z"},
  {id:"near-a",fecha_utc:"2026-11-17T19:00:00Z"}
];
const ids=rows=>rows.map(x=>x.id);

test("los futuros se muestran de más cercano a más lejano, incluso si vienen desordenados",()=>{
  const matches=games.filter(x=>Date.parse(x.fecha_utc)>NOW.getTime());
  assert.deepEqual(ids(orderMatchesByKickoff(matches,NOW,"next")),
    ["near-a","near-b","middle","far"]);
  assert.deepEqual(ids(orderMatchesByKickoff([...matches].reverse(),NOW,"next")),
    ["near-a","near-b","middle","far"]);
});

test("Todos: próximos primero, después el histórico más reciente",()=>{
  const ordered=orderMatchesByKickoff(games,NOW,"all");
  assert.deepEqual(ids(ordered),
    ["near-a","near-b","middle","far","past-near","past-old"]);
  // La función no muta la lista original que utiliza el histórico Top 3.
  assert.equal(games[0].id,"past-old");
});

test("Ya disputados: orden cronológico inverso, sin perturbar el futuro",()=>{
  const older=games.filter(x=>Date.parse(x.fecha_utc)<=NOW.getTime());
  assert.deepEqual(ids(orderMatchesByKickoff(older,NOW,"past")),
    ["past-near","past-old"]);
});

test("datos inválidos al final, sin impedir que se muestren partidos válidos",()=>{
  const more=[{id:"bad",fecha_utc:"fecha imposible"},...games];
  assert.equal(orderMatchesByKickoff(more,NOW,"all").at(-1).id,"bad");
  assert.equal(orderMatchesByKickoff([],NOW,"next").length,0);
});

test("filtro inicial de Partidos prioriza próximos partidos sin orden contrario",()=>{
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const app=readFileSync(new URL("../app.js",import.meta.url),"utf8");
  assert.match(html,/id="periodFilter"[^>]*><option value="next" selected>/);
  assert.doesNotMatch(html,/id="sortFilter"/);
  assert.match(app,/orderMatchesByKickoff\(list, now, period\)/);
});
