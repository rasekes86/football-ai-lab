import test from "node:test";
import assert from "node:assert/strict";
import { futureMarketSnapshot } from "../future_markets.mjs";
import { buildModel, FEEDS } from "../data.mjs";
const now=new Date("2026-11-16T15:00:00Z");
const pick=(seleccion, probabilidad, nivel="EXPLORATORIO_NO_VALIDADO", posicion_top3=null)=>
  ({mercado:"Córners totales",seleccion,probabilidad,cuota_justa:1/probabilidad,
    nivel,origen:"Modelo de conteos",posicion_top3});
const futures=[
  {id:"SP1|abc",fecha_utc:"2026-11-20T20:00:00Z",liga:"LaLiga",
   local:"Athletic Club",visitante:"Espanyol",mercados:{
     corners:[pick("Más de 7,5 córners",.76),pick("Más de 9,5 córners",.61,
       "BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",2)],
     double:[{mercado:"Doble oportunidad",seleccion:"1X: local o empate",probabilidad:.72,
       cuota_justa:1.389,nivel:"MODELO_NO_CALIBRADO",posicion_top3:1}]
   }},
  {id:"SP2|xyz",fecha_utc:"2026-11-18T19:00:00Z",liga:"Segunda División",
   local:"Tenerife",visitante:"Ceuta",mercados:{
     corners:[pick("Menos de 10,5 córners",.69,
       "BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",3)]
   }},
  {id:"SP1|past",fecha_utc:"2026-11-15T13:00:00Z",liga:"LaLiga",
   local:"Getafe",visitante:"Cádiz",mercados:{corners:[pick("Más de 8,5",.99)]}}
];
const model={marketFutures:futures};
test("feeds enlazan archivo nuevo sin modificar CSV originales",()=>{
  assert.equal(FEEDS.pronosticos_mercados_futuros,"pronosticos_mercados_futuros.json");
  const d=buildModel({pronosticos_mercados_futuros:{partidos:futures,calculado_utc:now.toISOString()}},now);
  assert.equal(d.marketFutures.length,3);
  assert.equal(d.archivedPicks.length,0);
});
test("córners muestra SOLO partidos futuros y primero el más próximo",()=>{
  const v=futureMarketSnapshot(model,{market:"corners"},now);
  assert.equal(v.futureMatches,2);
  assert.equal(v.fixtures.length,2);
  assert.equal(v.fixtures[0].local,"Tenerife");
  assert.equal(v.forecastCount,3);
  assert.equal(v.qualityCounts.top3,2);
  assert.equal(v.fixtures[1].best.probabilidad,.76);
});
test("filtra por liga y equipo, sin inventar selecciones de faltas",()=>{
  assert.equal(futureMarketSnapshot(model,{market:"corners",league:"LaLiga"},now).fixtures.length,1);
  assert.equal(futureMarketSnapshot(model,{market:"corners",team:"Ténerífe"},now).fixtures.length,1);
  const fouls=futureMarketSnapshot(model,{market:"fouls"},now);
  assert.equal(fouls.futureMatches,2);
  assert.equal(fouls.fixtures.length,0);
  assert.equal(fouls.withoutMarket,2);
});
test("distingue las selecciones archivadas de las extras",()=>{
  const top=futureMarketSnapshot(model,{market:"corners",quality:"top3"},now);
  assert.equal(top.fixtures.length,2);
  assert.equal(top.forecastCount,2);
  const audited=futureMarketSnapshot(model,{market:"corners",quality:"audited"},now);
  assert.equal(audited.forecastCount,2);
  const exploratory=futureMarketSnapshot(model,{market:"corners",quality:"exploratory"},now);
  assert.equal(exploratory.fixtures.length,1);
  assert.equal(exploratory.forecastCount,1);
});
test("orden de confianza, mercado de doble oportunidad y probabilidades válidas",()=>{
  const value=futureMarketSnapshot(model,{market:"corners",order:"confidence"},now);
  assert.equal(value.fixtures[0].local,"Athletic Club");
  const doubles=futureMarketSnapshot(model,{market:"double"},now);
  assert.equal(doubles.fixtures.length,1);
  assert.equal(doubles.fixtures[0].pronosticos[0].seleccion,"1X: local o empate");
  const bad={marketFutures:[{...futures[0],mercados:{corners:[
    pick("No válida",1.5),pick("Otra",NaN)
  ]}}]};
  assert.equal(futureMarketSnapshot(bad,{market:"corners"},now).fixtures.length,0);
});
