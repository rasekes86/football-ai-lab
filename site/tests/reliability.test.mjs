import test from "node:test";
import assert from "node:assert/strict";
import { reliabilitySnapshot } from "../reliability.mjs";
import { futureMarketSnapshot } from "../future_markets.mjs";
import { buildModel, FEEDS } from "../data.mjs";

const score=(registradas,muestra,aciertos,partidos_unicos,extra={})=>({
  registradas,pendientes:registradas-muestra,sin_estadistica:0,sin_marcador:0,
  muestra,partidos_unicos,aciertos,
  acierto_pct:muestra?100*aciertos/muestra:null,
  probabilidad_media_pct:muestra?66:null,
  brier:muestra?.18:null,logloss:muestra?.55:null,ece:muestra?.04:null,
  sesgo_pct:muestra?100*aciertos/muestra-66:null,
  evidencia:partidos_unicos>=30?"PRELIMINAR":"LIMITADA",
  brier_equilibrado_partidos:muestra?.2:null,
  logloss_equilibrado_partidos:muestra?.6:null,
  partidos_para_umbral:Math.max(0,30-partidos_unicos),
  estado_calibracion:partidos_unicos>=30?"EVALUABLE_DESCRIPTIVO":"INSUFICIENTES_PARTIDOS",
  calibracion:muestra?[{rango:"60–80%",muestra,partidos_unicos,probabilidad_media_pct:66,
    acierto_pct:100*aciertos/muestra}]:[],...extra
});
const doc={
  version:"future-market-audit-1.0",registradas:20,finalizadas:6,
  por_mercado:{corners:score(12,5,3,2),double:score(8,1,1,1)},
  por_mercado_liga:{corners:{"LaLiga":score(9,4,2,2),
    "Segunda División":score(3,1,1,1)}},
  por_mercado_calidad:{corners:{
    "BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA":score(8,4,2,2),
    "EXPLORATORIO_NO_VALIDADO":score(4,1,1,1)}},
  por_mercado_liga_calidad:{corners:{"LaLiga":{
    "BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA":score(6,3,1,2),
    "EXPLORATORIO_NO_VALIDADO":score(3,1,1,1)}}},
  por_mercado_registro:{corners:{top3:score(3,2,2,1),
    adicionales:score(9,3,1,2)}},
  por_mercado_liga_registro:{corners:{"LaLiga":{
    top3:score(1,1,1,1),adicionales:score(8,3,1,2)}}},
  ultimas_evaluaciones:[
    {categoria:"corners",liga:"LaLiga",nivel:"EXPLORATORIO_NO_VALIDADO",
      posicion_top3:"",estado:"FINALIZADO",resultado:"0"},
    {categoria:"corners",liga:"LaLiga",nivel:"BACKTEST_RETROSPECTIVO_APTO_SIN_VALIDACION_PROSPECTIVA",
      posicion_top3:"2",estado:"FINALIZADO",resultado:"1"},
    {categoria:"double",liga:"LaLiga",nivel:"MODELO_NO_CALIBRADO",
      posicion_top3:"",estado:"RESULTADO_NO_DISPONIBLE",resultado:""},
  ]
};
test("sin evaluaciones no inventa resultados o calibración",()=>{
  const s=reliabilitySnapshot({version:doc.version},{market:"corners"});
  assert.equal(s.available,true);
  assert.equal(s.metrics.muestra,0);
  assert.equal(s.metrics.brier,null);
  assert.equal(s.metrics.acierto_pct,null);
  assert.deepEqual(s.metrics.calibracion,[]);
  assert.equal(s.uniqueEnough,false);
  assert.equal(s.remainingGames,30);
  assert.equal(s.metrics.brier_equilibrado_partidos,null);
});
test("agregación prospectiva por mercado y liga",()=>{
  const s=reliabilitySnapshot(doc,{market:"corners",league:"LaLiga"});
  assert.equal(s.metrics.muestra,4);
  assert.equal(s.metrics.partidos_unicos,2);
  assert.equal(s.metrics.brier,.18);
  assert.equal(s.leagues.length,1);
  assert.equal(s.recent.length,2);
  assert.equal(s.uniqueEnough,false);
  assert.equal(s.remainingGames,28);
  assert.equal(s.metrics.brier_equilibrado_partidos,.2);
  assert.equal(s.metrics.estado_calibracion,"INSUFICIENTES_PARTIDOS");
});
test("calidad retrospectiva filtrada tanto por mercado como liga",()=>{
  const s=reliabilitySnapshot(doc,{market:"corners",league:"LaLiga",quality:"audited"});
  assert.equal(s.metrics.muestra,3);
  assert.equal(s.metrics.partidos_unicos,2);
  assert.equal(s.recent.length,1);
  const extra=reliabilitySnapshot(doc,{market:"corners",quality:"exploratory"});
  assert.equal(extra.metrics.muestra,1);
});
test("top3 NO mezcla líneas adicionales en el informe",()=>{
  const s=reliabilitySnapshot(doc,{market:"corners",quality:"top3"});
  assert.equal(s.metrics.registradas,3);
  assert.equal(s.metrics.muestra,2);
  assert.equal(s.recent.length,1);
  const scoped=reliabilitySnapshot(doc,{market:"corners",league:"LaLiga",quality:"top3"});
  assert.equal(scoped.metrics.muestra,1);
});
test("nuevos filtros de probabilidades y cuotas teóricas sin inventar pronósticos",()=>{
  const now=new Date("2026-11-16T15:00:00Z");
  const model={marketFutures:[{id:"abc",local:"Rayo Vallecano",visitante:"Valencia",
    fecha_utc:"2026-11-20T12:00:00Z",liga:"LaLiga",mercados:{corners:[
      {seleccion:"Más de 8,5",probabilidad:.72,cuota_justa:1.389},
      {seleccion:"Más de 9,5",probabilidad:.61,cuota_justa:1.639},
      {seleccion:"Más de 10,5",probabilidad:.48,cuota_justa:2.083},
    ]}}]};
  assert.equal(futureMarketSnapshot(model,{market:"corners",minProbability:".65"},now).forecastCount,1);
  assert.equal(futureMarketSnapshot(model,{market:"corners",minFair:"1.5"},now).forecastCount,2);
  assert.equal(futureMarketSnapshot(model,{market:"corners",minProbability:".65",
     minFair:"1.5"},now).forecastCount,0);
});
test("modelo consume resumen de auditoría independiente y conserva Top 3",()=>{
  assert.equal(FEEDS.fiabilidad_mercados_futuros,"fiabilidad_mercados_futuros.json");
  const model=buildModel({fiabilidad_mercados_futuros:doc});
  assert.equal(model.futureMarketAudit.registradas,20);
  assert.equal(model.archivedPicks.length,0);
});
