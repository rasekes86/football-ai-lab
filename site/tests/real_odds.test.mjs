import test from "node:test";
import assert from "node:assert/strict";
import { realOddsSnapshot, REAL_ODDS_CATEGORIES } from "../real_odds.mjs";
import { FEEDS, buildModel } from "../data.mjs";

const NOW=new Date("2026-11-16T12:00:00Z");
const FIXTURE="SP1|202611202000|ath bilbao|espanyol";
function quote(book="Mock Book A",price=2.2,overrides={}){
  return {
    fixture_id:FIXTURE,liga:"LaLiga",local:"Athletic Club",visitante:"Espanyol",
    fecha_utc:"2026-11-20T20:00:00Z",categoria:"result",
    seleccion:"Athletic Club gana",probabilidad_modelo:.56,
    nivel:"MODELO_NO_CALIBRADO",posicion_top3:1,
    cuota_real:price,bookmaker:book,bookmaker_id:book,
    mercado_proveedor:"h2h",resultado_proveedor:"1",linea:null,
    p_implicita:1/price,p_mercado_sin_margen:.43,margen_casa:.071,
    diferencia_puntos_pct:13,ev_teorico_unidad:Math.round((.56*price-1)*1e4)/1e4,
    actualizado_utc:"2026-11-16T11:00:00Z",
    capturado_utc:"2026-11-16T12:00:00Z",proveedor:"The Odds API V4",
    fuente:"https://the-odds-api.com/",
    etiqueta:"COMPARACION_INFORMATIVA_NO_VALIDADA",...overrides
  };
}
const MODEL={
  realOddsRaw:{estado:"CON_CUOTAS",capturado_utc:"2026-11-16T12:00:00Z",
    auditoria:{estimacion_creditos_maximos:2}},
  realOddsComparison:{comparaciones:[
    quote(),quote("Mock Book B",2.35),
    quote("Mock Book A",1.92,{categoria:"goals",seleccion:"Más de 2,5 goles",
      probabilidad_modelo:.60,ev_teorico_unidad:.152,mercado_proveedor:"totals",
      resultado_proveedor:"over",linea:2.5}),
  ]}
};

test("nuevo feed y modelo se conectan por separado sin alterar el Top3",()=>{
  assert.equal(FEEDS.cuotas_reales_verificadas,"cuotas_reales_verificadas.json");
  assert.equal(FEEDS.comparacion_cuotas_reales,"comparacion_cuotas_reales.json");
  const model=buildModel({
    cuotas_reales_verificadas:MODEL.realOddsRaw,
    comparacion_cuotas_reales:MODEL.realOddsComparison
  },NOW);
  assert.equal(model.realOddsComparison.comparaciones.length,3);
  assert.equal(model.archivedPicks.length,0);
});
test("sin fuente real no crea supuestas oportunidades ni precios",()=>{
  const x=realOddsSnapshot({realOddsRaw:{estado:"DESACTIVADO"},
    realOddsComparison:{comparaciones:[]}}, {},NOW);
  assert.equal(x.status,"DESACTIVADO");
  assert.equal(x.configured,false);
  assert.equal(x.cards.length,0);
  assert.equal(x.quotes,0);
  assert.equal(REAL_ODDS_CATEGORIES.length,3);
});
test("agrupa por partido mercado y selección, mejor precio se identifica por bookmaker",()=>{
  const x=realOddsSnapshot(MODEL,{},NOW);
  assert.equal(x.cards.length,2);
  assert.equal(x.quotes,3);
  assert.equal(x.games,1);
  assert.equal(x.providers.length,2);
  const win=x.cards.find(x=>x.categoria==="result");
  assert.equal(win.opciones.length,2);
  assert.equal(win.mejor.cuota_real,2.35);
  assert.equal(win.mejor.bookmaker,"Mock Book B");
  assert.equal(win.posicion_top3,1);
  assert.equal(x.quota,2);
});
test("filtros por liga mercado bookmaker equipo y probabilidad",()=>{
  assert.equal(realOddsSnapshot(MODEL,{market:"goals"},NOW).cards.length,1);
  assert.equal(realOddsSnapshot(MODEL,{league:"Segunda División"},NOW).cards.length,0);
  assert.equal(realOddsSnapshot(MODEL,{bookmaker:"Mock Book B"},NOW).cards.length,1);
  assert.equal(realOddsSnapshot(MODEL,{team:"Espanyòl"},NOW).cards.length,2);
  assert.equal(realOddsSnapshot(MODEL,{minProbability:".6"},NOW).cards.length,1);
  assert.equal(realOddsSnapshot(MODEL,{minProbability:".8"},NOW).cards.length,0);
});
test("caducidad, partido empezado y documento de terceros no se presentan como actual",()=>{
  assert.equal(realOddsSnapshot(MODEL,{},new Date("2026-11-17T15:00:00Z")).cards.length,0);
  assert.equal(realOddsSnapshot(MODEL,{},new Date("2026-11-21T12:00:00Z")).cards.length,0);
  const tampered={...MODEL,realOddsComparison:{comparaciones:[
    quote("Weird",2.5,{proveedor:"Sin verificar"}),
    quote("Bad price",1.1,{ev_teorico_unidad:5}),
    quote("No contract",2.2,{etiqueta:"NO_ES_REAL"}),
  ]}};
  assert.equal(realOddsSnapshot(tampered,{},NOW).cards.length,0);
});
