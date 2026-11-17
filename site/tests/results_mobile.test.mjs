import test from "node:test";
import assert from "node:assert/strict";
import {performanceSnapshot} from "../performance.mjs";
import {recentResultGroups,renderResultsMobile,archivedAdditionalCards} from "../results_mobile.mjs";

const NOW=new Date("2026-11-17T18:00:00Z");
function base(id="match",date="2026-11-15T13:00:00Z"){
  return {id,liga:"Segunda División",local:"Tenerife",visitante:"Ceuta",
    fecha_utc:date,archivado_utc:"2026-11-14T12:00:00Z"};
}
function top(i,status="PENDIENTE",result="",props={}){
  return {...base(),clave:"top-"+i,mercado:"Tiros",seleccion:"Más de 17,5 tiros",
    estado:status,resultado:result,...props};
}
function extra(status="PENDIENTE",result="",props={}){
  return {...base(),clave:"extra",mercado:"Total goles",seleccion:"Menos de 2,5 goles",
    tipo_cuota:"INDICATIVA_NO_VERIFICADA",cuota_decimal:"1.90",
    estado:status,resultado:result,...props};
}
function snapshot(tops=[],extras=[],filters={}){
  return performanceSnapshot({archivedPicks:tops,allOdds:extras},filters,NOW);
}

test("Top 3 and additional results have independent scoreboards",()=>{
  const x=snapshot([
    top(1,"FINALIZADO","1"),top(2,"FINALIZADO","0"),
    top(3,"ESTADISTICA_NO_DISPONIBLE","")
  ],[extra("FINALIZADO","1")]);
  const r=renderResultsMobile(x,[{...base(),followup:{
    estado:"FINALIZADO",resultado_local:"2",resultado_visitante:"0"}}],6);
  assert.match(r.scorecards,/TOP 3 ORIGINAL/);
  assert.match(r.scorecards,/UNA ADICIONAL \+1,50/);
  assert.match(r.scorecards,/1 pendientes de liquidar/);
  assert.match(r.recent,/1 aciertos \/ 2 resueltos/);
  assert.match(r.recent,/Acierto confirmado/);
  assert.match(r.recent,/2 – 0/);
  assert.match(r.balance,/0,90 u\./);
  assert.match(r.balance,/1 cuotas indicativas liquidadas/);
  assert.match(r.scorecards,/50\s*%/); // Top 3: one out of two verified outcomes
  assert.match(r.scorecards,/100\s*%/); // Additional: one out of one, separate rate
});
test("only genuine settled outcomes enter recent; missing stats stay pending",()=>{
  const x=snapshot([top(1,"ESTADISTICA_NO_DISPONIBLE",""),
    top(2,"RESULTADO_NO_DISPONIBLE","")],[extra()]);
  const r=renderResultsMobile(x,[],6);
  assert.equal(r.recentCount,0);
  assert.equal(r.hasMore,false);
  assert.match(r.recent,/Todavía no hay partidos/);
  assert.match(r.scorecards,/Sin resultados suficientes todavía/);
  assert.match(r.balance,/>—</);
  assert.doesNotMatch(r.recent,/Fallo confirmado/);
});
test("archived additional is one per fixture and ignored extra markets never appear",()=>{
  const x=snapshot([
    top(1,"FINALIZADO","1"),
    top(2,"FINALIZADO","1"),
    top(3,"FINALIZADO","1"),
    top(4,"FINALIZADO","0") // exploratory fourth, ignored
  ],[
    extra("FINALIZADO","0",{tipo_cuota:"OFRECIDA_API_REGISTRADA",cuota_decimal:"1.95"}),
    extra("FINALIZADO","1",{clave:"another",archivado_utc:"2026-11-14T12:01:00Z",cuota_decimal:"3.0"})
  ]);
  const r=renderResultsMobile(x,[],6);
  assert.equal(x.top.registered,3);
  assert.equal(x.additional.registered,1);
  assert.match(r.recent,/Fallo confirmado/);
  assert.match(r.recent,/Cuota API observada/);
  assert.match(r.balance,/−1,00 u\./);
  assert.doesNotMatch(r.recent,/3,000/);
  assert.match(r.balance,/1 cuotas API liquidadas/);
});
test("most recent fixtures first, one card per fixture, with safe load more",()=>{
  const a=top(1,"FINALIZADO","1");
  const b=top(1,"FINALIZADO","0",{id:"next",clave:"next-1",fecha_utc:"2026-11-16T13:00:00Z",archivado_utc:"2026-11-15T12:00:00Z"});
  const x=snapshot([a,b],[]);
  const grouped=recentResultGroups(x,[],1);
  assert.equal(grouped.total,2);
  assert.deepEqual(grouped.shown.map(y=>y.id),["next"]);
  assert.equal(grouped.hasMore,true);
  assert.equal(recentResultGroups(x,[],6).shown.length,2);
});
test("filters from audited model affect summaries AND recent cards",()=>{
  const recent=top(1,"FINALIZADO","1");
  const out=top(1,"FINALIZADO","1",{id:"other",clave:"other-1",liga:"Bundesliga",local:"Bayern",visitante:"Köln"});
  const x=snapshot([recent,out],[],{league:"Bundesliga"});
  const r=renderResultsMobile(x,[],6);
  assert.equal(r.recentCount,1);
  assert.match(r.recent,/Bundesliga/);
  assert.doesNotMatch(r.recent,/Tenerife – Ceuta/);
});
test("HTML escapes malicious names, picks, and identifiers",()=>{
  const x=snapshot([top(1,"FINALIZADO","1",{
    id:'<img src=x onerror=alert(1)>',clave:"hack",
    local:"<script>evil()</script>",seleccion:"<svg onload=evil()>"
  })],[]);
  const r=renderResultsMobile(x,[],6);
  assert.match(r.recent,/&lt;script&gt;/);
  assert.match(r.recent,/&lt;svg onload=evil\(\)&gt;/);
  assert.doesNotMatch(r.recent,/<script>/);
  assert.doesNotMatch(r.recent,/<svg onload=/);
});


