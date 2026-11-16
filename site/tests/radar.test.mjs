import test from "node:test";
import assert from "node:assert/strict";
import { radarSnapshot,radarMetric } from "../radar.mjs";
import { buildModel,FEEDS } from "../data.mjs";

const NOW=new Date("2026-11-16T15:00:00Z");
const X="SP2|202611201900|tenerife|ceuta";
const level="BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA";
const future=[
 {id:X,liga:"Segunda División",local:"Tenerife",visitante:"Ceuta",
  fecha_utc:"2026-11-20T19:00:00Z",mercados:{
    corners:[{mercado:"Córners totales",seleccion:"Más de 9,5 córners totales",
      probabilidad:.71,cuota_justa:1.408,nivel:level,posicion_top3:2,
      linea:9.5,direccion:"mas"},
      {mercado:"Córners totales",seleccion:"Menos de 11,5 córners totales",
      probabilidad:.67,cuota_justa:1.493,nivel:"EXPLORATORIO_NO_VALIDADO",
      linea:11.5,direccion:"menos"}],
    double:[{mercado:"Doble oportunidad",seleccion:"1X",
      probabilidad:.86,cuota_justa:1.163,nivel:"MODELO_NO_CALIBRADO"}]
  }},
 {id:"SP1|no-context",liga:"LaLiga",local:"Barcelona",visitante:"Sevilla",
  fecha_utc:"2026-11-22T20:00:00Z",mercados:{corners:[
    {mercado:"Córners totales",seleccion:"Más de 8,5 córners totales",
    probabilidad:.81,cuota_justa:1.235,nivel:"EXPLORATORIO_NO_VALIDADO",
    linea:8.5,direccion:"mas"}]}},
 {id:"SP1|old",liga:"LaLiga",local:"Getafe",visitante:"Girona",
  fecha_utc:"2026-11-15T20:00:00Z",mercados:{corners:[
    {mercado:"Córners totales",seleccion:"Más de 9,5 córners",
    probabilidad:.96,cuota_justa:1.042,nivel:level,linea:9.5,direccion:"mas"}]}}
];
function window(matches,values,opts={}) {
 const known=values.filter(v=>v!==null);
 const stats={};
 for(const m of ["corners","goals","shots","on_target","yellow","red","fouls"]){
   const use=m==="corners"?values: m==="goals"?Array(matches).fill(2):Array(matches).fill(null);
   const valid=use.filter(v=>v!==null);
   stats[m]={n:valid.length,mean:valid.length?valid.reduce((a,b)=>a+b,0)/valid.length:null,
     values:use};
 }
 return {matches,latest:"2026-11-14",wins:opts.wins||0,draws:opts.draws||0,
   losses:opts.losses||0,both_scored:opts.btts||0,
   goals_for:1,goals_against:1,metrics:stats};
}
const ctx=[{id:X,liga:"Segunda División",
  equipos:{
    local:{overall:{"5":window(5,[11,9,10,8,12]),"10":window(5,[11,9,10,8,12]),
                   "20":window(5,[11,9,10,8,12])},
      venue_only:{"5":window(5,[11,9,10,8,null]),"10":window(5,[11,9,10,8,null]),
                   "20":window(5,[11,9,10,8,null])}},
    visitante:{overall:{"5":window(5,[10,9,9,11,7]),"10":window(5,[10,9,9,11,7]),
                   "20":window(5,[10,9,9,11,7])},
      venue_only:{"5":window(5,[10,9,null,null,null]),
                   "10":window(5,[10,9,null,null,null]),
                   "20":window(5,[10,9,null,null,null])}}
  }}];
const model={marketFutures:future,radarContexts:ctx};
test("feed Fase 5 conectado sin alterar las selecciones Top3",()=>{
 assert.equal(FEEDS.radar_contexto_equipos,"radar_contexto_equipos.json");
 const d=buildModel({radar_contexto_equipos:{partidos:ctx},
   pronosticos_mercados_futuros:{partidos:future}},NOW);
 assert.equal(d.radarContexts.length,1);
 assert.equal(d.marketFutures.length,3);
 assert.equal(d.archivedPicks.length,0);
});
test("radar futuro elimina pasado y muestra cobertura real por equipo",()=>{
 const r=radarSnapshot(model,{market:"corners",scope:"venue_only",window:10},NOW);
 assert.equal(r.total,2);
 assert.equal(r.rows[0].id,X);
 assert.equal(r.rows[0].profile.verified,6);
 assert.equal(r.rows[0].profile.sample,10);
 assert.equal(r.rows[0].profile.coverage,.6);
 assert.equal(r.rows[0].profile.enough,false);
 assert.equal(r.rows[0].profile.home.mean,9.5);
 assert.equal(r.rows[0].profile.away.mean,9.5);
 assert.deepEqual(r.rows[0].profile.observedHome,
   {matched:2,observed:4,frequency:.5,direction:"over",line:9.5});
});
test("ausencia nunca da cobertura del 100% ni una media inventada",()=>{
 const r=radarSnapshot(model,{market:"corners"},NOW);
 const missing=r.rows.find(x=>x.id==="SP1|no-context");
 assert.equal(missing.profile.coverage,null);
 assert.equal(missing.profile.home.mean,null);
 assert.equal(missing.profile.verified,0);
 assert.equal(missing.profile.enough,false);
});
test("filtros: cobertura por estadística, probabilidad, calidad y liga",()=>{
 assert.equal(radarSnapshot(model,{market:"corners",coverage:.5},NOW).total,1);
 assert.equal(radarSnapshot(model,{market:"corners",coverage:.8},NOW).total,0);
 assert.equal(radarSnapshot(model,{market:"corners",league:"Segunda División",
    quality:"top3",minProbability:.7},NOW).total,1);
 assert.equal(radarSnapshot(model,{market:"corners",league:"LaLiga",
    quality:"top3"},NOW).total,0);
 assert.equal(radarSnapshot(model,{market:"corners",minFair:1.5},NOW).total,0);
});
test("local/fuera frente a general modifica cobertura sin contaminar pronóstico",()=>{
 const venue=radarSnapshot(model,{market:"corners",scope:"venue_only"},NOW).rows[0];
 const full=radarSnapshot(model,{market:"corners",scope:"overall"},NOW).rows[0];
 assert.equal(venue.profile.coverage,.6);
 assert.equal(full.profile.coverage,1);
 assert.equal(venue.best.probabilidad,full.best.probabilidad);
 assert.equal(full.profile.enough,true);
});
test("mercados resultados no extrapolan porcentajes ni hacen ranking de valor",()=>{
 const d=radarSnapshot(model,{market:"double"},NOW);
 assert.equal(d.total,1);
 assert.equal(d.metric,"goals");
 assert.equal(d.rows[0].profile.observedHome,null);
 assert.equal(d.rows[0].profile.observedAway,null);
 assert.equal(d.descriptiveOnly,true);
 assert.equal(radarMetric("fouls"),"fouls");
});
test("nuevos filtros de equipo y orden por cobertura no recogen matches pasados",()=>{
 const r=radarSnapshot(model,{market:"corners",team:"Ténerífe",order:"coverage"},NOW);
 assert.equal(r.total,1);
 assert.equal(r.rows[0].local,"Tenerife");
});
