import test from "node:test";
import assert from "node:assert/strict";
import { madridDay, breakdownSnapshot, renderPerformanceBreakdown } from "../site/performance_breakdown.mjs";

const make=(id,league,time,group,outcome,ret)=>{
  const result={id,liga:league,fecha_utc:time,group,
    estado:outcome===null?"ESTADISTICA_NO_DISPONIBLE":"FINALIZADO",
    resultado:outcome===null?"":String(outcome),return:ret};
  return result;
};
const rows=[
  make("m1","LaLiga","2026-11-20T23:30:00Z","Top 3",1,.25),
  make("m1","LaLiga","2026-11-20T23:30:00Z","Top 3",0,-1),
  make("m1","LaLiga","2026-11-20T23:30:00Z","Adicional +1,50",1,.8),
  make("m2","Bundesliga","2026-11-20T17:00:00Z","Top 3",0,-1),
  make("m2","Bundesliga","2026-11-20T17:00:00Z","Adicional +1,50",null,null),
  make("m3","Serie A","2026-11-22T18:00:00Z","Top 3",null,null)
];
const asOf="2026-11-21T18:00:00Z";

test("Agrupa por fecha local de Madrid, no fecha UTC",()=>{
  assert.equal(madridDay("2026-11-20T23:30:00Z"),"2026-11-21");
  assert.equal(madridDay("fecha inválida"),null);
});
test("Agrupación diaria excluye partidos futuros y no convierte pendientes en derrotas",()=>{
  const x=breakdownSnapshot({rows},asOf);
  assert.deepEqual(x.days.map(d=>d.key),["2026-11-21","2026-11-20"]);
  assert.equal(x.days[0].verifiedGames,1);
  assert.equal(x.days[0].top.hits,1);
  assert.equal(x.days[0].top.losses,1);
  assert.equal(x.days[0].additional.hits,1);
  assert.equal(x.days[0].total.settled,3);
  assert.ok(Math.abs(x.days[0].total.profit-.05)<1e-9);
  assert.equal(x.days[1].additional.pending,1);
  assert.equal(x.days[1].additional.settled,0);
  assert.equal(x.days[1].total.losses,1);
  assert.equal(x.leagues.find(l=>l.name==="Serie A").total.registered,0);
});
test("Vista por liga separa Top 3, adicional y balance mixto sin duplicarlos",()=>{
  const x=breakdownSnapshot({rows},asOf);
  const liga=x.leagues.find(l=>l.name==="LaLiga");
  assert.equal(liga.games,1);
  assert.equal(liga.top.settled,2);
  assert.equal(liga.additional.settled,1);
  assert.equal(liga.total.priced,3);
  const view=renderPerformanceBreakdown({rows},{asOf,league:"LaLiga",dayLimit:1});
  assert.equal(view.dayCount,2);
  assert.equal(view.hasMore,true);
  assert.match(view.leagues,/LaLiga/);
  assert.doesNotMatch(view.leagues,/Bundesliga/);
  assert.match(view.days,/Ver desglose por liga/);
});
