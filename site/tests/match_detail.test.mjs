import test from "node:test";
import assert from "node:assert/strict";
import {archivedAdditional,detailSnapshot,renderMatchDetail} from "../match_detail.mjs";

const now=new Date("2026-11-17T17:00:00Z");
const future="2026-11-21T18:00:00Z";
const past="2026-11-15T13:00:00Z";
const crest=()=>'<span class="mock-crest"></span>';
const match=(kick=future)=>({
  id:"SP1|match",liga:"LaLiga",local:"Sevilla",visitante:"Betis",
  fecha_utc:kick,odds:[],picks:[],forecast:null,historicalForecast:null,
  followup:null,breakdown:null
});
const pick=(m,i,results={})=>({
  id:m.id,clave:m.id+"|top"+i,liga:m.liga,fecha_utc:m.fecha_utc,
  archivado_utc:"2026-11-14T10:00:00Z",mercado:"Total goles",
  seleccion:i%2?"Menos de 2,5 goles":"Más de 1,5 goles",
  probabilidad:"0.63",estado:"PENDIENTE",resultado:"",
  ...results
});
const extra=(m,results={})=>({
  id:m.id,clave:m.id+"|extra",liga:m.liga,fecha_utc:m.fecha_utc,
  archivado_utc:"2026-11-14T10:00:00Z",mercado:"Ambos marcan",
  seleccion:"Sí",cuota_decimal:"1.909",
  tipo_cuota:"OFRECIDA_API_REGISTRADA",bookmaker:"Bet 365",
  proveedor_cuota:"5DollarFootballAPI",
  fecha_cuota_utc:"2026-11-14T09:45:00Z",
  marca_tiempo_tipo:"CAPTURA_NO_ACTUALIZACION",
  estado:"PENDIENTE",resultado:"",
  ...results
});

test("mobile detail prioritizes score, frozen Top3 and extra; advanced stays collapsed",()=>{
  const m=match();
  m.picks=[pick(m,1),pick(m,2),pick(m,3)];
  m.odds=[extra(m)];
  const html=renderMatchDetail(m,crest,now);
  assert.match(html,/match-v2-hero/);
  assert.match(html,/Top 3 del partido/);
  assert.match(html,/La adicional/);
  assert.match(html,/1,909/);
  assert.match(html,/Cuota registrada antes del inicio/);
  assert.match(html,/Estadísticas/); // in advanced methodology area
  assert.match(html,/<details class="match-v2-accordion">/);
  assert.equal((html.match(/class="match-v2-pick pending"/g)||[]).length,3);
  assert.doesNotMatch(html,/\sopen(?:[ >])/);
  assert.doesNotMatch(html,/>[4-9]\. /); // no exploratory bet
});

test("sporting hit and miss independent of indicative or API price",()=>{
  const m=match(past);
  m.picks=[pick(m,1,{estado:"FINALIZADO",resultado:"1"}),
    pick(m,2,{estado:"FINALIZADO",resultado:"0"}),
    pick(m,3,{estado:"ESTADISTICA_NO_DISPONIBLE",resultado:""})];
  m.odds=[extra(m,{tipo_cuota:"INDICATIVA_NO_VERIFICADA",
    estado:"FINALIZADO",resultado:"1",retorno_simulado_unidad:"0.909"})];
  m.followup={estado:"FINALIZADO",resultado_local:"1",resultado_visitante:"0"};
  const d=detailSnapshot(m,now);
  assert.deepEqual(d.score,["1","0"]);
  assert.equal(d.finished,2);
  assert.equal(d.wins,1);
  assert.equal(d.notFinished,1);
  const html=renderMatchDetail(m,crest,now);
  assert.match(html,/Acierto confirmado/);
  assert.match(html,/Fallo confirmado/);
  assert.match(html,/Estadística sin verificar/);
  assert.match(html,/Referencia no acreditada por bookmaker/);
  assert.match(html,/Balance hipotético de 1 unidad/);
  assert.match(html,/0,91 u\./);
});

