import test from "node:test";
import assert from "node:assert/strict";
import {performanceSnapshot} from "../performance.mjs";
import {recentResultGroups,renderResultsMobile} from "../results_mobile.mjs";

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