test("pending future additional displays exact archived pick, market and quote without expansion",()=>{
  const e=extra("PENDIENTE","",{
    id:"upcoming",clave:"upcoming|extra",
    fecha_utc:"2026-11-21T18:00:00Z",
    seleccion:"Menos de 3,5 goles",mercado:"Total goles",
    cuota_decimal:"2.025",tipo_cuota:"OFRECIDA_API_REGISTRADA"
  });
  const audited=snapshot([], [e]);
  const screen=renderResultsMobile(audited,[],6,8,NOW);
  assert.equal(screen.recentCount,0,"pending future bet is not a settled match");
  assert.equal(screen.additionalCount,1);
  assert.match(screen.additionalCards,/Tenerife – Ceuta/);
  assert.match(screen.additionalCards,/Total goles/);
  assert.match(screen.additionalCards,/Menos de 3,5 goles/);
  assert.match(screen.additionalCards,/2,025/);
  assert.match(screen.additionalCards,/Cuota API/);
  assert.match(screen.additionalCards,/Pendiente/);
  assert.match(screen.additionalCards,/data-open-id="upcoming"/);
  assert.doesNotMatch(screen.additionalCards,/<details/);
});
test("settled match displays the actual additional selection before details",()=>{
  const audited=snapshot([top(1,"FINALIZADO","1")],[
    extra("FINALIZADO","0",{seleccion:"Menos de 2,5 goles",mercado:"Total goles"})
  ]);
  const screen=renderResultsMobile(audited,[],6,8,NOW);
  const visible=screen.recent.split('<details class="results-v2-fixture-details">')[0];
  assert.match(visible,/ADICIONAL \+1,50/);
  assert.match(visible,/Total goles/);
  assert.match(visible,/Menos de 2,5 goles/);
  assert.match(visible,/cuota 1,90/);
  assert.match(visible,/Fallo confirmado/);
});
test("additional list contains only original first frozen quote, not alternatives or exploratory prices",()=>{
  const first=extra("FINALIZADO","1",{seleccion:"Ambos marcan: Sí",mercado:"Ambos marcan",cuota_decimal:"1.95"});
  const later=extra("FINALIZADO","0",{clave:"other",archivado_utc:"2026-11-14T12:01:00Z",seleccion:"Resultado 2",cuota_decimal:"8.0"});
  const exploratory=extra("FINALIZADO","1",{
    clave:"explore",tipo_cuota:"CUOTA_JUSTA_MODELO",cuota_decimal:"19.0"
  });
  const rows=snapshot([], [first,later,exploratory]);
  const cards=archivedAdditionalCards(rows,8,NOW);
  assert.equal(cards.total,1);
  assert.match(cards.html,/Ambos marcan: Sí/);
  assert.match(cards.html,/1,95/);
  assert.doesNotMatch(cards.html,/Resultado 2|8,00|19,00/);
});
test("pending soonest future extras first, then most recent past; load more is accurate",()=>{
  const extraFor=(id,kick)=>extra("PENDIENTE","",{id,clave:id+"|extra",
    fecha_utc:kick,archivado_utc:"2026-11-14T12:00:00Z"});
  const rows=snapshot([], [
    extraFor("past","2026-11-16T13:00:00Z"),
    extraFor("later","2026-11-25T13:00:00Z"),
    extraFor("soon","2026-11-21T13:00:00Z")
  ]);
  const list=archivedAdditionalCards(rows,2,NOW);
  assert.equal(list.total,3);
  assert.equal(list.hasMore,true);
  assert.ok(list.html.indexOf('data-open-id="soon"')<list.html.indexOf('data-open-id="later"'));
  assert.doesNotMatch(list.html,/data-open-id="past"/);
});
test("additional titles and market values are escaped in immediately visible cards",()=>{
  const row=extra("PENDIENTE","",{
    id:"<img src=x onerror=evil()>",clave:"escaped",
    seleccion:"<script>attack()</script>",mercado:"<svg onload=bad()>"
  });
  const screen=renderResultsMobile(snapshot([], [row]),[],6,8,NOW);
  assert.match(screen.additionalCards,/&lt;script&gt;attack/);
  assert.match(screen.additionalCards,/&lt;svg onload=bad\(\)&gt;/);
  assert.doesNotMatch(screen.additionalCards,/<script>|<svg onload=/);
});