test("missing and future result are never fabricated",()=>{
  const m=match();
  let html=renderMatchDetail(m,crest,now);
  assert.match(html,/Sin adicional archivada/);
  assert.match(html,/Todavía no hay un Top 3 archivado/);
  assert.match(html,/Pendiente de disputar/);
  assert.match(html,/>VS</);
  assert.doesNotMatch(html,/1,909/);
  m.followup={estado:"PENDIENTE",resultado_local:"2",resultado_visitante:"1"};
  html=renderMatchDetail(m,crest,now);
  assert.doesNotMatch(html,/class="match-v2-result"/);
});

test("first valid archived additional selected; no second price or old late quote",()=>{
  const m=match();
  const early=extra(m);
  const later=extra(m,{clave:m.id+"|later",archivado_utc:"2026-11-15T09:00:00Z",
    cuota_decimal:"5.50"});
  const invalid=extra(m,{clave:m.id+"|invalid",archivado_utc:"2026-11-16T09:00:00Z",
    cuota_decimal:"1.50"});
  const post=extra(m,{clave:m.id+"|after",archivado_utc:"2026-11-23T09:00:00Z",
    cuota_decimal:"99.0"});
  m.odds=[post,later,invalid,early];
  assert.equal(archivedAdditional(m).clave,early.clave);
  const html=renderMatchDetail(m,crest,now);
  assert.match(html,/1,909/);
  assert.doesNotMatch(html,/5,50|99,00/);
});

test("bad odd fields and wrong fixture cannot be treated as valid",()=>{
  const m=match();
  m.odds=[
    extra(m,{id:"other fixture"}),
    extra(m,{clave:"low",cuota_decimal:"1.50"}),
    extra(m,{clave:"no-date",archivado_utc:"??"}),
    extra(m,{clave:"unknown",tipo_cuota:"EXPLORATORIO"}),
  ];
  assert.equal(archivedAdditional(m),null);
});

test("verified statistics preserve unavailable values and whitelist sources",()=>{
  const m=match(past);
  m.breakdown={marcador:"2–0",fuente_marcador:"https://www.laliga.com/resultados",
    estadisticas:{
      corners:{nombre:"Córners",local:7,visitante:0,total:7,
        fuentes:["https://site.api.espn.com/test","https://evil.example/test"]},
      yellow:{nombre:"Amarillas",local:null,visitante:null,total:null}
    }};
  const html=renderMatchDetail(m,crest,now);
  assert.match(html,/Estadísticas finales/);
  assert.match(html,/Córners/);
  assert.match(html,/«—» significa sin dato, no cero/);
  assert.match(html,/ESPN · fuente/);
  assert.doesNotMatch(html,/href="https:\/\/evil/);
  assert.match(html,/https:\/\/evil\.example/);
});

test("HTML inputs escaped including IDs, bookmaker, probabilities and source",()=>{
  const m=match();
  m.local='<img src=x onerror=alert(1)>';
  m.picks=[pick(m,1,{seleccion:"<script>bad</script>"})];
  m.odds=[extra(m,{bookmaker:"<svg onload=bad()>"})];
  const html=renderMatchDetail(m,crest,now);
  assert.doesNotMatch(html,/<img src=x/);
  assert.doesNotMatch(html,/<script>/);
  assert.doesNotMatch(html,/<svg onload/);
  assert.match(html,/&lt;script&gt;/);
  assert.match(html,/&lt;svg onload=bad\(\)&gt;/);
});

test("forecasts are advanced estimates, not replacement original Top 3",()=>{
  const m=match();
  m.historicalForecast={modelo:"Poisson/Elo",
    prob_local:"0.40",prob_empate:"0.30",prob_visitante:"0.30"};
  const html=renderMatchDetail(m,crest,now);
  assert.match(html,/Pronóstico 1X2 del modelo/);
  assert.match(html,/Referencia histórica archivada/);
  assert.match(html,/40\s?%/);
  assert.match(html,/Todavía no hay un Top 3 archivado/);
});
